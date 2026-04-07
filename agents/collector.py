"""
collector.py - AI情報収集エージェント
ソース: Reddit, HackerNews, ArXiv, GitHub Trending
"""

import json
import os
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

TODAY = datetime.now().strftime("%Y-%m-%d")
OUTPUT_DIR = Path("knowledge/daily")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / f"{TODAY}.json"

AI_KEYWORDS = [
    "ai", "llm", "gpt", "claude", "gemini", "openai", "anthropic",
    "machine learning", "neural", "transformer", "agent", "rag",
    "deepseek", "qwen", "mistral", "diffusion", "multimodal",
    "ml", "model", "train", "inference", "vector"
]

REDDIT_SUBREDDITS = [
    "MachineLearning",
    "LocalLLaMA",
    "artificial",
    "ChatGPT",
    "singularity",
]


def get_reddit_token():
    client_id = os.environ.get("REDDIT_CLIENT_ID", "")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        print("Reddit creden
