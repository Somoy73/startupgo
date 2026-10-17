import { Skeleton } from "../ui/skeleton";

/** Placeholder rows shaped like the startup table: a name and tagline, then a few score columns. */
export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div aria-hidden className="divide-y divide-border">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-center gap-6 px-5 py-4">
          <div className="flex min-w-[250px] flex-1 flex-col gap-2">
            <Skeleton className="h-4 w-2/5" />
            <Skeleton className="h-3 w-4/5" />
          </div>
          <Skeleton className="hidden h-3 w-32 sm:block" />
          <Skeleton className="h-6 w-10 rounded-full" />
          <Skeleton className="hidden h-6 w-10 rounded-full sm:block" />
          <Skeleton className="hidden h-2 w-24 md:block" />
          <Skeleton className="hidden h-2 w-28 md:block" />
        </div>
      ))}
    </div>
  );
}
