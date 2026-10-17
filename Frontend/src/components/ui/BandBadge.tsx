import type { Scores } from "@/api/types";
import { badge } from "./styles";

const BAND_DOT: Record<Scores["band"], string> = {
  Strong: "bg-good",
  Promising: "bg-accent",
  Watch: "bg-warning",
  Early: "bg-serious",
};

export function BandBadge({ band }: { band: Scores["band"] }) {
  return (
    <span className={badge}>
      <span className={`size-2 rounded-full ${BAND_DOT[band]}`} aria-hidden />
      {band}
    </span>
  );
}
