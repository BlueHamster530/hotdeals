"""소스 파서 — 글번호 추출, HTML 구조 파싱(구조 변경 회귀 방지)."""

from bs4 import BeautifulSoup

from app.sources.arca import ArcaSource
from app.sources.clien import ClienSource
from app.sources.dogdrip import DogdripSource
from app.sources.fmkorea import FmkoreaSource
from app.sources.ppomppu import PpomppuSource
from app.sources.quasarzone import QuasarzoneSource


def test_extract_post_id_ruliweb_style():
    src = PpomppuSource()
    assert src.extract_post_id({"link": "https://bbs.ruliweb.com/market/board/1020/read/105126"}) == "105126"


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
    assert ids == {"12345", "12346"}
    cola = next(d for d in deals if d.source_post_id == "12345")
    assert "코카콜라" in cola.title
    assert cola.price == 15900
    assert cola.url == "https://www.clien.net/service/board/jirum/12345"


def test_clien_parse_handles_empty_html():
    assert ClienSource().parse(BeautifulSoup("<div>nothing</div>", "lxml")) == []


# --- 개드립 ---

_DOGDRIP_HTML = """
<a class="title" href="/hotdeal/301234">[쿠팡] 신라면 멀티팩 5개입 (3,900원/무배)</a>
<a class="title" href="/hotdeal/301235">[11번가] 삼성 SSD 1TB 109,000원</a>
<a class="other" href="/hotdeal/999">광고글</a>
"""


def test_dogdrip_parse():
    deals = DogdripSource().parse(BeautifulSoup(_DOGDRIP_HTML, "lxml"))
    ids = {d.source_post_id for d in deals}
    assert ids == {"301234", "301235"}
    ramen = next(d for d in deals if d.source_post_id == "301234")
    assert "신라면" in ramen.title
    assert ramen.price == 3900


# --- 아카라이브 ---

_ARCA_HTML = """
<a class="vrow column" href="/b/hotdeal/501234">
  <span class="title">[쿠팡] 코카콜라 제로 30캔 (15,900원)</span>
  <span class="deal-price">15,900원</span>
</a>
<a class="vrow column" href="/b/hotdeal/501235">
  <span class="title">[G마켓] LG 모니터 27인치</span>
</a>
<a class="vrow column" href="/b/notice/1">
  <span class="title">공지사항</span>
</a>
"""


def test_arca_parse():
    deals = ArcaSource().parse(BeautifulSoup(_ARCA_HTML, "lxml"))
    ids = {d.source_post_id for d in deals}
    assert ids == {"501234", "501235"}
    cola = next(d for d in deals if d.source_post_id == "501234")
    assert cola.price == 15900


# --- 퀘이사존 ---

_QZ_HTML = """
<div class="market-info-list-cont">
  <a class="subject-link" href="/bbs/qb_saleinfo/views/601234">
    <span class="ellipsis-with-reply-cnt">[쿠팡] 삼성 980 PRO SSD (109,000원)</span>
  </a>
  <span class="text-orange">109,000원</span>
</div>
<div class="market-info-list-cont">
  <a class="subject-link" href="/bbs/qb_saleinfo/views/601235">
    <span class="ellipsis-with-reply-cnt">닌텐도 스위치 OLED</span>
  </a>
</div>
"""


def test_quasarzone_parse():
    deals = QuasarzoneSource().parse(BeautifulSoup(_QZ_HTML, "lxml"))
    assert len(deals) == 2
    ssd = next(d for d in deals if d.source_post_id == "601234")
    assert ssd.price == 109000


# --- 펨코 ---

_FM_HTML = """
<li class="li_best2_pop0">
  <h3 class="title"><a href="/912345678">[쿠팡] 에어팟 프로 2 (249,000원)</a></h3>
</li>
<li class="li_best2_pop1">
  <h3 class="title"><a href="/912345679">펩시 제로 24캔 12,900원</a></h3>
</li>
"""


def test_fmkorea_parse():
    deals = FmkoreaSource().parse(BeautifulSoup(_FM_HTML, "lxml"))
    assert len(deals) == 2
    airpod = next(d for d in deals if d.source_post_id == "912345678")
    assert airpod.price == 249000


def test_all_parsers_handle_empty():
    empty = BeautifulSoup("<div></div>", "lxml")
    assert DogdripSource().parse(empty) == []
    assert ArcaSource().parse(empty) == []
    assert QuasarzoneSource().parse(empty) == []
    assert FmkoreaSource().parse(empty) == []
