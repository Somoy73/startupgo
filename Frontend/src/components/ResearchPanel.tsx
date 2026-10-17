import { useEffect, useState } from "react";
import { ApiError, backend } from "../api/backend";
import { IconAlert } from "./Icons";

const POLL_MS = 3000;

/**
 * Shown on a sourced startup the research agent hasn't scored. Opening the page queues the agent, polls its job and
 * calls onDone once the score is stored. A 409 means it was researched recently without a usable result.
 */
export function ResearchPanel({ slug, onDone }: { slug: string; onDone: () => void }) {
  const [message, setMessage] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const fail = (text: string) => {
      if (!active) return;
      setFailed(true);
      setMessage(text);
    };
    const poll = (id: number) => {
      backend
        .researchJob(id)
        .then((job) => {
          if (!active) return;
          if (job.status === "done") onDone();
          else if (job.status === "error") fail(job.error ?? "The research agent failed.");
          else timer = setTimeout(() => poll(id), POLL_MS);
        })
        .catch((e: unknown) => fail(e instanceof Error ? e.message : "Couldn't read the research job."));
    };
    backend
      .startResearch(slug)
      .then((job) => poll(job.id))
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 409) fail(e.message);
        else fail(e instanceof Error ? e.message : "Couldn't start research.");
      });
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [slug, onDone]);

  return (
    <div className="notice">
      <IconAlert />
      <span>
        {failed ? (
          <>
            <strong>Not assessed.</strong> {message}
          </>
        ) : (
          <>
            <strong>Researching…</strong> The research agent is reading public sources to score this
            startup. This can take a few minutes; the page updates when it finishes.
          </>
        )}
      </span>
    </div>
  );
}
