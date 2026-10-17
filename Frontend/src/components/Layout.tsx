import { useCallback, useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  LuBookOpen,
  LuClipboardList,
  LuColumns2,
  LuKanban,
  LuList,
  LuMoon,
  LuSearch,
  LuSun,
  LuTarget,
} from "react-icons/lu";
import { button, cx } from "@/components/ui";
import { CommandPalette } from "./CommandPalette";

type Theme = "light" | "dark";

const NAV = [
  { to: "/", label: "Discover", icon: LuList, end: true },
  { to: "/matching", label: "Matching", icon: LuTarget },
  // { to: "/assess", label: "Assess", icon: LuClipboardList },
  { to: "/pipeline", label: "Pipeline", icon: LuKanban },
  { to: "/compare", label: "Compare", icon: LuColumns2 },
  { to: "/methodology", label: "Methodology", icon: LuBookOpen },
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
    <div className="grid min-h-screen grid-cols-[224px_minmax(0,1fr)] max-lg:grid-cols-[minmax(0,1fr)]">
      <aside
        className={cx(
          "sticky top-0 flex h-screen flex-col gap-6 border-r border-line bg-surface px-3.5 py-5",
          "max-lg:z-10 max-lg:h-auto max-lg:flex-row max-lg:items-center max-lg:gap-3 max-lg:overflow-x-auto",
          "max-lg:border-r-0 max-lg:border-b max-lg:px-4 max-lg:py-2.5",
        )}
      >
        <NavLink to="/" className="flex items-center gap-2.5 px-2 text-lg font-bold text-fg hover:no-underline">
          <img src="/favicon.svg" alt="" className="size-7" />
          <span className="max-lg:hidden">Startup Go</span>
        </NavLink>
        <button
          className="flex w-full cursor-pointer items-center gap-2 rounded-lg border border-line bg-surface-2 px-2.5 py-1.75 text-note text-muted hover:text-fg"
          onClick={() => setPaletteOpen(true)}
          aria-label="Quick search"
        >
          <LuSearch className="size-4" />
          <span>Quick search</span>
          <kbd className="ml-auto">⌘K</kbd>
        </button>
        <nav className="flex flex-col gap-0.5 max-lg:flex-row" aria-label="Main">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cx(
                  "flex items-center gap-2.5 rounded-lg px-2.5 py-2 font-medium hover:no-underline max-lg:py-1.5 max-lg:whitespace-nowrap",
                  isActive ? "bg-accent-wash text-accent-ink" : "text-fg-2 hover:bg-surface-2",
                )
              }
            >
              <Icon className="size-4.5 flex-none" /> <span className="max-lg:hidden">{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto flex flex-col items-start gap-2.5 px-2 max-lg:m-0 max-lg:ml-auto max-lg:flex-row max-lg:p-0">
          <button
            className={button("default", { icon: true })}
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          >
            {theme === "dark" ? <LuSun /> : <LuMoon />}
          </button>
          <span className="text-small text-muted max-lg:hidden">Ocean & deep-tech deal intelligence</span>
        </div>
      </aside>
      <main className="max-w-[1280px] min-w-0 px-8 pt-7 pb-16 max-lg:px-4 max-lg:pt-5 max-lg:pb-12">
        <Outlet />
      </main>
      <CommandPalette open={paletteOpen} onClose={closePalette} />
    </div>
  );
}
