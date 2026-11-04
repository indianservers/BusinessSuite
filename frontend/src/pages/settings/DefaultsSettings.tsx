import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Save, Search } from "lucide-react";
import { api } from "@/services/api";
import { CurrencySelect, CountrySelect } from "@/lib/validation/business";
import { contract } from "@/lib/validation";
import { NativeSelect } from "@/components/ui/native-select";
import { Button } from "@/components/ui/button";
import { type DefaultValue, type DefaultValues } from "@/lib/form-defaults";
import "./defaults-settings.css";

type Choice = { value: string | number | boolean; label: string; pipeline_id?: number; branch_id?: number };
type Field = { key: string; label: string; group: string; type: string; default: DefaultValue; options?: Choice[]; reference?: string; min?: number; max?: number; help?: string };
type Configuration = { fields: Field[]; choices: Record<string, Choice[]>; overrides: DefaultValues; inherited: DefaultValues; effective: DefaultValues; version: number };
const endpoint = "/access/settings/defaults/configuration";
const modules = [["", "All applications"], ["crm", "CRM"], ["srm", "Sales"], ["fam", "Finance"], ["hrms", "People & HR"], ["project_management", "Projects & tasks"]];
const errorText = (error: any) => typeof error?.response?.data?.detail === "string" ? error.response.data.detail : "Could not save defaults. Please try again.";

