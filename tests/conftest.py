"""테스트 공통 픽스처. SQLite(메모리, StaticPool로 단일 공유 연결) 위에서 돈다."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.models import Base, Deal, Item, PriceHistory, Source


def _make_engine():
    # StaticPool + 단일 연결 → 여러 세션이 같은 인메모리 DB를 공유(같은 이벤트 루프 내).
    return create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )


async def seed_basic(session) -> dict:
    """딜 2건 + 가격이력 시드. i1(콜라)은 이력 충분 & 현재가 역대최저 → great."""
    src = Source(slug="t", name="테스트", kind="rss", enabled=True)
    session.add(src)
    await session.flush()

    base = datetime.now(timezone.utc)
    i1 = Item(normalized_key="cola", display_name="코카콜라 제로 30캔", category="제로음료")
    i2 = Item(normalized_key="ssd", display_name="삼성 SSD", category="전자기기")
    session.add_all([i1, i2])
    await session.flush()

    for p in [18000, 17000, 19000, 16000, 17500, 18500]:
        session.add(PriceHistory(item_id=i1.id, deal_id=None, price=p, observed_at=base))

    d1 = Deal(source_id=src.id, item_id=i1.id, source_post_id="1",
              title="[쿠팡] 코카콜라 제로 30캔 (14,900원)", url="http://x/1",
              price=14900, category="제로음료", posted_at=base)
    d2 = Deal(source_id=src.id, item_id=i2.id, source_post_id="2",
              title="[G마켓] 삼성 SSD 1TB (109,000원)", url="http://x/2",
              price=109000, category="전자기기", posted_at=base)
    session.add_all([d1, d2])
    await session.flush()
    session.add(PriceHistory(item_id=i1.id, deal_id=d1.id, price=14900, observed_at=base))
    session.add(PriceHistory(item_id=i2.id, deal_id=d2.id, price=109000, observed_at=base))
    await session.commit()
    return {"src": src.id, "i1": i1.id, "i2": i2.id, "d1": d1.id, "d2": d2.id}


@pytest_asyncio.fixture
async def session():
    engine = _make_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Sm = async_sessionmaker(engine, expire_on_commit=False)
    async with Sm() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded(session):
    """seed_basic 데이터가 들어간 (session, ids)."""
    ids = await seed_basic(session)
    return session, ids


@pytest_asyncio.fixture
async def api():
    """ASGI 테스트 클라이언트 + 세션메이커. get_session 의존성을 SQLite로 오버라이드."""
    from app.api.main import app
    from app.db import get_session

    engine = _make_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Sm = async_sessionmaker(engine, expire_on_commit=False)
    async with Sm() as s:
        ids = await seed_basic(s)

    async def override():
        async with Sm() as s:
            yield s

    app.dependency_overrides[get_session] = override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, Sm, ids
    app.dependency_overrides.clear()
    await engine.dispose()
