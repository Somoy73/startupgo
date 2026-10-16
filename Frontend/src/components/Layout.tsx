import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { IconBook, IconCompare, IconDeals, IconMoon, IconPipeline, IconSun } from "./Icons";

type Theme = "light" | "dark";

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

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("sg-theme", theme);
    } catch {
      /* storage unavailable */
    }
  }, [theme]);

  return (
    <div className="shell">
      <aside className="sidebar">
        <NavLink to="/" className="brand">
          <img src="/favicon.svg" alt="" />
          <span>Startup Go</span>
        </NavLink>
        <nav className="nav" aria-label="Main">
          <NavLink to="/" end>
            <IconDeals /> <span>Deal flow</span>
          </NavLink>
          <NavLink to="/pipeline">
            <IconPipeline /> <span>Pipeline</span>
          </NavLink>
          <NavLink to="/compare">
            <IconCompare /> <span>Compare</span>
          </NavLink>
          <NavLink to="/methodology">
            <IconBook /> <span>Methodology</span>
          </NavLink>
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
    </div>
  );
}
