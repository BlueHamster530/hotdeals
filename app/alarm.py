"""알림 계정·인증 헬퍼 (요구사항 3·10).

초대제 + 텔레그램 연결 흐름:
  mint_invite(관리자 CLI) → consume_invite(초대코드→연결코드 발급)
  → mark_connected(봇 /start: chat_id 연결 + auth_token 발급)
  → claim(웹이 auth_token 1회 수령) → user_by_token(이후 Bearer 인증)

신원은 추측 가능한 user_id가 아니라 비밀 auth_token으로 한다.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Invite, User


async def mint_invite(session: AsyncSession, label: str | None = None) -> str:
    """초대 코드 발급(관리자). 코드 문자열 반환."""
    code = secrets.token_urlsafe(6)
    session.add(Invite(code=code, label=label))
    await session.commit()
    return code


async def consume_invite(session: AsyncSession, code: str) -> User | None:
    """유효한(미사용) 초대코드면 사용자 생성 + 연결코드 발급. 아니면 None."""
    inv = (await session.execute(select(Invite).where(Invite.code == code))).scalar_one_or_none()
    if inv is None or inv.used_by_user_id is not None:
        return None

    user = User(link_code=secrets.token_urlsafe(8))
    session.add(user)
    await session.flush()  # user.id 확보
    inv.used_by_user_id = user.id
    inv.used_at = datetime.now(timezone.utc)
    await session.commit()
    return user


async def mark_connected(session: AsyncSession, link_code: str, chat_id: str) -> bool:
    """봇 /start <link_code>: chat_id 연결 + auth_token 발급(없으면). 성공 시 True."""
    user = (await session.execute(select(User).where(User.link_code == link_code))).scalar_one_or_none()
    if user is None:
        return False
    user.telegram_chat_id = str(chat_id)
    if not user.auth_token:
        user.auth_token = secrets.token_urlsafe(32)
    await session.commit()
    return True


async def claim(session: AsyncSession, link_code: str) -> str | None:
    """웹이 연결 완료를 확인하고 auth_token을 1회 수령. 연결 전이면 None."""
    user = (await session.execute(select(User).where(User.link_code == link_code))).scalar_one_or_none()
    if user is None or user.telegram_chat_id is None or not user.auth_token:
        return None
    token = user.auth_token
    user.link_code = None  # 1회용: 수령 후 무효화
    await session.commit()
    return token


async def user_by_token(session: AsyncSession, token: str | None) -> User | None:
    if not token:
        return None
    return (
        await session.execute(select(User).where(User.auth_token == token))
    ).scalar_one_or_none()
