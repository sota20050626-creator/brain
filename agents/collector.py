"""
collector.py - AI情報収集エージェント
ソース: Reddit, HackerNews, ArXiv, GitHub Search API, Hugging Face
"""

import json
import os
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import logging

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TODAY = datetime.now().strftime("%Y-%m-%d")
OUTPUT_DIR = Path("knowledge/daily")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / f"{TODAY}.json"

AI_KEYWORDS = [
    "ai", "llm", "gpt", "claude", "gemini", "openai", "anthropic",
    "machine learning", "neural", "transformer", "agent", "rag",
    "deepseek", "qwen", "mistral", "diffusion", "multimodal",
    "ml", "model", "train", "inference", "vector", "huggingface",
    "stable diffusion", "whisper", "chatbot", "fine-tuning"
]

REDDIT_SUBREDDITS = [
    "MachineLearning",
    "LocalLLaMA", 
    "artificial",
    "ChatGPT",
    "singularity",
    "huggingface",
    "StableDiffusion"
]

def safe_request(url, headers=None, data=None, timeout=10, max_retries=3):
    """安全なHTTPリクエスト実行（リトライ機能付き）"""
    headers = headers or {"User-Agent": "Brain/1.0"}
    
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read())
        except Exception as e:
            logger.warning(f"Request attempt {attempt + 1} failed for {url}: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # 指数バックオフ
    return None

def get_reddit_token():
    client_id = os.environ.get("REDDIT_CLIENT_ID", "")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        logger.warning("Reddit credentials not set, skipping Reddit")
        return None
    
    try:
        import base64
        encoded = base64.b64encode(
            (client_id + ":" + client_secret).encode()
        ).decode()
        data = urllib.parse.urlencode(
            {"grant_type": "client_credentials"}
        ).encode()
        
        headers = {
            "Authorization": "Basic " + encoded,
            "User-Agent": "Brain/1.0"
        }
        
        response = safe_request(
            "https://www.reddit.com/api/v1/access_token",
            headers=headers,
            data=data
        )
        return response["access_token"]
    except Exception as e:
        logger.error(f"Reddit auth failed: {e}")
        return None

def is_ai_related(text):
    """テキストがAI関連かどうかを判定"""
    if not text:
        return False
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in AI_KEYWORDS)

def fetch_reddit(token, subreddit, limit=10):
    if not token:
        return []
    
    try:
        headers = {
            "Authorization": "Bearer " + token,
            "User-Agent": "Brain/1.0"
        }
        
        url = f"https://oauth.reddit.com/r/{subreddit}/hot?limit={limit}"
        data = safe_request(url, headers=headers)
        
        posts = []
        for child in data["data"]["children"]:
            p = child["data"]
            # スコアとAI関連性でフィルタリング
            if p.get("score", 0) < 50:
                continue
            
            title_and_text = p["title"] + " " + p.get("selftext", "")
            if not is_ai_related(title_and_text):
                continue
                
            posts.append({
                "title": p["title"],
                "url": p.get("url", ""),
                "score": p.get("score", 0),
                "comments": p.get("num_comments", 0),
                "source": f"reddit/r/{subreddit}",
                "text": p.get("selftext", "")[:500],
                "timestamp": datetime.now().isoformat()
            })
        return posts
    except Exception as e:
        logger.error(f"Reddit fetch error for {subreddit}: {e}")
        return []

def fetch_hackernews(limit=30):
    try:
        # トップストーリー取得
        data = safe_request("https://hacker-news.firebaseio.com/v0/topstories.json")
        story_ids = data[:limit]
        
        stories = []
        for story_id in story_ids:
            try:
                story_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                story = safe_request(story_url, timeout=5)
                
                if not story or story.get("type") != "story":
                    continue
                
                title = story.get("title", "")
                if not is_ai_related(title):
                    continue
                    
                stories.append({
                    "title": title,
                    "url": story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                    "score": story.get("score", 0),
                    "comments": story.get("descendants", 0),
                    "source": "hackernews",
                    "timestamp": datetime.now().isoformat()
                })
                
                if len(stories) >= 10:  # AI関連記事10件で十分
                    break
                    
            except Exception as e:
                logger.warning(f"Failed to fetch HN story {story_id}: {e}")
                continue
                
        return stories
    except Exception as e:
        logger.error(f"HackerNews fetch error: {e}")
        return []

