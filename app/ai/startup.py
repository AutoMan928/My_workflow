
import logging
from app.ai.client import call_claude
from app.ai.schemas import StartupResult, StartupExtra
from app.config import CategoryConfig
from app.fetchers.base import RawItem

logger = logging.getLogger(__name__)

STARTUP_PROMPT = """\
你是一名专注AI应用创业的顾问。用户背景：有银行零售运营经验，熟悉银行产品/用户运营/数据分析，正在用AI工具提升效率，想探索适合自己的AI创业方向。

请评估以下创业项目/想法，判断对该用户的参考价值。

标题：{title}
描述：{description}

评分标准（基于对用户创业探索的参考价值）：
- 10分：AI应用创业方向，银行/金融/B2B场景，能用LLM/Agent独立开发，有清晰变现
- 7-9分：AI工具创业，通用场景，用户有能力切入，月入可期
- 4-6分：有一定启发的创业案例，可借鉴模式
- 0-3分：重资产/大团队/技术壁垒极高，或与用户背景完全无关

返回格式（严格 JSON，不要额外文字）：
{{
  "title_zh": "若标题为英文则翻译为简洁中文（15字以内），否则与原标题相同",
  "summary_zh": "2句话：①这个项目做什么 ②核心商业模式/成果",
  "score": <0-10浮点数>,
  "is_key": <true/false，score>=7才为true>,
  "ai_extra": {{
    "fit_score": <0-10，与用户银行背景的契合度>,
    "ai_approach": "能否用AI独立开发，核心技术路径（1句）",
    "monetization": "变现模式和启动成本估算（1句）",
    "entry_advice": "结合用户银行运营背景，最佳切入点建议（1句）"
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
