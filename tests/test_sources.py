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
<div class="board-list">
  <a href="/hotdeal/710301234?sort_index=date&page=1">[쿠팡] 신라면 멀티팩 5개입 (3,900원/무배)</a>
  <a href="/hotdeal/710301235?sort_index=date&page=1">[11번가] 삼성 SSD 1TB 109,000원</a>
  <a href="/hotdeal/category/123">카테고리</a>
</div>
"""


def test_dogdrip_parse():
    deals = DogdripSource().parse(BeautifulSoup(_DOGDRIP_HTML, "lxml"))
    ids = {d.source_post_id for d in deals}
    assert ids == {"710301234", "710301235"}
    ramen = next(d for d in deals if d.source_post_id == "710301234")
    assert "신라면" in ramen.title
    assert ramen.price == 3900


# --- 아카라이브 ---

_ARCA_HTML = """
<div class="vrow hybrid">
  <div class="vrow-inner">
    <div class="vrow-top deal">
      <span class="vcol col-title">
        <span class="badges"><span class="deal-store">G마켓</span></span>
        <a class="title hybrid-title" href="/b/hotdeal/501234?p=1">
          <span class="media-icon"></span>신라면 5입+너구리 5입<span class="info"><span class="comment-count">[3]</span></span>
        </a>
      </span>
    </div>
    <a class="title hybrid-bottom" href="/b/hotdeal/501234?p=1">
      <div class="vrow-bottom deal"><span class="deal-price">13,470원</span></div>
    </a>
  </div>
  <a class="title preview-image" href="/b/hotdeal/501234?p=1">
    <div class="vrow-preview"><img src="//ac-p.namu.la/x.png"/></div>
  </a>
</div>
<div class="vrow hybrid notice">
  <div class="vrow-inner"><a class="title hybrid-title" href="/b/hotdeal/2?p=1">공지</a></div>
</div>
"""


def test_arca_parse():
    deals = ArcaSource().parse(BeautifulSoup(_ARCA_HTML, "lxml"))
    ids = {d.source_post_id for d in deals}
    assert ids == {"501234"}  # 공지 제외
    d = deals[0]
    assert d.price == 13470
    assert "[3]" not in d.title
    assert "신라면" in d.title
    assert "G마켓" in d.title
    assert d.thumbnail_url == "https://ac-p.namu.la/x.png"


# --- 퀘이사존 ---

_QZ_HTML = """
<div class="market-info-list-cont">
  <img src="https://img2.quasarzone.com/store/abc.png"/>
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
    assert ssd.thumbnail_url == "https://img2.quasarzone.com/store/abc.png"


# --- 펨코 ---

_FM_HTML = """
<li class="li li_best2_pop0">
  <div class="li">
    <a href="/912345678"><img class="thumb" src="//image.fmkorea.com/lazy/transparent.gif"
       data-original="//image.fmkorea.com/thumb/912345678_70x50.webp"/></a>
    <h3 class="title"><a class="hotdeal_var8" href="/912345678">
      <span class="ellipsis-target">에어팟 프로 2</span><span class="comment_count">[5]</span>
    </a></h3>
    <div class="hotdeal_info">
      <span>쇼핑몰: <a class="strong" href="#">쿠팡</a></span> /
      <span>가격: <a class="strong" href="#">249,000원</a></span> /
      <span>배송: <a class="strong" href="#">무료</a></span>
    </div>
  </div>
</li>
<li class="li li_best2_pop1">
  <div class="li">
    <h3 class="title"><a class="hotdeal_var8" href="/912345679">
      <span class="ellipsis-target">펩시 제로 24캔</span>
    </a></h3>
    <div class="hotdeal_info">
      <span>가격: <a class="strong" href="#">12,900원</a></span>
    </div>
  </div>
</li>
"""


def test_fmkorea_parse():
    deals = FmkoreaSource().parse(BeautifulSoup(_FM_HTML, "lxml"))
    assert len(deals) == 2
    airpod = next(d for d in deals if d.source_post_id == "912345678")
    assert airpod.price == 249000
    assert "에어팟" in airpod.title
    assert "[5]" not in airpod.title
    assert "쿠팡" in airpod.title
    assert airpod.thumbnail_url == "https://image.fmkorea.com/thumb/912345678_70x50.webp"


def test_all_parsers_handle_empty():
    empty = BeautifulSoup("<div></div>", "lxml")
    assert DogdripSource().parse(empty) == []
    assert ArcaSource().parse(empty) == []
    assert QuasarzoneSource().parse(empty) == []
    assert FmkoreaSource().parse(empty) == []
