# 个人资讯获取平台 · 设计文档

**日期**：2026-06-08  
**域名**：news.daichao.fun  
**技术栈**：Python 3.11 / FastAPI / SQLite / Jinja2 / Tailwind / HTMX  
**架构方案**：简单单体 + 系统 cron（方案一）

---

## 1. 目标与约束

- 单用户，简单密码保护，不对外开放注册
- 每天定时抓取三类资讯，AI 加工后展示；重点条目推送飞书
- **可扩展性硬要求**：新增类别或信息源只改 `config.yaml`，不改代码
- 三类资讯均由新平台独立抓取，不依赖现有 CoWork 流程
- 中文无 RSS 站点通过自建 RSSHub 接入

---

## 2. 整体架构

### 请求流（Web）

```
浏览器 → Nginx(news.daichao.fun, SSL) → FastAPI:8000 → SQLite
```

### 抓取流（Cron）

```
cron → python -m app.run --slot morning --category all
         └─ pipeline.py
              ├─ 读 config.yaml → 取当前 slot 下所有 enabled source
              ├─ 并发调用对应 fetcher（asyncio.gather）
              ├─ dedup（sha256(url.strip().lower())，查近7天）
              ├─ 按 category.depth_level 调 ai/processor.py
              ├─ 写入 SQLite（item 表）
              ├─ 写 run_log
              └─ 时段末：汇总 is_key 条目 → feishu.py → 写 push_log
```

### 部署

```
docker-compose.yml:
  app:    127.0.0.1:8000 → FastAPI
  rsshub: 127.0.0.1:1200 → RSSHub（自建，中文源转 RSS）

Nginx: SSL 终止（Let's Encrypt），反向代理到 :8000

cron（服务器）:
  0 9  * * * python -m app.run --slot morning --category all
  0 19 * * * python -m app.run --slot evening --category banking
```

---

## 3. 项目目录结构

```
news-platform/
├── app/
│   ├── main.py              # FastAPI 入口，挂载路由
│   ├── run.py               # CLI 入口
│   ├── config.py            # 读取 config.yaml → Settings 对象
│   ├── models/
│   │   ├── base.py          # SQLAlchemy Base + engine + session
│   │   ├── category.py
│   │   ├── source.py
│   │   ├── item.py
│   │   ├── push_log.py
│   │   └── run_log.py
│   ├── fetchers/
│   │   ├── base.py          # 抽象 BaseFetcher → list[RawItem]
│   │   ├── rss.py           # feedparser，覆盖 RSS + RSSHub 源
│   │   ├── api_github.py    # GitHub Trending / Search API
│   │   ├── api_hn.py        # Hacker News Firebase API
│   │   ├── api_producthunt.py
│   │   ├── api_huggingface.py
│   │   └── scraper.py       # playwright，动态页面兜底
│   ├── ai/
│   │   ├── client.py        # Anthropic SDK 封装，统一调用入口
│   │   ├── processor.py     # 按 depth_level 路由到对应处理器
│   │   ├── banking.py       # 类1：摘要+打分+工作影响（score≥7触发）
│   │   ├── tech.py          # 类2：摘要+上升速度+相关度打分
│   │   └── startup.py       # 类3：结构化建议（适合度/AI做法/变现/切入）
│   ├── push/
│   │   └── feishu.py        # 飞书 webhook，时段汇总卡片
│   ├── web/
│   │   ├── routes/
│   │   │   ├── auth.py      # 密码登录，itsdangerous 签名 cookie
│   │   │   ├── home.py
│   │   │   ├── category.py
│   │   │   ├── search.py
│   │   │   ├── archive.py
│   │   │   ├── report.py    # 晨报/晚报视图
│   │   │   └── admin.py     # 来源管理页
│   │   └── templates/       # Jinja2 模板 + Tailwind
│   └── scheduler/
│       └── pipeline.py      # fetch→dedup→ai→save→push 主流程
├── config.yaml
├── .env                     # 不提交 git
├── docker-compose.yml
├── Dockerfile
├── crontab.example
└── tests/
    ├── test_fetchers.py
    ├── test_ai.py           # dry-run 模式
    └── test_pipeline.py
```

---

## 4. 数据模型

### category
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | |
| name | TEXT | 银行用户运营 |
| slug | TEXT UNIQUE | banking |
| depth_level | TEXT | light / medium / medium_deep / deep |
| schedule | JSON | ["morning", "evening"] |
| enabled | BOOL | |

