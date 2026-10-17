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
      <AppHeader />
      <main className="app-main">
        <Outlet />
      </main>
    </>
  );
}