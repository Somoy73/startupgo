import { useState } from "react";
import type { Thesis } from "./matching";
export const preset: Thesis = {
  id: "ocean",
  name: "Ocean & deep-tech",
  sectors: [],
  impactAreas: [],
  minTrl: 5,
  minPotential: 55,
  preset: true,
};
export const isPreset = (t: Thesis) => !!t.preset;
export const newThesis = (t?: Thesis): Thesis => ({
  ...t,
  id: crypto.randomUUID(),
  name: t ? `${t.name} copy` : "My thesis",
  sectors: t?.sectors ?? [],
  impactAreas: t?.impactAreas ?? [],
  minTrl: t?.minTrl ?? 1,
  minPotential: t?.minPotential ?? 0,
  preset: false,
});
export function useTheses() {
  const [theses, set] = useState<Thesis[]>([preset]);
  return {
    theses,
    save: (t: Thesis) =>
      set((old) =>
        old.some((o) => o.id === t.id) ? old.map((o) => (o.id === t.id ? t : o)) : [...old, t],
      ),
    remove: (id: string) => set((old) => old.filter((o) => o.id !== id)),
  };
}
