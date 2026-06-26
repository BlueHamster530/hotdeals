"""HTML 스크래핑 소스 기반 클래스.

RSS가 없는 커뮤니티(아카라이브, 펨코 등)용. list_url을 GET해서 받은 HTML을
subclass의 parse()가 RawDeal 목록으로 변환한다. RssSource와 동일한 Source 인터페이스라
파이프라인 입장에선 RSS/HTML 구분이 없다(하이브리드).

주의: HTML 구조는 사이트 개편 시 바뀌므로 selector는 깨질 수 있다. parse()는 방어적으로 작성하고,
한 행 파싱 실패가 전체를 막지 않도록 각 행을 try로 감싼다.
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.sources.base import RawDeal, Source

logger = logging.getLogger("html_source")


class HtmlSource(Source):
    kind = "html"
    list_url: str
    base_url: str = ""  # 상대경로 → 절대경로 변환용

    async def fetch(self, client: httpx.AsyncClient) -> list[RawDeal]:
        resp = await client.get(self.list_url, headers=self.extra_headers)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        return self.parse(soup)

    def parse(self, soup: BeautifulSoup) -> list[RawDeal]:
        raise NotImplementedError

    def absolute(self, href: str) -> str:
        return urljoin(self.base_url or self.list_url, href)
