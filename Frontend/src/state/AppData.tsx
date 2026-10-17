import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "../api/client";
import { frameworks } from "../api/mock-data";
import type { StartupDetail } from "../api/types";
type Data = {
  startups: StartupDetail[];
  frameworks: typeof frameworks;
  vocabulary: { sectors: string[]; countries: string[] };
  loading: boolean;
  error: string | null;
  upsertStartup: (s: StartupDetail) => void;
};
const Context = createContext<Data | null>(null);
export function AppDataProvider({ children }: { children: ReactNode }) {
  const [startups, setStartups] = useState<StartupDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api
      .listStartups()
      .then(setStartups)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);
  return (
    <Context.Provider
      value={{
        startups,
        frameworks,
        vocabulary: {
          sectors: [...new Set(startups.map((s) => s.sector))],
          countries: [...new Set(startups.map((s) => s.country))],
        },
        loading,
        error,
        upsertStartup: (s) =>
          setStartups((items) =>
            items.some((o) => o.slug === s.slug)
              ? items.map((o) => (o.slug === s.slug ? s : o))
              : [...items, s],
          ),
      }}
    >
      {children}
    </Context.Provider>
  );
}
export function useAppData() {
  const data = useContext(Context);
  if (!data) throw new Error("AppDataProvider missing");
  return data;
}
