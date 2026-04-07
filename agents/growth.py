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
            all_tags[tag] = all_tags.get(tag, 0) +
