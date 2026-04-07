"""
growth.py - 成長エージェント
毎日: X投稿文の下書き生成
週1(月曜): トレンド分析 + ビジネスアイデア + note記事下書き + GitHub Issue起票
"""

import json
import os
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

TODAY = datetime.now().strftime("%Y-%m-%d")
WEEKDAY = datetime.now().weekday()
KNOWLEDGE_DIR = Path("knowledge")
PROPOSALS_DIR = KNOWLEDGE_DIR / "proposals"
DRAFTS_DIR = KNOWLEDGE_DIR / "drafts"
PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
DRAFTS_DIR.mkdir(parents=True, exist_ok=True)


def call_claude(prompt, max_tokens=2000):
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
        return json.loads(r.read())["content"][0]["text"]


def load_recent_data(days=30):
    all_items, all_digests, all_tags = [], [], {}
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        filepath = KNOWLEDGE_DIR / "daily" / f"{date}.json"
        if not filepath.exists():
            continue
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        all_items.extend(data.get("summarized_items", []))
        if data.get("digest"):
            all_digests.append("[" + date + "] " + data["digest"])
        for tag, count in data.get("top_tags", {}).items():
            all_tags[tag] = all_tags.get(tag, 0) + count
    return all_items, all_digests, all_tags


# ────────────────────────────────────────────
# 毎日実行: X投稿文の下書き生成
# ────────────────────────────────────────────

def generate_x_drafts(items):
    top_items = sorted(items, key=lambda x: x.get("importance", 0), reverse=True)[:10]
    items_text = "\n".join([
        "- " + item.get("title_ja", item.get("title", "")) + ":" + item.get("summary_ja", "")[:80]
        for item in top_items
    ])
    prompt = """あなたはAI情報を発信するXアカウントの中の人です。
今日のAIニュースを元に、X投稿文を3本作成してください。

【今日のAIニュース】
""" + items_text + """

【ルール】
- 各投稿は140文字以内
- 専門用語を使いすぎず、一般人にも刺さる表現
- 体言止め・断言系で書く
- 末尾に関連ハッシュタグを2〜3個
- 3本はそれぞれ違うトピック・切り口にする

【出力形式】
投稿1:
（本文）

投稿2:
（本文）

投稿3:
（本文）"""
    return call_claude(prompt, max_tokens=800)


def save_x_drafts(drafts_text):
    path = DRAFTS_DIR / ("x_" + TODAY + ".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# X投稿下書き - " + TODAY + "\n\n")
        f.write("> 確認して気に入ったものをそのままXに投稿してください\n\n")
        f.write(drafts_text)
    print("  X下書き保存: " + str(path))
    return path


# ────────────────────────────────────────────
# 週1実行(月曜): トレンド分析
# ────────────────────────────────────────────

def analyze_trends(items, tags):
    top_items = sorted(items, key=lambda x: x.get("importance", 0), reverse=True)[:20]
    items_text = "\n".join([
        "- [" + str(item.get("importance", 5)) + "/10] " + item.get("title_ja", item.get("title", ""))
        for item in top_items
    ])
    tags_text = ", ".join([
        k + "(" + str(v) + "回)" for k, v in
        sorted(all_tags.items(), key=lambda x: x[1], reverse=True)[:10]
    ]) if False else ", ".join([
        k + "(" + str(v) + "回)" for k, v in
        sorted(tags.items(), key=lambda x: x[1], reverse=True)[:10]
    ])
    prompt = """あなたはAI技術のストラテジストです。
過去30日間のAIトレンドデータを分析してください。

【重要度上位の記事】
""" + items_text + """

【頻出タグ】
""" + tags_text + """

以下を分析してください：
1. 主要トレンド3つ（それぞれ2〜3文）
2. 次の1ヶ月で注目すべき技術・動向
3. 見落とされているが重要なシグナル

日本語で、具体的かつ鋭い分析をしてください。"""
    return call_claude(prompt, max_tokens=1000)


