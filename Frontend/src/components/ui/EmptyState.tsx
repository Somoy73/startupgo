import type { ReactNode } from "react";

/** Centred placeholder for loading, empty and error states. */
export function EmptyState({ children, error = false }: { children: ReactNode; error?: boolean }) {
  return <p className={`p-10 text-center ${error ? "text-critical" : "text-muted"}`}>{children}</p>;
}
