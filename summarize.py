"""
AI新闻聚合 - Day 3: LLM总结层
把fetch_sources.py抓到的内容,逐条丢给Gemini生成中文摘要
运行: pip install google-genai --break-system-packages
      python summarize.py

需要在.env里配置:
GEMINI_API_KEY=你的key (在 https://aistudio.google.com/app/apikey 免费获取)
"""

import os
import json
import time
from dotenv import load_dotenv
from google import genai

from fetch_sources import collect_all

load_dotenv()

# 免费层实测限速是每分钟5次(比官方文档写的更严格),按这个来算安全间隔
SECONDS_BETWEEN_CALLS = 13

# 处理全部条目,不再限制测试数量(缓存机制会避免重复消耗配额)
MODEL = "gemini-3.1-flash-lite"  # 摘要这种提取型任务用不着3.5 Flash,3.1-flash-lite便宜6倍且是当前世代(新账号能用)

CACHE_PATH = "summary_cache.json"
OUTPUT_PATH = "summarized_news.json"

client = genai.Client()  # 自动从环境变量GEMINI_API_KEY读取


def select_daily_picks(news: list, max_items: int = 15) -> list:
    """
    Gemini免费层每天只有20次请求的硬上限,所以不能全量总结172条。
    改成每个来源挑几条,凑成一份"每日精选",这也更符合日报产品的形态
    (没人想看172条新闻,想看的是当天最重要的十几条)。
    """
    by_source = {}
    for item in news:
        by_source.setdefault(item["source"], []).append(item)

    picks = []
    sources = list(by_source.keys())
    per_source_cap = max(1, max_items // len(sources)) if sources else 0

    for source in sources:
        # HN按score排序取最热的,RSS按原顺序(通常是最新的)取前几条
        items = sorted(by_source[source], key=lambda x: x.get("score", 0), reverse=True)
        picks.extend(items[:per_source_cap])

    return picks[:max_items]


def load_cache() -> dict:
    """缓存以url为key,存过的url不再重复调用API,避免每次跑demo都重新烧配额"""
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def build_prompt(item: dict) -> str:
    context = item["title"]
    if item.get("summary_raw"):
        context += f"\n\n补充信息: {item['summary_raw'][:300]}"

    return f"""你是一个AI科技新闻编辑,请用简体中文把下面这条新闻总结成2-3句话,
要求: 说清楚"发生了什么"和"为什么值得关注",语气客观简洁,不要用"本文/该文章"这类翻译腔。

标题: {context}
"""


def summarize_item(item: dict, retry: bool = True) -> str | None:
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=build_prompt(item),
        )
        return response.text.strip()
    except Exception as e:
        err_str = str(e)
        if retry and ("429" in err_str or "503" in err_str):
            print("  触发限流/服务繁忙,多等20秒后重试一次...")
            time.sleep(20)
            return summarize_item(item, retry=False)
        print(f"  总结失败: {e}")
        return None


def main():
    print("抓取原始数据...")
    news = collect_all()
    print(f"共抓到 {len(news)} 条\n")

    cache = load_cache()

    # 免费层每天20次请求硬上限,只精选一批做总结(15条,留点余量)
    daily_picks = select_daily_picks(news, max_items=15)
    print(f"本次精选 {len(daily_picks)} 条进行总结(免费层每日限额20次)\n")

    new_count = 0
    for i, item in enumerate(daily_picks, 1):
        url = item["url"]
        if url in cache:
            item["summary_zh"] = cache[url]
            continue

        new_count += 1
        print(f"[{i}/{len(daily_picks)}] 新条目,总结中: {item['title'][:50]}...")
        summary = summarize_item(item)
        item["summary_zh"] = summary
        cache[url] = summary
        save_cache(cache)  # 每条都存一次,中途中断也不丢进度
        if summary is None:
            print("  配额可能已耗尽,今天先跑到这里,明天配额重置后继续")
            break
        time.sleep(SECONDS_BETWEEN_CALLS)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(daily_picks, f, ensure_ascii=False, indent=2)

    print(f"\n完成: 本次新总结 {new_count} 条,缓存命中 {len(daily_picks) - new_count} 条")
    print(f"结果存到 {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
    