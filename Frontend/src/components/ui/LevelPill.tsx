export function LevelPill({ level, label }: { level: number; label: string }) {
  return (
    <span
      className="inline-grid h-6 min-w-7 place-items-center rounded-md bg-accent-wash font-[650] text-accent-ink tabular-nums"
      title={`${label} level ${level} of 9`}
    >
      {level}
    </span>
  );
}