def fetch_arxiv(query="ai OR llm OR transformer", max_results=10):
    """ArXiv論文検索（AI関連）"""
    try:
        yesterday = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
        encoded_query = urllib.parse.quote_plus(
            f"({query}) AND submittedDate:[{yesterday}000000 TO 20991231235959]"
        )
        
        url = f"http://export.arxiv.org/api/query?search_query={encoded_query}&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"
        
        req = urllib.request.Request(url, headers={"User-Agent": "Brain/1.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            content = response.read().decode('utf-8')
        
        # 簡易XML解析
        papers = []
        entries = re.findall(r'<entry>(.*?)</entry>', content, re.DOTALL)
        
        for entry in entries:
            title_match = re.search(r'<title>(.*?)</title>', entry, re.DOTALL)
            link_match = re.search(r'<id>(.*?)</id>', entry)
            summary_match = re.search(r'<summary>(.*?)</summary>', entry, re.DOTALL)
            
            if title_match and link_match:
                title = re.sub(r'\s+', ' ', title_match.group(1)).strip()
                papers.append({
                    "title": title,
                    "url": link_match.group(1),
                    "source": "arxiv",
                    "text": re.sub(r'\s+', ' ', summary_match.group(1)).strip()[:500] if summary_match else "",
                    "timestamp": datetime.now().isoformat()
                })
                
        return papers
    except Exception as e:
        logger.error(f"ArXiv fetch error: {e}")
        return []

def fetch_github(query="ai OR llm", limit=10):
    """GitHub検索（AI関連リポジトリ）"""
    try:
        token = os.environ.get("GITHUB_TOKEN", "")
        headers = {"User-Agent": "Brain/1.0"}
        if token:
            headers["Authorization"] = f"token {token}"
        
        # 過去1週間で更新されたリポジトリ
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        encoded_query = urllib.parse.quote_plus(f"{query} pushed:>{week_ago}")
        
        url = f"https://api.github.com/search/repositories?q={encoded_query}&sort=stars&order=desc&per_page={limit}"
        data = safe_request(url, headers=headers)
        
        repos = []
        for item in data.get("items", []):
            repos.append({
                "title": item["full_name"],
                "url": item["html_url"], 
                "source": "github",
                "text": (item.get("description") or "")[:500],
                "score": item.get("stargazers_count", 0),
                "timestamp": datetime.now().isoformat()
            })
            
        return repos
    except Exception as e:
        logger.error(f"GitHub fetch error: {e}")
        return []

def fetch_huggingface_models(limit=10):
    """Hugging Face新着モデル取得"""
    try:
        url = f"https://huggingface.co/api/models?sort=createdAt&direction=-1&limit={limit}"
        data = safe_request(url)
        
        models = []
        for model in data:
            if not model.get("modelId"):
                continue
                
            models.append({
                "title": f"New Model: {model['modelId']}",
                "url": f"https://huggingface.co/{model['modelId']}",
                "source": "huggingface",
                "text": f"Tags: {', '.join(model.get('tags', [])[:5])}",
                "score": model.get("downloads", 0),
                "timestamp": datetime.now().isoformat()
            })
            
        return models
    except Exception as e:
        logger.error(f"Hugging Face fetch error: {e}")
        return []

def main():
    logger.info("Starting AI information collection")
    all_content = []
    
    # Reddit収集
    token = get_reddit_token()
    if token:
        for subreddit in REDDIT_SUBREDDITS:
            logger.info(f"Fetching Reddit: r/{subreddit}")
            posts = fetch_reddit(token, subreddit)
            all_content.extend(posts)
            time.sleep(1)  # レート制限対策
    
    # HackerNews収集
    logger.info("Fetching HackerNews")
    hn_stories = fetch_hackernews()
    all_content.extend(hn_stories)
    
    # ArXiv収集
    logger.info("Fetching ArXiv papers")
    papers = fetch_arxiv()
    all_content.extend(papers)
    
    # GitHub収集
    logger.info("Fetching GitHub repositories")
    repos = fetch_github()
    all_content.extend(repos)
    
    # Hugging Face収集
    logger.info("Fetching Hugging Face models")
    models = fetch_huggingface_models()
    all_content.extend(models)
    
    # 結果保存
    result = {
        "date": TODAY,
        "total_items": len(all_content),
        "sources": {
            "reddit": len([x for x in all_content if x["source"].startswith("reddit")]),
            "hackernews": len([x for x in all_content if x["source"] == "hackernews"]),
            "arxiv": len([x for x in all_content if x["source"] == "arxiv"]),
            "github": len([x for x in all_content if x["source"] == "github"]),
            "huggingface": len([x for x in all_content if x["source"] == "huggingface"])
        },
        "items": all_content
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Collection complete: {len(all_content)} items saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
