"""수집 파이프라인.

흐름: 소스 fetch → Deal upsert(중복 무시) → 신규 Deal만 Item 연결 + PriceHistory 기록.
신규 게시글만 처리하므로 재실행해도 안전(멱등)하다.
"""

from __future__ import annotations

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import SessionLocal
from app.ingest.normalize import normalized_key
from app.models import Deal, Item, PriceHistory, Source
from app.sources.base import RawDeal
from app.sources.registry import SOURCES

logger = logging.getLogger("ingest")


async def sync_sources(session: AsyncSession) -> dict[str, int]:
    """코드 레지스트리의 소스를 DB에 반영하고 slug -> id 매핑을 반환."""
    for src in SOURCES:
        stmt = (
            pg_insert(Source)
            .values(slug=src.slug, name=src.name, kind=src.kind, enabled=True)
            .on_conflict_do_update(
                index_elements=["slug"],
                set_={"name": src.name, "kind": src.kind},
            )
        )
        await session.execute(stmt)
    await session.commit()

    rows = (await session.execute(select(Source.slug, Source.id))).all()
    return {slug: sid for slug, sid in rows}


async def _find_or_create_item(session: AsyncSession, deal: RawDeal) -> int:
    key = normalized_key(deal.title)
    ins = (
        pg_insert(Item)
        .values(normalized_key=key, display_name=deal.title[:255], category=deal.category)
        .on_conflict_do_nothing(index_elements=["normalized_key"])
        .returning(Item.id)
    )
    res = (await session.execute(ins)).first()
    if res:
        return res[0]
    return (await session.execute(select(Item.id).where(Item.normalized_key == key))).scalar_one()


async def _store_deal(session: AsyncSession, source_id: int, raw: RawDeal) -> int | None:
    """Deal을 upsert. 신규면 Item 연결 + 가격 이력 기록 후 deal_id 반환, 중복이면 None."""
    ins = (
        pg_insert(Deal)
        .values(
            source_id=source_id,
            source_post_id=raw.source_post_id,
            title=raw.title,
            url=raw.url,
            price=raw.price,
            category=raw.category,
            thumbnail_url=raw.thumbnail_url,
            posted_at=raw.posted_at,
        )
        .on_conflict_do_nothing(index_elements=["source_id", "source_post_id"])
        .returning(Deal.id)
    )
    res = (await session.execute(ins)).first()
    if res is None:
        # 이미 수집된 게시글 — 다만 썸네일이 나중에 생겼으면(og:image 보강 등) 채워준다
        if raw.thumbnail_url:
            await session.execute(
                Deal.__table__.update()
                .where(
                    Deal.source_id == source_id,
                    Deal.source_post_id == raw.source_post_id,
                    Deal.thumbnail_url.is_(None),
                )
                .values(thumbnail_url=raw.thumbnail_url)
            )
        return None

    deal_id = res[0]
    item_id = await _find_or_create_item(session, raw)
    await session.execute(
        Deal.__table__.update().where(Deal.id == deal_id).values(item_id=item_id)
    )
    if raw.price is not None:
        session.add(PriceHistory(item_id=item_id, deal_id=deal_id, price=raw.price))
    return deal_id


async def run_once() -> dict[str, int]:
    """모든 활성 소스를 1회 수집. 소스별 신규 건수를 반환."""
    settings = get_settings()
    results: dict[str, int] = {}

    async with SessionLocal() as session:
        slug_to_id = await sync_sources(session)

    new_deal_ids: list[int] = []
    headers = {"User-Agent": settings.http_user_agent}
    async with httpx.AsyncClient(headers=headers, timeout=20.0, follow_redirects=True) as client:
        for src in SOURCES:
            source_id = slug_to_id[src.slug]
            try:
                raw_deals = await src.fetch(client)
            except Exception as exc:  # 한 소스 실패가 전체를 막지 않도록
                logger.warning("소스 수집 실패 [%s]: %s", src.slug, exc)
                results[src.slug] = -1
                continue

            source_new: list[int] = []
            async with SessionLocal() as session:
                for raw in raw_deals:
                    try:
                        deal_id = await _store_deal(session, source_id, raw)
                        if deal_id is not None:
                            source_new.append(deal_id)
                    except Exception as exc:
                        logger.warning("딜 저장 실패 [%s] %s: %s", src.slug, raw.url, exc)
                await session.commit()

            new_deal_ids.extend(source_new)
            results[src.slug] = len(source_new)
            logger.info("[%s] 신규 %d건 / 수신 %d건", src.slug, len(source_new), len(raw_deals))

    # 미분류 신규 딜 AI 분류 (Gemini 키 없으면 내부에서 no-op)
    if new_deal_ids:
        try:
            from app.ai.classify import classify_new

            await classify_new(new_deal_ids)
        except Exception:
            logger.exception("AI 분류 오류")

    # 신규 딜에 대해 텔레그램 알림 매칭 (토큰 없으면 내부에서 no-op)
    if new_deal_ids:
        try:
            from app.notify.matcher import process_new_deals

            await process_new_deals(new_deal_ids)
        except Exception:
            logger.exception("알림 처리 오류")

    return results
