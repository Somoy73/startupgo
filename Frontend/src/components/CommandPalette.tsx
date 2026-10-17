import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LuSearch } from "react-icons/lu";
import { useAppData } from "@/state/AppData";

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
    <div
      className="fixed inset-0 z-50 grid items-start justify-items-center bg-black/35 px-4 pt-[12vh] pb-4"
      onMouseDown={onClose}
    >
      <div
        className="w-[min(560px,100%)] overflow-hidden rounded-xl border border-line bg-surface shadow-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Quick search"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2.5 border-b border-grid px-3.5 py-3">
          <LuSearch className="size-4.5 flex-none text-muted" />
          <input
            ref={inputRef}
            className="min-w-0 flex-1 border-0 bg-transparent text-base outline-none"
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
        <ul id="palette-list" role="listbox" className="m-0 max-h-[50vh] list-none overflow-y-auto p-1.5">
          {commands.map((c, i) => (
            <li
              key={c.id}
              id={`cmd-${c.id}`}
              role="option"
              aria-selected={i === active}
              className="flex cursor-pointer justify-between gap-3 rounded-lg px-2.5 py-2.25 aria-selected:bg-accent-wash aria-selected:text-accent-ink"
              onMouseEnter={() => setActive(i)}
              onClick={c.run}
            >
              <span>{c.label}</span>
              <span className="text-small text-muted">{c.hint}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
