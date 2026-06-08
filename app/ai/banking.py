
import logging
from app.ai.client import call_claude
from app.ai.schemas import BankingResult
from app.config import CategoryConfig
from app.fetchers.base import RawItem

logger = logging.getLogger(__name__)

BANKING_PROMPT = """\
你是一名银行行业分析师，负责从资讯中筛选对"银行从业者"有参考价值的内容。

【高相关（7-10分）】：
- 零售银行产品：储蓄、贷款、信用卡、理财、基金代销
- 移动银行 APP / 网银体验与功能迭代
- 银行客户增长、留存、活跃、流失、NPS、满意度
- 支付清结算、数字人民币、第三方支付竞争
- 金融监管政策（人民银行、国家金融监督管理总局、银保监、银行业协会）
- 银行数字化转型、智能客服、AI 风控、大模型在金融的应用
- 竞争银行或互联网金融平台的产品/营销/用户策略
- 银行存贷款利率调整、揽储政策、LPR变动

【中相关（4-6分）】：
- 银行股业绩、银行业整体经营数据
- 宏观经济/货币政策对银行业的影响分析
- 房贷、车贷、消费贷、小微贷的政策或市场动态
- 保险、证券、基金与银行渠道的交叉销售
- 跨境金融、SWIFT、人民币国际化
- 银行机构人事变动、并购重组

【无关（0-3分）】：
- 纯股票行情、大宗商品、期货价格（无银行视角分析）
- 电商、旅游文娱、汽车制造、房产开发、医疗、教育、农业
- 体育赛事、游戏、服装、宠物、食品消费品
- 国际地缘政治、军事冲突
- 芯片、AI模型研发、半导体（除非是银行数字化场景）
- 与银行/金融机构毫无关联的行业报告

以下是待分析的资讯：
标题：{title}
内容：{content}

返回格式（严格 JSON，不要额外文字）：
{{
  "title_zh": "若标题为英文则翻译为简洁中文，否则与原标题相同",
  "summary_zh": "2-3句中文摘要（若不相关，第一句写明'与银行行业无关'）",
  "score": <0-10浮点数，依据上述三档标准评分>,
  "is_key": <true/false，score>=7且对银行从业者有直接参考价值才为true>,
  "content_tag": "<监管政策类|业务方案类|竞品动态类|行业动态类|需求商机类|不相关>",
  "work_impact": "<score>=7时填一句话对银行工作的参考意义，否则填null>"
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
