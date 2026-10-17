export const REGIONS = [
  { id: "europe", label: "Europe" },
  { id: "north-america", label: "North America" },
  { id: "latin-america", label: "Latin America" },
  { id: "asia", label: "Asia" },
  { id: "africa", label: "Africa" },
  { id: "oceania", label: "Oceania" },
  { id: "nordics", label: "Nordics" },
  { id: "baltics", label: "Baltics" },
] as const;

export type Region = (typeof REGIONS)[number]["id"];

type Continent = Exclude<Region, "nordics" | "baltics">;

const COUNTRIES_BY_REGION: Record<Continent, string[]> = {
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
    "Latvia",
    "Lithuania",
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

/** Sub-regions overlap a continent: a Finnish startup is in both Europe and the Nordics. */
const SUBREGIONS: Record<Exclude<Region, Continent>, string[]> = {
  nordics: ["Denmark", "Faroe Islands", "Finland", "Iceland", "Norway", "Sweden"],
  baltics: ["Estonia", "Latvia", "Lithuania"],
};

const REGION_BY_COUNTRY = new Map(
  Object.entries(COUNTRIES_BY_REGION).flatMap(([region, countries]) =>
    countries.map((c) => [c.toLowerCase(), region as Continent] as const),
  ),
);

/** The continent a country belongs to. */
export function regionOf(country: string): Continent | null {
  return REGION_BY_COUNTRY.get(country.toLowerCase()) ?? null;
}

export function inRegion(country: string, region: Region): boolean {
  const key = country.toLowerCase();
  if (region in SUBREGIONS) return SUBREGIONS[region as keyof typeof SUBREGIONS].some((c) => c.toLowerCase() === key);
  return REGION_BY_COUNTRY.get(key) === region;
}

export function regionLabel(id: Region): string {
  return REGIONS.find((r) => r.id === id)?.label ?? id;
}
