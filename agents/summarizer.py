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
        print(f"警告: コストログの読み込みに失敗しました: {e}")
        return {"monthly": {}, "total_usd": 0}


def save_cost(input_tokens, output_tokens, label):
    cost = input_tokens * SONNET_INPUT_PRICE + output_tokens * SONNET_OUTPUT_PRICE
    try:
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
    except Exception as e:
        print(f"警告: コスト記録に失敗しました: {e}")
    return cost


def call_claude(prompt, max_tokens=2000, label="api_call", retry_count=3):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    
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
    
    for attempt in range(retry_count):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                result = json.loads(r.read())
                
            if "error" in result:
                raise ValueError(f"API Error: {result['error']}")
                
            usage = result.get("usage", {})
            save_cost(usage.get("input_tokens", 0), usage.get("output_tokens", 0), label)
            return result["content"][0]["text"]
            
        except urllib.error.HTTPError as e:
            if e.code == 429:  # Rate limit
                wait_time = 2 ** attempt
                print(f"レート制限に達しました。{wait_time}秒待機します...")
                time.sleep(wait_time)
                continue
            else:
                raise ValueError(f"HTTP Error {e.code}: {e.reason}")
        except Exception as e:
            if attempt == retry_count - 1:
                raise ValueError(f"API呼び出しに失敗しました: {e}")
            print(f"API呼び出し失敗 (試行 {attempt + 1}/{retry_count}): {e}")
            time.sleep(1)


def calculate_importance_score(item):
    """アイテムの重要度スコアを計算"""
    score = item.get("score", 0)
    
    # キーワードベースのスコア調整
    title_text = (item.get("title", "") + " " + item.get("text", "")).lower()
    
    # 重要なAI技術キーワード
    high_priority = ["gpt", "claude", "chatgpt", "llm", "ai", "artificial intelligence", 
                     "machine learning", "deep learning", "neural network", "transformer"]
    medium_priority = ["automation", "algorithm", "model", "training", "inference", "api"]
    
    for keyword in high_priority:
        if keyword in title_text:
            score += 10
    
    for keyword in medium_priority:
        if keyword in title_text:
            score += 5
    
    # 日付の新しさによるスコア調整
    if "date" in item:
        try:
            item_date = datetime.strptime(item["date"], "%Y-%m-%d")
            today_date = datetime.strptime(TODAY, "%Y-%m-%d")
            days_old = (today_date - item_date).days
            if days_old <= 1:
                score += 20
            elif days_old <= 3:
                score += 10
        except:
            pass
    
    return score


def summarize_items(items):
    if not items:
        print("要約するアイテムがありません")
        return []
    
    # 重要度スコアを再計算
    for item in items:
        item["calculated_score"] = calculate_importance_score(item)
    
    # 上位アイテムを選択（最大15件に拡張）
    top_items = sorted(items, key=lambda x: x.get("calculated_score", 0), reverse=True)[:15]
    
    items_text = "\n\n".join([
        "[" + str(i+1) + "] SOURCE: " + item.get("source", "不明") + 
        "\nTITLE: " + item.get("title", "タイトルなし") + 
        "\nTEXT: " + item.get("text", "")[:300] + ("..." if len(item.get("text", "")) > 300 else "")
        for i, item in enumerate(top_items)
    ])
    
    prompt = f"""あなたはAI技術のエキスパートアナリストです。
以下の{len(top_items)}件のAI関連情報を分析してください。

{items_text}

各アイテムについて以下のJSONフォーマットで回答してください。
必ずJSON配列のみを返し、余分なテキストは含めないこと。

要約のポイント:
- 技術的な詳細と実用性を重視
- 日本のビジネス環境への影響を考慮
- 重要度を1-10で評価（10が最重要）

[
  {{
    "id": 1,
    "title_ja": "日本語タイトル（具体的で分かりやすく）",
    "summary_ja": "重要なポイントを3-4行で簡潔にまとめた要約",
    "importance": 8,
    "category": "技術分野（例：LLM、自動化、API等）",
    "impact": "ビジネスへの影響度（高・中・低）"
  }}
]"""
    
    try:
        response = call_claude(prompt, max_tokens=3000, label="summarize")
        # JSONの抽出を改善
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            return json.loads(json_str)
        else:
            print("警告: 有効なJSONが見つかりませんでした")
            return []
    except json.JSONDecodeError as e:
        print(f"JSON解析エラー: {e}")
        print(f"レスポンス: {response[:500]}...")
        return []
    except Exception as e:
        print(f"要約処理エラー: {e}")
        return []
