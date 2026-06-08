
import logging
from app.ai.client import call_claude
from app.ai.schemas import TechResult
from app.config import CategoryConfig
from app.fetchers.base import RawItem

logger = logging.getLogger(__name__)

TECH_PROMPT = """\
你是一名服务于"银行从业者"的AI技术顾问。用户背景：在银行负责零售用户运营，日常工作涉及用户增长、留存、活跃运营、数据分析，同时在学习AI工具提升个人效率，并关注创业方向。

请评估以下技术资讯/工具/项目，判断其对该用户的价值。

标题：{title}
描述：{description}
热度指标（Stars/Score）：{stars}

【高分 7-10】：
- 可直接用于银行运营工作的AI工具（自动化、数据分析、内容生成、客服、BI等）
- 对银行数字化/金融科技有参考价值的技术动态
- 效率提升工具（编程辅助、笔记、工作流、低代码/无代码）
- Agent框架、LLM应用开发方向的突破性进展
- 爆火的AI产品/平台（可能成为行业标配工具）

【中分 4-6】：
- 通用AI/技术趋势，对个人学习有参考价值
- 开发者工具但有一定通用场景
- 大模型本身的技术进展

【低分 0-3】：
- 纯基础研究、学术论文（无工具/产品）
- 与工作/学习完全无关的硬件、游戏、娱乐技术
- 已经非常普及无新意的内容

返回格式（严格 JSON，不要额外文字）：
{{
  "title_zh": "若标题为英文则翻译为简洁中文（15字以内），否则与原标题相同",
  "summary_zh": "2-3句中文摘要，说明这是什么工具/技术，核心亮点是什么",
  "score": <0-10浮点数>,
  "is_key": <true/false，score>=7且值得立即关注才为true>,
  "tool_use_case": "<score>=6时填写：在银行运营工作或个人学习中的具体使用场景（1句），否则填null>",
  "learn_priority": "<高|中|低，表示学习/尝试的优先级>"
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
            description=(item.raw_text or "")[:500],
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
