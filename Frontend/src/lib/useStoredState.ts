import { useEffect, useState } from "react";

/**
 * useState remembered in this browser (localStorage). For per-viewer conveniences only:
 * storage can be unavailable (private mode, blocked), in which case it acts like useState.
 * `validate` turns whatever was stored into a valid value, or null to use the default.
 */
export function useStoredState<T>(key: string, initial: T, validate: (stored: unknown) => T | null) {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? initial : (validate(JSON.parse(raw)) ?? initial);
    } catch {
      return initial;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // Not persisted; the value still works for this visit.
    }
  }, [key, value]);

  return [value, setValue] as const;
}
