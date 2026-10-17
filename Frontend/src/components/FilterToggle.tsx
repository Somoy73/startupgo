import { SlidersHorizontal, X } from "lucide-react";
import { cn } from "../lib/utils";
import { Button } from "./ui/button";

type Props = {
  /** How many filter values are set; the button turns solid above 0. */
  count: number;
  open: boolean;
  onToggle: () => void;
  onClear: () => void;
  /** Id of the filter panel the button shows and hides. */
  controls: string;
};

/** "Filters" button that opens the filter panel, joined to an × that clears them once any is set. */
export function FilterToggle({ count, open, onToggle, onClear, controls }: Props) {
  const active = count > 0;
  return (
    <div role="group" aria-label="Filters" className="btn-group">
      <Button
        type="button"
        className={cn("btn inline-flex items-center gap-2", active && "btn-primary")}
        aria-expanded={open}
        aria-controls={controls}
        onClick={onToggle}
      >
        <SlidersHorizontal aria-hidden className="size-4" />
        Filters
        {active && <span className="small tabular opacity-80">{count}</span>}
      </Button>
      {active && (
        <Button
          type="button"
          className="btn btn-primary inline-flex items-center"
          title="Clear filters"
          aria-label="Clear filters"
          onClick={onClear}
        >
          <X aria-hidden className="size-4" />
        </Button>
      )}
    </div>
  );
}
