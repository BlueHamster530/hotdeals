"""활성 소스 레지스트리.

여기에 인스턴스를 추가하면 파이프라인이 자동으로 수집한다.
HTML 소스(루리웹/아카라이브/펨코 등)도 Source 인터페이스만 구현하면 동일하게 등록 가능.
"""

from app.sources.base import Source
from app.sources.clien import ClienSource
from app.sources.coolenjoy import CoolenjoySource
from app.sources.damoang import DamoangSource
from app.sources.ppomppu import PpomppuSource
from app.sources.ruliweb import RuliwebSource

# 모두 라이브 검증됨(2026-06). RSS 우선 + 검증된 HTML.
SOURCES: list[Source] = [
    PpomppuSource(),    # RSS
    CoolenjoySource(),  # RSS
    RuliwebSource(),    # RSS
    DamoangSource(),    # RSS (브라우저 UA)
    ClienSource(),      # HTML (브라우저 UA)
]

# 미활성(Cloudflare 봇차단으로 단순 httpx 불가 — 헤드리스 브라우저 필요):
#   arca.live(app/sources/arca.py 템플릿), 퀘이사존, 펨코.
#   from app.sources.arca import ArcaSource; SOURCES.append(ArcaSource())
