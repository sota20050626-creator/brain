"""
growth.py - 成長エージェント
毎日: X投稿文の下書き生成（当日+前日の最新データ使用）
週1(月曜): トレンド分析 + ビジネスアイデア + note記事下書き + GitHub Issue起票 + 自動PR作成
"""

import json
import os
import re
import base64
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

TODAY = datetime.now().strftime("%Y-%m-%d")
YESTERDAY = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
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
        filepath = KNOWLEDGE_DIR / "daily" / (date + ".json")
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


def load_latest_items():
    results = []
    for date in [TODAY, YESTERDAY]:
        filepath = KNOWLEDGE_DIR / "daily" / (date + ".json")
        if not filepath.exists():
            continue
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("summarized_items", [])
        results.extend(items)
        print("  Loaded " + str(len(items)) + " items from " + date)
    return results


def generate_x_drafts(items):
    top_items = sorted(items, key=lambda x: x.get("importance", 0), reverse=True)[:10]
    items_text = "\n".join([
        "- " + item.get("title_ja", item.get("title", "")) + ": " + item.get("summary_ja", "")[:80]
        for item in top_items
    ])
    prompt = """あなたはAI情報を発信するXアカウントの中の人です。
今日・昨日のAIニュースの中から最もホットなものを選んで、X投稿文を3本作成してください。

【最新AIニュース（今日+昨日）】
""" + items_text + """

【選び方のルール】
- 最もインパクトが大きいBIGNEWSを優先する
- 「え、マジで？」「知らなかった」と思わせるものを選ぶ
- 業界の転換点になりそうなものを優先する
- 3本は全て異なるトピックにする

【投稿文のルール】
- 各投稿は140文字以内
- 専門用語を使いすぎず、一般人にも刺さる表現
- 体言止め・断言系で書く
- 「速報」「今」「たった今」などの鮮度を感じさせる言葉を入れる
- 末尾に関連ハッシュタグを2〜3個

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
        f.write("> 今日+昨日(" + YESTERDAY + ")の最新AIニュースをもとに生成\n")
        f.write("> 確認して気に入ったものをそのままXに投稿してください\n\n")
        f.write(drafts_text)
    print("  X下書き保存: " + str(path))
    return path


def analyze_trends(items, tags):
    top_items = sorted(items, key=lambda x: x.get("importance", 0), reverse=True)[:20]
    items_text = "\n".join([
        "- [" + str(item.get("importance", 5)) + "/10] " + item.get("title_ja", item.get("title", ""))
        for item in top_items
    ])
    tags_text = ", ".join([
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


def generate_note_draft(trend_analysis, items):
    top_items = sorted(items, key=lambda x: x.get("importance", 0), reverse=True)[:7]
    items_text = "\n".join([
        "- " + item.get("title_ja", "") + ": " + item.get("summary_ja", "")[:120]
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
- 価格設定：¥980
- 文字数：全体で3,000〜4,000字
- 無料部分と有料部分を明確に分ける

【構成】

# タイトル
（クリックしたくなる、数字・感情・具体性を含むタイトル）

## はじめに（無料・200字）

## 今週起きた3大ニュース（無料・各150字）

## ここから有料（¥980）

## なぜこれが重要なのか（有料・400字）

## あなたのビジネス・仕事への影響（有料・400字）

## 来週の注目ポイント（有料・300字）

## 編集後記（有料・200字）

【文体ルール】
- です・ます調だが堅すぎない
- 専門用語は必ず一言で説明を添える
- 数字・固有名詞を積極的に使う
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
# 自動PR作成
# ────────────────────────────────────────────

def get_file_content(repo, filepath, token):
    req = urllib.request.Request(
        "https://api.github.com/repos/" + repo + "/contents/" + filepath,
        headers={
            "Authorization": "token " + token,
            "Accept": "application/vnd.github.v3+json",
        }
    )
    try:
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read())
            content = base64.b64decode(data["content"]).decode("utf-8")
            sha = data["sha"]
            return content, sha
    except Exception as e:
        print("  File fetch error: " + str(e))
        return None, None


def generate_improved_code(current_code, filename, trend_analysis):
    if filename == "collector.py":
        direction = """
- 新しいAI情報ソースの追加（信頼性が高く無料のAPIを優先）
- 収集精度の向上
- エラーハンドリングの強化
- タイムアウト処理の追加"""
    elif filename == "summarizer.py":
        direction = """
- 要約の精度向上
- 重要度スコアリングの改善
- カテゴリ分類の精度向上
- エラーハンドリングの強化"""
    else:
        direction = """
- 投稿文の品質向上
- 提案精度の改善
- エラーハンドリングの強化"""

    prompt = """あなたは優秀なPythonエンジニアです。
以下の """ + filename + """ を改善してください。

【現在のコード】
""" + current_code + """

【最新AIトレンド（参考）】
""" + trend_analysis[:500] + """

【改善の方針】
""" + direction + """

