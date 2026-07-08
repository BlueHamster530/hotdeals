"""AI 카테고리 분류 (요구사항 2·4) — Gemini.

**AI(Gemini)가 주 분류기**, 규칙(normalize.guess_category)은 AI 비활성(키 없음)이거나
API 호출 자체가 실패했을 때만 쓰는 저비용 폴백/캐시다. 순서를 반대로(규칙 먼저) 하면
"초파리제로"가 '제로' 키워드만 보고 제로음료로 오분류되는 식의 얕은 substring 매칭
오류가 AI 검증 없이 그대로 저장되는 문제가 있어 AI를 먼저 돌린다.
"""

from __future__ import annotations

import asyncio
import json
import logging

from google import genai
from google.genai import types
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.ingest.normalize import CATEGORIES, guess_category
from app.models import Deal, Item

logger = logging.getLogger("classify")

_BATCH = 20  # 한 번에 분류할 제목 수


def is_enabled() -> bool:
    return bool(get_settings().gemini_api_key)


async def classify_titles(titles: list[str]) -> list[str] | None:
    """제목 리스트 → 같은 길이의 카테고리 리스트(전부 CATEGORIES 안의 값).

    AI 비활성(키 없음)이거나 호출 자체가 실패하면 None을 반환한다(호출자가 키워드로 폴백).
    AI가 정상 응답해서 '기타'로 판단한 경우는 진짜 결과이므로 None이 아니라 '기타'를 반환한다.
    """
    if not titles:
        return []
    if not is_enabled():
        return None

    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    cats = ", ".join(CATEGORIES)
    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(titles))
    prompt = (
        f"다음 핫딜 제목들을 아래 카테고리 중 정확히 하나로 분류해. 애매하거나 해당 없으면 '기타'.\n"
        f"단어가 겹쳐도 실제 용도로 판단해(예: '초파리제로'는 살충제이지 제로음료가 아님).\n"
        f"카테고리: {cats}\n\n"
        f"제목 목록:\n{numbered}\n\n"
        f"출력은 입력과 같은 길이의 JSON 문자열 배열(카테고리명만, 순서대로). 다른 텍스트 금지."
    )
    cfg = types.GenerateContentConfig(response_mime_type="application/json")
    try:
        resp = await client.aio.models.generate_content(
            model=settings.gemini_model, contents=prompt, config=cfg
        )
        arr = json.loads(resp.text)
    except Exception as exc:
        logger.warning("AI 분류 실패, 키워드 폴백으로 전환: %s", exc)
        return None

    out = []
    for i in range(len(titles)):
        c = arr[i] if isinstance(arr, list) and i < len(arr) else "기타"
        out.append(c if c in CATEGORIES else "기타")
    return out


async def _set_category(session, deal: Deal, cat: str) -> None:
    deal.category = cat
    if deal.item_id is not None:  # 같은 상품이 분류를 공유하도록 Item에도 반영
        item = await session.get(Item, deal.item_id)
        if item is not None and not item.category:
            item.category = cat


async def _cached_item_category(session, deal: Deal) -> str | None:
    """같은 상품(Item)이 이전에 이미 분류됐으면 그 결과를 재사용(AI 호출 없이 무료).

    핫딜은 같은 상품이 여러 커뮤니티/시점에 재등록되는 경우가 흔해(normalized_key로
    Item 그룹핑), 매 재등록마다 AI를 다시 부르는 건 낭비다.
    """
    if deal.item_id is None:
        return None
    item = await session.get(Item, deal.item_id)
    return item.category if item and item.category else None


async def _classify_and_update(session, deals: list[Deal]) -> int:
    """아이템 캐시(무료) → AI(정확도) → AI 비활성/실패 시에만 키워드 규칙으로 폴백."""
    if not deals:
        return 0
    updated = 0

    need_ai: list[Deal] = []
    for d in deals:
        cached = await _cached_item_category(session, d)
        if cached:
            await _set_category(session, d, cached)
            updated += 1
        else:
            need_ai.append(d)

    if need_ai:
        cats = await classify_titles([d.title for d in need_ai])
        if cats is None:
            cats = [guess_category(d.title) for d in need_ai]
        for d, c in zip(need_ai, cats):
            if c:
                await _set_category(session, d, c)
                updated += 1

    await session.commit()
    return updated


async def classify_new(deal_ids: list[int]) -> int:
    """신규 수집 딜 중 미분류 처리(AI→규칙 폴백). 처리 건수 반환."""
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


_BACKFILL_PACE_SECONDS = 4  # 배치 간 대기(무료 티어 RPM 한도 보호). 캐시로 채워진 배치는 스킵.


async def classify_all() -> int:
    """기존 미분류 딜 전체 백필(관리자 CLI). id 커서로 전진해 중복/무한루프 방지.

    배치마다 AI를 호출할 수 있으므로(캐시 미스 시) 무료 티어 분당 요청 한도를 넘지 않도록
    배치 사이마다 짧게 대기한다.
    """
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
            if is_enabled():
                await asyncio.sleep(_BACKFILL_PACE_SECONDS)
    return total
