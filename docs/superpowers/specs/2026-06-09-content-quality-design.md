# News Platform — 内容质量提升设计文档

**Goal:** 提升 AI 筛选精准度，减少无关内容噪音，让每日简报真正做到"每条都值得看"。

**Architecture:** 在当前 Fetch → AI 评分 → 存储 的 pipeline 中，加入关键词预筛（Pre-filter）和更严格的评分阈值，同时优化 AI prompt 的负例说明。不引入新的基础设施，只调整配置和 prompt。

**Tech Stack:** FastAPI + SQLAlchemy + DeepSeek API (deepseek-chat) + RSSHub + SQLite + YAML config

---

## 当前系统状态

### 架构概览

```
RSSHub / API 数据源
    ↓ fetch (async)
RawItem 列表（每源 20-30 条）
    ↓ dedup（7天去重）
待评估列表
    ↓ DeepSeek AI 评分 (每条独立调用)
score, summary_zh, is_key, ai_extra
    ↓ min_save_score 过滤
存入 SQLite
    ↓ /daily 页面展示 (Top 6/类)
```

### 关键参数现状

| 类目 | min_save_score | is_key 阈值 | 主要来源 |
|------|---------------|-------------|---------|
| banking | 4.0 | 7.0 | 财联社、财新、36氪、华尔街见闻、第一财经 |
| tech | 无限制 | 7.5 | GitHub Trending、HN、ProductHunt、HuggingFace、机器之心、量子位 |
| startup | 无限制 | 6.5 | IndieHackers、ProductHunt、36氪创投、HN Show |

---

## 核心问题分析

### 问题 1：筛选阈值过低

- banking `min_save_score: 4.0` 允许大量"宏观行情"类内容进入，与零售运营工作相关性低
- tech/startup 无 min_save_score，所有非零分内容都存入数据库

### 问题 2：数据源噪音高

- 财联社、华尔街见闻是综合财经媒体，日均 100+ 条，银行直接相关不足 10%
- HackerNews 覆盖所有技术领域，与银行运营/AI 工具场景直接相关比例较低

### 问题 3：AI Prompt 边界案例处理不足

- 当前 prompt 列出负例，但对"宏观行情"等 4-6 分区间边界案例评分不稳定
- "读了没收获"的内容集中在 4-6 分区间

---

## 改进方案（推荐方案 A）

### 1. 提高 min_save_score 阈值

| 类目 | 当前 | 目标 | 理由 |
|------|------|------|------|
| banking | 4.0 | 5.5 | 切掉"宏观分析无具体措施"的内容 |
| tech | 无 | 5.0 | 过滤纯研究/无实际工具的内容 |
| startup | 无 | 5.0 | 过滤大公司动态等不可参考内容 |

### 2. 优化 AI Prompt 边界案例说明

**banking：** 明确"宏观经济分析，无银行具体产品或政策措施的 → 3 分以下"

**tech：** 明确"没有可使用产品/工具/demo 的纯研究 → 3 分以下"；"与银行运营和个人效率完全无关的底层技术 → 2 分以下"

**startup：** 明确"大厂融资、IPO、并购（无个人可参考的方法论）→ 2 分以下"

### 3. 新增关键词预筛（keyword_blacklist）

在 fetch 后、AI 评分前，对标题做关键词匹配，过滤明显无关内容，节省 AI 调用成本：

```yaml
# banking 黑名单示例
keyword_blacklist:
  - "游戏"
  - "电商"
  - "文旅"
  - "汽车"
  - "医疗"
  - "教育"
  - "农业"
  - "军事"
  - "体育"
  - "明星"
```

---

## 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `config.yaml` | 修改 | 调整 min_save_score，新增 keyword_blacklist |
| `app/config.py` | 修改 | CategoryConfig 增加 `keyword_blacklist: list[str]` 字段 |
| `app/ai/banking.py` | 修改 | BANKING_PROMPT 加强边界案例说明 |
| `app/ai/tech.py` | 修改 | TECH_PROMPT 加强"有实际工具"原则 |
| `app/ai/startup.py` | 修改 | STARTUP_PROMPT 聚焦个人可参考维度 |
| `app/scheduler/pipeline.py` | 修改 | 新增 `_prefilter_items()` 预筛函数 |

---

## 测试策略

1. **单元测试**：`_prefilter_items()` 的黑名单匹配逻辑
2. **Prompt 回归**：用 20 条历史"被误存的无关内容"验证新 prompt 给分下降
3. **集成测试**：dry_run 模式跑完整 pipeline，确认存储条数合理
4. **人工验证**：真实 pipeline 后检查每日简报页面内容质量

## 成功标准

- banking 每次 pipeline 存储条数：20-40 条 → **8-15 条**，is_key 命中率提升
- tech/startup 每次 pipeline 存储条数：≤ 20 条
- 主观评价："看了没用"的内容比例 < 20%
