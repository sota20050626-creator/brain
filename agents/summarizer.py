import json
import os
import urllib.request
import re
from datetime import datetime
from pathlib import Path
import time
import logging

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TODAY = datetime.now().strftime("%Y-%m-%d")
DATA_FILE = Path("knowledge/daily/" + TODAY + ".json")
COST_FILE = Path("knowledge/cost_log.json")

SONNET_INPUT_PRICE = 3.0 / 1_000_000
SONNET_OUTPUT_PRICE = 15.0 / 1_000_000

# リトライ設定
MAX_RETRIES = 3
RETRY_DELAY = 1


def load_cost_log():
    """コストログを読み込む"""
    if not COST_FILE.exists():
        return {"monthly": {}, "total_usd": 0}
    try:
        with open(COST_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"コストログの読み込みエラー: {e}")
        return {"monthly": {}, "total_usd": 0}


def save_cost(input_tokens, output_tokens, label):
    """コスト情報を保存する"""
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
        logger.error(f"コスト保存エラー: {e}")
        return 0


def call_claude(prompt, max_tokens=2000, label="api_call"):
    """Claude APIを呼び出す（リトライ機能付き）"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    
    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    
    for attempt in range(MAX_RETRIES):
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
                result = json.loads(r.read())
            
            if "error" in result:
                raise Exception(f"API Error: {result['error']}")
            
            usage = result.get("usage", {})
            save_cost(usage.get("input_tokens", 0), usage.get("output_tokens", 0), label)
            return result["content"][0]["text"]
            
        except Exception as e:
            logger.warning(f"API呼び出し失敗 (試行 {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                raise Exception(f"API呼び出しが{MAX_RETRIES}回失敗しました: {e}")


def calculate_importance_score(item):
    """アイテムの重要度スコアを計算する"""
    score = item.get("score", 0)
    
    # AI関連キーワードによる重要度補正
    high_impact_keywords = ["breakthrough", "革新", "画期的", "最新", "発表", "リリース", "GPT", "LLM", "AI"]
    medium_impact_keywords = ["改善", "更新", "アップデート", "機能", "性能"]
    
    title = item.get("title", "").lower()
    text = item.get("text", "")[:500].lower()  # 最初の500文字のみチェック
    content = title + " " + text
    
    # キーワードマッチングによるスコア調整
    for keyword in high_impact_keywords:
        if keyword.lower() in content:
            score += 10
    
    for keyword in medium_impact_keywords:
        if keyword.lower() in content:
            score += 5
    
    # テキストの長さによる調整（情報量の指標）
    text_length = len(item.get("text", ""))
    if text_length > 500:
        score += 3
    elif text_length > 200:
        score += 1
    
    return score


def summarize_items(items):
    """アイテムを要約する"""
    if not items:
        logger.warning("要約対象のアイテムがありません")
        return "[]"
    
    # 重要度スコアを再計算してソート
    for item in items:
        item["calculated_score"] = calculate_importance_score(item)
    
    top_items = sorted(items, key=lambda x: x.get("calculated_score", 0), reverse=True)[:5]
    
    items_text = "\n\n".join([
        f"[{i+1}] SOURCE: {item.get('source', 'Unknown')}\nTITLE: {item.get('title', 'No Title')}\nTEXT: {item.get('text', '')[:300]}"
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
    "title_ja": "日本語タイトル",
    "summary_ja": "2から3文で要約した重要なポイント",
    "importance": "high/medium/low",
    "category": "技術革新/製品発表/研究発表/その他",
    "key_points": ["重要ポイント1", "重要ポイント2"]
  }}
]

重要度の判定基準：
- high: 業界に大きな影響を与える革新的な技術や発表
- medium: 注目すべき改善や新機能
- low: 一般的な情報やマイナーな更新"""

    try:
        response = call_claude(prompt, max_tokens=3000, label=f"summarize_{len(top_items)}_items")
        
        # JSONの抽出と検証
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            # JSONの妥当性を検証
            parsed_json = json.loads(json_str)
            if isinstance(parsed_json, list):
                return json_str
            else:
                logger.error("レスポンスが配列形式ではありません")
        
        logger.error("有効なJSON配列が見つかりませんでした")
        return "[]"
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析エラー: {e}")
        return "[]"
    except Exception as e:
        logger.error(f"要約処理エラー: {e}")
        return "[]"
