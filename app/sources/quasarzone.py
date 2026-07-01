"""퀘이사존 지름/할인정보 스크래퍼 (Cloudflare 우회)."""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from app.ingest.normalize import parse_price, resolve_category
from app.sources.base import RawDeal
from app.sources.cf_source import CfHtmlSource

logger = logging.getLogger("quasarzone")

_ID_RE = re.compile(r"/qb_saleinfo/views/(\d+)")


class QuasarzoneSource(CfHtmlSource):
    slug = "quasarzone"
    name = "퀘이사존"
    list_url = "https://quasarzone.com/bbs/qb_saleinfo"
    base_url = "https://quasarzone.com"

    def parse(self, soup: BeautifulSoup) -> list[RawDeal]:
        deals: list[RawDeal] = []
        for row in soup.select("div.market-info-list-cont"):
            try:
                deal = self._parse_row(row)
                if deal:
                    deals.append(deal)
            except Exception as exc:
                logger.debug("행 파싱 실패: %s", exc)
        return deals

    def _parse_row(self, row) -> RawDeal | None:
        a = row.select_one("a.subject-link")
        if not a:
            a = row.select_one("a[href*='/qb_saleinfo/views/']")
        if not a:
            return None

        href = a.get("href", "")
        m = _ID_RE.search(href)
        if not m:
            return None

        title_el = a.select_one(".ellipsis-with-reply-cnt") or a
        title = title_el.get_text(strip=True)
        if not title:
            return None

        price_el = row.select_one(".text-orange")
        price = parse_price(price_el.get_text(strip=True)) if price_el else parse_price(title)

        thumb = None
        img = row.select_one("img")
        if img:
            src = img.get("src") or img.get("data-original")
            if src and "img" in src:
                thumb = self.absolute(src)

        cat_el = row.select_one(".category")
        cat = cat_el.get_text(strip=True) if cat_el else None

        return RawDeal(
            source_post_id=m.group(1),
            title=title,
            url=self.absolute(href),
            price=price,
            category=resolve_category(self.slug, cat, title),
            thumbnail_url=thumb,
        )
