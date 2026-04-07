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
    for lang in ["", "python"]:
        url = "https://github.com/trending/" + lang + "?since=daily"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; Brain/1.0)"}
            )
            with urllib.request.urlopen(req) as r:
                html = r.read().decode("utf-8", errors="ignore")

            repos = re.findall(
                r'<h2[^>]*>\s*<a\s+href="(/[^"]+)"[^>]*>(.*?)</a>',
                html, re.DOTALL
            )
            descs = re.findall(
                r'<p\s+class="col-9[^"]*"[^>]*>\s*(.*?)\s*</p>',
                html, re.DOTALL
            )
            stars = re.findall(
                r'aria-label="[^"]*stars[^"]*"[^>]*>\s*([\d,]+)',
                html
            )

            for i, (path, name) in enumerate(repos[:limit]):
                repo_name = re.sub(r"\s+", "", name.strip())
                desc = descs[i].strip() if i < len(descs) else ""
                desc = re.sub(r"<[^>]+>", "", desc).strip()
                star_count = stars[i].replace(",", "") if i < len(stars) else "0"

                results.append({
                    "title": repo_name + " - " + desc if desc else repo_name,
                    "url": "https://github.com" + path.strip(),
                    "score": int(star_count) if star_count.isdigit() else 0,
                    "comments": 0,
                    "source": "github_trending",
                    "text": desc,
                })

            time.sleep(1)

        except Exception as e:
            print("GitHub Trending error (" + lang + "): " + str(e))

    seen = set()
    unique = []
    for item in results:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)

    return unique[:limit]


def main():
    print("Brain Collector starting... [" + TODAY + "]")

    all_items = []

    token = get_reddit_token()
    for sub in REDDIT_SUBREDDITS:
        items = fetch_reddit(token, sub)
        all_items.extend(items)
        print("  Reddit r/" + sub + ": " + str(len(items)) + " posts")
        time.sleep(0.5)

    hn_items = fetch_hackernews()
    all_items.extend(hn_items)
    print("  HackerNews: " + str(len(hn_items)) + " posts")

    arxiv_items = fetch_arxiv()
    all_items.extend(arxiv_items)
    print("  ArXiv: " + str(len(arxiv_items)) + " papers")

    github_items = fetch_github_trending()
    all_items.extend(github_items)
    print("  GitHub Trending: " + str(len(github_items)) + " repos")

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

    print("Collected " + str(len(unique_items)) + " unique items -> " + str(OUTPUT_FILE))


if __name__ == "__main__":
    main()
