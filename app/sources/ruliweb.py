from app.sources.rss_source import RssSource


class RuliwebSource(RssSource):
    slug = "ruliweb"
    name = "루리웹"
    # 핫딜예판/유저핫딜 게시판(1020) RSS (확인됨). 링크 형식: .../read/105126
    feed_url = "https://bbs.ruliweb.com/market/board/1020/rss"
