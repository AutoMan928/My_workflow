
import logging
from app.ai.client import call_claude
from app.ai.schemas import BankingResult
from app.config import CategoryConfig
from app.fetchers.base import RawItem

logger = logging.getLogger(__name__)

BANKING_PROMPT = """\
你是一名银行零售用户运营专家，负责判断资讯是否与"银行用户运营"强相关。

【属于相关领域，可打高分】：
- 零售银行产品：储蓄、贷款、信用卡、理财、基金代销
- 移动银行 APP / 网银体验与功能迭代
- 银行客户增长、留存、活跃、流失分析
- 支付清结算、数字人民币、第三方支付竞争
- 金融监管政策（人民银行、国家金融监督管理总局、银保监）
- 银行数字化转型、智能客服、AI 风控
- 竞争银行或互联网金融平台的产品/营销动态

【与本领域无关，必须打低分（0-3）】：
- 电商、零售、旅游文娱、汽车、房产、医疗、教育、农业、工业制造
- 体育赛事、游戏、服装、宠物、食品消费品
- 国际地缘政治、军事冲突
- 股票行情、大宗商品价格（非银行业务分析）
- 任何与银行/金融机构服务用户无直接关系的行业报告

以下是待分析的资讯：
标题：{title}
内容：{content}

返回格式（严格 JSON，不要额外文字）：
{{
  "title_zh": "若标题为英文则翻译为简洁中文，否则与原标题相同",
  "summary_zh": "2-3句中文摘要（若不相关，第一句写明'与银行用户运营无关'）",
  "score": <0-10浮点数，仅基于与银行用户运营的垂直相关度打分>,
  "is_key": <true/false，score>=7且高度相关才为true>,
  "content_tag": "<监管政策类|业务方案类|竞品动态类|需求商机类|进展突破类|成果类|不相关>",
  "work_impact": "<score>=7时填一句话工作影响，否则填null>"
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
