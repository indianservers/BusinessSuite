import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { defaultsScope } from "@/lib/form-defaults";

type Group = { key: string; title: string; values: string[]; destination: string };
const base = "/access/settings";
const errorText = (error: any) => typeof error?.response?.data?.detail === "string" ? error.response.data.detail : "Could not save. Please try again.";

export default function StarterValuesSettings({ section }: { section: string }) {
  return section === "crm-lead-sources" ? <LeadSources/> : <StarterValues/>;
}

function StarterValues() {
  const qc = useQueryClient();
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const query = useQuery({ queryKey: ["starter-values", defaultsScope()], queryFn: () => api.get<{ groups: Group[] }>(`${base}/starter-values/catalog`).then(r => r.data) });
  async function add(key: string) {
    if (busy) return;
    setBusy(key); setMessage(""); setError("");
    try {
      const { data } = await api.post<{ total: number }>(`${base}/starter-values/apply`, { modules: [key] });
      setMessage(data.total ? `Added ${data.total} starter records. You can edit them in Settings.` : "Starter values are already configured. Existing values were preserved.");
      window.dispatchEvent(new Event("suite:record-mutated"));
      await Promise.all([qc.invalidateQueries({ queryKey: ["company-setup"] }), qc.invalidateQueries({ queryKey: ["form-defaults"] }), qc.invalidateQueries({ queryKey: ["defaults-configuration"] }), qc.invalidateQueries({ queryKey: ["shared-settings"] })]);
    } catch (error) { setError(errorText(error)); } finally { setBusy(""); }
  }
  return <section className="space-y-4">
    <p className="text-sm text-muted-foreground">Add a starting set for each application. Existing values, including disabled records, are preserved. You can add and edit records in their Settings pages.</p>
    <p className="rounded-lg border p-3 text-sm">Leave allowances and shift times are starter examples. Review them for your company. Salary amounts start at zero; configure amounts and tax treatment before running payroll.</p>
    <p className="text-sm">Currency, country, timezone, priorities, and other form choices are already available in <Link className="font-medium underline" to="/settings/business-defaults">Defaults</Link>.</p>
    {query.isPending && <p role="status">Loading starter values…</p>}
    {query.isError && <p role="alert">Could not load starter values. <button className="underline" onClick={() => void query.refetch()}>Retry</button></p>}
    {query.data?.groups.map(group => <article className="rounded-xl border p-5" key={group.key}><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-semibold">{group.title}</h2><Button disabled={!!busy} onClick={() => void add(group.key)}>{busy === group.key ? "Adding…" : "Add starter values"}</Button></div><ul className="my-4 grid list-inside list-disc gap-2 text-sm sm:grid-cols-2">{group.values.map(value => <li key={value}>{value}</li>)}</ul><Link className="text-sm font-medium underline" to={group.destination}>Manage in Settings</Link>{group.key === "hrms" && <div className="mt-2 flex flex-wrap gap-4 text-sm"><Link className="underline" to="/settings/salaryComponents">Salary components</Link><Link className="underline" to="/settings/shifts">Shifts</Link><Link className="underline" to="/settings/departments">Departments</Link><Link className="underline" to="/settings/designations">Designations</Link></div>}</article>)}
    {query.data && !query.data.groups.length && <p>No supported applications are enabled for this company.</p>}
    {message && <p role="status" className="text-sm">{message}</p>}{error && <p role="alert" className="text-sm text-destructive">{error}</p>}
  </section>;
}

function LeadSources() {
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const endpoint = `${base}/crm-lead-sources/options`;
  const query = useQuery({ queryKey: ["lead-source-settings", defaultsScope()], queryFn: () => api.get<{ sources: string[]; defaults: string[] }>(endpoint).then(r => r.data), refetchOnWindowFocus: false });
  useEffect(() => { if (query.data) setText(query.data.sources.join("\n")); }, [query.data]);
  if (query.isPending) return <p role="status">Loading lead sources…</p>;
  if (query.isError) return <p role="alert">Could not load lead sources. <button onClick={() => void query.refetch()}>Retry</button></p>;
  return <form className="max-w-2xl space-y-4" onSubmit={async event => {
    event.preventDefault(); if (busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const { data } = await api.put<{ sources: string[] }>(endpoint, { sources: text.split("\n").map(value => value.trim()).filter(Boolean) });
      setText(data.sources.join("\n")); setMessage("Lead sources saved. New forms will use this list; existing records keep their source.");
      await Promise.all([qc.invalidateQueries({ queryKey: ["form-defaults"] }), qc.invalidateQueries({ queryKey: ["defaults-configuration"] })]);
    } catch (error) { setError(errorText(error)); } finally { setBusy(false); }
  }}><p className="text-sm text-muted-foreground">Add one source per line. These choices are shared by lead, contact and deal forms. Other remains available as a fallback.</p><label className="block space-y-2 text-sm"><span>Lead sources</span><textarea required disabled={busy} aria-label="Lead sources" className="min-h-72 w-full rounded-lg border bg-background p-3" value={text} onChange={event => setText(event.target.value)}/></label><div className="flex flex-wrap gap-3"><Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save sources"}</Button><Button type="button" variant="outline" disabled={busy} onClick={() => setText(query.data?.defaults.join("\n") || "")}>Use starter list</Button></div>{message && <p role="status">{message}</p>}{error && <p role="alert" className="text-destructive">{error}</p>}</form>;
}
