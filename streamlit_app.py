"""
AI新闻聚合 - Day 4: 前端展示层
读取summarized_news.json,展示成网页
运行: pip install streamlit --break-system-packages
      streamlit run streamlit_app.py
"""

import json
import streamlit as st
from datetime import datetime

st.set_page_config(
    page_title="Daily AI Signal",
    page_icon="📡",
    layout="wide",
)


@st.cache_data(ttl=300)  # 缓存5分钟,避免每次交互都重新读文件
def load_news():
    try:
        with open("summarized_news.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def main():
    st.title("📡 Daily AI Signal")
    st.caption("每日AI科技资讯中文摘要 · 数据来源: Hacker News + 官方博客")

    news = load_news()

    if not news:
        st.warning("还没有数据,先跑一遍 `python3 summarize.py` 生成 summarized_news.json")
        return

    # 只展示有摘要的条目(过滤掉总结失败的None)
    valid_news = [item for item in news if item.get("summary_zh")]

    # 侧边栏筛选
    all_sources = sorted(set(item["source"] for item in valid_news))
    with st.sidebar:
        st.header("筛选")
        selected_sources = st.multiselect(
            "信息源", options=all_sources, default=all_sources
        )
        st.divider()
        st.metric("当前展示条数", len(valid_news))
        if news:
            st.caption(f"最后更新: {news[0].get('fetched_at', '未知')[:16]}")

    filtered = [item for item in valid_news if item["source"] in selected_sources]

    if not filtered:
        st.info("没有符合筛选条件的内容,试试调整左侧的信息源筛选")
        return

    # 按来源分组展示,而不是纯按score排序
    # (score排序会导致RSS内容全部被HN挤到最后,因为RSS条目score固定是0)
    for source in selected_sources:
        source_items = [item for item in filtered if item["source"] == source]
        if not source_items:
            continue

        st.subheader(source)
        for item in source_items:
            with st.container(border=True):
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(f"**[{item['title']}]({item['url']})**")
                    st.write(item["summary_zh"])
                with col2:
                    if item.get("score", 0) > 0:
                        st.metric("热度", item["score"])
        st.divider()


if __name__ == "__main__":
    main()