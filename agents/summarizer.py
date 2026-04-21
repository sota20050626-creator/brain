import json
import os
import urllib.request
import re
from datetime import datetime
from pathlib import Path
import time

TODAY = datetime.now().strftime("%Y-%m-%d")
DATA_FILE = Path("knowledge/daily/" + TODAY + ".json")
COST_FILE = Path("knowledge/cost_log.json")

SONNET_INPUT_PRICE = 3.0 / 1_000_000
SONNET_OUTPUT_PRICE = 15.0 / 1_000_000


def load_cost_log():
    if not COST_FILE.exists():
        return {"monthly": {}, "total_usd": 0}
    try:
        with open(COST_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"警告: コストログの読み込みに失敗: {e}")
        return {"monthly": {}, "total_usd": 0}


def save_cost(input_tokens, output_tokens, label):
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
        
        # ディレクトリが存在しない場合は作成
        COST_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(COST_FILE, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
        print("  コスト記録: " + label + " $" + str(round(cost, 4)) + " (in:" + str(input_tokens) + " out:" + str(output_tokens) + ")")
        return cost
    except Exception as e:
        print(f"警告: コスト保存に失敗: {e}")
        return 0


def call_claude(prompt, max_tokens=2000, label="api_call", retry_count=3):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    
    for attempt in range(retry_count):
        try:
            payload = json.dumps({
                "model": "claude-3-5-sonnet-20241022",
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
            
            if "error" in result:
                raise Exception(f"API Error: {result['error']}")
                
            usage = result.get("usage", {})
            save_cost(usage.get("input_tokens", 0), usage.get("output_tokens", 0), label)
            return result["content"][0]["text"]
            
        except Exception as e:
            print(f"API呼び出し失敗 (試行 {attempt + 1}/{retry_count}): {e}")
            if attempt < retry_count - 1:
                time.sleep(2 ** attempt)  # 指数バックオフ
            else:
                raise e


def calculate_importance_score(item):
    """重要度スコアの計算を改善"""
    score = item.get("score", 0)
    
    # キーワードベースの重要度調整
    important_keywords = [
        "breakthrough", "革新", "発表", "リリース", "新技術", "AGI", "GPT", 
        "Claude", "Gemini", "OpenAI", "研究", "論文", "breakthrough", "milestone"
    ]
    
    title = item.get("title", "").lower()
    text = item.get("text", "").lower()
    content = title + " " + text
    
    # キーワードマッチによる重要度補正
    keyword_bonus = sum(1 for keyword in important_keywords if keyword.lower() in content)
    score += keyword_bonus * 0.1
    
    # 文字数による重要度補正（長すぎず短すぎない記事を優先）
    text_length = len(item.get("text", ""))
    if 100 <= text_length <= 2000:
        score += 0.2
    elif text_length > 2000:
        score += 0.1
    
    return round(score, 3)


def summarize_items(items):
    # 重要度スコアを再計算
    for item in items:
        item["importance_score"] = calculate_importance_score(item)
    
    # 重要度でソートして上位5件を選択
    top_items = sorted(items, key=lambda x: x.get("importance_score", 0), reverse=True)[:5]
    
    items_text = "\n\n".join([
        f"[{i+1}] SOURCE: {item['source']}\nTITLE: {item['title']}\nTEXT: {item.get('text','')[:400]}{'...' if len(item.get('text','')) > 400 else ''}"
        for i, item in enumerate(top_items)
    ])
    
    prompt = f"""あなたはAI技術のエキスパートアナリストです。
以下の{len(top_items)}件のAI関連情報を分析してください。

{items_text}

各アイテムについて以下のJSONフォーマットで回答してください。
技術的な正確性と実用性を重視し、日本語は自然で読みやすくしてください。
必ずJSON配列のみを返し、余分なテキストは含めないこと。

[
  {{
    "id": 1,
    "title_ja": "日本語タイトル（簡潔で分かりやすく）",
    "summary_ja": "2-3文での要約（技術的詳細と影響を含む）",
    "importance": "high/medium/low",
    "category": "技術分野（例：LLM, Computer Vision, Robotics等）",
    "key_points": ["重要なポイント1", "重要なポイント2"]
  }}
]"""

    try:
        response = call_claude(prompt, max_tokens=3000, label="summarize_items")
        
        # JSONの抽出を改善
        json_match = re.search(r'\[[\s\S]*\]', response)
        if json_match:
            json_str = json_match.group()
            try:
                summaries = json.loads(json_str)
                # データ検証
                for summary in summaries:
                    if not all(key in summary for key in ["id", "title_ja", "summary_ja"]):
                        print("警告: 必須フィールドが不足している要約があります")
                return summaries
            except json.JSONDecodeError as e:
                print(f"JSON解析エラー: {e}")
                print(f"レスポンス: {response}")
                return []
        else:
            print("JSONが見つかりませんでした")
            print(f"レスポンス: {response}")
            return []
    except Exception as e:
        print(f"要約処理エラー: {e}")
        return []
