import { Outlet } from "@tanstack/react-router";
import { AppHeader } from "./AppHeader";
import oceanBg from "../assets/ocean-bg.jpg";

export function Layout() {
  return (
    <>
      <div className="sea-bg" aria-hidden="true">
        <img src={oceanBg} alt="" width={1920} height={1088} className="sea-bg-img" />
        <span className="sea-bg-veil" />
        <span className="sea-bg-tint" />
      </div>
      <div className="app-shell">
        <AppHeader />
        <main className="app-main px-[18px] pb-16 min-[801px]:px-10 min-[1100px]:px-14">
          <Outlet />
        </main>
        <footer className="app-footer">© MeatProxies 2026</footer>
      </div>
    </>
  );
}
