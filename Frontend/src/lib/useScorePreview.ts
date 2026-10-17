import { useEffect, useState } from "react";
import { api } from "@/api/client";
import type { Scores, ScorePreviewInput } from "@/api/types";

const DEBOUNCE_MS = 250;

/** Live scores for an unsaved assessment, computed by the backend's scoring model. */
export function useScorePreview(input: ScorePreviewInput | null): { scores: Scores | null; error: string | null } {
  const [scores, setScores] = useState<Scores | null>(null);
  const [error, setError] = useState<string | null>(null);
  const key = input ? JSON.stringify(input) : null;

  useEffect(() => {
    if (!key) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      api
        .previewScores(JSON.parse(key) as ScorePreviewInput)
        .then((s) => {
          if (cancelled) return;
          setScores(s);
          setError(null);
        })
        .catch((e: Error) => {
          if (!cancelled) setError(e.message);
        });
    }, DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [key]);

  return { scores, error };
}
