"""활성 소스 레지스트리.

여기에 인스턴스를 추가하면 파이프라인이 자동으로 수집한다.
"""

from app.sources.arca import ArcaSource
from app.sources.base import Source
from app.sources.clien import ClienSource
from app.sources.coolenjoy import CoolenjoySource
from app.sources.damoang import DamoangSource
from app.sources.dogdrip import DogdripSource
from app.sources.fmkorea import FmkoreaSource
from app.sources.ppomppu import PpomppuSource
from app.sources.quasarzone import QuasarzoneSource
from app.sources.ruliweb import RuliwebSource

SOURCES: list[Source] = [
    PpomppuSource(),       # RSS
    CoolenjoySource(),     # RSS
    RuliwebSource(),       # RSS
    DamoangSource(),       # RSS
    ClienSource(),         # HTML
    DogdripSource(),       # HTML
    ArcaSource(),          # HTML (Cloudflare)
    QuasarzoneSource(),    # HTML (Cloudflare)
    FmkoreaSource(),       # HTML (Cloudflare)
]