def generate_business_ideas(trend_analysis):
    prompt = """以下のAIトレンド分析を基に、具体的なビジネスアイデアを3つ提案してください。

【トレンド分析】
""" + trend_analysis + """

各アイデアについて：
- アイデア名
- 一言説明
- ターゲット顧客
- 収益モデル（具体的な金額感も含む）
- 最初の1ヶ月でできる最小限の実装
- リスクと対策

実現可能性が高く、$30/月以下のコストで始められるものを優先してください。
日本語で具体的に書いてください。"""
    return call_claude(prompt, max_tokens=1500)


# ────────────────────────────────────────────
# note下書き生成（売れる記事構成）
# ────────────────────────────────────────────

def generate_note_draft(trend_analysis, items):
    top_items = sorted(items, key=lambda x: x.get("importance", 0), reverse=True)[:7]
    items_text = "\n".join([
        "- " + item.get("title_ja", "") + ":" + item.get("summary_ja", "")[:120]
        for item in top_items
    ])

    prompt = """あなたはフォロワー数万人のAI情報発信者です。
今週のAIトレンドをもとに、noteで売れる有料記事の下書きを作成してください。

【今週のトレンド分析】
""" + trend_analysis + """

【注目ニュース TOP7】
""" + items_text + """

【記事の要件】
- 読者層：AI初心者〜中級者、副業・ビジネスに興味がある20〜40代
- 価格設定：¥980（この金額を払う価値を感じさせる内容）
- 文字数：全体で3,000〜4,000字
- 無料部分と有料部分を明確に分ける

【構成】

# タイトル
（例：「今週のAI業界、正直ヤバかった件【2026年4月第2週】」のような、
数字・感情・具体性を含む思わずクリックしたくなるタイトル）

## はじめに（無料・200字）
読者が「これは自分ごとだ」と感じる書き出し。
今週のAI業界を一言で表すキャッチコピーから入る。

## 今週起きた3大ニュース（無料・各150字）
具体的なニュース名・企業名・数字を使う。
「〜がリリース」「〜億円調達」など事実ベースで。

## ここから有料（¥980）

## なぜこれが重要なのか（有料・400字）
ニュースの「裏側」「本質」を解説。
一般ニュースでは語られない視点を提供する。

## あなたのビジネス・仕事への影響（有料・400字）
「で、自分はどうすればいいの？」に答える。
具体的なアクション3つを提示する。

## 来週の注目ポイント（有料・300字）
「先出し情報」として価値を出す。
次号への期待感を高める。

## 編集後記（有料・200字）
発信者の個人的な感想・体験談。
人間味を出してファン化を促す。

【文体ルール】
- 「です・ます」調だが堅すぎない
- 専門用語は必ず一言で説明を添える
- 数字・固有名詞を積極的に使う
- 読者への問いかけを各セクションに1つ入れる
- 日本語で書く"""

    return call_claude(prompt, max_tokens=3000)


def save_note_draft(note_text):
    path = DRAFTS_DIR / ("note_" + TODAY + ".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# note記事下書き - " + TODAY + "\n\n")
        f.write("> 【使い方】無料部分はそのまま公開、有料部分は980円で設定推奨\n")
        f.write("> 固有名詞・数字を確認して投稿してください\n\n")
        f.write("---\n\n")
        f.write(note_text)
    print("  note下書き保存: " + str(path))
    return path


def generate_agent_improvements():
    agent_files = {}
    for agent in ["collector.py", "summarizer.py", "growth.py"]:
        path = Path("agents") / agent
        if path.exists():
            with open(path, encoding="utf-8") as f:
                agent_files[agent] = f.read()[:1000]
    agents_text = "\n\n".join(["=== " + k + " ===\n" + v for k, v in agent_files.items()])
    prompt = """あなたは自律型AIシステムのアーキテクトです。
以下のエージェントシステムの改善提案をしてください。

【現在のエージェント概要】
""" + agents_text + """

改善提案（優先度順に3つ）：
1. 新しいデータソースの追加
2. 処理精度・効率の改善
3. 新機能の追加

各提案について「実装コスト」「期待効果」「リスク」を明記してください。
これらは提案です。実装はオーナーの承認後に行います。"""
    return call_claude(prompt, max_tokens=1000)


# ────────────────────────────────────────────
# 承認ゲート: GitHub Issue起票
# ────────────────────────────────────────────

