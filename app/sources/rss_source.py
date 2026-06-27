"""제너릭 RSS 소스. feed_url만 주면 동작한다."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from time import mktime

import feedparser
import httpx

from app.ingest.normalize import guess_category, parse_price
from app.sources.base import RawDeal, Source

_NUM_RE = re.compile(r"(\d+)")


class RssSource(Source):
    kind = "rss"
    feed_url: str

    def extract_post_id(self, entry) -> str:
        link = entry.get("link", "")
        nums = _NUM_RE.findall(link)
        if nums:
            return nums[-1]
        return entry.get("id") or link

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
                    posted_at=posted_at,
                )
            )
        return deals
