"""소스 파서 — 썸네일/글번호 추출, HTML 구조 파싱(구조 변경 회귀 방지)."""

from bs4 import BeautifulSoup

from app.sources.base import og_image
from app.sources.clien import ClienSource
from app.sources.ppomppu import PpomppuSource


def test_og_image_extraction_both_orders():
    # property→content 순서
    h1 = '<meta property="og:image" content="https://cdn/a.jpg"/>'
    assert og_image(h1) == "https://cdn/a.jpg"
    # content→property 순서
    h2 = "<meta content='https://cdn/b.jpg' property='og:image'>"
    assert og_image(h2) == "https://cdn/b.jpg"
    # 없으면 None
    assert og_image("<html>no og</html>") is None


def test_ppomppu_enrich_flag_on():
    # 뽐뿌는 RSS에 이미지가 없어 og:image 보강이 켜져 있어야 함
    assert PpomppuSource().enrich_thumbnail is True


def test_extract_post_id_ruliweb_style():
    src = PpomppuSource()
    # 링크에 숫자가 둘(게시판ID 1020, 글번호) → 마지막(글번호)만
    assert src.extract_post_id({"link": "https://bbs.ruliweb.com/market/board/1020/read/105126"}) == "105126"


def test_extract_thumbnail_priority():
    src = PpomppuSource()
    assert src.extract_thumbnail({"media_thumbnail": [{"url": "http://img/a.jpg"}]}) == "http://img/a.jpg"
    assert src.extract_thumbnail(
        {"enclosures": [{"type": "image/jpeg", "href": "http://img/b.jpg"}]}
    ) == "http://img/b.jpg"
    assert src.extract_thumbnail({"summary": '<a><img src="http://img/c.jpg" w=1></a> 본문'}) == "http://img/c.jpg"


def test_extract_thumbnail_none_when_absent():
    src = PpomppuSource()
    assert src.extract_thumbnail({"summary": "이미지 없는 본문"}) is None
    assert src.extract_thumbnail({}) is None


def test_extract_thumbnail_absolutizes_relative():
    # 쿨앤조이류 상대경로(/data/...)는 글 링크 기준 절대경로로 (실제로 잡았던 버그 회귀방지)
    src = PpomppuSource()
    e = {"link": "https://coolenjoy.net/bbs/jirum/123", "summary": '<img src="/data/editor/x.jpg">'}
    assert src.extract_thumbnail(e) == "https://coolenjoy.net/data/editor/x.jpg"
    # 절대경로는 그대로 유지
    e2 = {"link": "https://x/1", "media_thumbnail": [{"url": "https://cdn/a.jpg"}]}
    assert src.extract_thumbnail(e2) == "https://cdn/a.jpg"


# 클리앙 실제 구조 모사: 제목 앵커엔 클래스가 없고, 한 글에 앵커가 여러 개,
# 공지(notice) 행은 제외되어야 한다.
_CLIEN_HTML = """
<div class="list_item symph_row">
  <a href="/service/board/jirum/12345"><img src="//cdn.clien/x.jpg"></a>
  <a href="/service/board/jirum/12345">[쿠팡] 코카콜라 제로 30캔 (15,900원)</a>
</div>
<div class="list_item notice">
  <a href="/service/board/jirum/99999">공지글입니다</a>
</div>
<div class="list_item">
  <a href="/service/board/jirum/12346">[G마켓] 삼성 SSD 1TB</a>
</div>
"""


def test_clien_parse_extracts_and_skips_notice():
    deals = ClienSource().parse(BeautifulSoup(_CLIEN_HTML, "lxml"))
    ids = {d.source_post_id for d in deals}
    assert ids == {"12345", "12346"}            # 공지 99999 제외
    cola = next(d for d in deals if d.source_post_id == "12345")
    assert "코카콜라" in cola.title             # 빈 텍스트 썸네일 앵커가 아닌 제목 앵커 채택
    assert cola.price == 15900
    assert cola.url == "https://www.clien.net/service/board/jirum/12345"
    assert cola.thumbnail_url is not None       # 썸네일 추출


def test_clien_parse_handles_empty_html():
    # 구조가 완전히 바뀌어 매칭이 0이어도 예외 없이 빈 리스트
    assert ClienSource().parse(BeautifulSoup("<div>nothing</div>", "lxml")) == []
