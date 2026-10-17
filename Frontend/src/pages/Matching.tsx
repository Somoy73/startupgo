import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { LuPlus } from "react-icons/lu";
import { api } from "@/api/client";
import { button, card, cardPad, control, cx, PageHeader, row } from "@/components/ui";
import { MatchCard } from "@/components/matching/MatchCard";
import { ThesisEditor } from "@/components/matching/ThesisEditor";
import { matchBand, rankMatches, type Thesis } from "@/lib/matching";
import { isPreset, newThesis, useTheses } from "@/lib/theses";
import { useAppData } from "@/state/AppData";

export function Matching() {
  const { startups, vocabulary, frameworks, upsertStartup } = useAppData();
  const { theses, save, remove } = useTheses();
  const [params, setParams] = useSearchParams();
  const [edits, setEdits] = useState<Record<string, Thesis>>({});
  const [hideWeak, setHideWeak] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const selectedId = params.get("thesis") ?? theses[0].id;
  const saved = theses.find((t) => t.id === selectedId) ?? theses[0];
  const thesis = edits[saved.id] ?? saved;
  const dirty = JSON.stringify(thesis) !== JSON.stringify(saved);

  const select = (id: string) => setParams({ thesis: id }, { replace: true });
  const edit = (t: Thesis) => setEdits((e) => ({ ...e, [saved.id]: t }));
  const discard = () =>
    setEdits((e) => {
      const rest = { ...e };
      delete rest[saved.id];
      return rest;
    });

  const persist = (t: Thesis) => {
    save(t);
    discard();
    select(t.id);
  };
  const saveChanges = () => (isPreset(saved) ? persist(newThesis(thesis)) : persist(thesis));
  const createNew = () => persist(newThesis());
  const deleteThesis = () => {
    remove(saved.id);
    discard();
    select(theses[0].id);
  };

  const matches = useMemo(() => rankMatches(startups, thesis), [startups, thesis]);
  const counts = useMemo(() => {
    const c = { "Strong fit": 0, "Partial fit": 0, "Weak fit": 0 };
    for (const m of matches) c[matchBand(m)]++;
    return c;
  }, [matches]);
  const visible = hideWeak ? matches.filter((m) => matchBand(m) !== "Weak fit") : matches;

  const shortlist = async (slug: string) => {
    setActionError(null);
    try {
      upsertStartup(await api.setPipeline(slug, "screening"));
    } catch (e) {
      setActionError((e as Error).message);
    }
  };

  return (
    <>
      <PageHeader
        title="Matching"
        description="Describe your investment thesis; startups are ranked by fit and investment potential."
      />

      <div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-[380px_minmax(0,1fr)]">
        <section className={cx(card, cardPad, "xl:sticky xl:top-5")}>
          <div className={cx(row, "mb-3.5")}>
            <label className="sr-only" htmlFor="thesis">
              Thesis
            </label>
            <select
              id="thesis"
              className={cx(control, "flex-auto")}
              value={saved.id}
              onChange={(e) => select(e.target.value)}
            >
              <optgroup label="Presets">
                {theses.filter(isPreset).map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </optgroup>
              {theses.some((t) => !isPreset(t)) && (
                <optgroup label="My theses">
                  {theses
                    .filter((t) => !isPreset(t))
                    .map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                </optgroup>
              )}
            </select>
            <button
              className={button("default", { icon: true })}
              type="button"
              onClick={createNew}
              aria-label="New thesis"
            >
              <LuPlus size={16} />
            </button>
          </div>

          {frameworks && (
            <ThesisEditor
              thesis={thesis}
              editableName={!isPreset(saved)}
              sectors={vocabulary.sectors}
              impactAreas={frameworks.ocean_impact_areas}
              onChange={edit}
            />
          )}

          <div className={cx(row, "mt-4.5")}>
            {dirty && (
              <>
                <button className={button("primary")} type="button" onClick={saveChanges}>
                  {isPreset(saved) ? "Save as my thesis" : "Save changes"}
                </button>
                <button className={button()} type="button" onClick={discard}>
                  Reset
                </button>
              </>
            )}
            {!isPreset(saved) && (
              <button className={button("danger")} type="button" onClick={deleteThesis}>
                Delete
              </button>
            )}
          </div>
          <p className="mt-3 text-small text-muted">Custom theses are saved in this browser.</p>
        </section>

        <section>
          <div className="mb-2.5 flex flex-wrap items-center justify-between gap-3">
            <span className="text-small text-fg-2">
              {counts["Strong fit"]} strong · {counts["Partial fit"]} partial · {counts["Weak fit"]} weak
            </span>
            <label className={cx(row, "text-small")}>
              <input type="checkbox" checked={hideWeak} onChange={(e) => setHideWeak(e.target.checked)} />
              Hide weak fits
            </label>
          </div>
          {actionError && <p className="text-small text-critical">{actionError}</p>}
          <div className="flex flex-col gap-2.5">
            {visible.map((m, i) => (
              <MatchCard key={m.startup.slug} rank={i + 1} match={m} onShortlist={shortlist} />
            ))}
            {visible.length === 0 && (
              <p className={cx(card, "p-10 text-center text-muted")}>No startups fit this thesis yet.</p>
            )}
          </div>
        </section>
      </div>
    </>
  );
}
