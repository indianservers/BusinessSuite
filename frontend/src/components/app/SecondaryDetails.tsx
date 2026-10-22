import type { ReactNode } from "react";

export default function SecondaryDetails({ title, children, dark = false }: { title: string; children: ReactNode; dark?: boolean }) {
  return <details className={`rounded-lg border ${dark ? "border-white/10 bg-[#102235] text-slate-100" : "bg-card text-card-foreground"}`}>
    <summary className="cursor-pointer px-4 py-3 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">{title}</summary>
    <div className="space-y-4 border-t p-4">{children}</div>
  </details>;
}
