"""API 통합 — 공개 엔드포인트(무인증) + 알림(인증) + 챗봇 비활성."""

from app import alarm


async def test_healthz(api):
    client, _, _ = api
    r = await client.get("/healthz")
    assert r.status_code == 200 and r.json()["status"] == "ok"


async def test_deals_public_no_auth(api):
    client, _, _ = api
    r = await client.get("/api/deals")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    deal = body["deals"][0]
    assert "analysis" in deal
    assert "posted_at" in deal and "fetched_at" in deal  # 등록 시각 표시용


async def test_deals_search_and_filter(api):
    client, _, _ = api
    assert (await client.get("/api/deals", params={"q": "콜라"})).json()["count"] == 1
    assert (await client.get("/api/deals", params={"category": "전자기기"})).json()["count"] == 1


async def test_categories(api):
    client, _, _ = api
    assert (await client.get("/api/categories")).json()["categories"] == ["전자기기", "제로음료"]


async def test_chat_disabled_without_key(api):
    client, _, _ = api
    assert (await client.get("/api/chat/status")).json()["enabled"] is False
    r = await client.post("/api/chat", json={"messages": [{"role": "user", "content": "안녕"}]})
    assert r.status_code == 503


async def test_alarm_requires_auth(api):
    client, _, _ = api
    assert (await client.get("/api/alarm/keywords")).status_code == 401
    assert (
        await client.get("/api/alarm/keywords", headers={"Authorization": "Bearer bad-token"})
    ).status_code == 401


async def test_alarm_register_bad_invite(api):
    client, _, _ = api
    r = await client.post("/api/alarm/register", json={"invite_code": "없음"})
    assert r.status_code == 400


async def _connect_user(Sm, label="u"):
    """초대→연결까지 거쳐 auth_token을 만든 헬퍼."""
    async with Sm() as s:
        code = await alarm.mint_invite(s, label)
    async with Sm() as s:
        user = await alarm.consume_invite(s, code)
        link = user.link_code
    async with Sm() as s:
        await alarm.mark_connected(s, link, f"chat-{label}")
    async with Sm() as s:
        return await alarm.claim(s, link)


async def test_alarm_full_flow(api):
    client, Sm, _ = api
    token = await _connect_user(Sm, "me")
    h = {"Authorization": f"Bearer {token}"}

    assert (await client.get("/api/alarm/keywords", headers=h)).json()["keywords"] == []

    r = await client.post("/api/alarm/keywords", headers=h,
                          json={"keyword": "코카콜라 제로", "max_price": 16000, "min_rating": "great"})
    assert r.status_code == 200

    kws = (await client.get("/api/alarm/keywords", headers=h)).json()["keywords"]
    assert len(kws) == 1 and kws[0]["min_rating"] == "great" and kws[0]["max_price"] == 16000

    await client.delete(f"/api/alarm/keywords/{kws[0]['id']}", headers=h)
    assert (await client.get("/api/alarm/keywords", headers=h)).json()["keywords"] == []


async def test_alarm_cannot_delete_others_keyword(api):
    client, Sm, _ = api
    token_a = await _connect_user(Sm, "A")
    token_b = await _connect_user(Sm, "B")

    # B가 키워드 생성
    rb = await client.post("/api/alarm/keywords", headers={"Authorization": f"Bearer {token_b}"},
                           json={"keyword": "B의키워드"})
    kid = rb.json()["id"]

    # A가 B의 키워드 삭제 시도 → 무시되어야 함(본인것만 삭제)
    await client.delete(f"/api/alarm/keywords/{kid}", headers={"Authorization": f"Bearer {token_a}"})
    still = (await client.get("/api/alarm/keywords", headers={"Authorization": f"Bearer {token_b}"})).json()
    assert len(still["keywords"]) == 1   # 여전히 존재
