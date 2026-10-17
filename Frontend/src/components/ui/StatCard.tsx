import type { ReactNode } from "react";
import { Meter } from "./Meter";
import { card, cx } from "./styles";

interface Props {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  /** Larger value, for the headline number on a page. */
  hero?: boolean;
  /** Adds a bar under the value (0-100). */
  meter?: { value: number; label: string };
}

export function StatCard({ label, value, sub, hero = false, meter }: Props) {
  return (
    <div className={cx(card, "flex flex-col gap-1 px-4.5 py-4")}>
      <span className="text-ctl text-fg-2">{label}</span>
      <span className={hero ? "text-hero leading-none font-bold" : "text-stat leading-[1.1] font-[650]"}>{value}</span>
      {meter && <Meter value={meter.value} label={meter.label} showValue={false} />}
      {sub && <span className="text-sm text-muted">{sub}</span>}
    </div>
  );
}