### source
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | |
| category_slug | TEXT FK | |
| name | TEXT | |
| homepage | TEXT | |
| fetch_type | TEXT | rss / api_github / api_hn / api_ph / api_hf / scraper |
| feed_url | TEXT | RSS地址或API endpoint |
| enabled | BOOL | |
| extra | JSON | 扩展参数 |

### item
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | |
| source_id | INT FK | |
| category_slug | TEXT | |
| title | TEXT | |
| url | TEXT UNIQUE | |
| raw_text | TEXT | 原始正文（可空） |
| summary_zh | TEXT | AI 中文摘要 |
| score | FLOAT | 0-10 |
| is_key | BOOL | 重点标记，触发飞书推送 |
| ai_extra | JSON | 类3结构化建议 / 类1工作影响 |
| published_at | DATETIME | |
| fetched_at | DATETIME | |
| dedup_hash | TEXT UNIQUE | sha256(url.strip().lower()) |
| is_read | BOOL DEFAULT FALSE | |
| is_saved | BOOL DEFAULT FALSE | |

### push_log
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | |
| slot | TEXT | morning / evening |
| category_slug | TEXT | |
| pushed_at | DATETIME | |
| item_ids | JSON | 已推送的 item id 列表 |

### run_log
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | |
| slot | TEXT | |
| category_slug | TEXT | |
| started_at | DATETIME | |
| finished_at | DATETIME | |
| status | TEXT | success / partial / failed |
| items_fetched | INT | |
| items_new | INT | |
| error_msg | TEXT | |

---

## 5. config.yaml 结构

`config.py` 在加载 `config.yaml` 时，将 `feed_url` 中的 `{RSSHUB_BASE_URL}` 替换为同名环境变量值（默认 `http://rsshub:1200`）。其余 `{VAR}` 占位符同理。

```yaml
settings:
  dedup_days: 7
  db_path: data/news.db
  timezone: Asia/Shanghai

categories:
  - name: 银行用户运营
    slug: banking
    depth_level: medium_deep
    schedule: [morning, evening]
    importance_rule:
      is_key_threshold: 7.0
      boost_tags: [业务方案, 方法论, 监管政策, 竞品动态]
    sources:
      - name: 艾瑞咨询
        fetch_type: rss
        feed_url: "http://{RSSHUB_BASE_URL}/iresearch/report"
        enabled: true
      - name: 36氪·金融
        fetch_type: rss
        feed_url: "http://{RSSHUB_BASE_URL}/36kr/newsflashes"
        enabled: true
      - name: 央行官网
        fetch_type: scraper
        feed_url: "http://www.pbc.gov.cn/goutongjiaoliu/113456/index.html"
        enabled: true
        extra: {selector: ".newsList li"}

  - name: 技术与AI工具
    slug: tech
    depth_level: medium
    schedule: [morning]
    importance_rule:
      is_key_threshold: 7.5
    sources:
      - name: GitHub Trending
        fetch_type: api_github
        feed_url: "https://api.github.com/search/repositories"
        enabled: true
        extra: {topic: "ai,agent,llm", period: "daily"}
      - name: Hacker News
        fetch_type: api_hn
        feed_url: "https://hacker-news.firebaseio.com/v0"
        enabled: true
      - name: Product Hunt
        fetch_type: api_ph
        feed_url: "https://www.producthunt.com/feed"
        enabled: true
      - name: Hugging Face Trending
        fetch_type: api_hf
        feed_url: "https://huggingface.co/api"
        enabled: true
      - name: 机器之心
        fetch_type: rss
        feed_url: "http://{RSSHUB_BASE_URL}/jiqizhixin"
        enabled: true
      - name: 量子位
        fetch_type: rss
        feed_url: "http://{RSSHUB_BASE_URL}/qbitai"
        enabled: true

  - name: 个人创业
    slug: startup
    depth_level: deep
    schedule: [morning]
    importance_rule:
      is_key_threshold: 6.5
    sources:
      - name: IndieHackers
        fetch_type: rss
        feed_url: "https://www.indiehackers.com/feed.rss"
        enabled: true
      - name: Product Hunt
        fetch_type: api_ph
        feed_url: "https://www.producthunt.com/feed"
        enabled: true
        extra: {view: startup}
      - name: 36氪·创投
        fetch_type: rss
        feed_url: "http://{RSSHUB_BASE_URL}/36kr/venture"
        enabled: true
      - name: Hacker News Show HN
        fetch_type: api_hn
        feed_url: "https://hacker-news.firebaseio.com/v0"
        enabled: true
        extra: {filter: "show_hn"}
```

---

## 6. AI 分级处理

