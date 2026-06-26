"""제너릭 RSS 소스. feed_url만 주면 동작한다.

RSS를 제공하는 커뮤니티(뽐뿌, 쿨앤조이 등)는 이 클래스를 상속해 feed_url만 지정하면 된다.
HTML 스크래핑보다 안정적이고 ToS 측면에서도 안전 → 하이브리드 전략에서 1순위.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from time import mktime
from urllib.parse import urljoin, urlparse

import feedparser
import httpx

from app.ingest.normalize import guess_category, parse_price
from app.sources.base import BROWSER_HEADERS, RawDeal, Source, enrich_og_thumbnails

_NUM_RE = re.compile(r"(\d+)")
# 설명(HTML) 안의 첫 <img src="..."> 추출용
_IMG_RE = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.IGNORECASE)


class RssSource(Source):
    kind = "rss"
    feed_url: str
    # RSS에 이미지가 없는 소스는 True로 두면 글페이지 og:image로 썸네일 보강.
    enrich_thumbnail = False

    def extract_post_id(self, entry) -> str:
        """RSS entry에서 게시글 고유 ID 추출. 기본은 link의 마지막 숫자, 없으면 guid/link."""
        link = entry.get("link", "")
        nums = _NUM_RE.findall(link)
        if nums:
            return nums[-1]
        return entry.get("id") or link

    def extract_thumbnail(self, entry) -> str | None:
        """게시글 대표 이미지 URL(절대경로). 없으면 None(프론트에서 빈 칸 처리).

        우선순위: media:thumbnail/content → 이미지 enclosure → 본문 HTML 첫 <img>.
        일부 피드(쿨앤조이 등)는 상대경로(/data/...)를 주므로 글 링크 기준으로 절대화한다.
        """
        found = None
        for key in ("media_thumbnail", "media_content"):
            media = entry.get(key)
            if media and media[0].get("url"):
                found = media[0]["url"]
                break

        if not found:
            for enc in entry.get("enclosures", []):
                if str(enc.get("type", "")).startswith("image") and enc.get("href"):
                    found = enc["href"]
                    break

        if not found:
            html = entry.get("summary", "")
            if not html and entry.get("content"):
                html = entry["content"][0].get("value", "")
            m = _IMG_RE.search(html or "")
            found = m.group(1) if m else None

        if not found:
            return None
        # 상대경로면 글 링크 기준 절대경로로 (절대경로면 그대로 유지)
        return urljoin(entry.get("link", ""), found)

    async def fetch(self, client: httpx.AsyncClient) -> list[RawDeal]:
        resp = await client.get(self.feed_url, headers=self.extra_headers)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)

        deals: list[RawDeal] = []
        for entry in feed.entries:
            title = (entry.get("title") or "").strip()
            if not title:
                continue
            posted_at = None
            if entry.get("published_parsed"):
                posted_at = datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
            deals.append(
                RawDeal(
                    source_post_id=self.extract_post_id(entry),
                    title=title,
                    url=entry.get("link", ""),
                    price=parse_price(title),
                    category=guess_category(title),
                    thumbnail_url=self.extract_thumbnail(entry),
                    posted_at=posted_at,
                )
            )

        # 썸네일 없는 소스는 글페이지 og:image로 보강 (Referer = 피드 사이트 출처)
        if self.enrich_thumbnail:
            p = urlparse(self.feed_url)
            headers = {**BROWSER_HEADERS, "Referer": f"{p.scheme}://{p.netloc}/"}
            await enrich_og_thumbnails(deals, headers)
        return deals
