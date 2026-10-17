import { api } from "../api/client";
import { useAsync } from "./useAsync";
import type { AssessmentDraft } from "./assessment";
export function useScorePreview(input: { draft: AssessmentDraft }) {
  const result = useAsync(() => api.scorePreview(input), [JSON.stringify(input)]);
  return { scores: result.data, error: result.error };
}
