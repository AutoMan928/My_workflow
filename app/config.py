import os
import re
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel


class ImportanceRule(BaseModel):
    is_key_threshold: float
    boost_tags: list[str] = []


class SourceConfig(BaseModel):
    name: str
    fetch_type: str
    feed_url: str
    enabled: bool = True
    extra: dict = {}


class CategoryConfig(BaseModel):
    name: str
    slug: str
    depth_level: str
    schedule: list[str]
    importance_rule: ImportanceRule
    sources: list[SourceConfig]
    enabled: bool = True
    min_save_score: float = 0.0


class Settings(BaseModel):
    dedup_days: int = 7
    db_path: str = "data/news.db"
    timezone: str = "Asia/Shanghai"


class AppConfig(BaseModel):
    settings: Settings
    categories: list[CategoryConfig]


def _substitute_env_vars(text: str) -> str:
    """Replace {VAR_NAME} placeholders with environment variable values.

    If an environment variable is not found, the placeholder is left unchanged.
    """
    def replacer(match: re.Match) -> str:
        var = match.group(1)
        return os.environ.get(var, f"{{{var}}}")
    return re.sub(r"\{([A-Z_][A-Z0-9_]*)\}", replacer, text)


def load_config(path: str = "config.yaml") -> AppConfig:
    """Load and parse configuration from a YAML file.

    Environment variables in the format {VAR_NAME} are substituted before parsing.
    """
    raw = Path(path).read_text(encoding="utf-8")
    substituted = _substitute_env_vars(raw)
    data = yaml.safe_load(substituted)
    return AppConfig(**data)


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Get cached application configuration.

    Configuration is loaded from config.yaml and cached for reuse.
    """
    return load_config()
