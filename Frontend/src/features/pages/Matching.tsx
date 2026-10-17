import { useMemo, useState } from "react";
import { MatchRadar } from "../../components/matching/MatchRadar";
import { TopMatchList } from "../../components/matching/TopMatchList";
import { backend } from "../../api/backend";
import { rankByReadiness, similarStartups } from "../../lib/readiness-ranking";
import { useAsync } from "../../lib/useAsync";
import { Link } from "../../lib/navigation";

const PAGE_SIZE = 5;
const TOTAL_PAGES = 2;

export function Matching() {
  const { data: startups, loading, error } = useAsync(() => backend.startups(), []);
  const [hovered, setHovered] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  // Every assessed startup ranked; the radar and list show the top 10 (both pages).
  const ranked = useMemo(() => rankByReadiness(startups ?? []), [startups]);
  const allMatches = useMemo(() => ranked.slice(0, PAGE_SIZE * TOTAL_PAGES), [ranked]);

  // Handle dot or list item click: selects item & switches page if needed
  const toggle = (slug: string) => {
    setSelected((cur) => (cur === slug ? null : slug));

    // Find which page the startup is on and switch to it
    const itemIndex = allMatches.findIndex((m) => m.startup.slug === slug);
    if (itemIndex !== -1) {
      const targetPage = Math.floor(itemIndex / PAGE_SIZE) + 1;
      if (targetPage <= TOTAL_PAGES) {
        setPage(targetPage);
      }
    }
  };

  // Only 5 startups in the list for the current page
  const displayedMatches = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return allMatches.slice(start, start + PAGE_SIZE);
  }, [allMatches, page]);

  const picked = allMatches.find((m) => m.startup.slug === selected) ?? null;
  // Similar startups come from every ranked startup, not only the top 10.
  const similar = picked ? similarStartups(picked, ranked) : [];

  const similar = useMemo(() => {
      if (!picked || !startups) return [];
      return similarStartups(picked, allMatches);
    }, [picked, allMatches, startups]);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Matching</h1>
          <p>
            Startups ranked by their readiness index from the StartupGo database, highest first.
            Only startups with a completed assessment are ranked.
          </p>
        </div>
      </div>

      <div className={`mg-layout${picked ? " is-open" : ""}`}>
        <section className="card mg-card">
          <header className="mg-head">
            <span className="mg-dot" aria-hidden />
            Readiness ranking
          </header>
          {error && <p className="small error card-pad">{error}</p>}
          {!loading && allMatches.length === 0 && <p className="empty">No assessed startups yet.</p>}
          {allMatches.length > 0 && (
            <div className="mg-body">
              {/* Radar always displays ALL dots */}
              <div className="mg-graph">
                <MatchRadar
                  matches={allMatches}
                  hovered={hovered}
                  selected={selected}
                  onHover={setHovered}
                  onSelect={toggle}
                />
              </div>

              {/* List displays only the 5 for the current page */}
              <div className="mg-list max-w-[400px]">
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                  <h2 className="mg-eyebrow" style={{ margin: 0 }}>Top matches</h2>
                  <span className="small muted" style={{ fontWeight: 600 }}>
                    {page === 1 ? "Closest 1-5" : "Closest 6-10"}
                  </span>
                </div>

                <TopMatchList
                  matches={displayedMatches}
                  hovered={hovered}
                  selected={selected}
                  onHover={setHovered}
                  onSelect={toggle}
                />

                {/* Pagination Controls */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginTop: 16,
                    paddingTop: 14,
                    borderTop: "1px solid var(--border)",
                  }}
                >
                  <button
                    type="button"
                    className="btn"
                    disabled={page === 1}
                    aria-label="Previous page"
                    style={{
                      padding: "4px 10px",
                      fontSize: "14px",
                      minHeight: "32px",
                      opacity: page === 1 ? 0.35 : 1,
                      cursor: page === 1 ? "not-allowed" : "pointer",
                    }}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    ←
                  </button>

                  <div style={{ display: "flex", gap: "6px" }}>
                    {[1, 2].map((p) => (
                      <button
                        key={p}
                        type="button"
                        className={`btn ${page === p ? "btn-primary" : ""}`}
                        style={{
                          padding: "4px 10px",
                          fontSize: "13px",
                          minHeight: "32px",
                          minWidth: "32px",
                        }}
                        onClick={() => setPage(p)}
                      >
                        {p}
                      </button>
                    ))}
                  </div>

                  <button
                    type="button"
                    className="btn"
                    disabled={page === TOTAL_PAGES}
                    aria-label="Next page"
                    style={{
                      padding: "4px 10px",
                      fontSize: "14px",
                      minHeight: "32px",
                      opacity: page === TOTAL_PAGES ? 0.35 : 1,
                      cursor: page === TOTAL_PAGES ? "not-allowed" : "pointer",
                    }}
                    onClick={() => setPage((p) => Math.min(TOTAL_PAGES, p + 1))}
                  >
                    →
                  </button>
                </div>
              </div>
            </div>
          )}
        </section>

        {picked && (
          <aside className="mg-detail" aria-live="polite">
            <div className="mg-detail-inner" key={picked.startup.slug}>
              <button
                type="button"
                className="mg-close"
                onClick={() => setSelected(null)}
                aria-label="Close details"
              >
                ×
              </button>
              <p className="mg-eyebrow ">
                {picked.startup.sector} · {picked.startup.country}
              </p>
              <h3>
                <Link to={`/startups/${picked.startup.slug}`}>
                  {picked.startup.name}
                </Link>
              </h3>
              <p className="mg-detail-score">
                {picked.total}
                <small> / 100 readiness</small>
              </p>
              <p>{picked.startup.description}</p>
              <dl>
                <div>
                  <dt>Readiness</dt>
                  <dd>{picked.readiness}</dd>
                </div>
                <div>
                  <dt>Ocean impact</dt>
                  <dd>{picked.impact}</dd>
                </div>
                <div>
                  <dt>Investment potential</dt>
                  <dd>{picked.potential}</dd>
                </div>
              </dl>
            </div>
            {similar.length > 0 && (
              <section className="mg-similar" aria-label="Similar startups">
                <h4 className="mg-eyebrow">Startups you might also be interested in</h4>
                <div className="mg-similar-grid">
                  {similar.map((r) => (
                    <button type="button" key={r.startup.slug} className="mg-similar-card" onClick={() => setSelected(r.startup.slug)}>
                      <span className="tm-badge" aria-hidden>{r.startup.name[0]}</span>
                      <strong>{r.startup.name}</strong>
                      <small>{r.startup.sector}</small>
                      <span className="mg-similar-score">{r.total}<small> readiness</small></span>
                    </button>
                  ))}
                </div>
              </section>
            )}
          </aside>
        )}
      </div>
    </>
  );
}
