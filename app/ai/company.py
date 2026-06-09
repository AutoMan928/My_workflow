"""
AI processor for company intelligence monitoring.
Evaluates news/events for significance to a specific company (上海画龙信息科技有限公司).
"""
import logging
import os
from app.ai.client import call_claude
from app.ai.schemas import CompanyResult
from app.config import CategoryConfig
from app.fetchers.base import RawItem

logger = logging.getLogger(__name__)

_DEFAULT_COMPANY = "上海画龙信息科技有限公司"

COMPANY_PROMPT = """\
你是一名企业情报分析师，专门监控"{company}"的重要变动。

【高分 7-10 — 必须关注】：
- 融资/投资：新一轮融资、战略投资进入或退出
- 重要人事变动：创始人、CEO、CTO等核心高管变更
- 重大合同/战略合作：签署重要合作协议
- 风险事件：被列为失信被执行人、行政处罚、刑事案件
- 工商变更：股权结构变化、注册资本重大变更
- 重大产品发布或业务转型

【中分 4-6 — 一般关注】：
- 公司新闻报道（非紧急事项）
- 招聘信息（反映业务方向）
- 行业动态中提及该公司

【低分 0-3 — 噪音】：
- 与"{company}"无直接关系的内容
- 仅提及公司名称的行业综述或广告
- 重复或明显过时的信息

分析内容：
标题：{title}
内容：{content}

返回格式（严格 JSON，不要额外文字）：
{{
  "title_zh": "事件标题（中文，20字以内）",
  "summary_zh": "2-3句摘要，说明发生了什么、影响是什么",
  "score": <0-10浮点数>,
  "is_key": <true/false，score>=7才为true>,
  "event_type": "<融资|人事变动|合同合作|风险事件|工商变更|产品发布|行业动态|其他>",
  "impact_zh": "<score>=7时一句话说明对公司的潜在影响，否则为null>"
}}
"""


def process_company_batch(
    items: list[RawItem],
    category: CategoryConfig,
    dry_run: bool = False,
) -> list[CompanyResult]:
    company = os.environ.get("MONITOR_COMPANY_NAME", _DEFAULT_COMPANY)
    threshold = category.importance_rule.is_key_threshold
    results: list[CompanyResult] = []

    for item in items:
        content = (item.raw_text or "")[:800]
        prompt = COMPANY_PROMPT.format(
            company=company,
            title=item.title,
            content=content,
        )
        raw = call_claude(prompt, result_type="company", dry_run=dry_run)
        try:
            result = CompanyResult.model_validate_json(raw)
        except Exception as exc:
            logger.error("Parse failed for %r: %s", item.title, exc)
            result = CompanyResult(summary_zh=item.title, score=0.0, is_key=False)

        result = result.model_copy(update={"is_key": result.score >= threshold})
        if result.score < threshold:
            result = result.model_copy(update={"impact_zh": None})
        results.append(result)

    return results
