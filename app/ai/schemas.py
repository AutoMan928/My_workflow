from __future__ import annotations

from pydantic import BaseModel


class BankingResult(BaseModel):
    summary_zh: str
    score: float
    is_key: bool
    content_tag: str | None = None
    work_impact: str | None = None


class TechResult(BaseModel):
    summary_zh: str
    score: float
    is_key: bool


class StartupExtra(BaseModel):
    fit_score: float
    ai_approach: str
    monetization: str
    entry_advice: str


class StartupResult(BaseModel):
    summary_zh: str
    score: float
    is_key: bool
    ai_extra: StartupExtra
