import json
import os
import urllib.request
import re
from datetime import datetime
from pathlib import Path
from collections import Counter
import time

TODAY = datetime.now().strftime("%Y-%m-%d")
DATA_FILE = Path(f"knowledge/daily/{TODAY}.json")


def call_claude(prompt, max_tokens=2000, retry_count=3):
    """Claude APIを呼び出す（リトライ機能付き）"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    
    payload = json.dumps({
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    
    for attempt in range(retry_count):
        try:
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
                response_data = json.loads(r.read())
                if "content" in response_data and response_data["content"]:
                    return response_data["content"][0]["text"]
                else:
                    raise ValueError("Invalid response format from Claude API")
                    
        except Exception as e:
            print(f"API call attempt {attempt + 1} failed: {e}")
            if attempt < retry_count - 1:
                time.sleep(2 ** attempt)  # 指数バックオフ
            else:
                raise e


def _calculate_importance_score(item):
    """アイテムの重要度を計算"""
    base_score = item.get("score", 0)
    
    # タイトルと本文から重要キーワードを検索
    text_content = f"{item.get('title', '')} {item.get('text', '')}".lower()
    
    # 重要キーワードによる加点
    high_impact_keywords = ["breakthrough", "革新", "chatgpt", "gpt-4", "claude", "gemini", "革命", "発表"]
    medium_impact_keywords = ["ai", "machine learning", "deep learning", "neural", "algorithm", "model"]
    
    bonus = 0
    for keyword in high_impact_keywords:
        if keyword in text_content:
            bonus += 2
    
    for keyword in medium_impact_keywords:
        if keyword in text_content:
            bonus += 0.5
    
    return min(base_score + bonus, 10)  # 最大10点


def summarize_items(items):
    """アイテムを要約・分析"""
    if not items:
        return []
    
    # 重要度スコアを再計算
    for item in items:
        item["calculated_importance"] = _calculate_importance_score(item)
    
    # 上位10件を選択（重要度順）
    top_items = sorted(items, key=lambda x: x.get("calculated_importance", 0), reverse=True)[:10]
    
    # プロンプト用のテキストを生成
    items_text = "\n\n".join([
        f"[{i+1}] SOURCE: {item.get('source', 'Unknown')}\n"
        f"TITLE: {item.get('title', 'No title')}\n"
        f"TEXT: {item.get('text', '')[:300]}\n"
        f"SCORE: {item.get('calculated_importance', 0):.1f}"
        for i, item in enumerate(top_items)
    ])
    
    prompt = f"""あなたはAI技術のエキスパートアナリストです。
以下の{len(top_items)}件のAI関連情報を分析してください。

{items_text}

各アイテムについて以下のJSONフォーマットで回答してください。
必ずJSON配列のみを返し、余分なテキストは含めないこと。

[
  {{
    "id": 1,
    "title_ja": "正確で分かりやすい日本語タイトル",
    "summary_ja": "技術的詳細とビジネスインパクトを含む2から3文の要約",
    "importance": 8,
    "tags": ["LLM", "ビジネス"],
    "category": "技術",
    "confidence": 0.9
  }}
]

評価基準：
- importance: 1-10（技術革新度、市場インパクト、実用性を総合評価）
- tags: ["LLM", "Agent", "ビジネス", "画像生成", "音声", "コード", "論文", "中国AI", "オープンソース", "ツール", "企業動向"]から複数選択
- category: ["技術", "ビジネス", "ツール", "論文", "企業動向", "その他"]から1つ選択
- confidence: 0-1（要約の信頼度）"""

    try:
        response = call_claude(prompt, max_tokens=4000)
        
        # JSONの抽出を改善
        json_match = re.search(r'\[[\s\S]*\]', response)
        if not json_match:
            print("No JSON found in response")
            return _fallback_summary(top_items)
        
        summaries = json.loads(json_match.group())
        if not isinstance(summaries, list):
            print("Response is not a valid JSON array")
            return _fallback_summary(top_items)
            
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        return _fallback_summary(top_items)
    except Exception as e:
        print(f"Summarization error: {e}")
        return _fallback_summary(top_items)

    # 結果をマージ
    results = []
    for s in summaries:
        try:
            idx = s.get("id", 0) - 1
            if 0 <= idx < len(top_items):
                item = top_items[idx].copy()
                item.update({
                    "title_ja": s.get("title_ja", item.get("title", "No title")),
                    "summary_ja": s.get("summary_ja", "要約情報なし"),
                    "importance": max(1, min(10, s.get("importance", 5))),  # 1-10に制限
                    "tags": s.get("tags", []) if isinstance(s.get("tags"), list) else [],
                    "category": s.get("category", "その他"),
                    "confidence": max(0, min(1, s.get("confidence", 0.5))),  # 0-1に制限
                })
                results.append(item)
        except Exception as e:
            print(f"Error processing summary item: {e}")
            continue
    
    return sorted(results, key=lambda x: x.get("importance", 0), reverse=True)


def _fallback_summary(items):
    """要約に失敗した場合のフォールバック"""
    results = []
    for i, item in enumerate(items[:5]):  # 上位5件のみ
        fallback_item = item.copy()
        fallback_item.update({
            "title_ja": item.get("title", f"記事 {i+1}"),
            "summary_ja": "要約処理中にエラーが発生しました",
            "importance": min(10, item.get("calculated_importance", 5)),
            "tags": ["その他"],
            "category": "その他",
            "confidence": 0.3,
        })
        results.append(fallback_item)
    return results


def generate_daily_digest(items):
    """日次ダイジェストを生成"""
    if not items:
        return "今日は分析可能なAI関連情報がありませんでした。"
    
    top5 = items[:5]
    top5_text = "\n".join([
        f"- {item.get('title_ja', 'タイトルなし')}: {item.get('summary_ja', '要約なし')} (重要度: {item.get('importance', 0)})"
        for item in top5
    ])
    
    # タグ分析を追加
    tag_summary = _count_tags(items)
    
    prompt = f"""今日のAIトレンドトップ5:
{top5_text}

主要な技術分野: {', '.join([f"{tag}({count}件)" for tag, count in tag_summary.most_common(3)])}

これらを踏まえて、以下を日本語で書いてください：
1. 今日の最重要トレンド（重要度と技術的意義を含めて3行以内）
2. ビジネスへの示唆（実用性と市場インパクトを含めて2行以内）
3. 注目すべき技術動向（今後の展望を含めて2行以内）

データに基づいて客観的かつ簡潔にまとめてください。"""

    try:
        return call_claude(prompt, max_tokens=600)
    except Exception as e:
        print(f"Digest generation error: {e}")
        return f"ダイジェスト生成中にエラーが発生しましたが、{len(items)}件のAI関連情報を収集・分析しました。"


def _count_tags(items):
    """タグの集計"""
    tags = []
    for item in items:
        item_tags = item.get("tags", [])
        if isinstance(item_tags, list):
            tags.extend(item_tags)
    return Counter(tags)
