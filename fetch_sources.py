"""
AI新闻聚合 - Day 1: 抓取层
覆盖: Hacker News + Reddit(公开json) + RSS
运行: pip install requests feedparser --break-system-packages
      python fetch_sources.py
"""

import re
import os
import ssl
import requests
import feedparser
import time
from datetime import datetime
from dotenv import load_dotenv
import praw

load_dotenv()  # 从.env文件读取REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET

try:
    import certifi
    # 兜底: 强制用certifi自带的证书库,绕过macOS系统证书配置不全的问题
    ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())
except ImportError:
    print("提示: 建议 pip install certifi 以修复可能的SSL证书问题")

# ---------- 配置区 ----------

AI_KEYWORDS = [
    "ai", "llm", "gpt", "claude", "gemini", "openai", "anthropic",
    "machine learning", "neural", "deepseek", "transformer", "agent"
]

# 预编译成"单词边界"正则，避免"ai"匹配到"air"/"explained"/"remains"这种子串误判
_AI_PATTERNS = [re.compile(r"\b" + re.escape(k) + r"\b", re.IGNORECASE) for k in AI_KEYWORDS]

SUBREDDITS = ["MachineLearning", "LocalLLaMA", "artificial"]

# 初始化Reddit官方API客户端(需要在.env里配置client_id和secret)
_reddit_client = None

def get_reddit_client():
    global _reddit_client
    if _reddit_client is None:
        client_id = os.getenv("REDDIT_CLIENT_ID")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise RuntimeError(
                "缺少REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET,请检查.env文件是否配置正确"
            )
        _reddit_client = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent="ai-news-mvp/0.1 (personal project)",
        )
    return _reddit_client

RSS_FEEDS = {
    "OpenAI Blog": "https://openai.com/news/rss.xml",
    "Anthropic News": "https://www.anthropic.com/news/rss.xml",
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "Google AI Blog": "https://blog.google/technology/ai/rss/",
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
}

# 用更接近真实浏览器的UA，公开json接口对"一看就是脚本"的UA更容易403
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}


# ---------- 数据结构 ----------
# 每条新闻统一成: {title, url, source, summary_raw, score, fetched_at}

def is_ai_related(text: str) -> bool:
    return any(p.search(text) for p in _AI_PATTERNS)


# ---------- 抓取: Hacker News ----------

def fetch_hackernews(hits_per_keyword=15):
    """
    改用HN官方的Algolia搜索API,按关键词直接搜索最近的story,
    服务端过滤,一个关键词一次请求,远比逐条拉取100个item快很多。
    """
    items = []
    # 用几个覆盖面广的关键词去搜,别把AI_KEYWORDS全塞进去(太碎的词比如"agent"搜出来噪音大)
    search_terms = ["AI", "LLM", "GPT", "Claude", "Gemini", "OpenAI", "Anthropic", "DeepSeek"]

    for term in search_terms:
        try:
            resp = requests.get(
                "https://hn.algolia.com/api/v1/search_by_date",
                params={"tags": "story", "query": term, "hitsPerPage": hits_per_keyword},
                headers=HEADERS,
                timeout=15,
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
        except Exception as e:
            print(f"[HN] 关键词'{term}'搜索失败: {e}")
            continue

        for hit in hits:
            title = hit.get("title")
            if not title:
                continue
            items.append({
                "title": title,
                "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                "source": "Hacker News",
                "summary_raw": "",
                "score": hit.get("points", 0),
                "fetched_at": datetime.now().isoformat(),
            })

    return items


# ---------- 抓取: Reddit (公开json,无需API key) ----------

def fetch_reddit(subreddit, limit=25):
    items = []
    try:
        reddit = get_reddit_client()
        for post in reddit.subreddit(subreddit).hot(limit=limit):
            items.append({
                "title": post.title,
                "url": f"https://reddit.com{post.permalink}",
                "source": f"r/{subreddit}",
                "summary_raw": (post.selftext or "")[:500],
                "score": post.score,
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
        if feed.bozo:
            # bozo=1 说明解析时遇到问题(链接失效/格式错误/被重定向到非法内容等)
            print(f"[RSS {name}] 解析异常: {feed.bozo_exception}")
        entries = feed.entries[:20]
        print(f"[RSS {name}] 抓到 {len(entries)} 条")
        for entry in entries:
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

    # Reddit v1暂时砍掉: Reddit在2026年把API注册改成了审批制(Responsible Builder Policy),
    # 提交申请要排队审核,时间不可控,不适合一周MVP的节奏。
    # 等审批通过后,把下面这段取消注释即可重新启用。
    #
    # for sub in SUBREDDITS:
    #     print(f"抓取 r/{sub}...")
    #     all_items += fetch_reddit(sub)
    #     time.sleep(1)

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