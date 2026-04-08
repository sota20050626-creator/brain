"""
collector.py - AI情報収集エージェント
ソース: Reddit, HackerNews, ArXiv, GitHub Search API, X（日曜のみ）
"""

import json
import os
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

TODAY = datetime.now().strftime("%Y-%m-%d")
WEEKDAY = datetime.now().weekday()
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

X_SEARCH_QUERIES = [
    "AI LLM lang:ja -is:retweet",
    "ChatGPT Claude Gemini lang:en -is:retweet",
    "artificial intelligence breakthrough lang:en -is:retweet",
]

X_NOTABLE_ACCOUNTS = [
    "sama",
    "ylecun",
    "karpathy",
    "demishassabis",
    "goodfellow_ian",
]


def get_reddit_token():
    client_id = os.environ.get("REDDIT_CLIENT_ID", "")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        print("Reddit credentials not set, skipping Reddit")
        return None
    import base64
    encoded = base64.b64encode(
        (client_id + ":" + client_secret).encode()
    ).decode()
    data = urllib.parse.urlencode(
        {"grant_type": "client_credentials"}
    ).encode()
    req = urllib.request.Request(
        "https://www.reddit.com/api/v1/access_token",
        data=data,
        headers={
            "Authorization": "Basic " + encoded,
            "User-Agent": "Brain/1.0"
        }
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())["access_token"]
    except Exception as e:
        print("Reddit auth failed: " + str(e))
        return None


def fetch_reddit(token, subreddit, limit=10):
    if not token:
        return []
    req = urllib.request.Request(
        "https://oauth.reddit.com/r/" + subreddit + "/hot?limit=" + str(limit),
        headers={
            "Authorization": "Bearer " + token,
            "User-Agent": "Brain/1.0"
        }
    )
    try:
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read())
        posts = []
        for child in data["data"]["children"]:
            p = child["data"]
            if p.get("score", 0) < 100:
                continue
            posts.append({
                "title": p["title"],
                "url": p.get("url", ""),
                "score": p.get("score", 0),
                "comments": p.get("num_comments", 0),
                "source": "reddit/r/" + subreddit,
                "text": p.get("selftext", "")[:500],
            })
        return posts
    except Exception as e:
        print("Reddit fetch error: " + str(e))
        return []


def fetch_hackernews(limit=30):
    try:
        req = urllib.request.Request(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            headers={"User-Agent": "Brain/1.0"}
        )
        with urllib.request.urlopen(req) as r:
            story_ids = json.loads(r.read())[:100]
        posts = []
        for sid in story_ids:
            if len(posts) >= limit:
                break
            try:
                with urllib.request.urlopen(
                    "https://hacker-news.firebaseio.com/v0/item/" + str(sid) + ".json"
                ) as r:
                    item = json.loads(r.read())
                title = item.get("title", "").lower()
                if any(kw in title for kw in AI_KEYWORDS):
                    posts.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", "https://news.ycombinator.com/item?id=" + str(sid)),
                        "score": item.get("score", 0),
                        "comments": item.get("descendants", 0),
                        "source": "hackernews",
                        "text": "",
                    })
                time.sleep(0.05)
            except Exception:
                continue
        return posts
    except Exception as e:
        print("HackerNews error: " + str(e))
        return []


def fetch_arxiv(limit=10):
    query = urllib.parse.quote("cat:cs.AI OR cat:cs.LG OR cat:cs.CL")
    url = (
        "https://export.arxiv.org/api/query?search_query=" + query
        + "&sortBy=submittedDate&sortOrder=descending&max_results=" + str(limit)
    )
    try:
        with urllib.request.urlopen(url) as r:
            content = r.read().decode()
        entries = re.findall(r"<entry>(.*?)</entry>", content, re.DOTALL)
        papers = []
        for entry in entries:
            title = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
            summary = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
            link = re.search(r"<id>(.*?)</id>", entry)
            if title and summary:
                papers.append({
                    "title": title.group(1).strip().replace("\n", " "),
                    "url": link.group(1).strip() if link else "",
                    "score": 0,
                    "comments": 0,
                    "source": "arxiv",
                    "text": summary.group(1).strip()[:500].replace("\n", " "),
                })
        return papers
    except Exception as e:
        print("ArXiv error: " + str(e))
        return []


def fetch_github_trending(limit=10):
    results = []
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    queries = [
        "topic:llm pushed:>" + yesterday,
        "topic:ai pushed:>" + yesterday,
        "machine-learning stars:>100 pushed:>" + yesterday,
    ]

    for query in queries:
        try:
            encoded = urllib.parse.quote(query)
            url = (
                "https://api.github.com/search/repositories?q=" + encoded
                + "&sort=stars&order=desc&per_page=5"
            )
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Brain/1.0",
                    "Accept": "application/vnd.github.v3+json",
                }
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())

            for item in data.get("items", []):
                desc = item.get("description") or ""
                results.append({
                    "title": item["full_name"] + " - " + desc,
                    "url": item["html_url"],
                    "score": item.get("stargazers_count", 0),
                    "comments": 0,
                    "source": "github_trending",
                    "text": desc,
                })

            time.sleep(2)

        except Exception as e:
            print("GitHub API error: " + str(e))

    seen = set()
    unique = []
    for item in results:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)

    return unique[:limit]


