"""AI 분류 — 규칙 우선(무료), 애매한 것만 AI 폴백, 분류체계 일관성."""

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
    # GEMINI_API_KEY 미설정이면 None(호출자가 미분류로 남겨 다음 기회에 재시도)
    assert classify.is_enabled() is False
    assert await classify.classify_titles(["새청무 10kg", "아무거나"]) is None


async def test_classify_empty():
    assert await classify.classify_titles([]) == []


async def test_classify_and_update_uses_keyword_rule_without_ai(session):
    # 키워드로 잡히는 제목은 AI 호출 없이 규칙만으로 무료 분류된다.
    assert classify.is_enabled() is False
    src = Source(slug="t", name="테스트", kind="rss", enabled=True)
    session.add(src)
    await session.flush()
    d = Deal(source_id=src.id, source_post_id="1", title="코카콜라 제로 30캔", url="http://x/1")
    session.add(d)
    await session.flush()

    updated, ai_called = await classify._classify_and_update(session, [d])

    assert updated == 1
    assert ai_called is False
    assert d.category == guess_category("코카콜라 제로 30캔") == "제로음료"


async def test_classify_and_update_reuses_item_category_without_ai_call(session):
    # 같은 상품(Item)이 이미 분류돼 있으면 재게시 딜은 규칙/AI 호출 없이 그 값을 재사용한다.
    src = Source(slug="t", name="테스트", kind="rss", enabled=True)
    item = Item(normalized_key="k1", display_name="초파리제로", category="생활용품")
    session.add_all([src, item])
    await session.flush()
    d = Deal(source_id=src.id, item_id=item.id, source_post_id="1",
              title="초파리제로 살충제 2개입", url="http://x/1")
    session.add(d)
    await session.flush()

    updated, ai_called = await classify._classify_and_update(session, [d])

    assert updated == 1
    assert ai_called is False
    assert d.category == "생활용품"


async def test_classify_and_update_leaves_unmatched_null_when_ai_disabled(session):
    # 규칙으로도 못 잡고 AI도 비활성이면 미분류로 남는다(다음 기회에 재시도, 잘못된 값 강제 X)
    assert classify.is_enabled() is False
    src = Source(slug="t", name="테스트", kind="rss", enabled=True)
    session.add(src)
    await session.flush()
    d = Deal(source_id=src.id, source_post_id="1", title="새청무 10kg 상등급", url="http://x/1")
    session.add(d)
    await session.flush()

    updated, ai_called = await classify._classify_and_update(session, [d])

    assert updated == 0
    assert ai_called is False
    assert d.category is None
