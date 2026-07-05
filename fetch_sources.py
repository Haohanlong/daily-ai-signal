"""
AI新闻聚合 - Day 1: 抓取层
覆盖: Hacker News + Reddit(公开json) + RSS
运行: pip install requests feedparser --break-system-packages
      python fetch_sources.py
"""

import requests
import feedparser
import time
from datetime import datetime

# ---------- 配置区 ----------

AI_KEYWORDS = [
    "ai", "llm", "gpt", "claude", "gemini", "openai", "anthropic",
    "machine learning", "neural", "deepseek", "transformer", "agent"
]

SUBREDDITS = ["MachineLearning", "LocalLLaMA", "artificial"]

RSS_FEEDS = {
    "OpenAI Blog": "https://openai.com/news/rss.xml",
    "Anthropic News": "https://www.anthropic.com/news/rss.xml",
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
}

HEADERS = {"User-Agent": "ai-news-mvp/0.1 (personal project)"}


# ---------- 数据结构 ----------
# 每条新闻统一成: {title, url, source, summary_raw, score, fetched_at}

def is_ai_related(text: str) -> bool:
    text = text.lower()
    return any(k in text for k in AI_KEYWORDS)


# ---------- 抓取: Hacker News ----------

def fetch_hackernews(limit=100):
    items = []
    try:
        top_ids = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            headers=HEADERS, timeout=10
        ).json()[:limit]

        for story_id in top_ids:
            story = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                headers=HEADERS, timeout=10
            ).json()
            if not story or "title" not in story:
                continue
            if is_ai_related(story["title"]):
                items.append({
                    "title": story["title"],
                    "url": story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                    "source": "Hacker News",
                    "summary_raw": "",
                    "score": story.get("score", 0),
                    "fetched_at": datetime.now().isoformat(),
                })
    except Exception as e:
        print(f"[HN] 抓取失败: {e}")
    return items


# ---------- 抓取: Reddit (公开json,无需API key) ----------

def fetch_reddit(subreddit, limit=25):
    items = []
    try:
        url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        for post in data["data"]["children"]:
            d = post["data"]
            items.append({
                "title": d["title"],
                "url": f"https://reddit.com{d['permalink']}",
                "source": f"r/{subreddit}",
                "summary_raw": d.get("selftext", "")[:500],
                "score": d.get("score", 0),
                "fetched_at": datetime.now().isoformat(),
            })
    except Exception as e:
        print(f"[Reddit r/{subreddit}] 抓取失败: {e}")
    return items


# ---------- 抓取: RSS ----------

def fetch_rss(name, url):
    items = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:20]:
            items.append({
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "source": name,
                "summary_raw": entry.get("summary", "")[:500],
                "score": 0,
                "fetched_at": datetime.now().isoformat(),
            })
    except Exception as e:
        print(f"[RSS {name}] 抓取失败: {e}")
    return items


# ---------- 去重 ----------

def dedupe(items):
    seen_titles = set()
    result = []
    for item in items:
        key = item["title"].strip().lower()[:60]
        if key in seen_titles:
            continue
        seen_titles.add(key)
        result.append(item)
    return result


# ---------- 主流程 ----------

def collect_all():
    all_items = []

    print("抓取 Hacker News...")
    all_items += fetch_hackernews()

    for sub in SUBREDDITS:
        print(f"抓取 r/{sub}...")
        all_items += fetch_reddit(sub)
        time.sleep(1)  # 对reddit礼貌一点,避免被限流

    for name, url in RSS_FEEDS.items():
        print(f"抓取 {name}...")
        all_items += fetch_rss(name, url)

    all_items = dedupe(all_items)
    all_items.sort(key=lambda x: x["score"], reverse=True)

    return all_items


if __name__ == "__main__":
    news = collect_all()
    print(f"\n共抓到 {len(news)} 条AI相关内容\n")
    for item in news[:15]:
        print(f"[{item['source']}] {item['title']}")
        print(f"  {item['url']}\n")