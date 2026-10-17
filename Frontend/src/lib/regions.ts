export const REGIONS = [
  { id: "europe", label: "Europe" },
  { id: "north-america", label: "North America" },
  { id: "latin-america", label: "Latin America" },
  { id: "asia", label: "Asia" },
  { id: "africa", label: "Africa" },
  { id: "oceania", label: "Oceania" },
] as const;

export type Region = (typeof REGIONS)[number]["id"];

const COUNTRIES_BY_REGION: Record<Region, string[]> = {
  europe: [
    "Austria",
    "Belgium",
    "Denmark",
    "Estonia",
    "Faroe Islands",
    "Finland",
    "France",
    "Germany",
    "Greece",
    "Iceland",
    "Ireland",
    "Italy",
    "Netherlands",
    "Norway",
    "Poland",
    "Portugal",
    "Spain",
    "Sweden",
    "Switzerland",
    "United Kingdom",
  ],
  "north-america": ["Canada", "Mexico", "United States"],
  "latin-america": ["Argentina", "Brazil", "Chile", "Colombia", "Peru"],
  asia: [
    "China",
    "Hong Kong",
    "India",
    "Indonesia",
    "Israel",
    "Japan",
    "Malaysia",
    "Philippines",
    "Singapore",
    "South Korea",
    "Taiwan",
    "Thailand",
    "United Arab Emirates",
    "Vietnam",
  ],
  africa: ["Egypt", "Ghana", "Kenya", "Morocco", "Namibia", "Nigeria", "South Africa", "Tanzania"],
  oceania: ["Australia", "Fiji", "New Zealand"],
};

const REGION_BY_COUNTRY = new Map(
  Object.entries(COUNTRIES_BY_REGION).flatMap(([region, countries]) =>
    countries.map((c) => [c.toLowerCase(), region as Region] as const),
  ),
);

export function regionOf(country: string): Region | null {
  return REGION_BY_COUNTRY.get(country.toLowerCase()) ?? null;
}

export function regionLabel(id: Region): string {
  return REGIONS.find((r) => r.id === id)?.label ?? id;
}
