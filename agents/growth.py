"""
growth.py - 成長エージェント
・毎日: X投稿文の下書き生成
・週1(月曜): トレンド分析 + ビジネスアイデア + note記事下書き + GitHub Issue起票
"""

import json
import os
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

TODAY = datetime.now().strftime("%Y-%m-%d")
WEEKDAY = datetime.now().weekday()  # 0=月曜
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
            all_digests.append(f"[{date}] {data['digest']}")
        for tag, count in data.get("top_tags", {}).items():
            all_tags[tag] = all_tags.get(tag, 0) + count
    return all_items, all_digests, all_tags

# ────────────────────────────────────────────
# 毎日実行: X投稿文の下書き生成
# ────────────────────────────────────────────

def generate_x_drafts(items):
    """今日のデータからX投稿文を3本生成"""
    top_items = sorted(items, key=lambda x: x.get("importance", 0), reverse=True)[:10]
    items_text = "\n".join([
        f"- {item.get('title_ja', item.get('title', ''))}：{item.get('summary_ja', '')[:80]}"
        for item in top_items
    ])

    prompt = f"""あなたはAI情報を発信するXアカウントの中の人です。
今日のAIニュースを元に、X（Twitter）投稿文を3本作成してください。

【今日のAIニュース】
{items_text}

【ルール】
- 各投稿は140文字以内
- 専門用語を使いすぎず、一般人にも刺さる表現
- 「〜です」より「〜だ」「〜!」など体言止め・断言系で書く
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
    path = DRAFTS_DIR / f"x_{TODAY}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# X投稿下書き - {TODAY}\n\n")
        f.write("> 確認して気に入ったものをそのままXに投稿してください\n\n")
        f.write(drafts_text)
    print(f"  ✓ X下書き保存: {path}")
    return path

# ────────────────────────────────────────────
# 週1実行(月曜): トレンド分析 + ビジネスアイデア + note下書き
# ────────────────────────────────────────────

def analyze_trends(items, tags):
    top_items = sorted(items, key=lambda x: x.get("importance", 0), reverse=True)[:20]
    items_text = "\n".join([
        f"- [{item.get('importance',5)}/10] {item.get('title_ja', item.get('title',''))}"
        for item in top_items
    ])
    tags_text = ", ".join([
        f"{k}({v}回)" for k, v in
        sorted(tags.items(), key=lambda x: x[1], reverse=True)[:10]
    ])
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

実現可能性が高く、$30/月以下のコストで始められるものを優先してください。
日本語で具体的に書いてください。"""
    return call_claude(prompt, max_tokens=1500)

def generate_note_draft(trend_analysis, items):
    """note有料記事の下書きを生成"""
    top_items = sorted(items, key=lambda x: x.get("importance", 0), reverse=True)[:5]
    items_text = "\n".join([
        f"- {item.get('title_ja', '')}：{item.get('summary_ja', '')[:100]}"
        for item in top_items
    ])

    prompt = f"""あなたはAI情報を発信するnoteクリエイターです。
今週のAIトレンドをもとに、note有料記事の下書きを作成してください。

【今週のトレンド分析】
{trend_analysis}

【注目ニュース】
{items_text}

【記事の構成】
タイトル（クリックしたくなる、¥980〜1,480で買う価値を感じさせるもの）

はじめに（200字）

## 今週のAI業界で起きたこと（300字）

## 特に重要なトレンド3選（各200字）

## 一般人・ビジネスパーソンへの影響（200字）

## 来週の注目ポイント（150字）

おわりに（100字）

【ルール】
- 専門家でない人にも読める文体
- 具体的な事例・数字を使う
- 有料部分は「来週の注目ポイント」以降に設定することを想定
- 日本語で書く"""

    return call_claude(prompt, max_tokens=2000)

def save_note_draft(note_text):
    path = DRAFTS_DIR / f"note_{TODAY}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# note記事下書き - {TODAY}\n\n")
        f.write("> 確認・編集後にnoteに投稿してください。有料設定推奨: ¥980〜1,480\n\n")
        f.write(note_text)
    print(f"  ✓ note下書き保存: {path}")
    return path

def generate_agent_improvements():
    agent_files = {}
    for agent in ["collector.py", "summarizer.py", "growth.py"]:
        path = Path("agents") / agent
        if path.exists():
            with open(path, encoding="utf-8") as f:
                agent_files[agent] = f.read()[:1000]
    agents_text = "\n\n".join([f"=== {k} ===\n{v}" for k, v in agent_files.items()])
    prompt = f"""あなたは自律型AIシステムのアーキテクトです。
以下のエージェントシステムの改善提案をしてください。

【現在のエージェント概要】
{agents_text}

改善提案（優先度順に3つ）：
1. 新しいデータソースの追加
2. 処理精度・効率の改善
3. 新機能の追加

各提案について「実装コスト」「期待効果」「リスク」を明記してください。
⚠️ これらは提案です。実装はオーナーの承認後に行います。"""
    return call_claude(prompt, max_tokens=1000)

