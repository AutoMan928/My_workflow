import pytest
from app.ai.client import call_claude
from app.ai.schemas import BankingResult, TechResult, StartupResult
from app.ai.processor import process_items
from app.config import CategoryConfig, ImportanceRule
from app.fetchers.base import RawItem


def test_dry_run_banking():
    raw = call_claude("any prompt", result_type="banking", dry_run=True)
    result = BankingResult.model_validate_json(raw)
    assert 0 <= result.score <= 10
    assert result.summary_zh


def test_dry_run_tech():
    raw = call_claude("any prompt", result_type="tech", dry_run=True)
    result = TechResult.model_validate_json(raw)
    assert 0 <= result.score <= 10


def test_dry_run_startup():
    raw = call_claude("any prompt", result_type="startup", dry_run=True)
    result = StartupResult.model_validate_json(raw)
    assert result.ai_extra.entry_advice
    assert result.ai_extra.fit_score is not None


def test_banking_schema_valid():
    r = BankingResult(
        summary_zh="摘要", score=8.5, is_key=True,
        content_tag="监管政策类", work_impact="影响"
    )
    assert r.is_key is True


def test_startup_schema_requires_ai_extra():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        StartupResult(summary_zh="test", score=7.0, is_key=True, ai_extra={})


def _banking_cat():
    return CategoryConfig(
        name="银行", slug="banking", depth_level="medium_deep",
        schedule=["morning"], enabled=True,
        importance_rule=ImportanceRule(is_key_threshold=7.0, boost_tags=["监管政策类"]),
        sources=[],
    )


def _startup_cat():
    return CategoryConfig(
        name="创业", slug="startup", depth_level="deep",
        schedule=["morning"], enabled=True,
        importance_rule=ImportanceRule(is_key_threshold=6.5),
        sources=[],
    )


def test_process_banking_dry_run():
    results = process_items(
        [RawItem(title="央行降息", url="https://example.com/1", raw_text="内容")],
        _banking_cat(), dry_run=True
    )
    assert len(results) == 1
    assert results[0].score > 0


def test_process_startup_dry_run():
    results = process_items(
        [RawItem(title="AI记账App", url="https://example.com/2", raw_text="帮用户记账")],
        _startup_cat(), dry_run=True
    )
    assert results[0].ai_extra.entry_advice


def test_unknown_depth_raises():
    bad = CategoryConfig(
        name="X", slug="x", depth_level="unknown",
        schedule=["morning"], enabled=True,
        importance_rule=ImportanceRule(is_key_threshold=7.0), sources=[]
    )
    with pytest.raises(ValueError, match="Unknown depth_level"):
        process_items([RawItem(title="X", url="https://x.com")], bad, dry_run=True)
