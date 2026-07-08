"""제너릭 RSS 소스. feed_url만 주면 동작한다."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from time import mktime
from urllib.parse import urljoin

import feedparser
import httpx

from app.ingest.normalize import parse_price, resolve_category
from app.sources.base import RawDeal, Source

_NUM_RE = re.compile(r"(\d+)")
# 설명(HTML) 안의 첫 <img src="..."> 추출용
_IMG_RE = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.IGNORECASE)


class RssSource(Source):
    kind = "rss"
    feed_url: str

    def extract_post_id(self, entry) -> str:
        link = entry.get("link", "")
        nums = _NUM_RE.findall(link)
        if nums:
            return nums[-1]
        return entry.get("id") or link

    def extract_thumbnail(self, entry) -> str | None:
        """피드 entry의 대표 이미지 URL(절대경로). 없으면 None(og:image 보강이 폴백).

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
                    # RSS 자체에 <category>가 있는 소스(예: 루리웹)는 우선 사용, 없으면
                    # None → 수집 후 일괄 분류(app/ingest/classify.py)가 제목으로 처리
                    category=resolve_category(self.slug, entry.get("category")),
                    thumbnail_url=self.extract_thumbnail(entry),
                    posted_at=posted_at,
                )
            )
        return deals
