import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/api/client";
import { PIPELINE_STAGES, type PipelineStage } from "@/api/types";
import { StageSelect } from "@/components/StageSelect";
import { BandBadge, cx, Meter, PageHeader } from "@/components/ui";
import { PIPELINE_LABELS } from "@/lib/format";
import { useAppData } from "@/state/AppData";

export function Pipeline() {
  const { startups, error, upsertStartup } = useAppData();
  const [dragging, setDragging] = useState<string | null>(null);
  const [over, setOver] = useState<PipelineStage | null>(null);
  const [moveError, setMoveError] = useState<string | null>(null);

  const move = async (slug: string, stage: PipelineStage) => {
    const startup = startups.find((s) => s.slug === slug);
    if (!startup || startup.pipeline_stage === stage) return;
    upsertStartup({ ...startup, pipeline_stage: stage }); // optimistic
    setMoveError(null);
    try {
      await api.setPipeline(slug, stage);
    } catch (e) {
      upsertStartup(startup);
      setMoveError((e as Error).message);
    }
  };

  return (
    <>
      <PageHeader title="Pipeline" description="Drag deals between stages, or use the stage menu on each card." />
      {error && <p className="text-critical">{error}</p>}
      {moveError && <p className="text-small text-critical">Couldn't move deal: {moveError}</p>}
      <div className="grid grid-cols-[repeat(6,minmax(180px,1fr))] gap-3 overflow-x-auto pb-2">
        {PIPELINE_STAGES.map((stage) => {
          const deals = startups.filter((s) => s.pipeline_stage === stage);
          return (
            <section
              key={stage}
              className={cx(
                "flex min-h-80 flex-col gap-2 rounded-card bg-surface-2 p-2.5",
                over === stage && "outline-2 -outline-offset-2 outline-accent outline-dashed",
              )}
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
              <div className="flex justify-between px-1 pt-0.5 pb-1.5 text-small font-semibold">
                <span>{PIPELINE_LABELS[stage]}</span>
                <span className="text-muted tabular-nums">{deals.length}</span>
              </div>
              {deals.map((s) => (
                <article
                  key={s.slug}
                  className="flex cursor-grab flex-col gap-2 rounded-lg border border-line bg-surface p-2.5 active:cursor-grabbing"
                  draggable
                  onDragStart={() => setDragging(s.slug)}
                  onDragEnd={() => setDragging(null)}
                >
                  <div className="flex items-center justify-between gap-2">
                    <Link to={`/startups/${s.slug}`}>
                      <strong>{s.name}</strong>
                    </Link>
                    <BandBadge band={s.scores.band} />
                  </div>
                  <span className="text-small text-fg-2">{s.sector}</span>
                  <Meter value={s.scores.potential} label="Investment potential" />
                  <StageSelect
                    id={`stage-${s.slug}`}
                    label={`Stage for ${s.name}`}
                    value={s.pipeline_stage}
                    onChange={(stage) => move(s.slug, stage)}
                    compact
                  />
                </article>
              ))}
            </section>
          );
        })}
      </div>
    </>
  );
}
