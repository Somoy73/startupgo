import { useEffect, useState } from "react";
import { ApiError, backend } from "../../api/backend";
import type {
  ScrapeAgentInfo,
  ScrapedStartupAdded,
  ScrapeEvidence,
  ScrapeJob,
  ScrapeMode,
  ScrapeRecord,
  ScrapeResult,
  ScrapeSource,
  ScrapeTarget,
} from "../../api/backend-types";
import { Chip, type ChipTone } from "../../components/Chip";
import { IconAlert, IconExternal } from "../../components/Icons";
import {
  KIND_LABELS,
  MODE_LABELS,
  SCRAPE_PRESETS,
  canAddToDb,
  emptyDraft,
  parseUrls,
  recordsToCsv,
  togglePreset,
  type SourceDraft,
} from "../../lib/scrape";

const POLL_MS = 1500;
const MAX_SOURCES = 8;

const EVIDENCE: Record<ScrapeEvidence, { tone: ChipTone; label: string; title: string }> = {
  page: { tone: "success", label: "Quote on page", title: "The quote was found in the page text." },
  transcript: {
    tone: "info",
    label: "From PDF/image",
    title: "The quote was found in the model's text of a PDF or image.",
  },
  unverified: {
    tone: "warning",
    label: "Quote not found",
    title: "The quote isn't in the source text: treat this record as an assumption.",
  },
};
const SOURCE_TONES: Record<ScrapeSource["status"], ChipTone> = {
  read: "success",
  empty: "warning",
  skipped: "warning",
  error: "danger",
};

function download(name: string, type: string, content: string) {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([content], { type }));
  link.download = name;
  link.click();
  URL.revokeObjectURL(link.href);
}

/** The drafts as request sources, or the first problem to show. */
function toSources(drafts: SourceDraft[], maxPages: number): ScrapeTarget[] | string {
  const sources: ScrapeTarget[] = [];
  for (const d of drafts) {
    const name = drafts.length > 1 ? `${d.label}: ` : "";
    const { urls, invalid } = parseUrls(d.urlText);
    if (invalid.length) return `${name}Not a web address: ${invalid.join(", ")}`;
    if (d.goal.trim().length < 3) return `${name}Say what the agent should get.`;
    sources.push({
      goal: d.goal.trim(),
      urls,
      follow_links: d.followLinks,
      max_pages: maxPages,
      mode: d.mode,
      label: drafts.length > 1 ? d.label : "",
    });
  }
  return sources;
}