def create_github_issue(title, body):
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print("  GITHUB_TOKEN or GITHUB_REPOSITORY not set, skipping issue creation")
        return
    payload = json.dumps({
        "title": title,
        "body": body,
        "labels": ["brain-proposal", "pending-approval"]
    }).encode()
    req = urllib.request.Request(
        "https://api.github.com/repos/" + repo + "/issues",
        data=payload,
        headers={
            "Authorization": "token " + token,
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        }
    )
    try:
        with urllib.request.urlopen(req) as r:
            result = json.loads(r.read())
            print("  GitHub Issue作成: #" + str(result["number"]) + " " + result["html_url"])
    except Exception as e:
        print("  Issue作成失敗: " + str(e))


def create_approval_request(trend_analysis, business_ideas, agent_improvements, note_path):
    proposal = {
        "date": TODAY,
        "status": "pending_approval",
        "trend_analysis": trend_analysis,
        "business_ideas": business_ideas,
        "agent_improvements": agent_improvements,
        "note_draft_path": str(note_path),
        "approval_notes": "",
    }
    filepath = PROPOSALS_DIR / ("proposal_" + TODAY + ".json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(proposal, f, ensure_ascii=False, indent=2)

    md_path = PROPOSALS_DIR / ("proposal_" + TODAY + ".md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Brain Weekly Report - " + TODAY + "\n\n")
        f.write("Status: Pending Approval\n\n---\n\n")
        f.write("## Trend Analysis\n\n" + trend_analysis + "\n\n---\n\n")
        f.write("## Business Ideas\n\n" + business_ideas + "\n\n---\n\n")
        f.write("## Agent Improvements\n\n" + agent_improvements + "\n\n---\n\n")
        f.write("## Note Draft\n\n" + str(note_path) + " を確認してください\n\n---\n\n")
        f.write("## 承認方法\n\nこのIssueに approved ラベルを付けると次回実行時に反映されます\n")

    issue_body = "## Brain Weekly Report - " + TODAY + "\n\n"
    issue_body += "### Trend Analysis\n" + trend_analysis[:500] + "...\n\n"
    issue_body += "### Business Ideas\n" + business_ideas[:500] + "...\n\n"
    issue_body += "### Agent Improvements\n" + agent_improvements[:300] + "...\n\n"
    issue_body += "---\n"
    issue_body += "Detail: knowledge/proposals/proposal_" + TODAY + ".md\n"
    issue_body += "Note draft: knowledge/drafts/note_" + TODAY + ".md\n"
    issue_body += "X drafts: knowledge/drafts/x_" + TODAY + ".md\n\n"
    issue_body += "### 承認方法\n"
    issue_body += "- 承認: approved ラベルを付ける\n"
    issue_body += "- 却下: rejected ラベルを付けてClose\n"

    create_github_issue("Brain Weekly Report " + TODAY, issue_body)
    return filepath, md_path


# ────────────────────────────────────────────
# メイン
# ────────────────────────────────────────────

def main():
    print("Brain Growth Agent starting... [" + TODAY + "] (weekday=" + str(WEEKDAY) + ")")

    items, digests, tags = load_recent_data(days=30)
    print("  Loaded " + str(len(items)) + " items")

    if len(items) >= 3:
        print("  Generating X drafts...")
        x_drafts = generate_x_drafts(items)
        save_x_drafts(x_drafts)
    else:
        print("  Not enough data for X drafts")

    if WEEKDAY == 0:
        if len(items) < 5:
            print("  Not enough data for weekly analysis")
            return

        print("  Analyzing trends...")
        trend_analysis = analyze_trends(items, tags)

        print("  Generating business ideas...")
        business_ideas = generate_business_ideas(trend_analysis)

        print("  Generating note draft...")
        note_draft_text = generate_note_draft(trend_analysis, items)
        note_path = save_note_draft(note_draft_text)

        print("  Generating agent improvements...")
        agent_improvements = generate_agent_improvements()

        print("  Creating approval request + GitHub Issue...")
        create_approval_request(trend_analysis, business_ideas, agent_improvements, note_path)

        print("Weekly analysis complete!")
    else:
        print("Weekly analysis runs on Monday only (today weekday=" + str(WEEKDAY) + ")")
        print("Daily X drafts complete!")


if __name__ == "__main__":
    main()
