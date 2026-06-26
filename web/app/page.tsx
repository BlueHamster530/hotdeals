"use client";

import { useEffect, useState } from "react";
import { Deal, fetchCategories, fetchDeals } from "@/lib/api";
import { DealCard } from "@/components/DealCard";

export default function HomePage() {
  const [q, setQ] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 카테고리 목록은 한 번만
  useEffect(() => {
    fetchCategories().then(setCategories).catch(() => {});
  }, []);

  // 검색어/카테고리 변경 시 딜 재조회 (검색어는 300ms 디바운스)
  useEffect(() => {
    setLoading(true);
    setError(null);
    const timer = setTimeout(() => {
      fetchDeals({ q, category: category ?? undefined })
        .then(setDeals)
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    }, q ? 300 : 0);
    return () => clearTimeout(timer);
  }, [q, category]);

  return (
    <main>
      <div className="controls">
        <input
          className="search-input"
          placeholder="검색 (예: 콜라, 알뜰폰, SSD)"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <div className="chips">
          <button
            className={`chip ${category === null ? "active" : ""}`}
            onClick={() => setCategory(null)}
          >
            전체
          </button>
          {categories.map((c) => (
            <button
              key={c}
              className={`chip ${category === c ? "active" : ""}`}
              onClick={() => setCategory(c)}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="state">불러오기 실패: {error}</p>}
      {!error && loading && <p className="state">불러오는 중…</p>}
      {!error && !loading && deals.length === 0 && (
        <p className="state">조건에 맞는 핫딜이 없습니다.</p>
      )}

      {!loading && deals.length > 0 && (
        <div className="deal-list">
          {deals.map((deal) => (
            <DealCard key={deal.id} deal={deal} />
          ))}
        </div>
      )}
    </main>
  );
}
