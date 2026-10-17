import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { LuChevronLeft } from "react-icons/lu";

export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="mb-3 inline-flex items-center gap-1 text-note">
      <LuChevronLeft size={16} /> {children}
    </Link>
  );
}
