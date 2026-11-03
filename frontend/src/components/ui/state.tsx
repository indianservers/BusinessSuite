import { AlertTriangle, Inbox } from "lucide-react";
import { cn } from "@/lib/utils";

export function ProgressRing({
  value,
  size = 44,
  stroke = 4,
  label,
  className,
}: {
  value: number;
  size?: number;
  stroke?: number;
  label?: string;
  className?: string;
}) {
  const safeValue = Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0));
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (safeValue / 100) * circumference;

  return (
    <div className={cn("relative inline-flex shrink-0 items-center justify-center", className)} style={{ width: size, height: size }}>
      <svg className="-rotate-90" width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="hsl(var(--muted))" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="hsl(var(--primary))"
          strokeLinecap="round"
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <span className="absolute text-[10px] font-semibold text-foreground" aria-label={label || `${safeValue}% complete`}>
        {safeValue}%
      </span>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  className,
}: {
  title: string;
  description?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center rounded-lg border border-dashed bg-muted/20 px-4 py-8 text-center", className)}>
      <Inbox className="mb-3 h-8 w-8 text-muted-foreground" aria-hidden="true" />
      <p className="text-sm font-medium text-foreground">{title}</p>
      {description && <p className="mt-1 max-w-md text-sm text-muted-foreground">{description}</p>}
    </div>
  );
}

export function ErrorState({
  title = "Could not load data",
  description = "Please refresh or try again after a moment.",
  className,
}: {
  title?: string;
  description?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm", className)} role="alert">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden="true" />
      <div>
        <p className="font-medium text-destructive">{title}</p>
        <p className="mt-0.5 text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}

/** Reserve the data area's shape while its first response is pending. */
export function LoadingState({ label = "Loading data", className }: {label?:string;className?:string}) {
  return <div role="status" aria-label={label} aria-busy="true" className={cn("space-y-4 rounded-lg border bg-card p-4",className)}>
    <span className="sr-only">{label}</span>
    <div aria-hidden="true" className="space-y-4 motion-safe:animate-pulse">
      <div className="h-4 w-1/3 rounded bg-muted"/>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">{[0,1,2].map(i=><div key={i} className="h-20 rounded-lg bg-muted/70"/>)}</div>
      {[0,1,2].map(i=><div key={i} className="flex gap-3 border-t pt-3"><div className="h-8 w-8 rounded bg-muted"/><div className="flex-1 space-y-2"><div className="h-3 w-2/3 rounded bg-muted"/><div className="h-3 w-1/3 rounded bg-muted/60"/></div></div>)}
    </div>
  </div>;
}
