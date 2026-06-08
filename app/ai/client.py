import json
import logging
import os
from typing import Literal

import httpx

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
            "ai_approach": "【dry-run】可用AI API单人开发，周期约2个月。",
            "monetization": "【dry-run】订阅制，月费99元，预计6个月回本。",
            "entry_advice": "【dry-run】建议从微信小程序切入，先验证付费意愿。",
        },
    },
}

_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
_DEFAULT_MODEL = "deepseek-chat"


def call_claude(
    prompt: str,
    result_type: ResultType = "banking",
    model: str | None = None,
    max_tokens: int = 2000,
    dry_run: bool = False,
) -> str:
    if dry_run:
        return json.dumps(DRY_RUN_RESPONSES[result_type], ensure_ascii=False)

    api_key = os.environ["DEEPSEEK_API_KEY"]
    target_model = model or _DEFAULT_MODEL

    try:
        with httpx.Client(timeout=30, trust_env=False) as client:
            resp = client.post(
                f"{_DEEPSEEK_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": target_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.error("DeepSeek API call failed: %s", exc)
        raise
