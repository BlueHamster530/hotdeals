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
        for row in soup.select("div.vrow.hybrid"):
            cls = " ".join(row.get("class", []))
            if "notice" in cls or "head" in cls:
                continue
            try:
                deal = self._parse_row(row, seen)
                if deal:
                    deals.append(deal)
            except Exception as exc:
                logger.debug("행 파싱 실패: %s", exc)
        return deals

    def _parse_row(self, row, seen: set[str]) -> RawDeal | None:
        a = row.select_one("a.title.hybrid-title")
        if not a:
            return None
        href = a.get("href", "")
        m = _ID_RE.search(href)
        if not m:
            return None
        sn = m.group(1)
        if sn in seen:
            return None

        # 제목: 아이콘/댓글수 span 제거 후 텍스트만
        a_copy = BeautifulSoup(str(a), "lxml").find("a")
        for junk in a_copy.select(".media-icon, .info, .comment-count"):
            junk.decompose()
        title = a_copy.get_text(strip=True)
        if not title:
            return None
        seen.add(sn)

        # 가격: .deal-price ("13,470원")
        price_el = row.select_one(".deal-price")
        price = parse_price(price_el.get_text(strip=True)) if price_el else parse_price(title)

        # 썸네일: .vrow-preview img (namu.la CDN, protocol-relative)
        thumb = None
        img = row.select_one(".vrow-preview img")
        if img and img.get("src"):
            thumb = self.absolute(img["src"])

        # 쇼핑몰명을 제목 앞에 붙여 가독성↑ (예: "G마켓 · 신라면...")
        store_el = row.select_one(".deal-store")
        store = store_el.get_text(strip=True) if store_el else ""
        display_title = f"[{store}] {title}" if store else title

        return RawDeal(
            source_post_id=sn,
            title=display_title,
            url=self.absolute(f"/b/hotdeal/{sn}"),
            price=price,
            category=guess_category(title),
            thumbnail_url=thumb,
        )
