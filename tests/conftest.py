import asyncio
import os
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")
os.environ.setdefault("RSSHUB_BASE_URL", "http://localhost:1200")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
