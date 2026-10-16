from __future__ import annotations

import pytest
from app.db import engine


@pytest.fixture(autouse=True)
async def cleanup_engine():
    yield
    await engine.dispose()
