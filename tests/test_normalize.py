"""가격/카테고리/매칭키 파싱 — 핫딜 제목의 다양한 형식 + 흔한 함정."""

import pytest

from app.ingest.normalize import guess_category, normalized_key, parse_price


@pytest.mark.parametrize(
    "title, expected",
    [
        ("[G마켓] 코카콜라 제로 190ml 30캔 (15,900원/무료배송)", 15900),
        ("[쿠팡] 삼성 980 PRO 1TB SSD (109,000/무료)", 109000),
        ("[11번가] 펩시 제로라임 355ml 24캔 12900원", 12900),
        ("[네이버] 캐리어 스탠드 에어컨 (카드942,270원/무배)", 942270),
        ("[행사] 사은품 증정 무료배송", None),          # 가격 없음
        ("KT 알뜰폰 0원 요금제", None),                  # 0원/소액은 가격으로 안 봄
        ("커피 990원 특가", None),                       # 1000원 미만 무시
    ],
)
def test_parse_price(title, expected):
    assert parse_price(title) == expected


def test_parse_price_picks_largest_when_no_bracket():
    # 배송비 같은 작은 수에 휘둘리지 않고 최댓값(=상품가)을 택한다
    assert parse_price("상품 35000원 배송비 3000원") == 35000


@pytest.mark.parametrize(
    "title, category",
    [
        ("코카콜라 제로 30캔", "제로음료"),
        ("삼성 980 PRO SSD", "전자기기"),
        ("KT 알뜰폰 유심 요금제", "통신"),
        ("스타벅스 원두 1kg", "커피/차"),
        ("LG 트롬 세탁기", "가전"),
        ("아이오페 에센스 세트", "뷰티"),
        ("나이키 운동화 270", "패션"),
        ("종근당 비타민D 영양제", "건강"),
        ("로얄캐닌 강아지 사료 2kg", "반려동물"),
        ("부사 사과 5kg 가정용", "식품"),
        ("무설명 일반 상품", None),
        # 품종명은 규칙으론 못 잡음 → None (AI 분류가 폴백)
        ("[지마켓] 새청무 10kg 상등급", None),
    ],
)
def test_guess_category(title, category):
    assert guess_category(title) == category


def test_normalized_key_strips_shop_and_brackets():
    # 쇼핑몰 태그·괄호·가격·기호 제거 후 소문자 → 같은 상품 묶기용 키
    k1 = normalized_key("[쿠팡] 코카콜라 제로 30캔 (15,900원)")
    k2 = normalized_key("[G마켓] 코카콜라 제로 30캔 (14,900원/무료)")
    assert k1 == k2  # 쇼핑몰/가격이 달라도 같은 상품 → 같은 키
    assert "쿠팡" not in k1 and "원" not in k1
