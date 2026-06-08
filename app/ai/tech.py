
import logging
from app.ai.client import call_claude
from app.ai.schemas import TechResult
from app.config import CategoryConfig
from app.fetchers.base import RawItem

logger = logging.getLogger(__name__)

TECH_PROMPT = """\
你是一名关注银行运营、数据分析和AI自动化工具的技术研究员。请分析以下项目/资讯，返回 JSON（不要加代码块）：

标题：{title}
描述：{description}
热度指标（Stars/Score）：{stars}

返回格式（严格 JSON，不要额外文字）：
{{
  "summary_zh": "2-3句中文摘要",
  "score": <0-10浮点数，上升速度×与银行运营/数据分析/agent自动化的相关度>,
  "is_key": <true/false>
}}
"""


def process_tech_batch(
    items: list[RawItem],
    category: CategoryConfig,
    dry_run: bool = False,
) -> list[TechResult]:
    threshold = category.importance_rule.is_key_threshold
    results: list[TechResult] = []
    for item in items:
        stars = item.extra.get("stars") or item.extra.get("score", 0)
        prompt = TECH_PROMPT.format(
            title=item.title,
            description=(item.raw_text or "")[:400],
            stars=stars,
        )
        raw = call_claude(prompt, result_type="tech", dry_run=dry_run)
        try:
            result = TechResult.model_validate_json(raw)
        except Exception as exc:
            logger.error("Parse failed for %r: %s", item.title, exc)
            result = TechResult(summary_zh=item.title, score=0.0, is_key=False)
        result = result.model_copy(update={"is_key": result.score >= threshold})
        results.append(result)
    return results
