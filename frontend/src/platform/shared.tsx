import GridTable from "@/shared/data-grid/GridTable";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { platformApi as api } from "@/services/platform-api";
export type Data = Record<string, any>;
export const OwnerContext = createContext<{
    me: Data;
    refresh: () => void;
}>({ me: {}, refresh: () => { } });
export const useOwner = () => useContext(OwnerContext);
export const allowed = (me: Data, permission: string) => (me.permissions || []).includes(permission);
export function message(error: any): string {
    const detail = error?.response?.data?.detail;
    if (Array.isArray(detail))
        return detail.map(e => `${e.loc?.slice(1).join(".") || "Form"}: ${e.msg}`).join("; ");
    return typeof detail === "string" ? detail : detail?.message || error?.message || "Could not complete this operation.";
}
export function useData<T = any>(url: string, enabled = true) {
    const [data, setData] = useState<T>();
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(true);
    const [rev, setRev] = useState(0);
    useEffect(() => { if (!enabled) { setBusy(false); setError(""); setData(undefined); return; } const controller = new AbortController(); setBusy(true); setError(""); api.get<T>(url, { signal: controller.signal }).then(r => setData(r.data)).catch(e => { if (!controller.signal.aborted)
        setError(message(e)); }).finally(() => { if (!controller.signal.aborted)
        setBusy(false); }); return () => controller.abort(); }, [url, rev, enabled]);
    return { data, error, busy, refresh: () => setRev(r => r + 1), setData };
}
export function date(value?: string | null) { return value ? new Date(value).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", dateStyle: "medium", timeStyle: "short" }) : "—"; }
export function money(minor: number, currency = "INR") { return new Intl.NumberFormat("en-IN", { style: "currency", currency }).format((minor || 0) / 100); }
export function Badge({ children }: {
    children: ReactNode;
}) { return <span className="po-badge">{children}</span>; }
export function Alert({ error }: {
    error?: string;
}) { return error ? <div role="alert" className="po-error">{error}</div> : null; }
export function Loading({ busy, error }: {
    busy: boolean;
    error?: string;
}) { return <>{busy && <p role="status">Loading…</p>}<Alert error={error}/></>; }
export function Dialog({ title, children, onClose }: {
    title: string;
    children: ReactNode;
    onClose: () => void;
}) {
    useEffect(() => { const listener = (e: KeyboardEvent) => { if (e.key === "Escape")
        onClose(); }; window.addEventListener("keydown", listener); return () => window.removeEventListener("keydown", listener); }, [onClose]);
    return <div className="po-overlay"><section role="dialog" aria-modal="true" aria-label={title} className="po-dialog"><header><h2>{title}</h2><button type="button" aria-label="Close dialog" onClick={onClose}>×</button></header>{children}</section></div>;
}
export function Table({ columns, rows, empty = "No records match this view." }: {
    columns: {
        label: string;
        render: (r: any) => ReactNode;
    }[];
    rows: any[];
    empty?: string;
}) {
    return rows.length ? <div className="po-table-scroll"><GridTable gridId="platform/shared:table-1"><thead><tr>{columns.map(c => <th key={c.label}>{c.label}</th>)}</tr></thead><tbody>{rows.map((r, i) => <tr key={r.id ?? i}>{columns.map(c => <td key={c.label}>{c.render(r)}</td>)}</tr>)}</tbody></GridTable></div> : <p className="po-empty">{empty}</p>;
}
export function ModulePicker({ value, onChange, disabled = false }: {
    value: string[];
    onChange: (v: string[]) => void;
    disabled?: boolean;
}) {
    const { me } = useOwner();
    return <fieldset className="po-modules" disabled={disabled}><legend>Applications</legend>{(me.modules || []).map((m: Data) => <label key={m.key}><input type="checkbox" checked={value.includes(m.key)} onChange={e => onChange(e.target.checked ? [...value, m.key] : value.filter(k => k !== m.key))}/>{m.label}</label>)}</fieldset>;
}
export function Bars({ values }: {
    values: Record<string, number>;
}) {
    const max = Math.max(...Object.values(values), 1);
    return Object.keys(values).length ? <div className="po-bars">{Object.entries(values).map(([label, n]) => <div key={label}><span>{label}</span><div><i style={{ width: `${100 * n / max}%` }}/></div><strong>{n}</strong></div>)}</div> : <p className="po-empty">No activity in this period.</p>;
}
export async function download(url: string, filename: string) { const { data } = await api.get(url, { responseType: "blob" }); const link = document.createElement("a"); const objectUrl = URL.createObjectURL(data); link.href = objectUrl; link.download = filename; link.click(); setTimeout(() => URL.revokeObjectURL(objectUrl), 1000); }
