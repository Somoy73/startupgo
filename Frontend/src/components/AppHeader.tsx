import { Link, useLocation } from "@tanstack/react-router";
import { useState } from "react";
import { Menu, Waves, X } from "lucide-react";
import { Button } from "./ui/button";

const nav = [
  { name: "Discover", to: "/" },
  { name: "Matching", to: "/matching" },
  { name: "Assess", to: "/assess" },
  { name: "Pipeline", to: "/pipeline" },
  { name: "Compare", to: "/compare" },
  { name: "Methodology", to: "/methodology" },
] as const;
export function AppHeader() {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  return (
    <header className="app-header">
      <div className="header-inner">
        <Link to="/" className="brand">
          <span>
            <Waves size={18} />
          </span>
          Startup Go
        </Link>
        <nav className={open ? "app-nav is-open" : "app-nav"} aria-label="Main navigation">
          {nav.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              onClick={() => setOpen(false)}
              className={
                (item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to)) ? "active" : ""
              }
            >
              {item.name}
            </Link>
          ))}
        </nav>
        <Button asChild className="header-cta">
          <Link to="/assess">Assess a startup</Link>
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="menu-toggle"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          {open ? <X /> : <Menu />}
        </Button>
      </div>
    </header>
  );
}