【ルール】
- 既存の機能は必ず維持する
- 変更は最小限にとどめる
- 完全なPythonコードのみを返す
- 必ず ```python と ``` で囲む
- 必ず動作するコードを返す"""
    return call_claude(prompt, max_tokens=4000)


def create_branch(repo, branch_name, token):
    req = urllib.request.Request(
        "https://api.github.com/repos/" + repo + "/git/refs/heads/main",
        headers={
            "Authorization": "token " + token,
            "Accept": "application/vnd.github.v3+json",
        }
    )
    try:
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read())
            sha = data["object"]["sha"]
    except Exception as e:
        print("  Branch SHA fetch error: " + str(e))
        return False

    payload = json.dumps({
        "ref": "refs/heads/" + branch_name,
        "sha": sha
    }).encode()
    req = urllib.request.Request(
        "https://api.github.com/repos/" + repo + "/git/refs",
        data=payload,
        headers={
            "Authorization": "token " + token,
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        }
    )
    try:
        with urllib.request.urlopen(req) as r:
            print("  Branch created: " + branch_name)
            return True
    except Exception as e:
        print("  Branch creation error: " + str(e))
        return False


def commit_file(repo, filepath, content, sha, branch_name, commit_message, token):
    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    payload = json.dumps({
        "message": commit_message,
        "content": encoded,
        "sha": sha,
        "branch": branch_name,
    }).encode()
    req = urllib.request.Request(
        "https://api.github.com/repos/" + repo + "/contents/" + filepath,
        data=payload,
        headers={
            "Authorization": "token " + token,
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        }
    )
    req.get_method = lambda: "PUT"
    try:
        with urllib.request.urlopen(req) as r:
            print("  File committed: " + filepath)
            return True
    except Exception as e:
        print("  Commit error: " + str(e))
        return False


def create_pull_request(repo, branch_name, title, body, token):
    payload = json.dumps({
        "title": title,
        "body": body,
        "head": branch_name,
        "base": "main",
    }).encode()
    req = urllib.request.Request(
        "https://api.github.com/repos/" + repo + "/pulls",
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
            print("  PR created: " + result["html_url"])
            return result["html_url"]
    except Exception as e:
        print("  PR creation error: " + str(e))
        return None


def auto_improve_and_pr(trend_analysis):
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print("  GITHUB_TOKEN or GITHUB_REPOSITORY not set, skipping auto PR")
        return

    targets = [
        ("agents/collector.py", "collector.py"),
        ("agents/summarizer.py", "summarizer.py"),
        ("agents/growth.py", "growth.py"),
    ]

    branch_name = "brain-auto-improve-" + TODAY
    if not create_branch(repo, branch_name, token):
        return

    improved_files = []
    for filepath, filename in targets:
        print("  Improving " + filename + "...")
        current_code, sha = get_file_content(repo, filepath, token)
        if not current_code:
            continue

        improved_response = generate_improved_code(current_code, filename, trend_analysis)

        match = re.search(r"```python\n(.*?)```", improved_response, re.DOTALL)
        if not match:
            print("  No code block found for " + filename + ", skipping")
            continue
        improved_code = match.group(1)

        commit_msg = "Brain auto-improve: " + filename + " [" + TODAY + "]"
        if commit_file(repo, filepath, improved_code, sha, branch_name, commit_msg, token):
            improved_files.append(filename)

    if not improved_files:
        print("  No files improved, skipping PR")
        return

    pr_body = "## Brain 自動改善PR - " + TODAY + "\n\n"
    pr_body += "### 改善されたファイル\n"
    for f in improved_files:
        pr_body += "- " + f + "\n"
    pr_body += "\n### 改善の根拠\n"
    pr_body += trend_analysis[:300] + "\n\n"
    pr_body += "### 確認方法\n"
    pr_body += "1. 各ファイルの差分を確認\n"
    pr_body += "2. 問題なければ Merge ボタンを押すだけ\n"
    pr_body += "3. 問題があれば Close して却下\n\n"
    pr_body += "> このPRはBrain Growth Agentが自動生成しました\n"

    create_pull_request(
        repo,
        branch_name,
        "Brain auto-improve: " + ", ".join(improved_files) + " [" + TODAY + "]",
        pr_body,
        token
    )


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
        f.write("## 承認方法\n\nPRをMergeするだけ\n")

    issue_body = "## Brain Weekly Report - " + TODAY + "\n\n"
    issue_body += "### Trend Analysis\n" + trend_analysis[:500] + "...\n\n"
    issue_body += "### Business Ideas\n" + business_ideas[:500] + "...\n\n"
    issue_body += "### Agent Improvements\n" + agent_improvements[:300] + "...\n\n"
    issue_body += "---\n"
    issue_body += "Detail: knowledge/proposals/proposal_" + TODAY + ".md\n"
    issue_body += "Note draft: knowledge/drafts/note_" + TODAY + ".md\n"
    issue_body += "X drafts: knowledge/drafts/x_" + TODAY + ".md\n\n"
    issue_body += "### 承認方法\n"
    issue_body += "- 承認: PRをMerge\n"
    issue_body += "- 却下: PRをClose\n"

    create_github_issue("Brain Weekly Report " + TODAY, issue_body)
    return filepath, md_path


# ────────────────────────────────────────────
# メイン
# ────────────────────────────────────────────

def main():
    print("Brain Growth Agent starting... [" + TODAY + "] (weekday=" + str(WEEKDAY) + ")")

    items, digests, tags = load_recent_data(days=30)
    print("  Loaded " + str(len(items)) + " items (30 days)")

    latest_items = load_latest_items()
    if len(latest_items) >= 3:
        print("  Generating X drafts from latest 2 days data...")
        x_drafts = generate_x_drafts(latest_items)
        save_x_drafts(x_drafts)
    elif len(items) >= 3:
        print("  No latest data, using recent 30 days data...")
        x_drafts = generate_x_drafts(items)
        save_x_drafts(x_drafts)
    else:
        print("  Not enough data for X drafts")

    if True:
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

        print("  Creating auto-improve PR...")
        auto_improve_and_pr(trend_analysis)

        print("Weekly analysis complete!")
    else:
        print("Weekly analysis runs on Monday only (today weekday=" + str(WEEKDAY) + ")")
        print("Daily X drafts complete!")


if __name__ == "__main__":
    main()
