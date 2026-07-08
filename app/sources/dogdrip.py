"""개드립 핫딜 게시판 HTML 스크래퍼."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from app.ingest.normalize import parse_price
from app.sources.base import BROWSER_HEADERS, RawDeal
from app.sources.html_source import HtmlSource

_ID_RE = re.compile(r"/hotdeal/(\d{6,})")


class DogdripSource(HtmlSource):
    slug = "dogdrip"
    name = "개드립"
    list_url = "https://www.dogdrip.net/hotdeal?sort_index=date"
    base_url = "https://www.dogdrip.net"
    extra_headers = BROWSER_HEADERS

    def parse(self, soup: BeautifulSoup) -> list[RawDeal]:
        deals: list[RawDeal] = []
        seen: set[str] = set()
        for a in soup.select(".board-list a[href]"):
            href = a.get("href", "")
            m = _ID_RE.search(href)
            if not m:
                continue
            sn = m.group(1)
            if sn in seen:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            seen.add(sn)
            deals.append(
                RawDeal(
                    source_post_id=sn,
                    title=title,
                    url=self.absolute(f"/hotdeal/{sn}"),
                    price=parse_price(title),
                    category=None,  # 수집 후 일괄 분류(app/ingest/classify.py)
                )
            )
        return deals
