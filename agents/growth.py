"""
growth.py - 成長エージェント（週1回実行）
過去30日のデータを分析し、ビジネスアイデア・改善案を提案
→ あなたの承認待ちファイルを生成
"""

import json
import os
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

TODAY = datetime.now().strftime("%Y-%m-%d")
KNOWLEDGE_DIR = Path("knowledge")
PROPOSALS_DIR = KNOWLEDGE_DIR / "proposals"
PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)

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
    """過去N日分のデータを読み込む"""
    all_items = []
    all_digests = []
    all_tags = {}
    
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        filepath = KNOWLEDGE_DIR / "daily" / f"{date}.json"
        if filepath.exists():
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            items = data.get("summarized_items", [])
            all_items.extend(items)
            if data.get("digest"):
                all_digests.append(f"[{date}] {data['digest']}")
            for tag, count in data.get("top_tags", {}).items():
                all_tags[tag] = all_tags.get(tag, 0) + count
    
    return all_items, all_digests, all_tags

def analyze_trends(items, tags):
    """トレンド分析"""
    top_items = sorted(items, key=lambda x: x.get("importance", 0), reverse=True)[:20]
    items_text = "\n".join([
        f"- [{item.get('importance',5)}/10] {item.get('title_ja', item.get('title',''))}"
        for item in top_items
    ])
    
    tags_text = ", ".join([f"{k}({v}回)" for k, v in 
                           sorted(tags.items(), key=lambda x: x[1], reverse=True)[:10]])
    
    prompt = f"""あなたはAI技術のストラテジストです。
過去30日間のAIトレンドデータを分析してください。

【重要度上位の記事】
{items_text}

【頻出タグ】
{tags_text}

以下を分析してください：
1. 主要トレンド3つ（それぞれ2〜3文）
2. 次の1ヶ月で注目すべき技術・動向
3. 見落とされているが重要なシグナル

日本語で、具体的かつ鋭い分析をしてください。"""
    
    return call_claude(prompt, max_tokens=1000)

def generate_business_ideas(trend_analysis):
    """ビジネスアイデア生成"""
    prompt = f"""以下のAIトレンド分析を基に、具体的なビジネスアイデアを3つ提案してください。

【トレンド分析】
{trend_analysis}

各アイデアについて：
- アイデア名
- 一言説明
- ターゲット顧客
- 収益モデル（具体的な金額感も含む）
- 最初の1ヶ月でできる最小限の実装
- リスクと対策

実現可能性が高く、$20/月以下のコストで始められるものを優先してください。
日本語で具体的に書いてください。"""
    
    return call_claude(prompt, max_tokens=1500)

def generate_agent_improvements():
    """エージェント自身の改善提案"""
    # 現在のエージェントコードを読み込む
    agent_files = {}
    for agent in ["collector.py", "summarizer.py", "growth.py"]:
        path = Path("agents") / agent
        if path.exists():
            with open(path, encoding="utf-8") as f:
                agent_files[agent] = f.read()[:1000]  # 最初の1000文字
    
    agents_text = "\n\n".join([f"=== {k} ===\n{v}" for k, v in agent_files.items()])
    
    prompt = f"""あなたは自律型AIシステムのアーキテクトです。
以下のエージェントシステムの改善提案をしてください。

【現在のエージェント概要】
{agents_text}

改善提案（優先度順に3つ）：
1. 新しいデータソースの追加（具体的なAPI名と実装の難易度）
2. 処理精度・効率の改善
3. 新機能の追加

各提案について「実装コスト」「期待効果」「リスク」を明記してください。
⚠️ これらは提案です。実装はオーナーの承認後に行います。"""
    
    return call_claude(prompt, max_tokens=1000)

def create_approval_request(trend_analysis, business_ideas, agent_improvements):
    """承認リクエストファイルを生成"""
    proposal = {
        "date": TODAY,
        "status": "pending_approval",  # pending_approval | approved | rejected
        "trend_analysis": trend_analysis,
        "business_ideas": business_ideas,
        "agent_improvements": agent_improvements,
        "approval_notes": "",  # オーナーが記入
    }
    
    filepath = PROPOSALS_DIR / f"proposal_{TODAY}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(proposal, f, ensure_ascii=False, indent=2)
    
    # Markdown版も生成（読みやすい）
    md_path = PROPOSALS_DIR / f"proposal_{TODAY}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# 🧠 Brain 週次レポート - {TODAY}\n\n")
        f.write(f"**ステータス**: ⏳ 承認待ち\n\n")
        f.write(f"---\n\n")
        f.write(f"## 📊 トレンド分析\n\n{trend_analysis}\n\n")
        f.write(f"---\n\n")
        f.write(f"## 💡 ビジネスアイデア\n\n{business_ideas}\n\n")
        f.write(f"---\n\n")
        f.write(f"## 🔧 エージェント改善提案\n\n{agent_improvements}\n\n")
        f.write(f"---\n\n")
        f.write(f"## ✅ 承認\n\n")
        f.write(f"承認する場合: `proposal_{TODAY}.json` の `status` を `approved` に変更\n")
        f.write(f"却下する場合: `status` を `rejected` に変更し `approval_notes` に理由を記入\n")
    
    return filepath, md_path

def main():
    print(f"🧠 Brain Growth Agent starting... [{TODAY}]")
    
    # データ読み込み
    print("  📚 Loading recent data...")
    items, digests, tags = load_recent_data(days=30)
    print(f"  ✓ Loaded {len(items)} items from past 30 days")
    
    if len(items) < 5:
        print("  ⚠️  Not enough data yet, skipping growth analysis")
        return
    
    # 分析実行
    print("  📊 Analyzing trends...")
    trend_analysis = analyze_trends(items, tags)
    
    print("  💡 Generating business ideas...")
    business_ideas = generate_business_ideas(trend_analysis)
    
    print("  🔧 Generating agent improvements...")
    agent_improvements = generate_agent_improvements()
    
    # 承認リクエスト生成
    print("  📋 Creating approval request...")
    json_path, md_path = create_approval_request(
        trend_analysis, business_ideas, agent_improvements
    )
    
    print(f"\n✅ Growth analysis complete!")
    print(f"   📄 Proposal: {md_path}")
    print(f"   ⏳ Waiting for your approval...")

if __name__ == "__main__":
    main()
