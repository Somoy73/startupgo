import type { StartupDetail } from "../../api/types";
import { Meter } from "../Scores";
export function ScorePreview({
  preview,
  current,
  error,
}: {
  preview: StartupDetail["scores"] | null;
  current: StartupDetail["scores"] | null;
  error: string | null;
}) {
  return (
    <aside className="score-preview">
      <h2>Score preview</h2>
      {error ? (
        <p className="error">{error}</p>
      ) : preview ? (
        <>
          <div className="preview-number">
            {preview.potential}
            <span>/100</span>
          </div>
          {current && <p className="small muted">Current: {current.potential}</p>}
          {(["readiness", "ocean_impact", "momentum"] as const).map((k) => (
            <div key={k}>
              <p className="small">{k.replaceAll("_", " ")}</p>
              <Meter value={preview[k]} label={k} />
            </div>
          ))}
          <p className="small muted">Illustrative preview. Weights are provisional.</p>
        </>
      ) : (
        <p className="muted">Calculating…</p>
      )}
    </aside>
  );
}
