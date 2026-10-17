import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "@/api/client";
import type { Frameworks, StartupSummary } from "@/api/types";
import { vocabularyOf, type Vocabulary } from "@/lib/search";

/**
 * App-wide data: the startup list (small enough to search and match client-side)
 * and the static framework definitions. Loaded once, shared by every page.
 */
interface AppData {
  startups: StartupSummary[];
  vocabulary: Vocabulary;
  frameworks: Frameworks | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  upsertStartup: (startup: StartupSummary) => void;
}

const AppDataContext = createContext<AppData | null>(null);

export function AppDataProvider({ children }: { children: ReactNode }) {
  const [startups, setStartups] = useState<StartupSummary[]>([]);
  const [frameworks, setFrameworks] = useState<Frameworks | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [list, fw] = await Promise.all([api.startups(), api.frameworks()]);
      setStartups(list);
      setFrameworks(fw);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const upsertStartup = useCallback((startup: StartupSummary) => {
    setStartups((list) =>
      list.some((s) => s.slug === startup.slug)
        ? list.map((s) => (s.slug === startup.slug ? startup : s))
        : [...list, startup],
    );
  }, []);

  const value = useMemo(
    () => ({ startups, vocabulary: vocabularyOf(startups), frameworks, loading, error, refresh, upsertStartup }),
    [startups, frameworks, loading, error, refresh, upsertStartup],
  );

  return <AppDataContext.Provider value={value}>{children}</AppDataContext.Provider>;
}

export function useAppData(): AppData {
  const ctx = useContext(AppDataContext);
  if (!ctx) throw new Error("useAppData must be used inside <AppDataProvider>");
  return ctx;
}
