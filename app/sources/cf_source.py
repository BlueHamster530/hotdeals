"""Cloudflare 보호 사이트용 HTML 소스 기반 클래스.

curl_cffi로 브라우저 TLS 핑거프린트를 흉내 내 Cloudflare JS challenge를 우회한다.
httpx로는 403/503이 뜨는 아카라이브·퀘이사존·펨코 등에 사용.
"""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from app.sources.base import BROWSER_HEADERS, RawDeal, Source

logger = logging.getLogger("cf_source")


class CfHtmlSource(Source):
    kind = "html"
    list_url: str
    base_url: str = ""

    async def fetch(self, client) -> list[RawDeal]:
        async with AsyncSession(impersonate="chrome", headers=BROWSER_HEADERS) as s:
            resp = await s.get(self.list_url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            return self.parse(soup)

    def parse(self, soup: BeautifulSoup) -> list[RawDeal]:
        raise NotImplementedError

    def absolute(self, href: str) -> str:
        from urllib.parse import urljoin
        return urljoin(self.base_url or self.list_url, href)
