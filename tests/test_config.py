import pytest
from app.config import load_config, _substitute_env_vars

MINIMAL_CONFIG = """
settings:
  dedup_days: 7
  db_path: data/news.db
  timezone: Asia/Shanghai
categories:
  - name: 测试类别
    slug: test
    depth_level: medium
    schedule: [morning]
    enabled: true
    importance_rule:
      is_key_threshold: 7.0
      boost_tags: []
    sources:
      - name: 测试源
        fetch_type: rss
        feed_url: "http://{TEST_HOST}/feed"
        enabled: true
        extra: {}
"""


def test_substitute_env_vars(monkeypatch):
    monkeypatch.setenv("TEST_HOST", "example.com")
    assert _substitute_env_vars("http://{TEST_HOST}/feed") == "http://example.com/feed"


def test_missing_env_var_keeps_placeholder():
    result = _substitute_env_vars("http://{UNDEFINED_VAR}/feed")
    assert result == "http://{UNDEFINED_VAR}/feed"


def test_load_config(monkeypatch, tmp_path):
    monkeypatch.setenv("TEST_HOST", "rsshub:1200")
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(MINIMAL_CONFIG)
    cfg = load_config(str(cfg_file))
    assert cfg.settings.dedup_days == 7
    assert len(cfg.categories) == 1
    assert cfg.categories[0].slug == "test"
    assert cfg.categories[0].sources[0].feed_url == "http://rsshub:1200/feed"


def test_category_fields(monkeypatch, tmp_path):
    monkeypatch.setenv("TEST_HOST", "localhost:1200")
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(MINIMAL_CONFIG)
    cfg = load_config(str(cfg_file))
    src = cfg.categories[0].sources[0]
    assert src.fetch_type == "rss"
    assert src.enabled is True
