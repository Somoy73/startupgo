import type { SVGProps } from "react";

const base: SVGProps<SVGSVGElement> = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
};

export const IconDeals = () => (
  <svg {...base}>
    <path d="M3 5h18M3 12h18M3 19h12" />
  </svg>
);
export const IconPipeline = () => (
  <svg {...base}>
    <rect x="3" y="4" width="5" height="16" rx="1.5" />
    <rect x="10" y="4" width="5" height="11" rx="1.5" />
    <rect x="17" y="4" width="4" height="7" rx="1.5" />
  </svg>
);
export const IconCompare = () => (
  <svg {...base}>
    <path d="M8 3v18M16 3v18M3 8h5M16 14h5M3 16h5M16 6h5" />
  </svg>
);
export const IconBook = () => (
  <svg {...base}>
    <path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z" />
    <path d="M4 19V5" />
  </svg>
);
export const IconSearch = () => (
  <svg {...base}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </svg>
);
export const IconAlert = () => (
  <svg {...base}>
    <path d="M12 3 2 20h20z" />
    <path d="M12 10v4M12 17h.01" />
  </svg>
);
export const IconBack = () => (
  <svg {...base} width="16" height="16">
    <path d="m15 18-6-6 6-6" />
  </svg>
);
export const IconSun = () => (
  <svg {...base}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </svg>
);
export const IconMoon = () => (
  <svg {...base}>
    <path d="M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10z" />
  </svg>
);
export const IconExternal = () => (
  <svg {...base} width="13" height="13">
    <path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />
  </svg>
);
export const IconX = () => (
  <svg {...base} width="14" height="14">
    <path d="M18 6 6 18M6 6l12 12" />
  </svg>
);
export const IconTarget = () => (
  <svg {...base}>
    <circle cx="12" cy="12" r="9" />
    <circle cx="12" cy="12" r="5" />
    <circle cx="12" cy="12" r="1" />
  </svg>
);
export const IconClipboard = () => (
  <svg {...base}>
    <rect x="5" y="4" width="14" height="17" rx="2" />
    <path d="M9 4V3h6v1M9 11h6M9 15h4" />
  </svg>
);
export const IconCheck = () => (
  <svg {...base} width="14" height="14">
    <path d="m5 12 5 5 9-10" />
  </svg>
);
export const IconPlus = () => (
  <svg {...base} width="16" height="16">
    <path d="M12 5v14M5 12h14" />
  </svg>
);
