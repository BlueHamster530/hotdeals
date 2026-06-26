"""가격 분석 엔진 — 등급/점수/역대최저, 데이터 부족 처리, 등급 비교."""

from app.analysis.price_stats import analyze, meets_rating


def test_lowest_ever_is_great():
    a = analyze(14900, [18000, 17000, 19000, 16000, 14900])
    assert a.rating == "great"
    assert a.is_lowest_ever is True
    assert a.deal_score == 100
    assert a.discount_vs_avg_pct > 0


def test_expensive_is_poor():
    a = analyze(21000, [18000, 17000, 19000, 16000, 21000])
    assert a.rating == "poor"
    assert a.discount_vs_avg_pct < 0  # 평균보다 비쌈


def test_insufficient_samples_unknown():
    # 관측 3개 미만이면 등급을 매기지 않는다(섣부른 판단 방지)
    a = analyze(10000, [10000])
    assert a.rating == "unknown"
    assert a.verdict == "데이터 부족"


def test_no_price_unknown():
    a = analyze(None, [10000, 11000, 12000])
    assert a.rating == "unknown"


def test_all_same_price_no_crash():
    # 모든 가격이 동일해도 0으로 나누거나 깨지지 않아야 함
    a = analyze(10000, [10000, 10000, 10000])
    assert a.rating in {"great", "good", "normal", "poor"}
    assert a.min_price == a.max_price == 10000


def test_meets_rating_matrix():
    assert meets_rating("great", "good") is True
    assert meets_rating("good", "good") is True
    assert meets_rating("good", "great") is False
    assert meets_rating("normal", "good") is False
    assert meets_rating("poor", None) is True   # 조건 없으면 항상 통과
    assert meets_rating("unknown", "good") is False