def fetch_x_weekly(limit=20):
    """X情報収集（毎週日曜のみ実行）"""
    api_key = os.environ.get("TWITTER_API_KEY", "")
    api_secret = os.environ.get("TWITTER_API_SECRET", "")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN", "")
    access_secret = os.environ.get("TWITTER_ACCESS_SECRET", "")

    if not all([api_key, api_secret, access_token, access_secret]):
        print("  X API credentials not set, skipping X collection")
        return []

    # Bearer Tokenを取得
    import base64
    credentials = base64.b64encode(
        (urllib.parse.quote(api_key) + ":" + urllib.parse.quote(api_secret)).encode()
    ).decode()

    try:
        token_req = urllib.request.Request(
            "https://api.twitter.com/oauth2/token",
            data=b"grant_type=client_credentials",
            headers={
                "Authorization": "Basic " + credentials,
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )
        with urllib.request.urlopen(token_req) as r:
            bearer_token = json.loads(r.read())["access_token"]
    except Exception as e:
        print("  X Bearer Token取得エラー: " + str(e))
        return []

    results = []
    seen_ids = set()

    # キーワード検索
    for query in X_SEARCH_QUERIES[:2]:
        try:
            encoded_query = urllib.parse.quote(query)
            url = (
                "https://api.twitter.com/2/tweets/search/recent"
                "?query=" + encoded_query
                + "&max_results=10"
                + "&tweet.fields=public_metrics,created_at"
                + "&expansions=author_id"
                + "&user.fields=username,name"
            )
            req = urllib.request.Request(
                url,
                headers={"Authorization": "Bearer " + bearer_token}
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())

            users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

            for tweet in data.get("data", []):
                tweet_id = tweet["id"]
                if tweet_id in seen_ids:
                    continue
                seen_ids.add(tweet_id)

                author = users.get(tweet.get("author_id", ""), {})
                username = author.get("username", "unknown")
                metrics = tweet.get("public_metrics", {})
                score = metrics.get("like_count", 0) + metrics.get("retweet_count", 0) * 2

                results.append({
                    "title": tweet["text"][:100],
                    "url": "https://x.com/" + username + "/status/" + tweet_id,
                    "score": score,
                    "comments": metrics.get("reply_count", 0),
                    "source": "x_weekly",
                    "text": tweet["text"][:500],
                })

            time.sleep(2)

        except Exception as e:
            print("  X検索エラー: " + str(e))

    # 著名アカウントの投稿収集
    for username in X_NOTABLE_ACCOUNTS[:3]:
        try:
            url = (
                "https://api.twitter.com/2/tweets/search/recent"
                "?query=from:" + username + " -is:retweet"
                + "&max_results=5"
                + "&tweet.fields=public_metrics,created_at"
            )
            req = urllib.request.Request(
                url,
                headers={"Authorization": "Bearer " + bearer_token}
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())

            for tweet in data.get("data", []):
                tweet_id = tweet["id"]
                if tweet_id in seen_ids:
                    continue
                seen_ids.add(tweet_id)

                metrics = tweet.get("public_metrics", {})
                score = metrics.get("like_count", 0) + metrics.get("retweet_count", 0) * 2

                results.append({
                    "title": "@" + username + ": " + tweet["text"][:80],
                    "url": "https://x.com/" + username + "/status/" + tweet_id,
                    "score": score,
                    "comments": metrics.get("reply_count", 0),
                    "source": "x_weekly",
                    "text": tweet["text"][:500],
                })

            time.sleep(2)

        except Exception as e:
            print("  X著名アカウント取得エラー (" + username + "): " + str(e))

    results.sort(key=lambda x: x["score"], reverse=True)
    print("  X Weekly: " + str(len(results)) + " tweets")
    return results[:limit]


def main():
    print("Brain Collector starting... [" + TODAY + "] (weekday=" + str(WEEKDAY) + ")")

    all_items = []

    # Reddit
    token = get_reddit_token()
    for sub in REDDIT_SUBREDDITS:
        items = fetch_reddit(token, sub)
        all_items.extend(items)
        print("  Reddit r/" + sub + ": " + str(len(items)) + " posts")
        time.sleep(0.5)

    # HackerNews
    hn_items = fetch_hackernews()
    all_items.extend(hn_items)
    print("  HackerNews: " + str(len(hn_items)) + " posts")

    # ArXiv
    arxiv_items = fetch_arxiv()
    all_items.extend(arxiv_items)
    print("  ArXiv: " + str(len(arxiv_items)) + " papers")

    # GitHub Trending
    github_items = fetch_github_trending()
    all_items.extend(github_items)
    print("  GitHub Trending: " + str(len(github_items)) + " repos")

    # X（日曜のみ: weekday=6）
    if WEEKDAY == 6:
        print("  日曜日のためX収集を実行...")
        x_items = fetch_x_weekly()
        all_items.extend(x_items)
    else:
        print("  X収集は日曜のみ実行 (今日はweekday=" + str(WEEKDAY) + ")")

    # 重複除去
    seen_urls = set()
    unique_items = []
    for item in all_items:
        if item["url"] not in seen_urls:
            seen_urls.add(item["url"])
            unique_items.append(item)

    result = {
        "date": TODAY,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "total": len(unique_items),
        "raw_items": unique_items,
        "summary": None,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("Collected " + str(len(unique_items)) + " items -> " + str(OUTPUT_FILE))


if __name__ == "__main__":
    main()
