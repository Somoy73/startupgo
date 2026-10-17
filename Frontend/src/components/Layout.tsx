import { useCallback, useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { CommandPalette } from "./CommandPalette";
import {
  IconBook,
  IconClipboard,
  IconCompare,
  IconDeals,
  IconMoon,
  IconPipeline,
  IconSearch,
  IconSun,
  IconTarget,
} from "./Icons";

type Theme = "light" | "dark";

const NAV = [
  { to: "/", label: "Deal flow", icon: IconDeals, end: true },
  { to: "/matching", label: "Matching", icon: IconTarget },
  { to: "/assess", label: "Assess", icon: IconClipboard },
  { to: "/pipeline", label: "Pipeline", icon: IconPipeline },
  { to: "/compare", label: "Compare", icon: IconCompare },
  { to: "/methodology", label: "Methodology", icon: IconBook },
];

function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem("sg-theme");
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* storage unavailable */
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function Layout() {
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const closePalette = useCallback(() => setPaletteOpen(false), []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("sg-theme", theme);
    } catch {
      /* storage unavailable */
    }
  }, [theme]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="shell">
      <aside className="sidebar">
        <NavLink to="/" className="brand">
          <img src="/favicon.svg" alt="" />
          <span>Startup Go</span>
        </NavLink>
        <button className="quick-search" onClick={() => setPaletteOpen(true)} aria-label="Quick search">
          <IconSearch />
          <span>Quick search</span>
          <kbd>⌘K</kbd>
        </button>
        <nav className="nav" aria-label="Main">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end}>
              <Icon /> <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <button
            className="btn icon-btn"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          >
            {theme === "dark" ? <IconSun /> : <IconMoon />}
          </button>
          <span className="small muted">Ocean & deep-tech deal intelligence</span>
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
      <CommandPalette open={paletteOpen} onClose={closePalette} />
    </div>
  );
}
