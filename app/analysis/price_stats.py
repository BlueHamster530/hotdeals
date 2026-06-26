"""가격 분석 엔진 (요구사항 7의 핵심).

상품의 과거 관측가 분포 안에서 '현재가가 어디쯤인지'를 계산해
사용자가 '진짜 싼지 / 평균 할인인지 / 별로인지'를 한눈에 알게 한다.

순수 함수라 DB 없이 단독 테스트 가능. 색상은 의미 토큰만 반환하고
실제 색은 프론트가 매핑한다(관심사 분리).
"""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass

# price_position(역대가 중 현재가가 싼 정도) 구간별 등급 경계
_GREAT = 0.15   # 하위 15% 이하 → 역대급
_GOOD = 0.40
_NORMAL = 0.70

# 등급 판정에 필요한 최소 관측 수
MIN_SAMPLES = 3

# 등급 순위 (높을수록 좋은 딜). 알림 조건 비교에 사용.
RATING_RANK = {"unknown": -1, "poor": 0, "normal": 1, "good": 2, "great": 3}


def meets_rating(rating: str, minimum: str | None) -> bool:
    """deal의 rating이 최소 요구 등급(minimum) 이상인지. minimum이 None이면 항상 True."""
    if not minimum:
        return True
    return RATING_RANK.get(rating, -1) >= RATING_RANK.get(minimum, 99)


@dataclass(slots=True)
class PriceAnalysis:
    sample_size: int
    current_price: int | None
    min_price: int | None
    max_price: int | None
    avg_price: float | None
    median_price: float | None
    discount_vs_avg_pct: float | None   # 평균가 대비 할인율(%) — 양수면 평균보다 쌈
    price_position: float | None        # 0=역대 최저 수준, 1=역대 최고 수준
    deal_score: int | None              # 0~100, 높을수록 좋은 딜
    is_lowest_ever: bool
    verdict: str                        # 사용자 표시 문구(한국어)
    rating: str                         # great | good | normal | poor | unknown

    def to_dict(self) -> dict:
        return asdict(self)


def _verdict(rating: str, is_lowest: bool) -> str:
    if is_lowest:
        return "역대 최저가 🔥"
    return {
        "great": "역대급 특가",
        "good": "좋은 가격",
        "normal": "평범한 가격",
        "poor": "비싼 편",
    }[rating]


def analyze(current_price: int | None, history_prices: list[int]) -> PriceAnalysis:
    """현재가와 과거 관측가 목록으로 분석 결과를 만든다.

    history_prices 는 현재가를 포함한 모든 관측가여도 된다(현재가는 '더 싼 비율' 계산에서 제외됨).
    """
    prices = [p for p in history_prices if p and p > 0]
    n = len(prices)

    if current_price is None or current_price <= 0 or n < MIN_SAMPLES:
        return PriceAnalysis(
            sample_size=n,
            current_price=current_price,
            min_price=min(prices) if prices else None,
            max_price=max(prices) if prices else None,
            avg_price=round(statistics.fmean(prices), 1) if prices else None,
            median_price=statistics.median(prices) if prices else None,
            discount_vs_avg_pct=None,
            price_position=None,
            deal_score=None,
            is_lowest_ever=bool(prices) and current_price is not None and current_price <= min(prices),
            verdict="데이터 부족",
            rating="unknown",
        )

    mn, mx = min(prices), max(prices)
    avg = statistics.fmean(prices)
    med = statistics.median(prices)

    # 현재가보다 싼 관측 비율 → 0이면 역대 최저 수준, 1이면 역대 최고 수준
    cheaper = sum(1 for p in prices if p < current_price)
    position = cheaper / n
    discount = (avg - current_price) / avg * 100
    score = round((1 - position) * 100)
    is_lowest = current_price <= mn

    if is_lowest or position <= _GREAT:
        rating = "great"
    elif position <= _GOOD:
        rating = "good"
    elif position <= _NORMAL:
        rating = "normal"
    else:
        rating = "poor"

    return PriceAnalysis(
        sample_size=n,
        current_price=current_price,
        min_price=mn,
        max_price=mx,
        avg_price=round(avg, 1),
        median_price=med,
        discount_vs_avg_pct=round(discount, 1),
        price_position=round(position, 3),
        deal_score=score,
        is_lowest_ever=is_lowest,
        verdict=_verdict(rating, is_lowest),
        rating=rating,
    )
