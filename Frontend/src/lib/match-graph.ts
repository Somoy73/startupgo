export type GraphNode = { slug: string; score: number; x: number; y: number; highlighted: boolean };

/** Places matches around a center: higher score = closer. Coordinates in a size×size box. */
export function layoutNodes(matches: { slug: string; score: number }[], size: number): GraphNode[] {
  const c = size / 2;
  const inner = size * 0.16;
  const outer = size * 0.44;
  return matches.map((m, i) => {
    const t = 1 - Math.max(0, Math.min(100, m.score)) / 100;
    const r = inner + t * (outer - inner) * 1.6;
    const radius = Math.min(outer, r);
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / Math.max(1, matches.length) + (i % 2 ? 0.35 : 0);
    return {
      slug: m.slug,
      score: m.score,
      x: c + radius * Math.cos(angle),
      y: c + radius * Math.sin(angle),
      highlighted: i < 3,
    };
  });
}
