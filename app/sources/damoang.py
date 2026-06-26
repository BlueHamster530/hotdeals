from app.sources.base import BROWSER_HEADERS
from app.sources.rss_source import RssSource


class DamoangSource(RssSource):
    slug = "damoang"
    name = "다모앙"
    # 경제(economy) 게시판 RSS (확인됨). 링크: https://damoang.net/economy/76353
    feed_url = "https://damoang.net/bbs/rss.php?bo_table=economy"
    extra_headers = BROWSER_HEADERS  # 봇 UA는 403 — 브라우저 UA 필요
