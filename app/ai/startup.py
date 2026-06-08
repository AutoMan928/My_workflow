import logging
from app.ai.client import call_claude
from app.ai.schemas import StartupResult, StartupExtra
from app.config import CategoryConfig
from app.fetchers.base import RawItem

logger = logging.getLogger(__name__)

STARTUP_PROMPT = """\
你是一名专注中国市场的AI创业顾问。请评估以下创业项目/想法，返回 JSON（不要加代码块）：

标题：{title}
描述：{description}

评分标准（四条，每条2.5分，共10分）：
1. 能用AI单人/轻团队开发
2. 启动成本低
3. 面向中国市场
4. 有清晰变现路径

返回格式（严格 JSON，不要额外文字）：
{{
  "summary_zh": "2句中文摘要",
  "score": <0-10综合适合度>,
  "is_key": <true/false>,
  "ai_extra": {{
    "fit_score": <0-10浮点数，同score>,
    "ai_approach": "能否/如何用AI单人开发的具体说明",
    "monetization": "启动成本估算与变现路径",
    "entry_advice": "给我的切入建议，1-2句"
  }}
}}
"""


def process_startup_batch(
    items: list[RawItem],
    category: CategoryConfig,
    dry_run: bool = False,
) -> list[StartupResult]:
    threshold = category.importance_rule.is_key_threshold
    results: list[StartupResult] = []
    for item in items:
        prompt = STARTUP_PROMPT.format(
            title=item.title,
            description=(item.raw_text or "")[:600],
        )
        raw = call_claude(prompt, result_type="startup", dry_run=dry_run)
        try:
            result = StartupResult.model_validate_json(raw)
        except Exception as exc:
            logger.error("Parse failed for %r: %s", item.title, exc)
            result = StartupResult(
                summary_zh=item.title, score=0.0, is_key=False,
                ai_extra=StartupExtra(fit_score=0.0, ai_approach="解析失败",
                                      monetization="解析失败", entry_advice="解析失败"),
            )
        result = result.model_copy(update={"is_key": result.score >= threshold})
        results.append(result)
    return results