### 类1 banking（medium_deep）
- **输入**：title + raw_text（前 800 字）
- **输出**：
  - `summary_zh`：3-4 句中文摘要
  - `score`：0-10（监管影响力 × 业务可借鉴性）
  - `ai_extra.work_impact`：一句话工作影响（仅 score ≥ 7 时生成）
  - `content_tag`：监管政策类 / 业务方案类 / 竞品动态类 / 需求商机类 / 进展突破类 / 成果类

### 类2 tech（medium）
- **输入**：title + description + star 数/增速
- **输出**：
  - `summary_zh`：2-3 句中文摘要
  - `score`：0-10（上升速度 × 与银行运营/数据分析/agent自动化的相关度）
  - `is_key`：score ≥ 7.5

### 类3 startup（deep）
- **输入**：title + full_description
- **输出**：
  - `summary_zh`：2 句中文摘要
  - `score`：适合度综合评分
  - `ai_extra.fit_score`：详细评分（依据4条标准）
  - `ai_extra.ai_approach`：能否/如何用 AI 单人开发
  - `ai_extra.monetization`：启动成本与变现路径
  - `ai_extra.entry_advice`：给我的切入建议
  - `is_key`：score ≥ 6.5

### 创业筛选标准（类3 打分依据）
1. 能用 AI 单人/轻团队开发
2. 启动成本低
3. 面向中国市场
4. 有清晰变现路径

### Token 控制策略
- 每次批量最多 10 条打一个 prompt
- 深度分析（work_impact / ai_extra）只在初步分超阈值后触发
- `ai/client.py` 统一记录每次调用的 input/output token 到 run_log

---

## 7. Web 页面清单

| 路由 | 功能 |
|------|------|
| `/login` | 密码登录，itsdangerous 签名 cookie，48h 有效 |
| `/` | 首页：三类别分区，重点高亮（红色角标），最新在前 |
| `/category/{slug}` | 单类别列表，重要性/日期/标签筛选，HTMX 无刷新分页 |
| `/item/{id}` | 条目详情：全文摘要 + AI 分析 + 原文链接 |
| `/search` | 全文搜索（SQLite FTS5，标题+摘要） |
| `/archive` | 日历视图，按日期回看 |
| `/report/{slot}/{date}` | 晨报/晚报汇总视图，与飞书推送对应，可回看 |
| `/admin/sources` | 来源管理：开关 source、编辑 feed_url，写回 config.yaml |

类3 条目使用项目卡片展示（适合度 / AI 做法 / 变现 / 切入点），非普通列表行。

---

## 8. 飞书推送

- 使用自定义机器人 webhook（`FEISHU_WEBHOOK_URL` 环境变量）
- **推送时机**：cron 任务运行完毕后立即推送本次新增的 `is_key` 条目（不等到时段结束），`push_log` 记录已推送 item_ids 防重
- 每个时段汇总所有 `is_key` 条目，**一次推送一条消息**
- 格式：富文本卡片，按类别分组，每条含标题 + 一句话摘要 + 原文链接；类3 附适合度结论
- `push_log` 记录已推送 item_ids，防止重复推送

---

## 9. 环境变量（.env）

```
ANTHROPIC_API_KEY=
FEISHU_WEBHOOK_URL=
SITE_PASSWORD=
RSSHUB_BASE_URL=http://rsshub:1200
DATABASE_URL=sqlite:///data/news.db
```

---

## 10. 开发阶段（按序执行）

| 阶段 | 内容 |
|------|------|
| 1 | 脚手架：项目结构、FastAPI 起服务、SQLite + 模型、读 config.yaml |
| 2 | 抓取层：RSS / API / 爬虫三类 fetcher + 去重；先接 GitHub Trending、HN、Product Hunt |
| 3 | AI 加工层：分级摘要/打分/建议，带 dry-run 模式 |
| 4 | 入库 + 前端：首页、分类、搜索、归档、已读/收藏、晨晚报、来源管理、密码登录 |
| 5 | 飞书推送：webhook + 时段汇总 + push_log 去重 |
| 6 | 调度：CLI 入口配置，crontab.example |
| 7 | RSSHub 接入中文源：填入 config.yaml 初始种子 |
| 8 | Docker 化：docker-compose + Nginx 配置 + 部署 README |

### 工程要求
- 抓取与 AI 调用均有错误处理与重试（指数退避），单个源失败不影响整体，记录到 run_log
- 支持 `--dry-run` 模式（不调 Claude API，使用假数据）
- 代码文件控制在 400 行以内；超过时拆分模块
