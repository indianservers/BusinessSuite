import { Button } from "@/components/ui/button";
import {useModuleAction} from "@/hooks/use-module-action";
import GridTable from "@/shared/data-grid/GridTable";
import { useId, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ArrowDown, ArrowRight, ArrowUp, Building2, CalendarDays, Check, ChevronDown, Download, LockKeyhole, RefreshCw, ShieldCheck } from "lucide-react";
import { format, parseISO } from "date-fns";
import { useNavigate } from "react-router-dom";
import { analyticsApi, type BusinessModuleKey } from "./api";
import { useAuthStore } from "@/store/authStore";

type Metric = "all" | BusinessModuleKey;
const count = (value: number) => new Intl.NumberFormat().format(value);
const colors: Record<Metric, string> = { all: "#0070f3", crm: "#0070f3", hrms: "#8b5cf6", pms: "#0891b2", sales: "#d97706", finance: "#16a34a" };
const amount = (value: string, currency: string) => {
  const numeric = Number(value);
  if (!/^[A-Z]{3}$/.test(currency)) return `${count(numeric)} ${currency}`;
  try { return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 2 }).format(numeric); }
  catch { return `${count(numeric)} ${currency}`; }
};

export default function AnalyticsOverview() {
  const canExport=useModuleAction("export");
  const navigate = useNavigate();
  const gradient = useId().replace(/:/g, "");
  const user = useAuthStore((state) => state.user);
  const company = sessionStorage.getItem("suite-organization") || user?.access?.companyId || 1;
  const selectedBranch = sessionStorage.getItem("suite-branch") || "default";
  const [days, setDays] = useState(30);
  const [scope, setScope] = useState("all");
  const [metric, setMetric] = useState<Metric>("all");
  const [expanded, setExpanded] = useState(false);
  const [exported, setExported] = useState(false);
  const branchAccess = useQuery({ queryKey: ["analytics-branch-access", user?.id, company], queryFn: analyticsApi.branchContext });
  const allBranches = scope === "all" && branchAccess.data?.all_branches === true;
  const query = useQuery({
    queryKey: ["analytics-business-overview", user?.id, company, allBranches ? "all" : selectedBranch, days],
    queryFn: () => analyticsApi.businessOverview(days, allBranches),
    enabled: branchAccess.isSuccess,
    refetchInterval: 60_000,
    retry: 1,
  });
  const data = query.data;
  const loading = branchAccess.isLoading || query.isLoading;
  const failed = branchAccess.isError || query.isError;
  const available = data?.modules.filter((item) => item.status === "available") || [];
  const currentTotal = available.reduce((sum, item) => sum + (item.current || 0), 0);
  const previousTotal = available.reduce((sum, item) => sum + (item.previous || 0), 0);
  const cards = [{ key: "all" as Metric, name: "All records", label: "Across five business sources", total: available.reduce((sum, item) => sum + (item.total || 0), 0), current: currentTotal, previous: previousTotal, status: "available" }, ...(data?.modules || [])];
  const selected = data?.modules.find((item) => item.key === metric);
  const chart = useMemo(() => (data?.series || []).map((point) => ({
    date: parseISO(point.date).getTime(),
    current: metric === "all" ? Object.values(point.current).reduce((sum, value) => sum + (value || 0), 0) : point.current[metric] || 0,
    previous: metric === "all" ? Object.values(point.previous).reduce((sum, value) => sum + (value || 0), 0) : point.previous[metric] || 0,
  })), [data, metric]);
  const refresh = () => { void branchAccess.refetch(); void query.refetch(); };
  const scopeLabel = data?.context.branch_scope === "all" ? `All ${data.context.branch_count} branches` : "Selected branch";
  const currentActivity = selected ? selected.current || 0 : currentTotal;
  const restricted = selected?.status === "restricted";
  const start = data?.period.start ? format(parseISO(data.period.start), "MMM d") : "";
  const end = data?.period.end ? format(parseISO(data.period.end), "MMM d, yyyy") : "";

  const exportCsv = () => {
    if (!data) return;
    const rows: (string | number)[][] = [["Section", "Module", "Metric", "Branch", "Date", "Currency", "Value"]];
    available.forEach((item) => rows.push(["Snapshot", item.name, item.label, scopeLabel, "", "", item.total || 0]));
    data.series.forEach((point) => available.filter((item) => metric === "all" || metric === item.key).forEach((item) => rows.push(["Daily activity", item.name, item.label, scopeLabel, point.date, "", point.current[item.key] || 0])));
    Object.entries(data.money).forEach(([label, values]) => values.forEach((item) => rows.push(["Issued invoices", "Sales", label, scopeLabel, "", item.currency, item.amount])));
    const cell = (value: string | number) => { const text = String(value); return `"${(/^[\s\u0000-\u001f]*[=+@-]|^[\t\r\n]/.test(text) ? `'${text}` : text).replace(/"/g, '""')}"`; };
    const blob = new Blob([rows.map((row) => row.map(cell).join(",")).join("\r\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a"); link.href = url; link.download = `business-analytics-${data.period.start}-${data.period.end}.csv`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000); setExported(true); setTimeout(() => setExported(false), 2500);
  };

  return <div className="analytics-overview">
    <div className="analytics-toolbar">
      <div className="analytics-live"><span className={failed ? "is-warning" : ""} />{loading ? "Loading business data" : failed ? "Connection unavailable" : "Live business data"}<span className="analytics-toolbar-divider" /><span className="analytics-muted">{data ? scopeLabel : "Checking branch access"}</span></div>
      <div className="analytics-controls">
        <label className="analytics-control analytics-scope"><Building2 size={14} /><select aria-label="Analytics branch scope" value={allBranches ? "all" : "selected"} disabled={!branchAccess.isSuccess} onChange={(event) => setScope(event.target.value)}>{branchAccess.data?.all_branches && <option value="all">All branches</option>}<option value="selected">Current branch</option></select><ChevronDown size={12} /></label>
        <button type="button" className="analytics-control analytics-refresh" aria-label="Refresh analytics" disabled={query.isFetching || branchAccess.isFetching} onClick={refresh}><RefreshCw size={14} className={query.isFetching ? "animate-spin" : ""} /></button>
        <label className="analytics-control analytics-period"><CalendarDays size={14} /><select aria-label="Analytics date range" value={days} onChange={(event) => setDays(Number(event.target.value))}><option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option></select><ChevronDown size={12} /></label>
        <button type="button" className="analytics-control" disabled={!canExport || !data || failed} onClick={exportCsv}>{exported ? <Check size={14} /> : <Download size={14} />}{exported ? "Exported" : "Export"}</button>
      </div>
    </div>
    <div className="analytics-scope-note"><ShieldCheck size={14} /><span>{allBranches ? "Company-wide analytics across all authorized branches. The branch selector in the app header does not limit this view." : "Analytics follows the branch selected in the app header."} Current totals are snapshots; the date filter applies to new-record activity.</span></div>
    {failed && <div role="alert" className="analytics-error">Business analytics couldn’t be loaded. Check your connection and permissions. <button type="button" onClick={refresh}>Try again</button></div>}
    <section className="analytics-chart-panel" aria-label="Business analytics" aria-busy={loading}>
      <div className="analytics-metrics business-metrics">
        {(data ? cards : [{ key: "all", name: "All records", label: "" }, ...["CRM", "HRMS", "PMS", "Sales", "Finance"].map((name) => ({ key: name.toLowerCase(), name, label: "" }))]).map((item) => {
          const card = item as typeof cards[number];
          const blocked = card.status === "restricted";
          const old = card.previous || 0;
          const delta = old ? (((card.current || 0) - old) / old) * 100 : null;
          return <button key={card.key} type="button" disabled={blocked || !data} aria-pressed={metric === card.key} className={`analytics-metric ${metric === card.key ? "is-selected" : ""}`} onClick={() => setMetric(card.key as Metric)} style={{ "--metric-color": colors[card.key as Metric] } as React.CSSProperties}>
            <span className="analytics-metric-label">{card.name}<span className="analytics-metric-dot" /></span>
            <span className="analytics-metric-value">{loading && !data ? <span className="analytics-skeleton" /> : failed || blocked ? "—" : count(card.total || 0)}</span>
            <span className="analytics-business-label">{card.label}</span>
            <span className="analytics-metric-comparison">{blocked ? <><LockKeyhole size={10} />Access restricted</> : data && <><span>{count(card.current || 0)} in period</span>{delta !== null && <span className={`analytics-change ${delta < 0 ? "is-down" : ""}`}>{delta < 0 ? <ArrowDown size={10} /> : <ArrowUp size={10} />}{Math.abs(delta).toFixed(0)}%</span>}</>}</span>
          </button>;
        })}
      </div>
      <div className="analytics-chart-heading"><div><h2>{metric === "all" ? "Business activity" : `${selected?.name || "Business"} activity`}</h2><p>{currentActivity.toLocaleString()} {metric === "finance" ? "vouchers dated" : "records created"} in the selected period{selected ? ` · ${selected.label}` : " · CRM, HRMS, PMS, sales & finance"}</p></div><div className="analytics-chart-legend"><span><i style={{ background: colors[metric] }} />Current period</span><span><i />Previous period</span></div></div>
      <div className="analytics-chart" role="img" aria-label={`${currentActivity} business records in selected period`}>
        <ResponsiveContainer width="100%" height="100%"><AreaChart data={chart} margin={{ top: 12, right: 18, left: -16, bottom: 0 }}><defs><linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={colors[metric]} stopOpacity={0.17} /><stop offset="100%" stopColor={colors[metric]} stopOpacity={0.01} /></linearGradient></defs><CartesianGrid vertical={false} stroke="var(--analytics-border)" strokeDasharray="3 4" /><XAxis dataKey="date" tickFormatter={(value: number) => format(value, "MMM d")} tickLine={false} axisLine={false} minTickGap={55} tick={{ fontSize: 11, fill: "var(--analytics-muted)" }} dy={10} /><YAxis allowDecimals={false} tickLine={false} axisLine={false} tickFormatter={(value: number) => new Intl.NumberFormat(undefined, { notation: "compact" }).format(value)} domain={[0, (max: number) => Math.max(max, 4)]} tick={{ fontSize: 11, fill: "var(--analytics-muted)" }} /><Tooltip labelFormatter={(value: number) => format(value, "EEE, MMM d, yyyy")} formatter={(value: number, name: string) => [count(value), name === "current" ? "Current period" : "Previous period"]} contentStyle={{ background: "var(--analytics-surface)", border: "1px solid var(--analytics-border)", borderRadius: 8, color: "var(--analytics-text)", fontSize: 12 }} /><Area type="linear" dataKey="previous" stroke="#a1a1aa" strokeDasharray="4 4" strokeWidth={1.5} fill="transparent" isAnimationActive={false} /><Area type="linear" dataKey="current" stroke={colors[metric]} strokeWidth={2} fill={`url(#${gradient})`} isAnimationActive={false} /></AreaChart></ResponsiveContainer>
        {!loading && !failed && data && (restricted || !currentActivity) && <div className="analytics-chart-empty"><strong>{restricted ? "This module requires additional access." : "No new records in this period."}</strong><span>Current business totals are shown above. Try a longer date range.</span></div>}
      </div>
      <div className="analytics-chart-footer"><span>{start} – {end}</span><span>Daily activity · {data?.context.timezone || "Organization timezone"}</span></div>
    </section>
    <div className="analytics-section-label"><h2>Across your business</h2><span>Current operational totals · {scopeLabel}</span></div>
    <div className="business-module-grid">{data?.modules.map((item) => <section className="analytics-detail-panel" key={item.key}><div className="analytics-panel-heading"><div><span className="business-module-dot" style={{ background: colors[item.key] }} /><h3>{item.name}</h3></div><Button variant="outline" type="button" disabled={item.status === "restricted"} onClick={() => navigate(item.path)}>Open <ArrowRight size={13} /></Button></div><div className="business-module-body">{item.status === "restricted" ? <p className="analytics-muted">Your role doesn’t include this module.</p> : <><div><span>{item.label}</span><strong>{count(item.total || 0)}</strong></div>{Object.entries(item.details).map(([label, value]) => <div key={label}><span>{label}</span><strong>{count(value)}</strong></div>)}</>}</div></section>)}</div>
    <section className="analytics-detail-panel"><div className="analytics-panel-heading"><div><h3>Invoice performance</h3></div><span className="analytics-muted">Current issued-invoice snapshot · source currency</span></div><div className="business-money-grid">{[["invoiced", "Invoiced"], ["collected", "Collected"], ["outstanding", "Outstanding"]].map(([key, label]) => <div key={key}><span>{label}</span>{data?.money[key]?.length ? data.money[key].map((item) => <strong key={item.currency}>{amount(item.amount, item.currency)}<small>{item.currency}</small></strong>) : <p className="analytics-muted">{loading ? "Loading…" : Object.keys(data?.money || {}).length ? "No issued invoice amounts" : "No financial data available in this scope"}</p>}</div>)}</div></section>
    <section className="analytics-detail-panel"><div className="analytics-panel-heading"><div><Building2 size={15} /><h3>Branch breakdown</h3><span className="analytics-count">{data?.context.branch_count || 0}</span></div><button type="button" onClick={() => setExpanded(!expanded)}>{expanded ? "Show less" : "View all"} <ArrowRight size={13} /></button></div><div className="business-branch-table"><GridTable gridId="apps/analytics/AnalyticsOverview:table-1" variant="matrix" staticLayout><thead><tr><th>Branch</th>{data?.modules.map((item) => <th key={item.key}>{item.name}<small>{item.label}</small></th>)}</tr></thead><tbody>{data?.branches.slice(0, expanded ? undefined : 7).map((branch) => <tr key={branch.id ?? "unassigned"}><td>{branch.name}{!branch.active && <span className="analytics-status">Archived</span>}</td>{data.modules.map((item) => <td key={item.key}>{item.status === "restricted" ? "—" : count(branch.counts[item.key] || 0)}</td>)}</tr>)}</tbody></GridTable>{!data && <div className="analytics-panel-empty">{failed ? "Branch data unavailable." : "Loading branch totals…"}</div>}</div><div className="analytics-breakdown-footer"><span>Current records attributed by verified branch ownership. Unassigned legacy records are listed separately.</span></div></section>
    <footer className="analytics-overview-footer"><span><ShieldCheck size={13} />Organization, branch and module permissions enforced.</span><span>{data ? `Updated ${format(parseISO(data.context.as_of), "HH:mm")} · ` : ""}Refreshes every minute</span></footer>
    <p className="business-definition">{data?.definition}</p>
  </div>;
}
