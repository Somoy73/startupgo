import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { PIPELINE_STAGES, type PipelineStage } from "../api/types";
import { BandBadge, Meter } from "../components/Scores";
import { PIPELINE_LABELS } from "../lib/format";
import { useAsync } from "../lib/useAsync";

export function Pipeline() {
  const { data, error, setData } = useAsync(() => api.startups(), []);
  const [dragging, setDragging] = useState<string | null>(null);
  const [over, setOver] = useState<PipelineStage | null>(null);
  const [moveError, setMoveError] = useState<string | null>(null);

  const move = async (slug: string, stage: PipelineStage) => {
    if (!data) return;
    const previous = data;
    setData(data.map((s) => (s.slug === slug ? { ...s, pipeline_stage: stage } : s)));
    setMoveError(null);
    try {
      await api.setPipeline(slug, stage);
    } catch (e) {
      setData(previous);
      setMoveError((e as Error).message);
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Pipeline</h1>
          <p>Drag deals between stages, or use the stage menu on each card.</p>
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      {moveError && <p className="error small">Couldn't move deal: {moveError}</p>}
      <div className="board">
        {PIPELINE_STAGES.map((stage) => {
          const deals = (data ?? []).filter((s) => s.pipeline_stage === stage);
          return (
            <section
              key={stage}
              className={`column${over === stage ? " drop" : ""}`}
              aria-label={PIPELINE_LABELS[stage]}
              onDragOver={(e) => {
                e.preventDefault();
                setOver(stage);
              }}
              onDragLeave={() => setOver((o) => (o === stage ? null : o))}
              onDrop={(e) => {
                e.preventDefault();
                setOver(null);
                if (dragging) move(dragging, stage);
                setDragging(null);
              }}
            >
              <div className="column-head">
                <span>{PIPELINE_LABELS[stage]}</span>
                <span className="muted tabular">{deals.length}</span>
              </div>
              {deals.map((s) => (
                <article
                  key={s.slug}
                  className="deal"
                  draggable
                  onDragStart={() => setDragging(s.slug)}
                  onDragEnd={() => setDragging(null)}
                >
                  <div className="row">
                    <Link to={`/startups/${s.slug}`}><strong>{s.name}</strong></Link>
                    <BandBadge band={s.scores.band} />
                  </div>
                  <span className="small secondary">{s.sector}</span>
                  <Meter value={s.scores.potential} label="Investment potential" />
                  <label className="visually-hidden" htmlFor={`stage-${s.slug}`}>Stage for {s.name}</label>
                  <select
                    id={`stage-${s.slug}`}
                    className="select small"
                    value={s.pipeline_stage}
                    onChange={(e) => move(s.slug, e.target.value as PipelineStage)}
                  >
                    {PIPELINE_STAGES.map((p) => (
                      <option key={p} value={p}>{PIPELINE_LABELS[p]}</option>
                    ))}
                  </select>
                </article>
              ))}
            </section>
          );
        })}
      </div>
    </>
  );
}
