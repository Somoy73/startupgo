import { Button } from "../../components/ui/button";
import { useMemo, useState } from "react";
import { useSearchParams } from "../../lib/navigation";
import { api } from "../../api/client";
import { IconPlus } from "../../components/Icons";
import { MatchCard } from "../../components/matching/MatchCard";
import { ThesisEditor } from "../../components/matching/ThesisEditor";
import { matchBand, rankMatches, type Thesis } from "../../lib/matching";
import { isPreset, newThesis, useTheses, preset } from "../../lib/theses";
import { useAppData } from "../../state/AppData";

export function Matching() {
  const { startups, vocabulary, frameworks, upsertStartup } = useAppData();
  const { theses, save, remove } = useTheses();
  const [params, setParams] = useSearchParams();
  const [edits, setEdits] = useState<Record<string, Thesis>>({});
  const [hideWeak, setHideWeak] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const selectedId = params.get("thesis") ?? (theses[0] ?? preset).id;
  const saved = theses.find((t) => t.id === selectedId) ?? theses[0] ?? preset;
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
    select((theses[0] ?? preset).id);
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
      <div className="page-head">
        <div>
          <h1>Matching</h1>
          <p>Not implemented !</p>
        </div>
      </div>

      <div className="matching-layout">
        <section className="card card-pad thesis-panel">
          <div className="row-gap" style={{ marginBottom: 14 }}>
            <label className="visually-hidden" htmlFor="thesis">
              Thesis
            </label>
            <select
              id="thesis"
              className="select grow"
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
            <Button
              className="btn icon-btn"
              type="button"
              onClick={createNew}
              aria-label="New thesis"
            >
              <IconPlus />
            </Button>
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

          <div className="row-gap" style={{ marginTop: 18 }}>
            {dirty && (
              <>
                <Button className="btn btn-primary" type="button" onClick={saveChanges}>
                  {isPreset(saved) ? "Save as my thesis" : "Save changes"}
                </Button>
                <Button className="btn" type="button" onClick={discard}>
                  Reset
                </Button>
              </>
            )}
            {!isPreset(saved) && (
              <Button className="btn btn-danger" type="button" onClick={deleteThesis}>
                Delete
              </Button>
            )}
          </div>
          <p className="small muted" style={{ marginTop: 12 }}>
            Preview theses last for this session.
          </p>
        </section>

        <section>
          <div className="match-summary">
            <span className="small secondary">
              {counts["Strong fit"]} strong · {counts["Partial fit"]} partial · {counts["Weak fit"]}{" "}
              weak
            </span>
            <label className="small row-gap">
              <input
                type="checkbox"
                checked={hideWeak}
                onChange={(e) => setHideWeak(e.target.checked)}
              />
              Hide weak fits
            </label>
          </div>
          {actionError && <p className="small error">{actionError}</p>}
          <div className="stack" style={{ gap: 10 }}>
            {visible.map((m, i) => (
              <MatchCard key={m.startup.slug} rank={i + 1} match={m} onShortlist={shortlist} />
            ))}
            {visible.length === 0 && <p className="card empty">No startups fit this thesis yet.</p>}
          </div>
        </section>
      </div>
    </>
  );
}
