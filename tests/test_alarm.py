"""알림 보안 흐름 — 초대제, 1회용 토큰, 인증 (요구사항 10)."""

from app import alarm


async def test_invite_single_use(session):
    code = await alarm.mint_invite(session, "친구A")
    user = await alarm.consume_invite(session, code)
    assert user is not None and user.link_code

    # 같은 코드 재사용 차단
    assert await alarm.consume_invite(session, code) is None


async def test_invalid_invite_rejected(session):
    assert await alarm.consume_invite(session, "없는코드") is None


async def test_connect_and_token_flow(session):
    code = await alarm.mint_invite(session, None)
    user = await alarm.consume_invite(session, code)
    link = user.link_code

    # 연결 전에는 claim 불가
    assert await alarm.claim(session, link) is None

    # 텔레그램 연결 → auth_token 발급
    assert await alarm.mark_connected(session, link, "chat-123") is True

    token = await alarm.claim(session, link)
    assert token                                  # 토큰 수령
    assert await alarm.claim(session, link) is None  # 1회용(재수령 차단)


async def test_token_auth(session):
    code = await alarm.mint_invite(session, None)
    user = await alarm.consume_invite(session, code)
    await alarm.mark_connected(session, user.link_code, "chat-1")
    token = await alarm.claim(session, user.link_code)

    assert (await alarm.user_by_token(session, token)).id == user.id
    assert await alarm.user_by_token(session, "위조토큰") is None
    assert await alarm.user_by_token(session, None) is None
