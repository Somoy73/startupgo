import { Outlet } from "@tanstack/react-router";
import { AppHeader } from "./AppHeader";

export function Layout() {
  return (
    <>
      <AppHeader />
      <main className="app-main">
        <Outlet />
      </main>
    </>
  );
}