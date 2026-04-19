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


def calculate_credibility_score(item):
    """Case-Grounded Evidence Verification: AI情報の信頼性スコアを算出"""
    try:
        score = 0
        text = item.get("text", "") + " " + item.get("title", "")
        
        # 1. キーワード頻度分析 (0-30点)
        tech_keywords = [
            "research", "paper", "study", "experiment", "data", "analysis", 
            "AI", "machine learning", "neural", "model", "algorithm",
            "published", "journal", "conference", "peer-review"
        ]
        keyword_count = sum(1 for keyword in tech_keywords if keyword.lower() in text.lower())
        keyword_score = min(keyword_count * 2, 30)
        score += keyword_score
        
        # 2. 引用・参照数の推定 (0-25点)
        citation_patterns = [
            r'\[\d+\]',  # [1], [2] 形式
            r'\(\d{4}\)',  # 年号 (2024)
            r'et al\.',  # 論文引用
            r'doi:', r'arxiv:', r'https?://.*\.pdf'
        ]
        citation_count = sum(len(re.findall(pattern, text, re.IGNORECASE)) 
                           for pattern in citation_patterns)
        citation_score = min(citation_count * 3, 25)
        score += citation_score
        
        # 3. ソースの権威性 (0-45点)
        source = item.get("source", "").lower()
        authority_sources = {
            "arxiv": 35, "nature": 45, "science": 45, "acm": 40,
            "ieee": 40, "mit": 40, "stanford": 40, "google": 35,
            "openai": 35, "microsoft": 30, "meta": 30, "anthropic": 35,
            "github": 25, "medium": 15, "blog": 10, "reddit": 5
        }
        authority_score = 0
        for auth_source, points in authority_sources.items():
            if auth_source in source:
                authority_score = max(authority_score, points)
                break
        else:
            # 一般的なドメイン評価
            if any(ext in source for ext in ['.edu', '.gov']):
                authority_score = 30
            elif any(ext in source for ext in ['.org', '.ac.']):
                authority_score = 25
            elif source.startswith('http'):
                authority_score = 15
            else:
                authority_score = 10
        
        score += authority_score
        
        # 最終スコア正規化 (0-100)
        final_score = min(score, 100)
        return final_score
        
    except Exception:
        # エラー時はデフォルトスコア50を返す
        return 50


def verify_evidence_quality(items):
    """収集したAI情報の信頼性を検証し、品質レポートを生成"""
    try:
        results = []
        high_quality = 0
        medium_quality = 0
        low_quality = 0
        
        for item in items:
            credibility_score = calculate_credibility_score(item)
            
            # 信頼度レベル分類
            if credibility_score >= 70:
                quality_level = "HIGH"
                high_quality += 1
            elif credibility_score >= 40:
                quality_level = "MEDIUM"
                medium_quality += 1
            else:
                quality_level = "LOW"
                low_quality += 1
            
            # アイテムに信頼度情報を追加
            verified_item = item.copy()
            verified_item["credibility_score"] = credibility_score
            verified_item["quality_level"] = quality_level
            results.append(verified_item)
        
        # 品質レポート生成
        total_items = len(items)
        quality_report = {
            "total_items": total_items,
            "high_quality": high_quality,
            "medium_quality": medium_quality,
            "low_quality": low_quality,
            "average_score": round(sum(item["credibility_score"] for item in results) / total_items, 2) if total_items > 0 else 0
        }
        
        print(f"  信頼性検証完了: 高品質={high_quality}, 中品質={medium_quality}, 低品質={low_quality}")
        
        return results, quality_report
        
    except Exception as e:
        print(f"  信頼性検証でエラー: {e}")
        # エラー時は元のアイテムをそのまま返す
        return items, {"error": str(e)}


def summarize_items(items):
    # 信頼性検証を実行
    try:
        verified_items, quality_report = verify_evidence_quality(items)
        # 信頼性スコアも考慮したソート (既存スコア70% + 信頼性スコア30%)
        for item in verified_items:
            original_score = item.get("score", 0)
            credibility_score = item.get("credibility_score", 50)
            item["combined_score"] = original_score * 0.7 + credibility_score * 0.3
    except Exception:
        # エラー時は既存のアイテムを使用
        verified_items = items
        for item in verified_items:
            item["combined_score"] = item.get("score", 0)
    
    # 統合スコアでソート
    top_items = sorted(verified_items, key=lambda x: x.get("combined_score", 0), reverse=True)[:10]
    
    items_text = "\n\n".join([
        "[" + str(i+1) + "] SOURCE: " + item["source"] + 
        "\nTITLE: " + item["title"] + 
        "\nTEXT: " + item.get("text","")[:200] +
        ("\nCREDIBILITY: " + str(item.get("credibility_score", "N/A")) if "credibility_score" in item else "")
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
    "summary_ja": "要約内容"
  }
]"""

    try:
        response = call_claude(prompt, max_tokens=2000, label="summarize")
        return response
    except Exception as e:
        print(f"要約でエラー: {e}")
        return "[]"
