"""개드립 핫딜 게시판 HTML 스크래퍼."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from app.ingest.normalize import guess_category, parse_price
from app.sources.base import BROWSER_HEADERS, RawDeal
from app.sources.html_source import HtmlSource

_ID_RE = re.compile(r"/hotdeal/(\d+)")


class DogdripSource(HtmlSource):
    slug = "dogdrip"
    name = "개드립"
    list_url = "https://www.dogdrip.net/hotdeal"
    base_url = "https://www.dogdrip.net"
    extra_headers = BROWSER_HEADERS

    def parse(self, soup: BeautifulSoup) -> list[RawDeal]:
        deals: list[RawDeal] = []
        for a in soup.select("a.title"):
            href = a.get("href", "")
            m = _ID_RE.search(href)
            if not m:
                continue
            title = a.get_text(strip=True)
            if not title:
                continue
            deals.append(
                RawDeal(
                    source_post_id=m.group(1),
                    title=title,
                    url=self.absolute(href),
                    price=parse_price(title),
                    category=guess_category(title),
                )
            )
        return deals
