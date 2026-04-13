"""
growth.py - 成長エージェント
毎日: X投稿文の下書き生成（当日+前日の最新データ使用）
週1(月曜): トレンド分析 + ビジネスアイデア + note記事下書き + GitHub Issue起票 + 自動PR作成 + 新技術自己搭載
"""

import json
import os
import re
import base64
import urllib.request
import urllib.parse
import time
from datetime import datetime, timedelta
from pathlib import Path

TODAY = datetime.now().strftime("%Y-%m-%d")
YESTERDAY = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
WEEKDAY = datetime.now().weekday()
KNOWLEDGE_DIR = Path("knowledge")
PROPOSALS_DIR = KNOWLEDGE_DIR / "proposals"
DRAFTS_DIR = KNOWLEDGE_DIR / "drafts"
COST_FILE = KNOWLEDGE_DIR / "cost_log.json"
PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
DRAFTS_DIR.mkdir(parents=True, exist_ok=True)

SONNET_INPUT_PRICE = 3.0 / 1_000_000
SONNET_OUTPUT_PRICE = 15.0 / 1_000_000


def load_cost_log():
    """コストログを読み込む"""
    try:
        if not COST_FILE.exists():
            return {"monthly": {}, "total_usd": 0}
        with open(COST_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: コストログの読み込みに失敗: {e}")
        return {"monthly": {}, "total_usd": 0}


def save_cost(input_tokens, output_tokens, label):
    """コストを記録する"""
    try:
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
    except Exception as e:
        print(f"Error: コストログの保存に失敗: {e}")
        return 0


def call_claude(prompt, max_tokens=2000, label="api_call", retry_count=3):
    """Claude APIを呼び出す（リトライ機能付き）"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    
    for attempt in range(retry_count):
        try:
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
            with urllib.request.urlopen(req, timeout=30) as r:
                result = json.loads(r.read())
            usage = result.get("usage", {})
            save_cost(usage.get("input_tokens", 0), usage.get("output_tokens", 0), label)
            return result["content"][0]["text"]
        except Exception as e:
            print(f"API呼び出し失敗 (試行 {attempt + 1}/{retry_count}): {e}")
            if attempt < retry_count - 1:
                time.sleep(2 ** attempt)  # 指数バックオフ
            else:
                raise


def load_recent_data(days=30):
    """最近のデータを読み込む"""
    all_items, all_digests, all_tags = [], [], {}
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        filepath = KNOWLEDGE_DIR / "daily" / (date + ".json")
        if not filepath.exists():
            continue
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            all_items.extend(data.get("items", []))
            if data.get("digest"):
                all_digests.append(data["digest"])
            for tag, count in data.get("tags", {}).items():
                all_tags[tag] = all_tags.get(tag, 0) + count
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: {filepath}の読み込みに失敗: {e}")
            continue
    return all_items, all_digests, all_tags


def generate_enhanced_posts():
    """品質を向上させた投稿文を生成"""
    try:
        items, digests, tags = load_recent_data(2)
        if not items:
            print("データが不足しているため、投稿文生成をスキップします")
            return
        
        recent_digest = digests[0] if digests else "データなし"
        top_tags = sorted(tags.items(), key=lambda x: x[1], reverse=True)[:10]
        
        prompt = f"""
あなたは経験豊富なコンテンツマーケターです。以下の最新データから魅力的なX投稿文を3つ生成してください。

【直近の知識】
{recent_digest}

【トレンドタグ】
{', '.join([f"{tag}({count})" for tag, count in top_tags])}

【生成ルール】
1. 各投稿は140文字以内
2. 実践的な価値を提供
3. 感情に訴える要素を含める
4. 行動促進する内容にする
5. ハッシュタグを効果的に活用

以下のフォーマットで出力:
=== 投稿1 ===
[投稿文]

=== 投稿2 ===
[投稿文]

=== 投稿3 ===
[投稿文]
"""
        
        result = call_claude(prompt, max_tokens=1000, label="enhanced_posts")
        
        with open(DRAFTS_DIR / f"x_posts_{TODAY}.md", "w", encoding="utf-8") as f:
            f.write(f"# X投稿文案 ({TODAY})\n\n")
            f.write(result)
        
        print(f"投稿文を生成しました: {DRAFTS_DIR / f'x_posts_{TODAY}.md'}")
        
    except Exception as e:
        print(f"Error: 投稿文生成に失敗: {e}")


def analyze_trends_and_propose():
    """トレンド分析と提案生成（精度向上版）"""
    try:
        items, digests, tags = load_recent_data(7)
        if not items:
            print("データが不足しているため、分析をスキップします")
            return
        
        prompt = f"""
あなたは戦略コンサルタントです。過去7日間のデータを分析し、実行可能な提案を行ってください。

【分析データ】
アイテム数: {len(items)}
主要トレンド: {', '.join([f"{tag}({count})" for tag, count in sorted(tags.items(), key=lambda x: x[1], reverse=True)[:15]])}

最新ダイジェスト:
{digests[0] if digests else "データなし"}

【出力フォーマット】
## トレンド分析
- 急成長分野:
- 注目技術:
- 市場機会:

## ビジネスアイデア (3つ)
### アイデア1: [タイトル]
- 概要: 
- 市場性: 
- 実現可能性: 

### アイデア2: [タイトル]
- 概要:
- 市場性:
- 実現可能性:

### アイデア3: [タイトル]
- 概要:
- 市場性:
- 実現可能性:

## note記事案
タイトル: 
概要: (200文字)
構成案: (5つの見出し)

## 推奨行動
1. 
2. 
3. 
"""
        
        result = call_claude(prompt, max_tokens=3000, label="trend_analysis")
        
        output_file = PROPOSALS_DIR / f"analysis_{TODAY}.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"# 週間分析レポート ({TODAY})\n\n")
            f.write(result)
        
        print(f"分析レポートを生成しました: {output_file}")
        
    except Exception as e:
        print(f"Error: トレンド分析に失敗: {e}")


def create_github_issue():
    """GitHub Issue作成"""
    try:
        token = os.environ.get("GITHUB_TOKEN")
        repo = os.environ.get("GITHUB_REPO", "username/repo")
        
        if not token:
            print("Warning: GITHUB_TOKENが設定されていません")
            return
        
        items, _, tags = load_recent_data(7)
        top_tech = [tag for tag, count in sorted(tags.items(), key=lambda x: x[1], reverse=True)[:5]]
        
        issue_title = f"週間技術調査タスク ({TODAY})"
        issue_body = f"""
## 調査対象技術
{chr(10).join([f'- [ ] {tech}' for tech in top_tech])}

## 調査内容
- [ ] 最新動向調査
- [ ] 実装例収集
- [ ] ベストプラクティス整理
- [ ] サンプルコード作成

## 期限
{(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')}

*このIssueは自動生成されました*
"""
        
        payload = json.dumps({
            "title": issue_title,
            "body": issue_body,
            "labels": ["enhancement", "auto-generated"]
        }).encode()
        
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/issues",
            data=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json"
            }
        )
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read())
            print(f"GitHub Issue作成完了: {result.get('html_url', 'URL不明')}")
            
    except Exception as e:
        print(f"Warning: GitHub Issue作成に失敗: {e}")


def main():
    """メイン処理"""
    print(f"=== Growth Agent 実行開始 ({TODAY}) ===")
    
    try:
        # 毎日: 投稿文生成
        print("投稿文生成中...")
        generate_enhanced_posts()
        
        # 月曜日: 週次処理
        if WEEKDAY == 0:  # 月曜日
            print("週次分析実行中...")
            analyze_trends_and_propose()
            print("GitHub Issue作成中...")
            create_github_issue()
        
        # コスト情報表示
        cost_log = load_cost_log()
        month = TODAY[:7]
        if month in cost_log["monthly"]:
            monthly_cost = cost_log["monthly"][month]["usd"]
            print(f"今月のAPI使用料: ${monthly_cost:.4f}")
        
        print("=== 実行完了 ===")
        
    except Exception as e:
        print(f"Error: メイン処理でエラーが発生: {e}")
        raise


if __name__ == "__main__":
    main()
