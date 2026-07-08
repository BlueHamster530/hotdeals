"""카테고리 분류 백필 — 규칙 기반(캐시 → 키워드), 분류체계 일관성."""

from app.ingest import classify
from app.ingest.normalize import CATEGORIES, guess_category
from app.models import Deal, Item, Source


def test_taxonomy_has_etc_and_matches_rules():
    assert "기타" in CATEGORIES
    # 규칙 사전의 카테고리가 모두 분류체계에 포함
    from app.ingest.normalize import _CATEGORY_KEYWORDS
    for cat, _ in _CATEGORY_KEYWORDS:
        assert cat in CATEGORIES


async def test_classify_and_update_uses_keyword_rule(session):
    src = Source(slug="t", name="테스트", kind="rss", enabled=True)
    session.add(src)
    await session.flush()
    d = Deal(source_id=src.id, source_post_id="1", title="코카콜라 제로 30캔", url="http://x/1")
    session.add(d)
    await session.flush()

    updated = await classify._classify_and_update(session, [d])

    assert updated == 1
    assert d.category == guess_category("코카콜라 제로 30캔") == "제로음료"


async def test_classify_and_update_reuses_item_category(session):
    # 같은 상품(Item)이 이미 분류돼 있으면 재게시 딜은 그 값을 재사용한다.
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
    assert d.category == "생활용품"


async def test_classify_and_update_leaves_unmatched_null(session):
    # 규칙으로도 못 잡으면 미분류로 남는다(잘못된 값을 강제하지 않음)
    src = Source(slug="t", name="테스트", kind="rss", enabled=True)
    session.add(src)
    await session.flush()
    d = Deal(source_id=src.id, source_post_id="1", title="새청무 10kg 상등급", url="http://x/1")
    session.add(d)
    await session.flush()

    updated = await classify._classify_and_update(session, [d])

    assert updated == 0
    assert d.category is None
