"""카테고리 분류 백필 — 규칙(app.ingest.normalize.guess_category) 기반.

AI(Gemini) 분류를 시도했었지만, 이 프로젝트가 쓰는 무료 키의 실제 한도가
일일 20 요청이라 수집량을 감당하지 못해 걷어냈다(2026-07-08). 이제 전부
키워드 규칙으로만 분류하고, 규칙이 못 잡는 애매한 제목은 미분류(None)로
남겨둔다(잘못된 값을 강제하는 것보다 안전. 키워드 사전을 보강하면 소급 적용됨).
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.db import SessionLocal
from app.ingest.normalize import guess_category
from app.models import Deal, Item

logger = logging.getLogger("classify")

_BATCH = 20  # 한 번에 처리할 건수(커서 진행 단위)


async def _set_category(session, deal: Deal, cat: str) -> None:
    deal.category = cat
    if deal.item_id is not None:  # 같은 상품이 분류를 공유하도록 Item에도 반영
        item = await session.get(Item, deal.item_id)
        if item is not None and not item.category:
            item.category = cat


async def _cached_item_category(session, deal: Deal) -> str | None:
    """같은 상품(Item)이 이전에 이미 분류됐으면 그 결과를 재사용.

    핫딜은 같은 상품이 여러 커뮤니티/시점에 재등록되는 경우가 흔해(normalized_key로
    Item 그룹핑), 매 재등록마다 다시 계산하는 건 낭비다.
    """
    if deal.item_id is None:
        return None
    item = await session.get(Item, deal.item_id)
    return item.category if item and item.category else None


async def _classify_and_update(session, deals: list[Deal]) -> int:
    """아이템 캐시 → 키워드 규칙. 둘 다 못 잡으면 미분류(None)로 남긴다."""
    if not deals:
        return 0
    updated = 0
    for d in deals:
        cached = await _cached_item_category(session, d)
        c = cached or guess_category(d.title)
        if c:
            await _set_category(session, d, c)
            updated += 1
    await session.commit()
    return updated


async def classify_new(deal_ids: list[int]) -> int:
    """신규 수집 딜 중 미분류 처리. 처리 건수 반환."""
    if not deal_ids:
        return 0
    async with SessionLocal() as session:
        deals = (
            await session.execute(
                select(Deal).where(Deal.id.in_(deal_ids), Deal.category.is_(None))
            )
        ).scalars().all()
        total = 0
        for i in range(0, len(deals), _BATCH):
            total += await _classify_and_update(session, deals[i : i + _BATCH])
        if total:
            logger.info("분류 %d건", total)
        return total


async def classify_all() -> int:
    """기존 미분류 딜 전체 백필(관리자 CLI). id 커서로 전진해 중복/무한루프 방지."""
    total = 0
    last_id = 0
    async with SessionLocal() as session:
        while True:
            deals = (
                await session.execute(
                    select(Deal)
                    .where(Deal.category.is_(None), Deal.id > last_id)
                    .order_by(Deal.id)
                    .limit(_BATCH)
                )
            ).scalars().all()
            if not deals:
                break
            last_id = deals[-1].id
            total += await _classify_and_update(session, deals)
            logger.info("분류 진행: 누적 %d건 (cursor=%d)", total, last_id)
    return total
