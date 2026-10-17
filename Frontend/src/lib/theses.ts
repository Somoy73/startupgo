import { useCallback, useState } from "react";
import type { Thesis } from "./matching";

/**
 * Investor theses. Presets ship with the app; custom theses live in this
 * browser's localStorage until the backend gets a theses table.
 */

export const PRESET_THESES: Thesis[] = [
  {
    id: "preset-blue-carbon",
    name: "Blue carbon & habitat restoration",
    stages: ["seed", "series-a", "project-finance"],
    sectors: [],
    regions: [],
    impactAreas: ["C", "D"],
    minTrl: 5,
    minBrl: null,
    minOceanImpact: 40,
    qualityWeight: 0.3,
  },
  {
    id: "preset-clean-ocean-europe",
    name: "Clean ocean, Europe",
    stages: [],
    sectors: [],
    regions: ["europe"],
    impactAreas: ["B"],
    minTrl: 6,
    minBrl: 5,
    minOceanImpact: null,
    qualityWeight: 0.4,
  },
  {
    id: "preset-ocean-data-growth",
    name: "Ocean data & shipping, Series A+",
    stages: ["series-a", "series-b", "series-c+"],
    sectors: ["Ocean data", "Shipping decarbonisation"],
    regions: [],
    impactAreas: ["D", "E"],
    minTrl: 7,
    minBrl: 6,
    minOceanImpact: null,
    qualityWeight: 0.4,
  },
];

const STORAGE_KEY = "sg-theses";

export const isPreset = (t: Thesis) => t.id.startsWith("preset-");

export function newThesis(base?: Thesis): Thesis {
  return {
    ...(base ?? {
      stages: [],
      sectors: [],
      regions: [],
      impactAreas: [],
      minTrl: null,
      minBrl: null,
      minOceanImpact: null,
      qualityWeight: 0.3,
    }),
    id: `custom-${Date.now().toString(36)}`,
    name: base ? `${base.name} (copy)` : "New thesis",
  };
}

function load(): Thesis[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Thesis[]) : [];
  } catch {
    return [];
  }
}

function persist(theses: Thesis[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(theses));
  } catch {
    /* storage unavailable: theses stay in memory for this session */
  }
}

export function useTheses() {
  const [custom, setCustom] = useState<Thesis[]>(load);

  const update = useCallback((next: Thesis[]) => {
    setCustom(next);
    persist(next);
  }, []);

  const save = useCallback(
    (thesis: Thesis) =>
      update(
        custom.some((t) => t.id === thesis.id)
          ? custom.map((t) => (t.id === thesis.id ? thesis : t))
          : [...custom, thesis],
      ),
    [custom, update],
  );

  const remove = useCallback((id: string) => update(custom.filter((t) => t.id !== id)), [custom, update]);

  return { theses: [...PRESET_THESES, ...custom], save, remove };
}
