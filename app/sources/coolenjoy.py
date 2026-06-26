from app.sources.rss_source import RssSource


class CoolenjoySource(RssSource):
    slug = "coolenjoy"
    name = "쿨앤조이"
    # 지름게시판(jirum) RSS
    feed_url = "https://coolenjoy.net/bbs/rss.php?bo_table=jirum"
