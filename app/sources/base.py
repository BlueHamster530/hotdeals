"""소스 추상화.

모든 커뮤니티 소스(RSS든 HTML이든)는 동일한 인터페이스로 RawDeal 목록을 돌려준다.
파이프라인은 소스가 RSS인지 HTML인지 몰라도 된다 → 하이브리드 수집의 핵심.
"""

from __future__ import annotations

import abc
import asyncio
import re
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
    thumbnail_url: str | None = None
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


# og:image (property/content 순서 양쪽 대응)
_OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)'
    r'|<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    re.IGNORECASE,
)


def og_image(html: str) -> str | None:
    m = _OG_IMAGE_RE.search(html or "")
    if not m:
        return None
    return m.group(1) or m.group(2)


_STUB_MAX_LEN = 1000  # 이보다 작으면 anti-bot 스텁(쿠키만 주는 빈 페이지)으로 간주


async def enrich_og_thumbnails(
    deals: list[RawDeal], headers: dict[str, str], limit: int = 3
) -> None:
    """썸네일이 없는 딜의 글페이지 og:image를 채운다. 신규 딜에만 1회 호출(파이프라인).

    일부 사이트(뽐뿌)는 첫 요청에 세션 쿠키만 주고 스텁을 반환한다 → 실제 글로 워밍업해
    쿠키를 확보하고, 응답이 스텁이면 1회 재시도. 전용 클라이언트로 쿠키 jar를 공유한다.
    """
    targets = [d for d in deals if not d.thumbnail_url and d.url]
    if not targets:
        return

    async with httpx.AsyncClient(headers=headers, timeout=10.0, follow_redirects=True) as client:
        try:  # 워밍업: 첫 글로 세션 쿠키 확보
            await client.get(targets[0].url)
        except Exception:
            pass

        sem = asyncio.Semaphore(limit)

        async def _one(deal: RawDeal) -> None:
            async with sem:
                for _ in range(2):  # 스텁이면 쿠키 확보 후 1회 재시도
                    try:
                        r = await client.get(deal.url)
                    except Exception:
                        return
                    if r.status_code == 200 and len(r.content) > _STUB_MAX_LEN:
                        img = og_image(r.text)
                        if img:
                            deal.thumbnail_url = img
                        return

        await asyncio.gather(*(_one(d) for d in targets))
