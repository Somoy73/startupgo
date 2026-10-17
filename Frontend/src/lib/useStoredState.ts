import { useEffect, useRef, useState } from "react";

/**
 * useState remembered in this browser (localStorage). For per-viewer conveniences only.
 *
 * The page is rendered on the server first, where there is no storage, so the stored value
 * is read after mounting (the first render matches the server's). Storage can also be
 * unavailable in the browser (private mode, blocked); then this acts like useState.
 * `validate` turns whatever was stored into a valid value, or null to keep the initial one.
 */
export function useStoredState<T>(key: string, initial: T, validate: (stored: unknown) => T | null) {
  const [value, setValue] = useState<T>(initial);
  const loaded = useRef(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(key);
      const stored = raw === null ? null : validate(JSON.parse(raw));
      if (stored !== null) setValue(stored);
    } catch {
      // Unreadable or unavailable: keep the initial value.
    }
    loaded.current = true;
    // Read once per key; `validate` is expected to be stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    if (!loaded.current) return;
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // Not persisted; the value still works for this visit.
    }
  }, [key, value]);

  return [value, setValue] as const;
}