export default function DefaultsSettings() {
  const [module, setModule] = useState("");
  const [branch, setBranch] = useState("");
  return <DefaultsEditor key={`${module}:${branch}`} module={module} branch={branch} changeScope={(nextModule, nextBranch) => { setModule(nextModule); setBranch(nextBranch); }}/>;
}
function DefaultsEditor({ module, branch, changeScope }: { module: string; branch: string; changeScope: (module: string, branch: string) => void }) {
  const qc = useQueryClient();
  const [overrides, setOverrides] = useState<DefaultValues>({});
  const [saved, setSaved] = useState<DefaultValues>({});
  const [version, setVersion] = useState(0);
  const [search, setSearch] = useState("");
  const [activeGroup, setActiveGroup] = useState("General");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const params = { module: module || undefined, branch_id: branch ? Number(branch) : undefined };
  const query = useQuery({ queryKey: ["defaults-configuration", module, branch, sessionStorage.getItem("suite-organization")], queryFn: () => api.get<Configuration>(endpoint, { params }).then(r => r.data), refetchOnWindowFocus: false, staleTime: 0 });
  useEffect(() => { if (query.data) { setOverrides(query.data.overrides); setSaved(query.data.overrides); setVersion(query.data.version); } }, [query.data]);
  const dirty = JSON.stringify(overrides) !== JSON.stringify(saved);
  useEffect(() => {
    const prevent = (event: BeforeUnloadEvent) => { if (dirty) event.preventDefault(); };
    const beforeContext = (event: Event) => { if (dirty && !window.confirm("Discard unsaved default changes?")) event.preventDefault(); };
    window.addEventListener("beforeunload", prevent); window.addEventListener("suite:before-context-change", beforeContext);
    return () => { window.removeEventListener("beforeunload", prevent); window.removeEventListener("suite:before-context-change", beforeContext); };
  }, [dirty]);
  if (query.isPending) return <p role="status">Loading defaults…</p>;
  if (query.isError || !query.data) return <div role="alert">Could not load defaults. <Button variant="outline" onClick={() => void query.refetch()}>Retry</Button></div>;
  const data = query.data;
  const values = { ...data.inherited, ...overrides };
  const set = (key: string, value: DefaultValue) => { setOverrides(current => ({ ...current, [key]: value, ...(key === "pipeline_id" ? { stage_id: null } : {}), ...(key === "branch_id" ? { department_id: null } : {}) })); setMessage(""); setError(""); };
  const inherit = (key: string) => setOverrides(current => { const next = { ...current }; delete next[key]; return next; });
  const scope = (nextModule: string, nextBranch: string) => { if (!dirty || window.confirm("Discard unsaved default changes?")) changeScope(nextModule, nextBranch); };
  async function save() {
    if (busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const { data: result } = await api.put(endpoint, { values: overrides, version }, { params });
      setVersion(result.version); setSaved(overrides); setMessage("Defaults saved. New forms will use these values.");
      await Promise.all([qc.invalidateQueries({ queryKey: ["form-defaults"] }), qc.invalidateQueries({ queryKey: ["master-form-options"] }), qc.invalidateQueries({ queryKey: ["shared-settings"] })]);
    } catch (error) { setError(errorText(error)); } finally { setBusy(false); }
  }
  const matching = data.fields.filter(field => (search.trim() || field.group === activeGroup) && `${field.label} ${field.group} ${field.help || ""}`.toLowerCase().includes(search.toLowerCase().trim()));
  const groups = [...new Set(matching.map(field => field.group))];
  function control(field: Field) {
    const value = values[field.key]; const disabled = busy || !Object.prototype.hasOwnProperty.call(overrides, field.key);
    if (field.type === "currency") return <CurrencySelect label={field.label} value={String(value || "")} disabled={disabled} onChange={value => set(field.key, value)}/>;
    if (field.type === "country") return <CountrySelect label={field.label} value={String(value || "")} disabled={disabled} onChange={value => set(field.key, value)}/>;
    if (field.type === "number") return <input aria-label={field.label} type="number" min={field.min} max={field.max} step={field.key === "tax_rate" ? "0.01" : "1"} value={value === null ? "" : String(value)} disabled={disabled} placeholder="Not set" onChange={event => set(field.key, event.target.value === "" ? null : Number(event.target.value))}/>;
    if (field.type === "days") return <div className="defaults-days" role="group" aria-label={field.label}>{[1, 2, 3, 4, 5, 6, 0].map(day => <button type="button" aria-label={["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][day]} aria-pressed={Array.isArray(value) && value.includes(day)} disabled={disabled} key={day} onClick={() => { const days = Array.isArray(value) ? value : []; set(field.key, days.includes(day) ? days.filter(item => item !== day) : [...days, day]); }}>{["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"][day]}</button>)}</div>;
    let options = field.options || data.choices[field.reference || ""] || [];
    if (field.type === "timezone") options = [...new Set([String(value), "Asia/Kolkata", "UTC", ...((Intl as any).supportedValuesOf?.("timeZone") || [])])].map(zone => ({ value: zone, label: zone }));
    if (field.type === "phone") options = contract.countries.map(country => ({ value: country.code, label: `${country.code} · ${country.country}` }));
    if (field.key === "stage_id") options = options.filter(option => option.pipeline_id === values.pipeline_id);
    if (field.key === "department_id" && values.branch_id) options = options.filter(option => option.branch_id === values.branch_id);
    const unique = options.filter((option, index) => options.findIndex(item => item.value === option.value) === index);
    return <NativeSelect searchable disabled={disabled} aria-label={field.label} value={value === null ? "" : String(value)} onChange={event => { const option = unique.find(option => String(option.value) === event.target.value); set(field.key, option?.value ?? null); }}>
      {field.default === null && <option value="">None</option>}{unique.map(option => <option key={String(option.value)} value={String(option.value)}>{option.label}</option>)}
    </NativeSelect>;
  }
  return <section className="defaults-settings">
    <p className="defaults-intro">Choose the starting values for new forms. You can change them while filling a form. Saved records and open drafts keep their values.</p>
    <div className="defaults-toolbar"><label>Application<NativeSelect searchable aria-label="Defaults application" disabled={busy} value={module} onChange={event => scope(event.target.value, branch)}>{modules.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</NativeSelect></label><label>Branch<NativeSelect searchable aria-label="Defaults branch" disabled={busy} value={branch} onChange={event => scope(module, event.target.value)}><option value="">All branches</option>{data.choices.branches.map(option => <option key={String(option.value)} value={String(option.value)}>{option.label}</option>)}</NativeSelect></label><label className="defaults-search"><Search size={16}/><input aria-label="Search defaults" placeholder="Find a default…" value={search} onChange={event => setSearch(event.target.value)}/></label></div>
    <p className="defaults-scope">{branch || module ? "Custom values here override company defaults. Turn Custom off to inherit." : "Set company-wide values. Turn Custom on to choose a value."}</p>
    <nav className="defaults-categories" aria-label="Defaults categories">{[...new Set(data.fields.map(field => field.group))].map(group => <button type="button" key={group} aria-current={!search.trim() && activeGroup === group ? "page" : undefined} onClick={() => { setActiveGroup(group); setSearch(""); }}>{group}</button>)}</nav>
    {groups.map(group => <section className="defaults-group" key={group}><h2>{group}</h2><div>{matching.filter(field => field.group === group).map(field => <div className="defaults-row" key={field.key}><div><label id={`default-label-${field.key}`}>{field.label}</label>{field.help && <p>{field.help}</p>}</div><div className="defaults-control">{control(field)}</div><label className="defaults-override"><input type="checkbox" aria-label={`Custom ${field.label.toLowerCase()}`} checked={Object.prototype.hasOwnProperty.call(overrides, field.key)} disabled={busy} onChange={event => event.target.checked ? set(field.key, values[field.key]) : inherit(field.key)}/>Custom</label></div>)}</div></section>)}
    {!matching.length && <p role="status">No defaults match your search.</p>}
    <footer className="defaults-footer"><Button type="button" variant="outline" disabled={busy || !Object.keys(overrides).length} onClick={() => { setOverrides({}); setMessage(""); }}><RotateCcw size={15}/>Use inherited values</Button><span>{Object.keys(overrides).length} custom defaults{dirty ? " · Unsaved changes" : ""}</span><Button type="button" disabled={busy || !dirty} onClick={() => void save()}><Save size={15}/>{busy ? "Saving…" : "Save defaults"}</Button></footer>
    {error && <p role="alert" className="text-destructive">{error}</p>}{message && <p role="status">{message}</p>}
  </section>;
}
