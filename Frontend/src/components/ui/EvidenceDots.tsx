export function EvidenceDots({ level, label }: { level: number; label: string }) {
  return (
    <span className="inline-flex items-center gap-0.75" aria-label={`Evidence ${level} of 4: ${label}`}>
      {[1, 2, 3, 4].map((i) => (
        <i key={i} className={`size-2.5 rounded-xs ${i <= level ? "bg-accent" : "bg-track opacity-50"}`} />
      ))}
      <span className="ml-1.5 text-label text-fg-2">{label}</span>
    </span>
  );
}
