import { useState, type CSSProperties, type ReactNode, type ElementType } from "react";
import { assetUrl } from "@/lib/utils";
import "./suite-visuals.css";

export type PortraitKind = "person" | "employee" | "customer" | "vendor" | "company";

export function SuiteMetric({ label, value, icon: Icon, children }: { label: string; value: ReactNode; icon?: ElementType; children?: ReactNode }) {
  return <div className="suite-metric"><div><p>{label}</p><strong>{value}</strong>{children}</div>{Icon && <span className="suite-metric-icon"><Icon size={23} aria-hidden="true"/></span>}</div>;
}

export function SuiteHeading({ title, description, icon: Icon, actions }: { title: string; description?: ReactNode; icon: ElementType; actions?: ReactNode }) {
  return <header className="suite-page-heading"><div className="suite-heading-identity"><span className="suite-heading-icon"><Icon size={25} aria-hidden="true" /></span><div><h1>{title}</h1>{description && <div className="suite-heading-description">{description}</div>}</div></div>{actions && <div className="suite-heading-actions">{actions}</div>}</header>;
}

export function SuiteFileIcon({ name }: { name: string }) {
  const extension = name.split(".").pop()?.toUpperCase() || "FILE";
  return <span className="suite-file-icon" aria-label={`${extension} file`}><svg viewBox="0 0 40 48" aria-hidden="true"><path d="M7 2h18l10 10v33H7Z" fill="currentColor" opacity=".1" stroke="currentColor" strokeWidth="2"/><path d="M25 2v12h10M14 22h14M14 28h14" fill="none" stroke="currentColor" strokeWidth="2"/></svg><small>{extension.slice(0, 5)}</small></span>;
}

/** Neutral artwork represents a missing picture; it never impersonates a real person. */
export function SuiteAvatar({ name, src, kind = "person", size = 40 }: {
  name: string; src?: string | null; kind?: PortraitKind; size?: number;
}) {
  const [failed, setFailed] = useState<string>();
  const url = src ? assetUrl(src) : undefined;
  const business = kind === "company" || kind === "vendor";
  return <span className={`suite-avatar suite-avatar--${kind}`} style={{ width: size, height: size } as CSSProperties}>
    {url && url !== failed ? <img src={url} alt={name} loading="lazy" decoding="async" width={size} height={size} onError={() => setFailed(url)} /> :
      <svg viewBox="0 0 80 80" role="img" aria-label={`Generic ${kind} picture for ${name}`}>
        <rect width="80" height="80" rx={business ? 18 : 40} fill={business ? "#e0f2f1" : "#ede9fe"}/>
        <circle cx="65" cy="13" r="23" fill={business ? "#b2dfdb" : "#ddd6fe"}/>
        {business ? <><path d="M18 65V27l25-10v48M43 33h19v32" fill="#fff" stroke="#0f766e" strokeWidth="3" strokeLinejoin="round"/><path d="M27 32h6m-6 10h6m-6 10h6m18-9h4m-4 10h4M14 66h52" stroke="#0f766e" strokeWidth="3" strokeLinecap="round"/><path d="M36 66V55h8v11" fill="#5eead4"/></> : <><path d="M13 80c1-23 13-32 27-32s26 9 27 32" fill="#8b7bc8"/><path d="m29 51 11 13 11-13" fill="#fff"/><circle cx="40" cy="31" r="16" fill="#c4b5fd"/><path d="M24 29c0-21 33-23 33 0-9-1-15-6-19-10-2 5-8 9-14 10" fill="#5b4b88"/></>}
      </svg>}
  </span>;
}

export function SuiteIllustration({ variant = "records" }: { variant?: string }) {
  const artwork: Record<string, ReactNode> = {
    hrms: <><circle cx="70" cy="61" r="10" fill="currentColor" opacity=".3"/><path d="M50 91c0-21 40-21 40 0" fill="currentColor" opacity=".5"/><path d="M98 58h18m-18 10h13m-13 10h17" stroke="currentColor" strokeWidth="4" strokeLinecap="round"/></>,
    crm: <><circle cx="68" cy="62" r="9" fill="currentColor" opacity=".6"/><circle cx="96" cy="62" r="9" fill="currentColor" opacity=".3"/><path d="M49 91c0-22 38-22 38 0m-4-8c8-11 30-8 30 8" stroke="currentColor" strokeWidth="5" strokeLinecap="round" opacity=".5"/></>,
    pms: <><path d="m48 59 4 4 7-9m-11 20 4 4 7-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/><path d="M70 59h42M70 74h30" stroke="currentColor" strokeWidth="6" strokeLinecap="round" opacity=".3"/></>,
    srm: <><path d="m52 59 27-10 27 10v27H52Z" fill="currentColor" opacity=".2"/><path d="m52 59 27 10 27-10M79 69v19M65 54l27 10" stroke="currentColor" strokeWidth="3" strokeLinejoin="round"/></>,
    fam: <><path d="M48 83V70m17 13V62m17 21V69m17 14V54" stroke="currentColor" strokeWidth="9" strokeLinecap="round" opacity=".35"/><path d="m48 62 20-14 18 7 20-15" stroke="currentColor" strokeWidth="2"/></>,
    power_apps: <><path d="M56 61h48M80 61v23" stroke="currentColor" strokeWidth="2"/><rect x="48" y="53" width="19" height="18" rx="5" fill="currentColor" opacity=".25"/><rect x="95" y="53" width="19" height="18" rx="5" fill="currentColor" opacity=".5"/><rect x="71" y="78" width="19" height="15" rx="5" fill="currentColor" opacity=".7"/></>,
  };
  return <svg className="suite-illustration" viewBox="0 0 180 120" fill="none" aria-hidden="true">
    <ellipse cx="90" cy="104" rx="69" ry="9" fill="currentColor" opacity=".08"/>
    <circle cx="92" cy="57" r="48" fill="currentColor" opacity=".06"/>
    <rect x="34" y="25" width="96" height="72" rx="10" fill="hsl(var(--card))" stroke="currentColor" strokeOpacity=".3" strokeWidth="2"/>
    <path d="M34 44h96" stroke="currentColor" strokeOpacity=".2"/>
    <circle cx="46" cy="35" r="2" fill="currentColor"/><circle cx="54" cy="35" r="2" fill="currentColor" opacity=".4"/>
    {artwork[variant] || <><rect x="47" y="55" width="19" height="28" rx="4" fill="currentColor" opacity=".15"/><path d="M76 59h36M76 69h29M76 79h20" stroke="currentColor" strokeWidth="4" strokeLinecap="round" opacity=".3"/></>}
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
