
from pydantic import BaseModel


class BankingResult(BaseModel):
    title_zh: str | None = None
    summary_zh: str
    score: float
    is_key: bool
    content_tag: str | None = None
    work_impact: str | None = None


class TechResult(BaseModel):
    title_zh: str | None = None
    summary_zh: str
    score: float
    is_key: bool
    tool_use_case: str | None = None
    learn_priority: str | None = None


class StartupExtra(BaseModel):
    fit_score: float
    ai_approach: str
    monetization: str
    entry_advice: str


class StartupResult(BaseModel):
    title_zh: str | None = None
    summary_zh: str
    score: float
    is_key: bool
    ai_extra: StartupExtra


class CompanyResult(BaseModel):
    title_zh: str | None = None
    summary_zh: str
    score: float
    is_key: bool
    event_type: str | None = None
    impact_zh: str | None = None