export function AgentScraper() {
  const [drafts, setDrafts] = useState<SourceDraft[]>(() => [emptyDraft()]);
  const [stealth, setStealth] = useState(true);
  const [maxPages, setMaxPages] = useState(8);
  const [info, setInfo] = useState<ScrapeAgentInfo | null>(null);
  const [llm, setLlm] = useState("");
  const [job, setJob] = useState<ScrapeJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const running = job !== null && (job.status === "queued" || job.status === "running");

  useEffect(() => {
    backend.scrapeInfo().then(
      (i) => {
        setInfo(i);
        setLlm(i.default);
      },
      () => setInfo(null),
    );
  }, []);

  const jobId = job?.id;
  useEffect(() => {
    if (!running || jobId === undefined) return;
    const timer = setInterval(() => {
      backend.scrapeJob(jobId).then(setJob, (e: unknown) => {
        setError(e instanceof Error ? e.message : "Couldn't read the scrape job.");
        setJob(null);
      });
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [running, jobId]);

  const update = (key: number, change: Partial<SourceDraft>) =>
    setDrafts((ds) => ds.map((d) => (d.key === key ? { ...d, ...change } : d)));
  const remove = (key: number) =>
    setDrafts((ds) => (ds.length > 1 ? ds.filter((d) => d.key !== key) : [emptyDraft()]));

  async function run() {
    const sources = toSources(drafts, maxPages);
    if (typeof sources === "string") return setError(sources);
    setError(null);
    try {
      setJob(await backend.startScrape({ sources, stealth, ...(llm ? { llm } : {}) }));
    } catch (e) {
      setError(
        e instanceof ApiError || e instanceof Error ? e.message : "Couldn't start the agent.",
      );
    }
  }

  const result = job?.status === "done" ? job.result : null;
  const model = info?.models.find((m) => m.name === llm);
  const selected = new Set(drafts.map((d) => d.presetId));
  return (
    <div className="landing">
      <div className="page-head">
        <div>
          <h1>Agent scraper</h1>
          <p>
            Pick one or more sources. The agent reads their pages, PDFs and images, and returns
            records with the quote behind each one, plus what it could not find. Startups it finds
            can go straight into the database.
          </p>
        </div>
      </div>

      <section className="dash-card" aria-labelledby="scrape-heading">
        <div className="dash-card-head">
          <h2 id="scrape-heading">What should it get?</h2>
          {model && info && (
            <span className="muted" style={{ fontSize: 12 }}>
              {model.model} ·{" "}
              {model.multimodal
                ? "reads PDFs and images"
                : "reads text PDFs; images and scanned PDFs need a multimodal model"}{" "}
              · {info.web_search ? "searches the web" : "no web search"}
              {!model.key_set && " · API key missing in Modules/Agent/.env"}
            </span>
          )}
        </div>

        <div className="row-gap" role="group" aria-label="Sources">
          {SCRAPE_PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              className={selected.has(preset.id) ? "btn btn-primary" : "btn"}
              aria-pressed={selected.has(preset.id)}
              disabled={running || (!selected.has(preset.id) && drafts.length >= MAX_SOURCES)}
              onClick={() => setDrafts((ds) => togglePreset(ds, preset))}
            >
              {preset.label}
            </button>
          ))}
          <button
            type="button"
            className="btn"
            disabled={running || drafts.length >= MAX_SOURCES}
            onClick={() => setDrafts((ds) => [...ds, emptyDraft(`Custom source ${ds.length + 1}`)])}
          >
            + Custom source
          </button>
        </div>

        <div className="stack" style={{ marginTop: 16, gap: 16 }}>
          {drafts.map((d) => (
            <SourceCard
              key={d.key}
              draft={d}
              several={drafts.length > 1}
              disabled={running}
              onChange={(change) => update(d.key, change)}
              onRemove={() => remove(d.key)}
            />
          ))}
          <div className="row-gap">
            <label
              className="row-gap"
              title="Chrome with the stealth patches. Off = plain HTTP, which many sites block."
            >
              <input
                type="checkbox"
                checked={stealth}
                onChange={(e) => setStealth(e.target.checked)}
                disabled={running}
              />
              Stealth browser
            </label>
            {info && info.models.length > 1 && (
              <label className="row-gap">
                Model
                <select
                  className="select"
                  value={llm}
                  onChange={(e) => setLlm(e.target.value)}
                  disabled={running}
                >
                  {info.models.map((m) => (
                    <option key={m.name} value={m.name}>
                      {m.name === "nvidia" ? "NVIDIA" : m.name === "gemini" ? "Gemini" : m.name}
                      {m.name === info.default ? " (default)" : ""}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label className="row-gap">
              Max pages per source
              <input
                className="input"
                type="number"
                min={1}
                max={20}
                value={maxPages}
                style={{ width: 72 }}
                onChange={(e) =>
                  setMaxPages(Math.min(20, Math.max(1, Number(e.target.value) || 1)))
                }
                disabled={running}
              />
            </label>
            <button type="button" className="btn btn-primary" onClick={run} disabled={running}>
              {running
                ? "Working…"
                : drafts.length > 1
                  ? `Run agent on ${drafts.length} sources`
                  : "Run agent"}
            </button>
          </div>
        </div>
      </section>

      {error && (
        <div className="notice" role="alert" style={{ marginTop: 20 }}>
          <IconAlert />
          <span>{error}</span>
        </div>
      )}
      {job && running && <Progress job={job} />}
      {job?.status === "error" && (
        <div className="notice" role="alert" style={{ marginTop: 20 }}>
          <IconAlert />
          <span>
            <strong>The agent stopped.</strong> {job.error}
          </span>
        </div>
      )}
      {result && <Result result={result} />}
    </div>
  );
}

function SourceCard({
  draft,
  several,
  disabled,
  onChange,
  onRemove,
}: {
  draft: SourceDraft;
  several: boolean;
  disabled: boolean;
  onChange: (change: Partial<SourceDraft>) => void;
  onRemove: () => void;
}) {
  const id = `source-${draft.key}`;
  return (
    <fieldset className="scrape-source" aria-label={draft.label}>
      <div className="row-gap">
        {several ? (
          <input
            className="input"
            aria-label="Source name"
            value={draft.label}
            maxLength={80}
            onChange={(e) => onChange({ label: e.target.value })}
            disabled={disabled}
            style={{ fontWeight: 700 }}
          />
        ) : (
          <strong>{draft.label}</strong>
        )}
        <label className="row-gap" htmlFor={`${id}-mode`}>
          Focus
        </label>
        <select
          id={`${id}-mode`}
          className="select"
          value={draft.mode}
          onChange={(e) => onChange({ mode: e.target.value as ScrapeMode })}
          disabled={disabled}
        >
          {Object.entries(MODE_LABELS).map(([mode, label]) => (
            <option key={mode} value={mode}>
              {label}
            </option>
          ))}
        </select>
        <label
          className="row-gap"
          title="Also read the links on these pages that match the goal, PDFs included."
        >
          <input
            type="checkbox"
            checked={draft.followLinks}
            onChange={(e) => onChange({ followLinks: e.target.checked })}
            disabled={disabled}
          />
          Follow relevant links
        </label>
        {(several || draft.presetId) && (
          <button
            type="button"
            className="btn"
            aria-label={`Remove ${draft.label}`}
            onClick={onRemove}
            disabled={disabled}
            style={{ marginLeft: "auto" }}
          >
            ×
          </button>
        )}
      </div>
      {draft.hint && (
        <p className="muted" style={{ fontSize: 12 }}>
          {draft.hint}
        </p>
      )}
      <label className="field">
        Goal
        <textarea
          className="textarea"
          rows={2}
          value={draft.goal}
          onChange={(e) => onChange({ goal: e.target.value })}
          placeholder="e.g. List open calls for ocean startups with deadline and budget"
          disabled={disabled}
        />
      </label>
      <label className="field">
        URLs (one per line; leave empty and the agent searches the web)
        <textarea
          className="textarea"
          rows={2}
          value={draft.urlText}
          onChange={(e) => onChange({ urlText: e.target.value })}
          placeholder="https://… pages, .pdf or image links"
          disabled={disabled}
        />
      </label>
    </fieldset>
  );
}

function Progress({ job }: { job: ScrapeJob }) {
  const last = job.progress.at(-1);
  return (
    <section className="dash-card" style={{ marginTop: 20 }} role="status">
      <strong>{job.status === "queued" ? "Queued…" : (last ?? "Starting…")}</strong>
      {job.progress.length > 1 && (
        <ul className="scrape-list muted">
          {job.progress.slice(0, -1).map((step, i) => (
            <li key={i}>{step}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Result({ result }: { result: ScrapeResult }) {
  const several = result.groups.length > 1;
  return (
    <section className="dash-card" style={{ marginTop: 20 }} aria-labelledby="scrape-result">
      <div className="dash-card-head">
        <h2 id="scrape-result">
          {result.records.length} record{result.records.length === 1 ? "" : "s"}
          {several && ` from ${result.groups.length} sources`}
        </h2>
        {result.records.length > 0 && (
          <div className="row-gap">
            <button
              type="button"
              className="btn"
              onClick={() =>
                download("scrape.json", "application/json", JSON.stringify(result, null, 2))
              }
            >
              Download JSON
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => download("scrape.csv", "text/csv", recordsToCsv(result.records))}
            >
              Download CSV
            </button>
          </div>
        )}
      </div>
      {several ? (
        <ul className="scrape-list plain">
          {result.groups.map((g) => (
            <li key={g.label}>
              <strong>{g.label}</strong>{" "}
              <span className="muted">
                {g.error ? `nothing read: ${g.error}` : `${g.records} records. ${g.summary}`}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        result.summary && <p>{result.summary}</p>
      )}
      {result.notices.map((notice) => (
        <div className="notice" key={notice} style={{ marginTop: 12, marginBottom: 0 }}>
          <IconAlert />
          <span>{notice}</span>
        </div>
      ))}

      {result.records.length > 0 && (
        <div className="table-wrap" style={{ marginTop: 12 }}>
          <table className="data">
            <thead>
              <tr>
                {several && <th>Source</th>}
                <th>Record</th>
                <th>Fields</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {result.records.map((record, i) => (
                <tr key={i}>
                  {several && <td className="muted">{record.group}</td>}
                  <td className="name-cell">
                    <div className="row-gap" style={{ gap: 6 }}>
                      <Chip tone="neutral">{KIND_LABELS[record.kind] ?? record.kind}</Chip>
                      <strong>{record.title}</strong>
                    </div>
                    <span>{record.details}</span>
                    {record.quote && <span>“{record.quote}”</span>}
                    {record.website && (
                      <span>
                        <a href={record.website} target="_blank" rel="noreferrer">
                          {record.website.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "")}
                        </a>
                      </span>
                    )}
                    {canAddToDb(record) && <AddToDb record={record} />}
                  </td>
                  <td>
                    {record.attributes.map((a, j) => (
                      <div key={j}>
                        <span className="muted">{a.name.replace(/_/g, " ")}:</span> {a.value}
                      </div>
                    ))}
                  </td>
                  <td>
                    <div className="row-gap" style={{ gap: 6 }}>
                      <Chip
                        tone={EVIDENCE[record.evidence].tone}
                        title={EVIDENCE[record.evidence].title}
                      >
                        {EVIDENCE[record.evidence].label}
                      </Chip>
                      {record.self_reported && (
                        <Chip
                          tone="warning"
                          title="Read on the company's own website: a claim, not independent evidence."
                        >
                          Self-reported
                        </Chip>
                      )}
                      {record.also_in.length > 0 && (
                        <Chip tone="primary" title="Other sources of this run describe it too.">
                          Also in {record.also_in.join(", ")}
                        </Chip>
                      )}
                    </div>
                    {record.source_url && (
                      <div>
                        <a
                          href={record.source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="dash-more"
                        >
                          source <IconExternal />
                        </a>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {result.gaps.length > 0 && (
        <>
          <h3 style={{ marginTop: 20 }}>Not found / check next</h3>
          <ul className="scrape-list">
            {result.gaps.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        </>
      )}

      <h3 style={{ marginTop: 20 }}>Sources</h3>
      <ul className="scrape-list plain">
        {result.sources.map((source) => (
          <li key={`${source.group}-${source.url}`} className="row-gap">
            <Chip tone={SOURCE_TONES[source.status]}>{source.status}</Chip>
            {several && <span className="muted">{source.group}</span>}
            <a href={source.url} target="_blank" rel="noreferrer">
              {source.url}
            </a>
            {source.status !== "read" && <span className="muted">{source.detail}</span>}
          </li>
        ))}
      </ul>
      <p className="muted" style={{ fontSize: 11, marginTop: 12 }}>
        {result.model} · {result.usage}
      </p>
    </section>
  );
}

const ADDED_TEXT: Record<ScrapedStartupAdded["status"], string> = {
  created: "Added to the database",
  promoted: "Added (it was a BlueInvest lead)",
  exists: "Already in the database: evidence added",
};

/** Add a scraped startup to the database; asks for a website when the record has none. */
function AddToDb({ record }: { record: ScrapeRecord }) {
  const [website, setWebsite] = useState("");
  const [state, setState] = useState<
    | { step: "idle" | "adding" }
    | { step: "added"; added: ScrapedStartupAdded }
    | { step: "error"; message: string }
  >({ step: "idle" });

  async function add() {
    setState({ step: "adding" });
    try {
      const added = await backend.addScrapedStartup(record, website.trim() || undefined);
      setState({ step: "added", added });
    } catch (e) {
      setState({ step: "error", message: e instanceof Error ? e.message : "Couldn't add it." });
    }
  }

  if (state.step === "added") {
    return (
      <span className="row-gap" style={{ gap: 6, marginTop: 6 }}>
        <Chip tone="success">{ADDED_TEXT[state.added.status]}</Chip>
        <a href={`/startups/${encodeURIComponent(state.added.slug)}`} className="dash-more">
          Open {state.added.name} →
        </a>
      </span>
    );
  }
  const needsWebsite = !record.website;
  return (
    <span className="row-gap" style={{ gap: 6, marginTop: 6 }}>
      {needsWebsite && (
        <input
          className="input"
          aria-label={`Website of ${record.title}`}
          placeholder="Website (needed)"
          value={website}
          onChange={(e) => setWebsite(e.target.value)}
          style={{ width: 180, padding: "6px 10px" }}
        />
      )}
      <button
        type="button"
        className="btn"
        style={{ minHeight: 30, padding: "4px 12px", fontSize: 12 }}
        onClick={add}
        disabled={state.step === "adding" || (needsWebsite && !website.trim())}
        title="Add as a sourced startup; opening it starts the research agent, which scores it."
      >
        {state.step === "adding" ? "Adding…" : "Add to DB"}
      </button>
      {state.step === "error" && <span className="muted">{state.message}</span>}
    </span>
  );
}
