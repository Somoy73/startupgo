import { Outlet, useRouterState } from "@tanstack/react-router";
import { AppHeader } from "./AppHeader";
import { useReveal } from "../lib/useReveal";
import oceanBg from "../assets/ocean-bg.jpg";

export function Layout() {
  // Keyed by path, so each new page plays the enter animation (styles.css, .page-enter); search
  // and filter changes on the same page don't.
  const path = useRouterState({ select: (s) => s.location.pathname });
  const revealReady = useReveal();
  return (
    <>
      <div className="sea-bg" aria-hidden="true">
        <img src={oceanBg} alt="" width={1920} height={1088} className="sea-bg-img" />
        <span className="sea-bg-veil" />
        <span className="sea-bg-tint" />
      </div>
      <div className="app-shell">
        <AppHeader />
        <main
          data-reveal-ready={revealReady || undefined}
          className="app-main px-[18px] pb-16 min-[801px]:px-10 min-[1100px]:px-14">
          <div key={path} className="page-enter">
            <Outlet />
          </div>
        </main>
        <footer className="app-footer">© MeatProxies 2026</footer>
      </div>
    </>
  );
}
