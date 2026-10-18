import { useEffect, useState, type ReactNode } from "react";
import { cn } from "../lib/utils";

/** Matches the .slide-collapse transition in styles.css. */
const DURATION_MS = 250;

/**
 * Content that slides open and closed (height) instead of jumping. Closed content is `hidden` once the
 * slide ends, so it stays out of the tab order and the accessibility tree, like a plain `hidden` toggle.
 */
export function Collapse({
  open,
  id,
  className,
  children,
}: {
  open: boolean;
  /** For the toggle's aria-controls. */
  id?: string;
  className?: string;
  children: ReactNode;
}) {
  const [shown, setShown] = useState(open); // in the page (not `hidden`)
  const [expanded, setExpanded] = useState(open); // at full height

  useEffect(() => {
    if (open) {
      setShown(true);
      // Expand a frame after unhiding, so the height transition has a closed state to start from.
      const frame = requestAnimationFrame(() => setExpanded(true));
      return () => cancelAnimationFrame(frame);
    }
    setExpanded(false);
    const timer = setTimeout(() => setShown(false), DURATION_MS);
    return () => clearTimeout(timer);
  }, [open]);

  return (
    <div id={id} hidden={!shown} data-open={expanded} className="slide-collapse">
      <div className={cn("slide-collapse-inner", className)}>{children}</div>
    </div>
  );
}
