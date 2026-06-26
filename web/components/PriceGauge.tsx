import { PriceAnalysis, Rating, formatKRW } from "@/lib/api";

// 등급 → 마커 색 (게이지 마커와 verdict 배지에 공통 사용)
export const RATING_COLOR: Record<Rating, string> = {
  great: "#639922",
  good: "#185FA5",
  normal: "#BA7517",
  poor: "#E24B4A",
  unknown: "#888780",
};

// 등급 → verdict 배지 배경/글자색
export const VERDICT_STYLE: Record<Rating, { bg: string; fg: string }> = {
  great: { bg: "#EAF3DE", fg: "#27500A" },
  good: { bg: "#E6F1FB", fg: "#0C447C" },
  normal: { bg: "#FAEEDA", fg: "#633806" },
  poor: { bg: "#FCEBEB", fg: "#791F1F" },
  unknown: { bg: "var(--surface-2)", fg: "var(--text-2)" },
};

export function PriceGauge({ analysis }: { analysis: PriceAnalysis }) {
  const { min_price, max_price, current_price, rating, sample_size } = analysis;

  // 데이터가 부족하면 게이지 대신 안내 문구
  if (
    current_price == null ||
    min_price == null ||
    max_price == null ||
    sample_size < 3
  ) {
    return <div className="gauge-empty">가격 이력 데이터가 부족합니다</div>;
  }

  // 현재가가 [역대최저, 역대최고] 구간 어디에 위치하는지(%)
  const span = max_price - min_price;
  const pos = span > 0 ? ((current_price - min_price) / span) * 100 : 0;
  const clamped = Math.max(0, Math.min(100, pos));

  return (
    <div>
      <div className="gauge-track">
        <span className="gauge-band g" />
        <span className="gauge-band a" />
        <span className="gauge-band r" />
      </div>
      <div className="gauge-marker-row">
        <span
          className="gauge-marker"
          style={{ left: `${clamped}%`, background: RATING_COLOR[rating] }}
        />
      </div>
      <div className="gauge-labels">
        <span>역대최저 {formatKRW(min_price)}</span>
        {analysis.avg_price != null && <span>평균 {formatKRW(Math.round(analysis.avg_price))}</span>}
        <span>역대최고 {formatKRW(max_price)}</span>
      </div>
    </div>
  );
}
