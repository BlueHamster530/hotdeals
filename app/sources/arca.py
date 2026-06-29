"""아카라이브 핫딜 채널 스크래퍼 (Cloudflare 우회)."""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from app.ingest.normalize import guess_category, parse_price
from app.sources.base import RawDeal
from app.sources.cf_source import CfHtmlSource

logger = logging.getLogger("arca")

_ID_RE = re.compile(r"/b/hotdeal/(\d+)")


class ArcaSource(CfHtmlSource):
    slug = "arca"
    name = "아카라이브"
    list_url = "https://arca.live/b/hotdeal"
    base_url = "https://arca.live"

    def parse(self, soup: BeautifulSoup) -> list[RawDeal]:
        deals: list[RawDeal] = []
        seen: set[str] = set()
        for a in soup.select("a.title.hybrid-title"):
            href = a.get("href", "")
            m = _ID_RE.search(href)
            if not m:
                continue
            sn = m.group(1)
            if sn in seen:
                continue
            title = a.get_text(strip=True)
            if not title:
                continue
            # 댓글 수 표시 "[N]" 제거
            title = re.sub(r"\[\d+\]$", "", title).strip()
            if not title:
                continue
            seen.add(sn)

            # 같은 행(vrow)에서 가격 추출 시도
            row = a.find_parent("div", class_="vrow")
            price = parse_price(title)

            deals.append(
                RawDeal(
                    source_post_id=sn,
                    title=title,
                    url=self.absolute(f"/b/hotdeal/{sn}"),
                    price=price,
                    category=guess_category(title),
                )
            )
        return deals
