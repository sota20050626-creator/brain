import json
import os
import urllib.request
import re
from datetime import datetime
from pathlib import Path

TODAY = datetime.now().strftime("%Y-%m-%d")
DATA_FILE = Path("knowledge/daily/" + TODAY + ".json")
COST_FILE = Path("knowledge/cost_log.json")

SONNET_INPUT_PRICE = 3.0 / 1_000_000
SONNET_OUTPUT_PRICE = 15.0 / 1_000_000

# 礼儀正しさ考慮機能の辞書
POLITENESS_PATTERNS = {
    "polite": [
        r"です", r"ます", r"でしょう", r"いたします", r"させていただ",
        r"恐れ入り", r"申し上げ", r"いたし", r"ございます", r"でございます"
    ],
    "humble": [
        r"拝見", r"拝読", r"存じ", r"承知", r"お聞かせ", r"お教え",
        r"ご指導", r"ご教示", r"申し上げます", r"お伺い"
    ],
    "aggressive": [
        r"バカ", r"アホ", r"クソ", r"ダメ", r"最悪", r"無能",
        r"間違っている", r"論外", r"話にならない", r"問題外"
    ]
}


def calculate_politeness_score(text):
    """テキストの礼儀正しさスコアを計算"""
    try:
        if not text:
            return 0
        
        polite_count = 0
        humble_count = 0
        aggressive_count = 0
        
        for pattern in POLITENESS_PATTERNS["polite"]:
            polite_count += len(re.findall(pattern, text))
        
        for pattern in POLITENESS_PATTERNS["humble"]:
            humble_count += len(re.findall(pattern, text))
        
        for pattern in POLITENESS_PATTERNS["aggressive"]:
            aggressive_count += len(re.findall(pattern, text))
        
        # 文字数で正規化
        text_length = len(text) if len(text) > 0 else 1
        
        polite_ratio = (polite_count + humble_count) / text_length * 1000
        aggressive_ratio = aggressive_count / text_length * 1000
        
        # 礼儀正しさ補正係数を計算（-0.3 〜 +0.3）
        politeness_adjustment = min(0.3, max(-0.3, polite_ratio - aggressive_ratio * 2))
        
        return politeness_adjustment
    except Exception:
        return 0


def adjust_score_for_politeness(items):
    """重要度スコアに礼儀正しさを考慮した調整を適用"""
    try:
        for item in items:
            original_score = item.get("score", 0)
            text_content = item.get("text", "") + " " + item.get("title", "")
            
            politeness_adjustment = calculate_politeness_score(text_content)
            adjusted_score = original_score + politeness_adjustment
            
            item["score"] = max(0, adjusted_score)  # スコアが負にならないよう調整
            item["politeness_adjustment"] = politeness_adjustment
            
    except Exception:
        # エラーが発生しても既存機能を維持
        pass
    
    return items


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
    print("  コスト記録: " + label + " $" + str(round(cost, 4)) + " (in:" + str(input_tokens) + " out:" + str(output_tokens) + ")")
    return cost


def call_claude(prompt, max_tokens=2000, label="api_call"):
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
    with urllib.request.urlopen(req) as r:
        result = json.loads(r.read())
    usage = result.get("usage", {})
    save_cost(usage.get("input_tokens", 0), usage.get("output_tokens", 0), label)
    return result["content"][0]["text"]


def summarize_items(items):
    # 礼儀正しさを考慮したスコア調整を適用
    items = adjust_score_for_politeness(items)
    
    top_items = sorted(items, key=lambda x: x.get("score", 0), reverse=True)[:5]
    items_text = "\n\n".join([
        "[" + str(i+1) + "] SOURCE: " + item["source"] + "\nTITLE: " + item["title"] + "\nTEXT: " + item.get("text","")[:200]
        for i, item in enumerate(top_items)
    ])
    prompt = """あなたはAI技術のエキスパートアナリストです。
以下の""" + str(len(top_items)) + """件のAI関連情報を分析してください。

""" + items_text + """

各アイテムについて以下のJSONフォーマットで回答してください。
必ずJSON配列のみを返し、余分なテキストは含めないこと。

[
  {
    "id": 1,
    "title_ja": "日本語タイトル",
    "summary_ja": "2-3文の要約",
    "importance": "high/medium/low",
    "category": "カテゴリ名",
    "impact": "技術への影響度の説明"
  }
]"""
    
    return call_claude(prompt, 4000, "summarize")
