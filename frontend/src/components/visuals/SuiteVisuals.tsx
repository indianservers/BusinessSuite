import { useState, type CSSProperties } from "react";
import { assetUrl } from "@/lib/utils";
import "./suite-visuals.css";

export type PortraitKind = "person" | "employee" | "customer" | "vendor" | "company";

/** Neutral artwork represents a missing picture; it never impersonates a real person. */
export function SuiteAvatar({ name, src, kind = "person", size = 40 }: {
  name: string; src?: string | null; kind?: PortraitKind; size?: number;
}) {
  const [failed, setFailed] = useState<string>();
  const url = src ? assetUrl(src) : undefined;
  const business = kind === "company" || kind === "vendor";
  return <span className={`suite-avatar suite-avatar--${kind}`} style={{ width: size, height: size } as CSSProperties}>
    {url && url !== failed ? <img src={url} alt={name} loading="lazy" onError={() => setFailed(url)} /> :
      <svg viewBox="0 0 80 80" role="img" aria-label={`Generic ${kind} picture for ${name}`}>
        <rect width="80" height="80" rx={business ? 18 : 40} fill={business ? "#e0f2f1" : "#ede9fe"}/>
        <circle cx="65" cy="13" r="23" fill={business ? "#b2dfdb" : "#ddd6fe"}/>
        {business ? <><path d="M18 65V27l25-10v48M43 33h19v32" fill="#fff" stroke="#0f766e" strokeWidth="3" strokeLinejoin="round"/><path d="M27 32h6m-6 10h6m-6 10h6m18-9h4m-4 10h4M14 66h52" stroke="#0f766e" strokeWidth="3" strokeLinecap="round"/><path d="M36 66V55h8v11" fill="#5eead4"/></> : <><path d="M13 80c1-23 13-32 27-32s26 9 27 32" fill="#8b7bc8"/><path d="m29 51 11 13 11-13" fill="#fff"/><circle cx="40" cy="31" r="16" fill="#c4b5fd"/><path d="M24 29c0-21 33-23 33 0-9-1-15-6-19-10-2 5-8 9-14 10" fill="#5b4b88"/></>}
      </svg>}
  </span>;
}

export function SuiteIllustration({ variant = "records" }: { variant?: string }) {
  return <svg className="suite-illustration" viewBox="0 0 180 120" fill="none" aria-hidden="true">
    <ellipse cx="90" cy="104" rx="69" ry="9" fill="currentColor" opacity=".08"/>
    <circle cx="92" cy="57" r="48" fill="currentColor" opacity=".06"/>
    <rect x="34" y="25" width="96" height="72" rx="10" fill="hsl(var(--card))" stroke="currentColor" strokeOpacity=".3" strokeWidth="2"/>
    <path d="M34 44h96" stroke="currentColor" strokeOpacity=".2"/>
    <circle cx="46" cy="35" r="2" fill="currentColor"/><circle cx="54" cy="35" r="2" fill="currentColor" opacity=".4"/>
    {variant === "records" ? <><rect x="47" y="55" width="19" height="28" rx="4" fill="currentColor" opacity=".15"/><path d="M76 59h36M76 69h29M76 79h20" stroke="currentColor" strokeWidth="4" strokeLinecap="round" opacity=".3"/></> : <><path d="M49 82V68m18 14V58m18 24V64m18 18V51" stroke="currentColor" strokeWidth="9" strokeLinecap="round" opacity=".35"/><path d="m48 62 20-14 18 7 20-15" stroke="currentColor" strokeWidth="2"/></>}
    <rect x="119" y="64" width="31" height="31" rx="10" fill="currentColor"/><path d="m128 79 5 5 9-11" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M22 43v8m-4-4h8m122-23v8m-4-4h8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" opacity=".4"/>
  </svg>;
}

/** Small, accessible distribution chart. Counts describe only the supplied loaded records. */
export function SuiteDistribution({ records, field, label }: { records: unknown[]; field: string; label: string }) {
  const counts = new Map<string, number>();
  records.forEach(record => { const value = (record as Record<string, unknown>)[field]; const key = value == null || value === "" ? "Unspecified" : String(value); counts.set(key, (counts.get(key) || 0) + 1); });
  const entries = [...counts].sort((a, b) => b[1] - a[1]);
  const top = entries.slice(0, 5);
  if (entries.length > 5) top.push(["Other", entries.slice(5).reduce((sum, [, count]) => sum + count, 0)]);
  return <details className="suite-distribution"><summary>{label} overview <span>{records.length.toLocaleString()} loaded records</span></summary>
    <div className="suite-distribution-bars" role="list" aria-label={`${label} distribution for loaded records`}>
      {top.map(([name, count], index) => <div role="listitem" key={`${index}:${name}`}><span title={name}>{name}</span><meter min={0} max={Math.max(records.length, 1)} value={count} aria-label={`${name}: ${count} of ${records.length}`} /><strong>{count}</strong></div>)}
      {!records.length && <p>No loaded records to chart.</p>}
    </div><p>Current loaded records only. Search and filters update this chart.</p>
  </details>;
}
