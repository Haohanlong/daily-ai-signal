"""
AI新闻聚合 - 分类打标层
读取summarized_news.json,给每条新闻分配1个话题标签,用于前端的个性化"调频"筛选。
运行: python3 classify.py

需要在.env里配置(与summarize.py共用):
GEMINI_API_KEY=你的key
"""

import os
import json
import time
from dotenv import load_dotenv
from google import genai

load_dotenv()

SECONDS_BETWEEN_CALLS = 13
MODEL = "gemini-3.1-flash-lite"

INPUT_PATH = "summarized_news.json"
CACHE_PATH = "classify_cache.json"
OUTPUT_PATH = "web/data.json"

# 受众标签体系:一条新闻可能同时对多种人有价值,所以每条最多打1-3个标签
PERSONAS = {
    "founder": "创业者",       # 融资、商业化、行业格局、战略决策
    "student": "学生",         # 想扩充AI行业见识、当泛知识积累的人(不局限于纯入门内容)
    "creator": "内容创作者",    # 有话题性、传播性,适合做内容素材
    "developer": "程序员",     # 技术细节、开源项目、API、开发工具
}

DEFAULT_PERSONAS = ["student"]

client = genai.Client()


def load_json(path: str, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_prompt(item: dict) -> str:
    return f"""你是一个AI科技新闻编辑,服务对象是可能无法访问海外原文链接的中文读者,
所以除了打标签,还要替他们把"这条新闻到底意味着什么"讲清楚,不依赖点开原文。

请判断下面这条新闻对哪些受众有价值(1-3个),并给每个选中的受众各写一句话(20-40字),
说清楚"这条新闻对这类人具体意味着什么/该怎么用这个信息",不要重复标题,要说人话不要翻译腔。

可选受众:
- founder: 创业者(融资、商业化、行业格局、战略决策相关)
- student: 学生(不局限于纯入门内容——只要是"了解这个行业在发生什么、值得当见识积累"的新闻都算,包括技术突破、产品动态、行业格局变化,门槛应该偏低)
- creator: 内容创作者(有话题性/传播性,适合做成短视频或社交媒体内容)
- developer: 程序员(技术细节、开源项目、API、开发工具相关)

标题: {item['title']}
摘要: {item.get('summary_zh', '')}

严格按下面的JSON格式返回,不要任何多余文字、不要markdown代码块标记:
{{"personas": ["key1", "key2"], "takeaways": {{"key1": "一句话说明", "key2": "一句话说明"}}}}"""


def classify_item(item: dict, retry: bool = True) -> dict:
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=build_prompt(item),
        )
        raw = response.text.strip()
        # 防御性处理: 万一模型还是包了markdown代码块
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(raw)
        keys = [k for k in parsed.get("personas", []) if k in PERSONAS][:3]
        if not keys:
            keys = DEFAULT_PERSONAS
        takeaways = {k: v for k, v in parsed.get("takeaways", {}).items() if k in keys}
        return {"personas": keys, "takeaways": takeaways}
    except Exception as e:
        err_str = str(e)
        if retry and ("429" in err_str or "503" in err_str):
            print("  触发限流,等待20秒后重试...")
            time.sleep(20)
            return classify_item(item, retry=False)
        print(f"  分类失败,回退到默认标签: {e}")
        return {"personas": DEFAULT_PERSONAS, "takeaways": {}}


def main():
    news = load_json(INPUT_PATH, [])
    if not news:
        print(f"没有找到 {INPUT_PATH},先跑 python3 summarize.py")
        return

    cache = load_json(CACHE_PATH, {})
    new_count = 0

    for i, item in enumerate(news, 1):
        url = item["url"]
        if url in cache:
            item["personas"] = cache[url]["personas"]
            item["takeaways"] = cache[url]["takeaways"]
            continue

        new_count += 1
        print(f"[{i}/{len(news)}] 分类中: {item['title'][:50]}...")
        result = classify_item(item)
        item["personas"] = result["personas"]
        item["takeaways"] = result["takeaways"]
        cache[url] = result
        save_json(CACHE_PATH, cache)
        time.sleep(SECONDS_BETWEEN_CALLS)

    # 给所有条目补上中文标签(包括缓存命中的)
    for item in news:
        item["persona_labels"] = [PERSONAS.get(p, "学生") for p in item.get("personas", DEFAULT_PERSONAS)]

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    save_json(OUTPUT_PATH, news)
    print(f"\n完成: 本次新分类 {new_count} 条,结果存到 {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
