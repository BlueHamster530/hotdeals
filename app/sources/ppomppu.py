from app.sources.rss_source import RssSource


class PpomppuSource(RssSource):
    slug = "ppomppu"
    name = "뽐뿌"
    # 뽐뿌게시판 공식 RSS (확인됨). RSS에 이미지가 없어 글페이지 og:image로 보강.
    feed_url = "https://www.ppomppu.co.kr/rss.php?id=ppomppu"
    enrich_thumbnail = True
