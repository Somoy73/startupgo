import type { ReactNode } from "react";
import { card, cardPad, cx } from "./styles";

/** A padded card with a heading; `aside` sits on the right (text is rendered as a muted note). */
export function Section({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className={cx(card, cardPad)}>
      <div className="mb-3.5 flex flex-wrap items-baseline justify-between gap-3">
        <h2>{title}</h2>
        {typeof aside === "string" ? <span className="text-small text-muted">{aside}</span> : aside}
      </div>
      {children}
    </section>
  );
}
