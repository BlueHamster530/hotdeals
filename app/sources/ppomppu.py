from app.sources.rss_source import RssSource


class PpomppuSource(RssSource):
    slug = "ppomppu"
    name = "뽐뿌"
    feed_url = "https://www.ppomppu.co.kr/rss.php?id=ppomppu"
