"""커맨드라인 진입점.

  python -m app.cli init-db      # 테이블 생성
  python -m app.cli ingest       # 1회 수집
  python -m app.cli loop         # INGEST_INTERVAL_SECONDS 주기로 반복 수집
  python -m app.cli seed-demo    # 데모 데이터
  python -m app.cli bot          # 텔레그램 연결 봇 (long-polling)
  python -m app.cli invite [메모] # 알림 초대 코드 발급(관리자용)
  python -m app.cli classify      # 미분류 딜 AI 카테고리 백필
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from app.config import get_settings
from app.db import engine, SessionLocal
from app.ingest.pipeline import run_once
from app.models import Base
from app.seed_demo import seed as seed_demo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("cli")


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("테이블 생성 완료")


async def ingest_once() -> None:
    results = await run_once()
    total = sum(c for c in results.values() if c > 0)
    logger.info("수집 완료: 신규 %d건 %s", total, results)


async def loop() -> None:
    interval = get_settings().ingest_interval_seconds
    logger.info("loop 모드 시작 (%d초 주기). Ctrl+C로 종료.", interval)
    while True:
        try:
            await ingest_once()
        except Exception:
            logger.exception("수집 사이클 오류")
        await asyncio.sleep(interval)


async def classify_backfill() -> None:
    from app.ingest.classify import classify_all

    n = await classify_all()
    logger.info("분류 백필 완료: %d건", n)


async def mint_invite(label: str | None) -> None:
    from app.alarm import mint_invite as _mint

    async with SessionLocal() as session:
        code = await _mint(session, label)
    print(f"\n초대 코드: {code}" + (f"   (메모: {label})" if label else ""))
    print("→ 친구에게 전달하세요. 웹 '알림 설정'에서 이 코드를 입력하면 텔레그램 연결로 이어집니다.\n")


def main() -> None:
    parser = argparse.ArgumentParser(prog="hotdeals")
    parser.add_argument(
        "command",
        choices=["init-db", "ingest", "loop", "seed-demo", "bot", "invite", "classify"],
    )
    parser.add_argument("label", nargs="?", default=None, help="invite 명령용 메모(누구 것인지)")
    args = parser.parse_args()

    if args.command == "invite":
        asyncio.run(mint_invite(args.label))
        return
    if args.command == "classify":
        asyncio.run(classify_backfill())
        return

    from app.notify.telegram import run_link_bot

    runners = {
        "init-db": init_db,
        "ingest": ingest_once,
        "loop": loop,
        "seed-demo": seed_demo,
        "bot": run_link_bot,
    }
    asyncio.run(runners[args.command]())


if __name__ == "__main__":
    main()
