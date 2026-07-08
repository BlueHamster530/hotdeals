"""펨코(FM Korea) 핫딜 스크래퍼 (Cloudflare 우회)."""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from app.ingest.normalize import parse_price, resolve_category
from app.sources.base import RawDeal
from app.sources.cf_source import CfHtmlSource

logger = logging.getLogger("fmkorea")

_ID_RE = re.compile(r"/(\d{6,})")


class FmkoreaSource(CfHtmlSource):
    slug = "fmkorea"
    name = "펨코"
    list_url = "https://www.fmkorea.com/hotdeal"
    base_url = "https://www.fmkorea.com"

    def parse(self, soup: BeautifulSoup) -> list[RawDeal]:
        deals: list[RawDeal] = []
        seen: set[str] = set()
        for li in soup.select("li[class*='li_best2_pop']"):
            try:
                deal = self._parse_row(li, seen)
                if deal:
                    deals.append(deal)
            except Exception as exc:
                logger.debug("행 파싱 실패: %s", exc)
        return deals

    def _parse_row(self, li, seen: set[str]) -> RawDeal | None:
        a = li.select_one("h3.title a.hotdeal_var8") or li.select_one("h3.title a")
        if not a:
            return None
        href = a.get("href", "")
        m = _ID_RE.search(href)
        if not m:
            return None
        sn = m.group(1)
        if sn in seen:
            return None

        # 제목: 댓글수 span 제거
        target = a.select_one(".ellipsis-target")
        title = target.get_text(strip=True) if target else a.get_text(strip=True)
        title = re.sub(r"\[\d+\]$", "", title).strip()
        if not title:
            return None
        seen.add(sn)

        # 가격/쇼핑몰: .hotdeal_info ("쇼핑몰: 네이버 / 가격: 1,141,140원 / 배송: 무료")
        info = li.select_one(".hotdeal_info")
        price = None
        store = ""
        if info:
            price = parse_price(info.get_text(" ", strip=True))
            store_a = info.select_one("span a.strong")
            store = store_a.get_text(strip=True) if store_a else ""

        # 썸네일: img.thumb data-original (protocol-relative, lazy)
        thumb = None
        img = li.select_one("img.thumb") or li.select_one("img")
        if img:
            src = img.get("data-original") or img.get("src")
            if src and "transparent.gif" not in src:
                thumb = self.absolute(src)

        display_title = f"[{store}] {title}" if store else title

        cat_el = li.select_one(".category a") or li.select_one("span.category")
        cat = cat_el.get_text(strip=True) if cat_el else None

        return RawDeal(
            source_post_id=sn,
            title=display_title,
            url=self.absolute(f"/{sn}"),
            price=price,
            category=resolve_category(self.slug, cat),
            thumbnail_url=thumb,
        )
