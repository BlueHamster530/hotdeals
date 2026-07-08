"""AI 분류 — AI 우선, 비활성(키 없음)/실패 시 키워드 폴백, 분류체계 일관성."""

from app.ai import classify
from app.ingest.normalize import CATEGORIES, guess_category
from app.models import Deal, Source


def test_taxonomy_has_etc_and_matches_rules():
    assert "기타" in CATEGORIES
    # 규칙 사전의 카테고리가 모두 분류체계에 포함
    from app.ingest.normalize import _CATEGORY_KEYWORDS
    for cat, _ in _CATEGORY_KEYWORDS:
        assert cat in CATEGORIES


async def test_classify_disabled_returns_none():
    # GEMINI_API_KEY 미설정이면 None(호출자가 키워드로 폴백)
    assert classify.is_enabled() is False
    assert await classify.classify_titles(["새청무 10kg", "아무거나"]) is None


async def test_classify_empty():
    assert await classify.classify_titles([]) == []


async def test_classify_and_update_falls_back_to_keyword_when_ai_disabled(session):
    # AI 비활성 상태에서도 _classify_and_update는 키워드 규칙으로 분류를 채운다(저비용 캐시 경로)
    assert classify.is_enabled() is False
    src = Source(slug="t", name="테스트", kind="rss", enabled=True)
    session.add(src)
    await session.flush()
    d = Deal(source_id=src.id, source_post_id="1", title="코카콜라 제로 30캔", url="http://x/1")
    session.add(d)
    await session.flush()

    updated = await classify._classify_and_update(session, [d])

    assert updated == 1
    assert d.category == guess_category("코카콜라 제로 30캔") == "제로음료"
