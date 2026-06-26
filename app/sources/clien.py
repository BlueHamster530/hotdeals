"""클리앙 알뜰구매(jirum) HTML 스크래퍼. 라이브 DOM 기준 검증됨(2026-06).

제목 링크엔 클래스가 없어 URL 패턴(/service/board/jirum/<번호>)으로 글을 식별한다.
한 글에 앵커가 여러 개(썸네일+제목)라 글번호별로 가장 긴 텍스트(=제목)를 택한다.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from app.ingest.normalize import guess_category, parse_price
from app.sources.base import BROWSER_HEADERS, RawDeal
from app.sources.html_source import HtmlSource

_ID_RE = re.compile(r"/service/board/jirum/(\d+)")
_SKIP_ROW_CLASSES = ("notice", "hongbo")  # 공지·홍보 행 제외


class ClienSource(HtmlSource):
    slug = "clien"
    name = "클리앙"
    list_url = "https://www.clien.net/service/board/jirum"
    base_url = "https://www.clien.net"
    extra_headers = BROWSER_HEADERS  # 봇 UA는 403 — 브라우저 UA 필요

    def parse(self, soup: BeautifulSoup) -> list[RawDeal]:
        # 글번호 -> (제목, href, row). 같은 글의 여러 앵커 중 최장 텍스트를 제목으로.
        best: dict[str, tuple[str, str, object]] = {}
        for a in soup.select('a[href*="/service/board/jirum/"]'):
            href = a.get("href", "")
            m = _ID_RE.search(href)
            if not m:
                continue
            title = a.get_text(strip=True)
            if not title:
                continue
            row = a.find_parent("div", class_="list_item")
            if row and any(c in (row.get("class") or []) for c in _SKIP_ROW_CLASSES):
                continue
            sn = m.group(1)
            if sn not in best or len(title) > len(best[sn][0]):
                best[sn] = (title, href, row)

        deals: list[RawDeal] = []
        for sn, (title, href, row) in best.items():
            thumb = None
            if row is not None:
                img = row.select_one("img")
                if img:
                    src = img.get("src") or img.get("data-src")
                    thumb = self.absolute(src) if src else None
            deals.append(
                RawDeal(
                    source_post_id=sn,
                    title=title,
                    url=self.absolute(href),
                    price=parse_price(title),
                    category=guess_category(title),
                    thumbnail_url=thumb,
                )
            )
        return deals
