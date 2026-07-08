"""가격/카테고리/매칭키 파싱 — 핫딜 제목의 다양한 형식 + 흔한 함정."""

import pytest

from app.ingest.normalize import (
    guess_category,
    normalized_key,
    parse_price,
    resolve_category,
    should_collect,
)


@pytest.mark.parametrize(
    "slug, source_cat, expected",
    [
        # 소스 카테고리가 고신뢰로 매핑됨
        ("arca", "food", "식품"),
        ("arca", "elec", "전자기기"),
        ("arca", "game", "게임"),
        ("quasarzone", "가전/TV", "가전"),
        ("fmkorea", "가전제품", "가전"),
        # 루리웹 RSS <category>(글쓴이가 직접 지정, 라이브 확인됨)
        ("ruliweb", "상품권", "상품권/쿠폰"),
        ("ruliweb", "음식", "식품"),
        ("ruliweb", "게임S/W", "게임"),
        ("ruliweb", "게임H/W", "게임"),
        # 매핑에 없는 카테고리·소스 카테고리 없음 → None (제목 키워드 추측은 여기서 안 함,
        # 수집 후 app/ingest/classify.py가 일괄 처리)
        ("quasarzone", "생활/식품", None),
        ("ruliweb", "취미용품", None),
        ("arca", None, None),
        ("ppomppu", None, None),
    ],
)
def test_resolve_category(slug, source_cat, expected):
    assert resolve_category(slug, source_cat) == expected


@pytest.mark.parametrize(
    "title, price, expected",
    [
        ("[쿠팡] 신라면 5개입 (3,900원)", 3900, True),      # 가격 있음 → 수집
        ("[네이버페이] 일일적립 43원", None, True),          # 무가격이지만 네이버페이 예외
        ("네이버 페이 클릭적립", None, True),                # 띄어쓴 변형도 예외
        ("오늘의집 이번주 핫딜 선공개", None, False),        # 무가격 → 제외
        ("무료 사은품 증정 이벤트", None, False),            # 무가격 → 제외
        ("KT 알뜰폰 0원 요금제", 0, False),                  # 0원 → 제외
    ],
)
def test_should_collect(title, price, expected):
    assert should_collect(title, price) is expected


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
        ("KT 알뜰폰 유심 요금제", "요금제"),
        ("SK텔레콤 5G 다이렉트요금제", "요금제"),
        ("스팀 겨울 세일 인기 게임 번들", "게임"),
        ("스타벅스 원두 1kg", "커피/차"),
        ("LG 트롬 세탁기", "가전"),
        ("아이오페 에센스 세트", "뷰티"),
        ("나이키 운동화 270", "패션"),
        ("종근당 비타민D 영양제", "건강"),
        ("로얄캐닌 강아지 사료 2kg", "반려동물"),
        ("부사 사과 5kg 가정용", "식품"),
        ("무설명 일반 상품", None),
        # 브랜드명이 들어가도 잡화/굿즈면 음료로 오분류하지 않음 (실제 잡았던 버그)
        ("[KREAM] 코카콜라 폴딩 스토리지 박스 캠핑 수납함", "생활용품"),
        ("코카콜라 굿즈 텀블러 470ml", "생활용품"),
        # '제로'가 들어가도 살충제면 제로음료로 오분류하지 않음 (실제 잡았던 버그)
        ("[홈플러스] 초파리제로 살충제 2개입", "생활용품"),
        # 'lte'/'5g'/'데이터'는 스마트폰·공유기 스펙에도 흔해 요금제로 오분류하지 않음
        # (실제 잡았던 버그: 전자기기 제목이 요금제로 잘못 분류됨)
        ("갤럭시 S25 5G 256GB 자급제 언락", "전자기기"),
        ("샌디스크 데이터 백업용 SSD 1TB", "전자기기"),
        ("5G 라우터 무선 공유기", "전자기기"),
        # 품종명은 규칙으론 못 잡음 → None (미분류로 남고, 키워드 사전 보강 시 소급 적용됨)
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
