"""아카라이브 핫딜 채널 HTML 스크래퍼.

⚠️ 검증 필요: 아래 selector는 arca.live/b/hotdeal의 일반적인 DOM 구조 기준이다.
실제 적용 전 라이브 페이지로 한 번 확인하고, 어긋나면 ROW_SELECTOR/필드 selector를 조정할 것.

빠른 검증 방법:
    import httpx, asyncio
    from app.sources.arca import ArcaSource
    async def t():
        async with httpx.AsyncClient(headers={"User-Agent":"Mozilla/5.0"}) as c:
            for d in (await ArcaSource().fetch(c))[:5]:
                print(d.title, d.price, d.url, d.thumbnail_url)
    asyncio.run(t())
"""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from app.ingest.normalize import guess_category, parse_price
from app.sources.base import RawDeal
from app.sources.html_source import HtmlSource

logger = logging.getLogger("arca")

# 게시글 링크에서 글 번호 추출: /b/hotdeal/123456?...
_ID_RE = re.compile(r"/b/hotdeal/(\d+)")
# 한 행(게시글). 공지/광고 행은 .notice 등으로 걸러진다.
_ROW_SELECTOR = "a.vrow.column"


class ArcaSource(HtmlSource):
    slug = "arca"
    name = "아카라이브"
    list_url = "https://arca.live/b/hotdeal"
    base_url = "https://arca.live"

    def parse(self, soup: BeautifulSoup) -> list[RawDeal]:
        deals: list[RawDeal] = []
        for row in soup.select(_ROW_SELECTOR):
            try:
                deal = self._parse_row(row)
                if deal:
                    deals.append(deal)
            except Exception as exc:  # 한 행 실패가 전체를 막지 않도록
                logger.debug("행 파싱 실패: %s", exc)
        return deals

    def _parse_row(self, row) -> RawDeal | None:
        href = row.get("href", "")
        m = _ID_RE.search(href)
        if not m:
            return None  # 핫딜 게시글이 아닌 행(공지 등)

        # 제목: .title 우선, 없으면 행 전체 텍스트
        title_el = row.select_one(".title")
        title = (title_el.get_text(strip=True) if title_el else row.get_text(strip=True)).strip()
        if not title:
            return None

        # 가격: 핫딜 전용 필드(.deal-price) 우선, 없으면 제목에서 추출
        price_el = row.select_one(".deal-price")
        price = parse_price(price_el.get_text(strip=True)) if price_el else parse_price(title)

        # 썸네일: 지연로딩(data-src) 대응
        img = row.select_one("img")
        thumb = None
        if img:
            thumb = img.get("src") or img.get("data-src")
            if thumb:
                thumb = self.absolute(thumb)

        return RawDeal(
            source_post_id=m.group(1),
            title=title,
            url=self.absolute(href),
            price=price,
            category=guess_category(title),
            thumbnail_url=thumb,
        )
