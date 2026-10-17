import type { ReactNode } from "react";

interface Props {
  title: ReactNode;
  /** Shown next to the title, e.g. a band badge. */
  badge?: ReactNode;
  description?: ReactNode;
  /** A muted line under the description, e.g. sector · location · stage. */
  meta?: ReactNode;
  /** Buttons or controls on the right. */
  actions?: ReactNode;
}

export function PageHeader({ title, badge, description, meta, actions }: Props) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
      <div>
        {badge ? (
          <div className="mb-1.5 flex flex-wrap items-center gap-2">
            <h1>{title}</h1>
            {badge}
          </div>
        ) : (
          <h1>{title}</h1>
        )}
        {description && <p className="mt-1 text-fg-2">{description}</p>}
        {meta && <p className="mt-1.5 text-small text-fg-2">{meta}</p>}
      </div>
      {actions}
    </div>
  );
}
