import json
import os
import urllib.request
import re
from datetime import datetime
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.manifold import LocallyLinearEmbedding
from sklearn.ensemble import IsolationForest

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


def geometric_regularization_scoring(items):
    """
    重要度スコアリングの幾何学的正則化
    TF-IDF特徴量に対してLocallyLinearEmbeddingを適用し、異常値を検出してスコアを調整
    """
    try:
        if len(items) < 10:  # データが少ない場合はスキップ
            print("  幾何学的正則化: データ数が少ないためスキップ")
            return items
        
        # テキストデータの抽出
        texts = []
        for item in items:
            text = item.get("title", "") + " " + item.get("text", "")[:500]
            texts.append(text)
        
        # TF-IDF特徴量を計算
        vectorizer = TfidfVectorizer(
            max_features=100,
            stop_words='english',
            min_df=1,
            max_df=0.95
        )
        tfidf_matrix = vectorizer.fit_transform(texts).toarray()
        
        # 低次元埋め込み（LocallyLinearEmbedding）
        n_neighbors = min(5, len(items) - 1)
        n_components = min(10, tfidf_matrix.shape[1] - 1)
        
        lle = LocallyLinearEmbedding(
            n_neighbors=n_neighbors,
            n_components=n_components,
            random_state=42
        )
        embedded_features = lle.fit_transform(tfidf_matrix)
        
        # 異常値検出
        isolation_forest = IsolationForest(
            contamination=0.1,
            random_state=42
        )
        anomaly_scores = isolation_forest.fit_predict(embedded_features)
        
        # スコアの正則化
        for i, item in enumerate(items):
            original_score = item.get("score", 0)
            
            # 埋め込み空間での密度スコア（中心からの距離の逆数）
            center = np.mean(embedded_features, axis=0)
            distance = np.linalg.norm(embedded_features[i] - center)
            density_score = 1.0 / (1.0 + distance)
            
            # 異常値ペナルティ
            anomaly_penalty = 0.8 if anomaly_scores[i] == -1 else 1.0
            
            # 正則化されたスコア
            regularized_score = original_score * density_score * anomaly_penalty
            item["score"] = regularized_score
            item["geometric_regularized"] = True
        
        print(f"  幾何学的正則化: {len(items)}件のアイテムを処理、{np.sum(anomaly_scores == -1)}件の異常値を検出")
        return items
        
    except Exception as e:
        print(f"  幾何学的正則化でエラーが発生: {str(e)}")
        # エラーが発生した場合は元のデータをそのまま返す
        for item in items:
            item["geometric_regularized"] = False
        return items


def summarize_items(items):
    # 幾何学的正則化を適用
    items = geometric_regularization_scoring(items)
    
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
    "summary_ja": "2から3行の簡潔な要約",
    "importance": 0.85,
    "category": "技術分野",
    "impact_analysis": "影響の分析"
  }
]"""
    
    return call_claude(prompt, label="summarize_items")
