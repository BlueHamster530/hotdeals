"""알림 매처. 신규 딜을 저장된 키워드와 대조해 조건 통과 시 텔레그램 발송.

조건: (1) 키워드가 제목에 포함  (2) max_price 이하(설정 시)  (3) min_rating 이상(설정 시).
중복 발송은 notifications 테이블(keyword_id, deal_id 유니크)로 방지.
"""

from __future__ import annotations

import html
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.price_stats import analyze, meets_rating
from app.analysis.service import histories_for_items
from app.config import get_settings
from app.db import SessionLocal
from app.models import Deal, Keyword, Notification, Source, User
from app.notify.telegram import send_message

logger = logging.getLogger("matcher")


def _format(deal: Deal, source: str, analysis) -> str:
    title = html.escape(deal.title)
    src = html.escape(source)
    lines = [f"🔥 <b>{html.escape(analysis.verdict)}</b>"]
    if analysis.deal_score is not None:
        lines[0] += f" · {analysis.deal_score}점"
    lines.append(title)
    if deal.price is not None:
        price_line = f"💰 {deal.price:,}원"
        if analysis.discount_vs_avg_pct is not None and analysis.discount_vs_avg_pct > 0:
            price_line += f" (평균 대비 {analysis.discount_vs_avg_pct}%↓)"
        if analysis.min_price is not None:
            price_line += f" · 역대최저 {analysis.min_price:,}원"
        lines.append(price_line)
    lines.append(f"[{src}] <a href=\"{html.escape(deal.url)}\">원문 보기</a>")
    return "\n".join(lines)


async def process_new_deals(deal_ids: list[int]) -> int:
    """신규 딜들에 대해 알림 매칭+발송. 발송 건수 반환."""
    if not deal_ids or not get_settings().telegram_bot_token:
        return 0

    async with SessionLocal() as session:
        kw_rows = (
            await session.execute(
                select(Keyword, User.telegram_chat_id)
                .join(User, User.id == Keyword.user_id)
                .where(Keyword.enabled.is_(True), User.telegram_chat_id.is_not(None))
            )
        ).all()
        if not kw_rows:
            return 0

        deal_rows = (
            await session.execute(
                select(Deal, Source.name)
                .join(Source, Source.id == Deal.source_id)
                .where(Deal.id.in_(deal_ids))
            )
        ).all()
        item_ids = [d.item_id for d, _ in deal_rows if d.item_id is not None]
        histories = await histories_for_items(session, item_ids)

        sent = 0
        async with httpx.AsyncClient(timeout=15.0) as client:
            for deal, source_name in deal_rows:
                history = histories.get(deal.item_id or -1, [])
                analysis = analyze(deal.price, history)
                title_low = deal.title.lower()

                for kw, chat_id in kw_rows:
                    if kw.keyword.lower() not in title_low:
                        continue
                    if kw.max_price is not None and (deal.price is None or deal.price > kw.max_price):
                        continue
                    if not meets_rating(analysis.rating, kw.min_rating):
                        continue

                    # 중복 방지: 먼저 기록 시도, 이미 있으면 건너뜀
                    ins = (
                        pg_insert(Notification)
                        .values(keyword_id=kw.id, deal_id=deal.id)
                        .on_conflict_do_nothing(index_elements=["keyword_id", "deal_id"])
                        .returning(Notification.id)
                    )
                    if (await session.execute(ins)).first() is None:
                        continue

                    if await send_message(chat_id, _format(deal, source_name, analysis), client):
                        sent += 1
            await session.commit()

    if sent:
        logger.info("텔레그램 알림 %d건 발송", sent)
    return sent
