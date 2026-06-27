"""DB 연동 분석 서비스. price_stats(순수 함수)를 실제 데이터에 연결한다."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.price_stats import PriceAnalysis, analyze
from app.models import Deal, Item, PriceHistory, Source


async def histories_for_items(
    session: AsyncSession, item_ids: list[int]
) -> dict[int, list[int]]:
    """여러 상품의 가격 이력을 한 번에 조회(N+1 방지). item_id -> [price...]."""
    if not item_ids:
        return {}
    rows = (
        await session.execute(
            select(PriceHistory.item_id, PriceHistory.price).where(
                PriceHistory.item_id.in_(item_ids)
            )
        )
    ).all()
    out: dict[int, list[int]] = defaultdict(list)
    for item_id, price in rows:
        out[item_id].append(price)
    return out


async def list_deals(
    session: AsyncSession,
    q: str | None = None,
    category: str | None = None,
    limit: int = 30,
    offset: int = 0,
) -> list[dict]:
    """검색(q)·카테고리 필터된 최신 딜 목록. 각 딜에 가격 분석을 붙여 반환."""
    stmt = (
        select(Deal, Source.name)
        .join(Source, Source.id == Deal.source_id)
        .where(Deal.is_active.is_(True))
    )
    if q:
        stmt = stmt.where(Deal.title.ilike(f"%{q}%"))
    if category:
        stmt = stmt.where(Deal.category == category)
    stmt = stmt.order_by(Deal.posted_at.desc().nullslast(), Deal.id.desc()).limit(limit).offset(offset)

    rows = (await session.execute(stmt)).all()
    deals = [d for d, _ in rows]
    item_ids = [d.item_id for d in deals if d.item_id is not None]
    histories = await histories_for_items(session, item_ids)

    result = []
    for deal, source_name in rows:
        history = histories.get(deal.item_id or -1, [])
        analysis = analyze(deal.price, history)
        result.append(
            {
                "id": deal.id,
                "title": deal.title,
                "url": deal.url,
                "price": deal.price,
                "category": deal.category,
                "source": source_name,
                "posted_at": deal.posted_at,      # 커뮤니티 게시 시각(없을 수 있음)
                "fetched_at": deal.fetched_at,    # 우리가 수집한 시각(항상 있음, 폴백용)
                "item_id": deal.item_id,
                "analysis": analysis.to_dict(),
            }
        )
    return result


async def item_detail(session: AsyncSession, item_id: int) -> dict | None:
    """상품 상세: 가격 이력 + 분석 + 같은 상품의 최근 딜들(요구사항 6)."""
    item = await session.get(Item, item_id)
    if item is None:
        return None

    history_rows = (
        await session.execute(
            select(PriceHistory.price, PriceHistory.observed_at)
            .where(PriceHistory.item_id == item_id)
            .order_by(PriceHistory.observed_at.asc())
        )
    ).all()
    prices = [p for p, _ in history_rows]

    deal_rows = (
        await session.execute(
            select(Deal, Source.name)
            .join(Source, Source.id == Deal.source_id)
            .where(Deal.item_id == item_id)
            .order_by(Deal.posted_at.desc().nullslast(), Deal.id.desc())
            .limit(20)
        )
    ).all()

    # 현재가 = 가장 최근 관측가
    current_price = prices[-1] if prices else None
    analysis: PriceAnalysis = analyze(current_price, prices)

    return {
        "id": item.id,
        "display_name": item.display_name,
        "category": item.category,
        "analysis": analysis.to_dict(),
        "price_history": [
            {"price": p, "observed_at": ts} for p, ts in history_rows
        ],
        "recent_deals": [
            {
                "id": d.id,
                "title": d.title,
                "url": d.url,
                "price": d.price,
                "source": name,
                "posted_at": d.posted_at,
            }
            for d, name in deal_rows
        ],
    }


async def list_categories(session: AsyncSession) -> list[str]:
    rows = (
        await session.execute(
            select(Deal.category).where(Deal.category.is_not(None)).distinct()
        )
    ).all()
    return sorted(c for (c,) in rows)
