"""데모 데이터 시드. 외부 네트워크 없이 API/분석을 바로 확인하기 위한 용도.

  python -m app.cli seed-demo

실제 수집 데이터와 섞이지 않도록 'demo' 소스로만 넣는다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.ingest.normalize import normalized_key
from app.models import Deal, Item, PriceHistory, Source

# (상품명, 카테고리, [과거가격...], 현재가)
_DEMO = [
    ("코카콜라 제로 190ml 30캔", "제로음료",
     [18900, 17500, 19000, 16900, 18000, 17900, 16500], 14900),   # 역대 최저가
    ("삼성 980 PRO 1TB SSD", "전자기기",
     [129000, 119000, 135000, 112000, 121000, 109000], 115000),    # 좋은 편
    ("펩시 제로라임 355ml 24캔", "제로음료",
     [13900, 12900, 14500, 13500, 12900], 13500),                  # 평범
    ("LG 27인치 모니터", "전자기기",
     [199000, 189000, 209000, 179000], 215000),                    # 비싼 편
]


async def seed() -> None:
    async with SessionLocal() as session:
        # demo 소스 보장
        src = (await session.execute(select(Source).where(Source.slug == "demo"))).scalar_one_or_none()
        if src is None:
            src = Source(slug="demo", name="데모", kind="rss", enabled=False)
            session.add(src)
            await session.flush()

        # 기존 demo 딜 정리(멱등)
        await session.execute(delete(Deal).where(Deal.source_id == src.id))

        base = datetime.now(timezone.utc)
        post_no = 0
        for name, category, past_prices, current in _DEMO:
            key = normalized_key(name)
            item = (await session.execute(select(Item).where(Item.normalized_key == key))).scalar_one_or_none()
            if item is None:
                item = Item(normalized_key=key, display_name=name, category=category)
                session.add(item)
                await session.flush()

            # 과거 가격 이력
            for i, p in enumerate(past_prices):
                session.add(
                    PriceHistory(
                        item_id=item.id, deal_id=None, price=p,
                        observed_at=base - timedelta(days=len(past_prices) - i),
                    )
                )

            # 현재 딜 + 현재가 이력
            post_no += 1
            deal = Deal(
                source_id=src.id, item_id=item.id, source_post_id=f"demo-{post_no}",
                title=f"[데모] {name} ({current:,}원)", url=f"https://example.com/demo/{post_no}",
                price=current, category=category, posted_at=base,
            )
            session.add(deal)
            await session.flush()
            session.add(PriceHistory(item_id=item.id, deal_id=deal.id, price=current, observed_at=base))

        await session.commit()
    print("데모 데이터 시드 완료 (소스: demo)")