# ────────────────────────────────────────────
# 承認ゲート: GitHub Issue起票
# ────────────────────────────────────────────

def create_github_issue(title, body):
    """GitHub IssueをAPIで起票する"""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")  # "owner/repo" 形式
    if not token or not repo:
        print("  ⚠️  GITHUB_TOKEN or GITHUB_REPOSITORY not set, skipping issue creation")
        return

    payload = json.dumps({
        "title": title,
        "body": body,
        "labels": ["brain-proposal", "pending-approval"]
    }).encode()

    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues",
        data=payload,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        }
    )
    try:
        with urllib.request.urlopen(req) as r:
            result = json.loads(r.read())
            print(f"  ✓ GitHub Issue作成: #{result['number']} {result['html_url']}")
    except Exception as e:
        print(f"  ⚠️  Issue作成失敗: {e}")

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
    filepath = PROPOSALS_DIR / f"proposal_{TODAY}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(proposal, f, ensure_ascii=False, indent=2)

    md_path = PROPOSALS_DIR / f"proposal_{TODAY}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# 🧠 Brain 週次レポート - {TODAY}\n\n")
        f.write(f"**ステータス**: ⏳ 承認待ち\n\n---\n\n")
        f.write(f"## 📊 トレンド分析\n\n{trend_analysis}\n\n---\n\n")
        f.write(f"## 💡 ビジネスアイデア\n\n{business_ideas}\n\n---\n\n")
        f.write(f"## 🔧 エージェント改善提案\n\n{agent_improvements}\n\n---\n\n")
        f.write(f"## 📝 note下書き\n\n`{note_path}` を確認してください\n\n---\n\n")
        f.write(f"## ✅ 承認方法\n\n")
        f.write(f"このIssueに `approved` ラベルを付けると次回実行時に反映されます\n")

    # GitHub Issue起票
    issue_body = f"""## 🧠 Brain 週次提案 - {TODAY}

### 📊 主要トレンド
{trend_analysis[:500]}...

### 💡 ビジネスアイデア（抜粋）
{business_ideas[:500]}...

### 🔧 改善提案（抜粋）
{agent_improvements[:300]}...

---
**詳細**: `knowledge/proposals/proposal_{TODAY}.md` を確認
**note下書き**: `knowledge/drafts/note_{TODAY}.md` を確認
**X下書き**: `knowledge/drafts/x_{TODAY}.md` を確認

### 承認方法
- ✅ 承認: このIssueに `approved` ラベルを付ける
- ❌ 却下: このIssueを `rejected` ラベルを付けてClose
"""
    create_github_issue(f"🧠 週次提案 {TODAY} - Brain Growth Report", issue_body)
    return filepath, md_path

# ────────────────────────────────────────────
# メイン
# ────────────────────────────────────────────

def main():
    print(f"🧠 Brain Growth Agent starting... [{TODAY}] (weekday={WEEKDAY})")

    items, digests, tags = load_recent_data(days=30)
    print(f"  📚 Loaded {len(items)} items")

    # ── 毎日: X投稿文生成 ──
    if len(items) >= 3:
        print("  ✍️  Generating X drafts...")
        x_drafts = generate_x_drafts(items[:1])  # 今日分だけ使う
        save_x_drafts(x_drafts)
    else:
        print("  ⚠️  Not enough data for X drafts")

    # ── 週1(月曜): フル分析 ──
    if WEEKDAY == 0:
        if len(items) < 5:
            print("  ⚠️  Not enough data for weekly analysis")
            return

        print("  📊 Analyzing trends...")
        trend_analysis = analyze_trends(items, tags)

        print("  💡 Generating business ideas...")
        business_ideas = generate_business_ideas(trend_analysis)

        print("  📝 Generating note draft...")
        note_path = generate_note_draft(trend_analysis, items)
        save_note_draft(note_path) if isinstance(note_path, str) else None

        # note_pathが文字列で返ってくる場合の修正
        note_draft_text = note_path if isinstance(note_path, str) else ""
        note_path = save_note_draft(note_draft_text)

        print("  🔧 Generating agent improvements...")
        agent_improvements = generate_agent_improvements()

        print("  📋 Creating approval request + GitHub Issue...")
        create_approval_request(trend_analysis, business_ideas, agent_improvements, note_path)

        print(f"\n✅ Weekly analysis complete!")
    else:
        print(f"  ℹ️  週次分析は月曜のみ実行 (今日は weekday={WEEKDAY})")
        print(f"\n✅ Daily X drafts complete!")

if __name__ == "__main__":
    main()
