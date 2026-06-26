"""AI 분류 — 비활성(키 없음) 폴백, 분류체계 일관성."""

from app.ai import classify
from app.ingest.normalize import CATEGORIES


def test_taxonomy_has_etc_and_matches_rules():
    assert "기타" in CATEGORIES
    # 규칙 사전의 카테고리가 모두 분류체계에 포함
    from app.ingest.normalize import _CATEGORY_KEYWORDS
    for cat, _ in _CATEGORY_KEYWORDS:
        assert cat in CATEGORIES


async def test_classify_disabled_returns_etc():
    # GEMINI_API_KEY 미설정이면 전부 '기타'(규칙만 동작, AI 폴백 off)
    assert classify.is_enabled() is False
    assert await classify.classify_titles(["새청무 10kg", "아무거나"]) == ["기타", "기타"]


async def test_classify_empty():
    assert await classify.classify_titles([]) == []
