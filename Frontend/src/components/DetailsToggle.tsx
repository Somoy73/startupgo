import { ChevronDown } from "lucide-react";
import { cn } from "../lib/utils";
import { Button } from "./ui/button";

type Props = {
  open: boolean;
  onToggle: () => void;
  /** Id of the element the button shows and hides. */
  controls: string;
  showLabel?: string;
  hideLabel?: string;
};

/** "Show details ▾" button for a box's header; expands extra detail inside the box. */
export function DetailsToggle({
  open,
  onToggle,
  controls,
  showLabel = "Show details",
  hideLabel = "Hide details",
}: Props) {
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      aria-expanded={open}
      aria-controls={controls}
      onClick={onToggle}
    >
      {open ? hideLabel : showLabel}
      <ChevronDown aria-hidden className={cn("transition-transform", open && "rotate-180")} />
    </Button>
  );
}
