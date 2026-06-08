
import logging
from app.ai.client import call_claude
from app.ai.schemas import BankingResult
from app.config import CategoryConfig
from app.fetchers.base import RawItem

logger = logging.getLogger(__name__)

BANKING_PROMPT = """\
你是一名银行零售运营专家助手。请分析以下资讯，返回 JSON（不要加代码块）：

标题：{title}
内容：{content}

返回格式（严格 JSON，不要额外文字）：
{{
  "summary_zh": "3-4句中文摘要",
  "score": <0-10浮点数，监管影响力×业务可借鉴性>,
  "is_key": <true/false>,
  "content_tag": "<监管政策类|业务方案类|竞品动态类|需求商机类|进展突破类|成果类>",
  "work_impact": "<一句话工作影响，score>=7时填充，否则填null>"
}}
"""


def process_banking_batch(
    items: list[RawItem],
    category: CategoryConfig,
    dry_run: bool = False,
) -> list[BankingResult]:
    results: list[BankingResult] = []
    threshold = category.importance_rule.is_key_threshold
    boost_tags = set(category.importance_rule.boost_tags)

    for item in items:
        content = (item.raw_text or "")[:800]
        prompt = BANKING_PROMPT.format(title=item.title, content=content)
        raw = call_claude(prompt, result_type="banking", dry_run=dry_run)
        try:
            result = BankingResult.model_validate_json(raw)
        except Exception as exc:
            logger.error("Parse failed for %r: %s", item.title, exc)
            result = BankingResult(summary_zh=item.title, score=0.0, is_key=False)

        boosted = result.content_tag in boost_tags if result.content_tag else False
        result = result.model_copy(update={"is_key": (
            result.score >= threshold or (result.score >= threshold - 1 and boosted)
        )})
        if result.score < threshold:
            result = result.model_copy(update={"work_impact": None})
        results.append(result)
    return results
