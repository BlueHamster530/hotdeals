"""AI 분류 — AI 우선, 비활성(키 없음)/실패 시 키워드 폴백, 분류체계 일관성."""

from app.ai import classify
from app.ingest.normalize import CATEGORIES, guess_category
from app.models import Deal, Item, Source


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


async def test_classify_and_update_reuses_item_category_without_ai_call(session):
    # 같은 상품(Item)이 이미 분류돼 있으면 재게시 딜은 AI/키워드 호출 없이 그 값을 재사용한다.
    # 제목에 '제로'가 있어 키워드 규칙이라면 '제로음료'로 잘못 잡겠지만, 캐시가 우선이어야 한다.
    src = Source(slug="t", name="테스트", kind="rss", enabled=True)
    item = Item(normalized_key="k1", display_name="초파리제로", category="생활용품")
    session.add_all([src, item])
    await session.flush()
    d = Deal(source_id=src.id, item_id=item.id, source_post_id="1",
              title="초파리제로 살충제 2개입", url="http://x/1")
    session.add(d)
    await session.flush()

    updated = await classify._classify_and_update(session, [d])

    assert updated == 1
    assert d.category == "생활용품"  # 캐시 재사용, 키워드 오분류(제로음료) 아님
