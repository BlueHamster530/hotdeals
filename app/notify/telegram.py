"""텔레그램 연동 (httpx 직접 호출, 외부 봇 라이브러리 미사용).

- send_message: 알림 발송 (sendMessage)
- run_link_bot: 연결용 long-polling. /start <code> 를 받으면 해당 코드의 User에 chat_id를 연결.

보안: 토큰은 settings(.env)에서만 읽고 로그/응답에 노출하지 않는다.
"""

from __future__ import annotations

import logging

import httpx

from app import alarm
from app.config import get_settings
from app.db import SessionLocal

logger = logging.getLogger("telegram")

_API = "https://api.telegram.org/bot{token}/{method}"


def _enabled() -> bool:
    return bool(get_settings().telegram_bot_token)


async def send_message(chat_id: str, text: str, client: httpx.AsyncClient | None = None) -> bool:
    """텔레그램 메시지 발송. 성공 여부 반환."""
    settings = get_settings()
    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN 미설정 — 발송 건너뜀")
        return False

    url = _API.format(token=settings.telegram_bot_token, method="sendMessage")
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False}

    owns = client is None
    client = client or httpx.AsyncClient(timeout=15.0)
    try:
        resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            logger.warning("텔레그램 발송 실패 chat=%s status=%s", chat_id, resp.status_code)
            return False
        return True
    except Exception as exc:
        logger.warning("텔레그램 발송 예외 chat=%s: %s", chat_id, exc)
        return False
    finally:
        if owns:
            await client.aclose()


async def run_link_bot() -> None:
    """getUpdates long-polling 루프. /start <code> 처리. Ctrl+C로 종료."""
    settings = get_settings()
    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN 미설정 — 봇을 시작할 수 없음")
        return

    get_url = _API.format(token=settings.telegram_bot_token, method="getUpdates")
    offset: int | None = None
    logger.info("텔레그램 연결 봇 시작 (long-polling)")

    async with httpx.AsyncClient(timeout=40.0) as client:
        while True:
            try:
                params = {"timeout": 30, "allowed_updates": '["message"]'}
                if offset is not None:
                    params["offset"] = offset
                resp = await client.get(get_url, params=params)
                data = resp.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    msg = update.get("message") or {}
                    text = (msg.get("text") or "").strip()
                    chat_id = msg.get("chat", {}).get("id")
                    if chat_id is None:
                        continue

                    if text.startswith("/start"):
                        parts = text.split(maxsplit=1)
                        code = parts[1].strip() if len(parts) > 1 else ""
                        async with SessionLocal() as session:
                            ok = await alarm.mark_connected(session, code, str(chat_id)) if code else False
                        if ok:
                            await send_message(
                                str(chat_id),
                                "✅ 연결 완료! 웹의 <b>알림 설정</b> 화면으로 돌아가면 자동으로 켜져요. "
                                "이제 저장한 키워드 핫딜을 알려드릴게요.",
                                client,
                            )
                        else:
                            await send_message(
                                str(chat_id),
                                "안녕하세요! 알림은 <b>초대제</b>예요. 웹 <b>알림 설정</b>에서 초대코드로 "
                                "등록한 뒤 발급되는 연결코드로 다시 시도해 주세요.",
                                client,
                            )
            except Exception as exc:
                logger.warning("폴링 오류: %s", exc)
                await _sleep(3)


async def _sleep(sec: float) -> None:
    import asyncio

    await asyncio.sleep(sec)
