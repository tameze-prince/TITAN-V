import pytest_asyncio

from titan.persistence.database import engine


@pytest_asyncio.fixture(autouse=True)
async def reset_async_engine() -> None:
    await engine.dispose()
    yield
    await engine.dispose()
