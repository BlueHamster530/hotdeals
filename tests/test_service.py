"""DB 서비스 — 검색/필터/상세/카테고리/배치조회 + 분석 연동."""

from app.analysis import service


async def test_list_deals_attaches_analysis(seeded):
    session, ids = seeded
    deals = await service.list_deals(session)
    assert len(deals) == 2
    cola = next(d for d in deals if d["item_id"] == ids["i1"])
    assert cola["analysis"]["rating"] == "great"          # 역대최저
    assert cola["analysis"]["is_lowest_ever"] is True


async def test_search_filters_by_keyword(seeded):
    session, _ = seeded
    res = await service.list_deals(session, q="콜라")
    assert len(res) == 1 and "콜라" in res[0]["title"]


async def test_search_no_match_returns_empty(seeded):
    session, _ = seeded
    assert await service.list_deals(session, q="존재하지않는상품") == []


async def test_category_filter(seeded):
    session, _ = seeded
    res = await service.list_deals(session, category="전자기기")
    assert len(res) == 1 and res[0]["category"] == "전자기기"


async def test_special_chars_in_query_do_not_crash(seeded):
    # LIKE 와일드카드(%/_)나 따옴표가 와도 파라미터 바인딩이라 안전(SQL injection 방지)
    session, _ = seeded
    for q in ["100%", "a_b", "'; DROP TABLE deals;--"]:
        res = await service.list_deals(session, q=q)
        assert isinstance(res, list)


async def test_item_detail(seeded):
    session, ids = seeded
    detail = await service.item_detail(session, ids["i1"])
    assert detail["display_name"].startswith("코카콜라")
    assert len(detail["price_history"]) == 7              # 과거6 + 현재1
    assert detail["analysis"]["rating"] == "great"
    assert detail["recent_deals"]                         # 같은 상품 최근 딜


async def test_item_detail_missing_returns_none(seeded):
    session, _ = seeded
    assert await service.item_detail(session, 999999) is None


async def test_list_categories_sorted_distinct(seeded):
    session, _ = seeded
    assert await service.list_categories(session) == ["전자기기", "제로음료"]


async def test_histories_for_items_batch(seeded):
    session, ids = seeded
    h = await service.histories_for_items(session, [ids["i1"], ids["i2"]])
    assert len(h[ids["i1"]]) == 7
    assert h[ids["i2"]] == [109000]
