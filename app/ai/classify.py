"""AI 카테고리 분류 (요구사항 2·4) — Gemini.

규칙(normalize.guess_category)으로 못 잡은 미분류 딜을 고정 분류체계 중 하나로 분류한다.
'새청무 10kg'처럼 품종명/신상품은 규칙 사전에 없으므로 AI가 폴백 처리.
Gemini 키가 없으면 전부 '기타'로 두고(비활성), 규칙 분류만 동작.
"""

from __future__ import annotations

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


async def classify_titles(titles: list[str]) -> list[str]:
    """제목 리스트 → 같은 길이의 카테고리 리스트(전부 CATEGORIES 안의 값)."""
    if not titles:
        return []
    if not is_enabled():
        return ["기타"] * len(titles)

    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    cats = ", ".join(CATEGORIES)
    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(titles))
    prompt = (
        f"다음 핫딜 제목들을 아래 카테고리 중 정확히 하나로 분류해. 애매하거나 해당 없으면 '기타'.\n"
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
        logger.warning("AI 분류 실패: %s", exc)
        return ["기타"] * len(titles)

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


async def _classify_and_update(session, deals: list[Deal]) -> int:
    """규칙 우선(무료) → 남은 것만 AI. AI 비활성이면 규칙으로 못 잡은 건 null로 둔다(나중에 키 넣으면 처리)."""
    if not deals:
        return 0
    updated = 0
    ai_needed: list[Deal] = []
    for d in deals:
        c = guess_category(d.title)
        if c:
            await _set_category(session, d, c)
            updated += 1
        else:
            ai_needed.append(d)

    if ai_needed and is_enabled():
        cats = await classify_titles([d.title for d in ai_needed])
        for d, c in zip(ai_needed, cats):
            await _set_category(session, d, c)
            updated += 1

    await session.commit()
    return updated


async def classify_new(deal_ids: list[int]) -> int:
    """신규 수집 딜 중 미분류 처리(규칙→AI). 처리 건수 반환."""
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
