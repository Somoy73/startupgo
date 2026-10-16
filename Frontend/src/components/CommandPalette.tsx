import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAppData } from "../state/AppData";
import { IconSearch } from "./Icons";

interface Command {
  id: string;
  label: string;
  hint: string;
  run: () => void;
}

const MAX_STARTUPS = 6;

/** ⌘K / Ctrl+K quick switcher: jump to a startup, or run the text as a deal-flow search. */
export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { startups } = useAppData();
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setText("");
      setActive(0);
      inputRef.current?.focus();
    }
  }, [open]);

  const commands = useMemo<Command[]>(() => {
    const go = (path: string) => () => {
      navigate(path);
      onClose();
    };
    const q = text.trim().toLowerCase();
    const startupHits = startups
      .filter((s) => !q || `${s.name} ${s.tagline} ${s.sector}`.toLowerCase().includes(q))
      .slice(0, MAX_STARTUPS)
      .map((s) => ({ id: s.slug, label: s.name, hint: s.sector, run: go(`/startups/${s.slug}`) }));
    const actions: Command[] = [
      ...(q
        ? [
            {
              id: "search",
              label: `Search deal flow for “${text.trim()}”`,
              hint: "Search",
              run: go(`/?q=${encodeURIComponent(text.trim())}`),
            },
          ]
        : []),
      { id: "assess", label: "Assess a new startup", hint: "Action", run: go("/assess") },
      { id: "matching", label: "Match startups to a thesis", hint: "Action", run: go("/matching") },
    ];
    return [...startupHits, ...actions];
  }, [text, startups, navigate, onClose]);

  if (!open) return null;

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") setActive((i) => Math.min(commands.length - 1, i + 1));
    else if (e.key === "ArrowUp") setActive((i) => Math.max(0, i - 1));
    else if (e.key === "Enter") commands[active]?.run();
    else if (e.key === "Escape") onClose();
    else return;
    e.preventDefault();
  };

  return (
    <div className="palette-backdrop" onMouseDown={onClose}>
      <div
        className="palette"
        role="dialog"
        aria-modal="true"
        aria-label="Quick search"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="palette-input">
          <IconSearch />
          <input
            ref={inputRef}
            value={text}
            placeholder="Jump to a startup or search…"
            onChange={(e) => {
              setText(e.target.value);
              setActive(0);
            }}
            onKeyDown={onKeyDown}
            role="combobox"
            aria-expanded="true"
            aria-controls="palette-list"
            aria-activedescendant={commands[active] ? `cmd-${commands[active].id}` : undefined}
          />
          <kbd>esc</kbd>
        </div>
        <ul id="palette-list" role="listbox">
          {commands.map((c, i) => (
            <li
              key={c.id}
              id={`cmd-${c.id}`}
              role="option"
              aria-selected={i === active}
              onMouseEnter={() => setActive(i)}
              onClick={c.run}
            >
              <span>{c.label}</span>
              <span className="small muted">{c.hint}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
