"""소스 추상화.

모든 커뮤니티 소스(RSS든 HTML이든)는 동일한 인터페이스로 RawDeal 목록을 돌려준다.
파이프라인은 소스가 RSS인지 HTML인지 몰라도 된다 → 하이브리드 수집의 핵심.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from datetime import datetime

import httpx

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}


@dataclass(slots=True)
class RawDeal:
    """정규화 이전, 소스에서 막 긁어온 원본 딜."""

    source_post_id: str           # 소스 내 게시글 고유 ID (dedup 키)
    title: str
    url: str
    price: int | None = None      # 원 단위. 파싱 실패 시 None
    category: str | None = None
    posted_at: datetime | None = None


class Source(abc.ABC):
    slug: str          # DB sources.slug 와 매칭
    name: str
    kind: str          # "rss" | "html"
    extra_headers: dict[str, str] = {}

    @abc.abstractmethod
    async def fetch(self, client: httpx.AsyncClient) -> list[RawDeal]:
        """현재 게시판 목록을 긁어 RawDeal 리스트로 반환. 네트워크 예외는 호출측에서 처리."""
        raise NotImplementedError
