"""펨코(FM Korea) 핫딜 스크래퍼 (Cloudflare 우회)."""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from app.ingest.normalize import guess_category, parse_price
from app.sources.base import RawDeal
from app.sources.cf_source import CfHtmlSource

logger = logging.getLogger("fmkorea")

_ID_RE = re.compile(r"/(\d{8,})")


class FmkoreaSource(CfHtmlSource):
    slug = "fmkorea"
    name = "펨코"
    list_url = "https://www.fmkorea.com/hotdeal"
    base_url = "https://www.fmkorea.com"

    def parse(self, soup: BeautifulSoup) -> list[RawDeal]:
        deals: list[RawDeal] = []
        for row in soup.select("li.li_best2_pop0, li.li_best2_pop1, li.li_best2_pop2"):
            try:
                deal = self._parse_row(row)
                if deal:
                    deals.append(deal)
            except Exception as exc:
                logger.debug("행 파싱 실패: %s", exc)

        if not deals:
            deals = self._fallback_parse(soup)
        return deals

    def _parse_row(self, row) -> RawDeal | None:
        a = row.select_one("a.hotdeal_var8")
        if not a:
            a = row.select_one("h3.title a") or row.select_one("a[href]")
        if not a:
            return None

        href = a.get("href", "")
        m = _ID_RE.search(href)
        if not m:
            return None

        title = a.get_text(strip=True)
        if not title:
            return None

        return RawDeal(
            source_post_id=m.group(1),
            title=title,
            url=self.absolute(href),
            price=parse_price(title),
            category=guess_category(title),
        )

    def _fallback_parse(self, soup: BeautifulSoup) -> list[RawDeal]:
        deals: list[RawDeal] = []
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            m = _ID_RE.search(href)
            if not m:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            sn = m.group(1)
            if any(d.source_post_id == sn for d in deals):
                continue
            deals.append(
                RawDeal(
                    source_post_id=sn,
                    title=title,
                    url=self.absolute(href),
                    price=parse_price(title),
                    category=guess_category(title),
                )
            )
        return deals
