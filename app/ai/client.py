
import json
import logging
import os
from typing import Literal

logger = logging.getLogger(__name__)

ResultType = Literal["banking", "tech", "startup"]

DRY_RUN_RESPONSES: dict[str, dict] = {
    "banking": {
        "summary_zh": "【dry-run】银行资讯测试摘要，涉及监管政策变化。",
        "score": 7.5,
        "is_key": True,
        "content_tag": "监管政策类",
        "work_impact": "【dry-run】该政策对零售贷款业务有直接影响。",
    },
    "tech": {
        "summary_zh": "【dry-run】AI工具测试摘要，项目增速迅猛。",
        "score": 8.0,
        "is_key": True,
    },
    "startup": {
        "summary_zh": "【dry-run】创业项目测试摘要。",
        "score": 7.2,
        "is_key": True,
        "ai_extra": {
            "fit_score": 7.2,
            "ai_approach": "【dry-run】可用Claude API单人开发，周期约2个月。",
            "monetization": "【dry-run】订阅制，月费99元，预计6个月回本。",
            "entry_advice": "【dry-run】建议从微信小程序切入，先验证付费意愿。",
        },
    },
}

_client = None


def _get_client():
    global _client
    if _client is None:
        from anthropic import Anthropic
        _client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def call_claude(
    prompt: str,
    result_type: ResultType = "banking",
    model: str | None = None,
    max_tokens: int = 2000,
    dry_run: bool = False,
) -> str:
    if dry_run:
        return json.dumps(DRY_RUN_RESPONSES[result_type], ensure_ascii=False)

    default_model = (
        "claude-sonnet-4-6" if result_type == "startup"
        else "claude-haiku-4-5-20251001"
    )
    try:
        response = _get_client().messages.create(
            model=model or default_model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception as exc:
        logger.error("Claude API call failed: %s", exc)
        raise
