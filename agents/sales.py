"""
sales.py - 営業リストアップエージェント
LinkedIn・Wantedly対象アカウントの課題分析 + Brainを押せるポイント自動生成
出力: knowledge/sales/sales_list_YYYY-MM-DD.md
"""

import json
import os
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

TODAY = datetime.now().strftime("%Y-%m-%d")
KNOWLEDGE_DIR = Path("knowledge")
SALES_DIR = KNOWLEDGE_DIR / "sales"
COST_FILE = KNOWLEDGE_DIR / "cost_log.json"
SALES_DIR.mkdir(parents=True, exist_ok=True)

SONNET_INPUT_PRICE = 3.0 / 1_000_000
SONNET_OUTPUT_PRICE = 15.0 / 1_000_000

# ★ 営業対象リスト（手動で追加していく）
# 形式: {"name": "会社名", "platform": "linkedin or wantedly", "url": "アカウントURL", "description": "事業内容メモ"}
TARGETS = [
    {
        "name": "サンプル株式会社",
        "platform": "wantedly",
        "url": "https://www.wantedly.com/companies/sample",
        "description": "中小企業向けSaaSを提供。営業・マーケ担当5名。AI活用はほぼゼロ。",
    },
    {
        "name": "株式会社テックサンプル",
        "platform": "linkedin",
        "url": "https://www.linkedin.com/company/tech-sample",
        "description": "受託開発会社。エンジニア20名。情報収集・提案書作成が属人化している。",
    },
]


