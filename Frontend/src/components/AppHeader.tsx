import { Link, useLocation } from "@tanstack/react-router";
import { useState } from "react";
import { Bot, Menu, Waves, X } from "lucide-react";
import { Button } from "./ui/button";
import { navItems } from "../lib/nav-items";

export function AppHeader() {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  // On the home page the buttons sit under the main title instead of up here.
  const heroButtons = location.pathname === "/";

  return (
    <header className={`app-header${heroButtons ? " is-home" : ""}`}>
      <div className="header-inner px-[18px] min-[801px]:px-10 min-[1100px]:px-14 py-3">
        <Link to="/" className="brand">
          <span>
            <Waves size={18} />
          </span>
          Startup Go
        </Link>
        {!heroButtons && (
          <nav className={open ? "app-nav is-open" : "app-nav"} aria-label="Main navigation">
            {navItems.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                onClick={() => setOpen(false)}
                className={
                  location.pathname === item.to || location.pathname.startsWith(item.to + "/")
                    ? "active"
                    : ""
                }
              >
                {item.name}
              </Link>
            ))}
          </nav>
        )}
        {/* On every page, the home page included: right-most at the top. */}
        <Link
          to="/agent-scraper"
          className={`header-scraper${location.pathname === "/agent-scraper" ? " active" : ""}`}
          onClick={() => setOpen(false)}
        >
          <Bot size={16} aria-hidden="true" />
          Agent Scraper
        </Link>
        {!heroButtons && (
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
        )}
      </div>
    </header>
  );
}
