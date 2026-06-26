"use client";

import { useState } from "react";
import { Deal, formatKRW, proxiedImage, relativeTime } from "@/lib/api";
import { PriceGauge, RATING_COLOR, VERDICT_STYLE } from "./PriceGauge";

// 썸네일: 있으면 프록시 경유로 표시, 없거나 로딩 실패하면 빈 슬롯
function Thumb({ src }: { src: string | null }) {
  const [broken, setBroken] = useState(false);
  if (!src || broken) {
    return <div className="thumb thumb-empty">이미지 없음</div>;
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img className="thumb" src={proxiedImage(src)} alt="" loading="lazy" onError={() => setBroken(true)} />
  );
}

function discountLabel(pct: number | null) {
  if (pct == null) return null;
  if (pct >= 0) {
    return <span className="deal-discount" style={{ color: "#3B6D11" }}>평균 대비 {pct}%↓</span>;
  }
  return <span className="deal-discount" style={{ color: "#A32D2D" }}>평균 대비 {Math.abs(pct)}%↑</span>;
}

export function DealCard({ deal }: { deal: Deal }) {
  const { analysis } = deal;
  const verdictStyle = VERDICT_STYLE[analysis.rating];
  const when = relativeTime(deal.posted_at ?? deal.fetched_at);

  return (
    <article className="deal-card">
      <Thumb src={deal.thumbnail_url} />
      <div className="deal-body">
        <div className="deal-meta">
          <span className="deal-source">
            {deal.source}
            {deal.category ? ` · ${deal.category}` : ""}
            {when ? ` · ${when}` : ""}
          </span>
          {analysis.rating !== "unknown" && (
            <span
              className="verdict"
              style={{ background: verdictStyle.bg, color: verdictStyle.fg }}
            >
              {analysis.verdict}
              {analysis.deal_score != null ? ` · ${analysis.deal_score}점` : ""}
            </span>
          )}
        </div>

        {/* 제목 클릭 → 원본 게시글로 이동 */}
        <a className="deal-title" href={deal.url} target="_blank" rel="noopener noreferrer">
          {deal.title} <span className="ext">↗</span>
        </a>

        <div className="deal-price-row">
          <span className="deal-price" style={{ color: RATING_COLOR[analysis.rating] }}>
            {formatKRW(deal.price)}
          </span>
          {discountLabel(analysis.discount_vs_avg_pct)}
        </div>

        <PriceGauge analysis={analysis} />
      </div>
    </article>
  );
}
