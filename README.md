# Daily AI Signal

面向中文读者的AI科技资讯每日精选。

## 这是什么

每天自动抓取 Hacker News 与几个权威英文AI资讯源（OpenAI Blog、TechCrunch AI、Google AI Blog、Hugging Face Blog、VentureBeat AI），用大模型生成简体中文摘要，产出一份可以在几分钟内读完的每日AI资讯精选。

## 为什么做这个

英文AI资讯赛道已经非常拥挤（TLDR AI、The Rundown、Superhuman AI 等头部newsletter订阅数都在百万级别，甚至已经出现专门帮你去重整合多个newsletter的meta产品）。直接在英文市场里做内容聚合，没有任何护城河。

但目前没有一个产品做**中文输出、面向中文读者**的AI资讯聚合——这是一个真实存在、暂时没人占的位置，也恰好是我自己的天然优势（中文社群 + 中西加英四语能力）。

这个项目首先是我的第一个完整开发并上线的软件项目，其次才是一次关于"内容聚合能不能找到差异化定位"的真实市场验证。

## MVP做什么

- 抓取：Hacker News（Algolia搜索API，按AI相关关键词）+ 5个英文AI资讯RSS源
- 去重：跨源去重，避免同一条新闻重复出现
- 精选：每个来源分摊配额，每天精选约15条（对齐LLM免费层每日请求上限）
- 中文摘要：用Gemini生成2-3句话的中文摘要，说清楚"发生了什么"和"为什么值得关注"
- 展示：Streamlit网页，按来源分组展示，支持筛选

## MVP不做什么（先不做,不代表以后不做）

- 不做英文原创内容/编辑评论,先做"信息压缩+翻译"这一层最基础的价值
- 不做用户账号系统、订阅推送,先验证"这份内容本身有没有人愿意看"
- 不做Twitter/X数据源(API访问已被官方锁死,审批制,不确定性太高)
- 不做Reddit数据源(2026年起API改为审批制,同上)

## 技术栈

- Python 3.12
- 抓取: requests + feedparser (RSS) + Hacker News Algolia API
- 总结: Gemini API (gemini-3.1-flash-lite)
- 展示: Streamlit
- 部署: Streamlit Community Cloud

## 当前状态

- [x] 抓取层跑通(HN + RSS)
- [x] 去重逻辑
- [x] LLM中文摘要跑通,带本地缓存避免重复消耗配额
- [x] Streamlit前端本地跑通
- [ ] 部署上线
- [ ] 社交媒体(小红书)发布,收集第一批真实反馈

## 一条原则

这个仓库永远不删,即使以后方向调整或重做。这是第一个完整做完的项目,过程比结果更值得留档。