def load_cost_log():
    if not COST_FILE.exists():
        return {"monthly": {}, "total_usd": 0}
    with open(COST_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_cost(input_tokens, output_tokens, label):
    cost = input_tokens * SONNET_INPUT_PRICE + output_tokens * SONNET_OUTPUT_PRICE
    log = load_cost_log()
    month = TODAY[:7]
    if month not in log["monthly"]:
        log["monthly"][month] = {"usd": 0, "calls": [], "input_tokens": 0, "output_tokens": 0}
    log["monthly"][month]["usd"] = round(log["monthly"][month]["usd"] + cost, 6)
    log["monthly"][month]["input_tokens"] += input_tokens
    log["monthly"][month]["output_tokens"] += output_tokens
    log["monthly"][month]["calls"].append({
        "date": TODAY,
        "label": label,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "usd": round(cost, 6)
    })
    log["total_usd"] = round(sum(v["usd"] for v in log["monthly"].values()), 6)
    with open(COST_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    return cost


def call_claude(prompt, max_tokens=1500, label="sales_api_call"):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
    )
    with urllib.request.urlopen(req) as r:
        result = json.loads(r.read())
    usage = result.get("usage", {})
    save_cost(usage.get("input_tokens", 0), usage.get("output_tokens", 0), label)
    return result["content"][0]["text"]


def analyze_target(target):
    """1社分の課題分析 + Brainを押せるポイントを生成"""
    prompt = """あなたはAIソリューションの営業コンサルタントです。
以下の企業情報をもとに、営業アプローチを設計してください。

【企業情報】
会社名: """ + target["name"] + """
プラットフォーム: """ + target["platform"] + """
URL: """ + target["url"] + """
事業内容メモ: """ + target["description"] + """

【Brainとは】
自律型AI情報収集・コンテンツ生成・営業リストアップシステム。
主なサービスメニュー:
- スポット受託: ¥49,800〜148,000（AI業務自動化の構築）
- note有料記事: ¥980（AI情報発信）
- 月次サポート: ¥30,000/月（継続的なAI活用支援）

以下を分析してください：

## 1. 推定課題（3つ）
この企業が抱えていそうな課題を具体的に

## 2. Brainで解決できるポイント（3つ）
各課題に対してBrainがどう貢献できるか、数字・効果を含めて

## 3. 最初の一言（アイスブレイク）
DM・メッセージの書き出し文（50字以内、相手の状況に寄り添う内容）

## 4. 提案プラン
- おすすめメニュー: （上記サービスから選択）
- 想定単価: 
- 成約確度: 高/中/低
- 理由:

## 5. 注意点
この企業へのアプローチで気をつけること

日本語で具体的に書いてください。"""
    return call_claude(prompt, max_tokens=1500, label="sales_analyze_" + target["name"][:10])


def search_wantedly_companies(keyword):
    """Wantedly検索URL生成（手動確認用）"""
    encoded = urllib.parse.quote(keyword)
    return "https://www.wantedly.com/companies?q=" + encoded


def search_linkedin_companies(keyword):
    """LinkedIn検索URL生成（手動確認用）"""
    encoded = urllib.parse.quote(keyword)
    return "https://www.linkedin.com/search/results/companies/?keywords=" + encoded


def generate_sales_list(analyses):
    """営業リスト全体のサマリーを生成"""
    targets_summary = "\n\n".join([
        "### " + a["target"]["name"] + "\n" + a["analysis"][:300]
        for a in analyses
    ])
    prompt = """以下の営業対象分析をもとに、今週アプローチすべき優先順位を付けてください。

""" + targets_summary + """

【出力形式】
優先度1位: 会社名 / 理由（1文）
優先度2位: 会社名 / 理由（1文）
...

次のアクション（今日やること）を3つ具体的に書いてください。"""
    return call_claude(prompt, max_tokens=500, label="sales_priority")


def save_sales_list(analyses, priority_summary):
    path = SALES_DIR / ("sales_list_" + TODAY + ".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# 営業リスト - " + TODAY + "\n\n")
        f.write("> Brain自動生成 | 確認して営業アクションに活用してください\n\n")
        f.write("---\n\n")
        f.write("## 🎯 優先順位・今日のアクション\n\n")
        f.write(priority_summary)
        f.write("\n\n---\n\n")
        f.write("## 📋 個別企業分析\n\n")
        for a in analyses:
            t = a["target"]
            f.write("### " + t["name"] + "\n")
            f.write("- **プラットフォーム**: " + t["platform"] + "\n")
            f.write("- **アカウントURL**: [" + t["url"] + "](" + t["url"] + ")\n\n")
            f.write(a["analysis"])
            f.write("\n\n---\n\n")

        f.write("## 🔍 新規ターゲット探索リンク\n\n")
        f.write("### Wantedly\n")
        keywords_w = ["AI活用", "DX推進", "スタートアップ", "マーケティング自動化"]
        for kw in keywords_w:
            url = search_wantedly_companies(kw)
            f.write("- [" + kw + "](" + url + ")\n")
        f.write("\n### LinkedIn\n")
        keywords_l = ["AI導入", "業務効率化", "コンテンツマーケティング"]
        for kw in keywords_l:
            url = search_linkedin_companies(kw)
            f.write("- [" + kw + "](" + url + ")\n")

        f.write("\n\n---\n\n")
        f.write("## ➕ 次のターゲットを追加するには\n\n")
        f.write("`agents/sales.py` の `TARGETS` リストに以下の形式で追加してください:\n\n")
        f.write("```python\n")
        f.write('{\n')
        f.write('    "name": "会社名",\n')
        f.write('    "platform": "linkedin or wantedly",\n')
        f.write('    "url": "アカウントURL",\n')
        f.write('    "description": "事業内容・課題のメモ",\n')
        f.write('}\n')
        f.write("```\n")

    print("  営業リスト保存完了: " + str(path))
    return path


def main():
    print("Brain Sales Agent 起動... [" + TODAY + "]")

    if not TARGETS:
        print("  ターゲットが設定されていません")
        print("  sales.py の TARGETS リストに企業情報を追加してください")
        return

    print("  " + str(len(TARGETS)) + " 社を分析中...")
    analyses = []
    for target in TARGETS:
        print("  分析中: " + target["name"])
        analysis = analyze_target(target)
        analyses.append({"target": target, "analysis": analysis})

    print("  優先順位・アクション生成中...")
    priority_summary = generate_sales_list(analyses)

    print("  営業リスト保存中...")
    path = save_sales_list(analyses, priority_summary)

    print("営業リスト生成完了!")
    print("確認: " + str(path))


if __name__ == "__main__":
    main()
