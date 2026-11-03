import { PhoneInput } from "@/lib/validation/PhoneInput";
import { phoneFields, phoneError } from "@/lib/validation";
import { useMemo, useState } from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { crmApi, type CRMApiRecord, type CRMApiValue, type CRMDuplicateGroup } from "./api";

const protectedFields = new Set(["id", "organization_id", "owner_user_id", "branch_id", "department_id", "assigned_team_id", "created_at", "updated_at", "created_by_user_id", "updated_by_user_id", "deleted_at", "branchName", "phone_validation_issues"]);
const empty = (value: CRMApiValue) => value == null || (typeof value === "string" && !value.trim());
const text = (value: CRMApiValue): string => empty(value) ? "" : typeof value === "object" ? JSON.stringify(value) : String(value);
const label = (field: string) => field.replace(/_/g, " ").replace(/^./, c => c.toUpperCase());
const title = (record: CRMApiRecord) => text(record.full_name || record.name || record.email) || `Record #${record.id}`;
function superset(current: CRMApiValue, incoming: CRMApiValue): CRMApiValue {
  if (empty(current)) return incoming;
  if (Array.isArray(current) && Array.isArray(incoming)) return [...current, ...incoming.filter(value => !current.some(item => JSON.stringify(item) === JSON.stringify(value)))] as CRMApiValue;
  if (current && incoming && typeof current === "object" && typeof incoming === "object" && !Array.isArray(current) && !Array.isArray(incoming)) {
    const result = { ...current };
    for (const [key, value] of Object.entries(incoming)) result[key] = superset(result[key], value);
    return result;
  }
  return current;
}

export default function MergeWizardModal({ group, onClose, onMerged }: { group: CRMDuplicateGroup; onClose: () => void; onMerged: (winnerId: number, mergedCount: number) => void }) {
  const records = group.records || [];
  const [winnerId, setWinnerId] = useState(Number(records[0]?.id || 0));
  const [overrides, setOverrides] = useState<CRMApiRecord>({});
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const fields = useMemo(() => [...new Set(records.flatMap(record => Object.keys(record)))].filter(field => !protectedFields.has(field) && !/[A-Z]/.test(field) && !field.startsWith("converted_") && !["related", "custom_fields", "custom_fields_json", "timeline"].includes(field)), [records]);
  const combined = useMemo(() => {
    const ordered = [records.find(record => Number(record.id) === winnerId)!, ...records.filter(record => Number(record.id) !== winnerId).sort((a, b) => Number(a.id) - Number(b.id))].filter(Boolean);
    const result: CRMApiRecord = {};
    for (const record of ordered) for (const field of fields) {
      if (field === "notes" && !empty(result[field]) && !empty(record[field]) && result[field] !== record[field]) result[field] = `${text(result[field])}\n\n${text(record[field])}`;
      else if (field === "tags_text" && result[field] && record[field]) result[field] = [...new Set(`${result[field]},${record[field]}`.split(",").map(tag => tag.trim()).filter(Boolean))].join(", ");
      else result[field] = superset(result[field], record[field]);
    }
    return { ...result, ...overrides };
  }, [records, fields, winnerId, overrides]);
  const submit = async () => {
    for(const field of fields.filter(field=>phoneFields.has(field))) {
      const message=phoneError(text(combined[field]),text(combined[field+"_country_code"])||"+91");
      if(message){setError(`${label(field)}: ${message}`);return;}
    }
    setSaving(true); setError("");
    try {
      const response = await crmApi.mergeDuplicates({ entityType: group.entityType, winnerId, loserIds: records.map(record => Number(record.id)).filter(id => id !== winnerId), fieldValues: overrides, allowUndetected: group.manualSelection === true });
      onMerged(Number(response.data.winner.id), response.data.mergedIds.length);
    } catch (err) {
      const detail = (err as {response?: {data?: {detail?: unknown}}}).response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Records could not be merged. Review the selected values and try again.");
    } finally { setSaving(false); }
  };
  return <Dialog open onOpenChange={open => { if (!open && !saving) onClose(); }}><DialogContent className="flex max-h-[90dvh] max-w-6xl flex-col overflow-hidden" onEscapeKeyDown={event => { if (saving) event.preventDefault(); }} onPointerDownOutside={event => { if (saving) event.preventDefault(); }}>
    <header className="pr-8"><DialogTitle className="text-xl font-semibold">Merge duplicate records</DialogTitle><p className="mt-1 text-sm text-muted-foreground">{group.reasons.join(", ")}. Choose the record to keep, then review the combined details.</p></header>
    {error && <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
    <div className="min-h-0 space-y-4 overflow-y-auto">
      <p className="rounded-md border bg-muted/30 p-3 text-sm">Empty fields are filled from the other records automatically. Notes, tags, custom fields, products, services, and related work are combined. For conflicting values, the chosen record takes priority; select another value or edit the combined result below.</p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{records.map(record => <button key={String(record.id)} type="button" disabled={saving} aria-pressed={winnerId === Number(record.id)} onClick={() => { setWinnerId(Number(record.id)); setOverrides({}); }} className={`rounded-lg border p-3 text-left ${winnerId === Number(record.id) ? "border-primary bg-primary/5" : "bg-card"}`}><strong className="block">{title(record)}</strong><span className="text-sm text-muted-foreground">#{String(record.id)} · {winnerId === Number(record.id) ? "Keep this record" : "Merge into chosen record"}</span></button>)}</div>
      <div className="overflow-x-auto rounded-lg border"><table className="w-full min-w-[700px] text-left text-sm"><thead className="bg-muted/60"><tr><th className="p-3">Field</th>{records.map(record => <th key={String(record.id)} className="min-w-40 p-3">{title(record)}</th>)}<th className="min-w-56 p-3">Combined result</th></tr></thead><tbody>{fields.filter(field=>!field.endsWith("_country_code")).map(field => <tr key={field} className="border-t align-top"><th className="p-3 font-medium">{label(field)}</th>{records.map(record => <td key={String(record.id)} className="p-3"><button type="button" disabled={saving || empty(record[field])} className="max-w-64 whitespace-pre-wrap break-words rounded border px-2 py-1 text-left hover:bg-muted disabled:opacity-50" aria-label={`Use ${label(field)} from record ${record.id}`} onClick={() => setOverrides(current => ({ ...current, [field]: record[field], ...(field === "phone" ? {phone_country_code: record.phone_country_code} : field === "alternate_phone" ? {alternate_phone_country_code: record.alternate_phone_country_code} : {}) }))}>{text(record[field]) || "—"}</button></td>)}<td className="p-3">{phoneFields.has(field) ? <PhoneInput label={`Combined ${label(field)}`} disabled={saving} value={text(combined[field])} countryCode={text(combined[field+"_country_code"])} onChange={value=>setOverrides(current=>({...current,[field]:value}))} onCountryCodeChange={code=>setOverrides(current=>({...current,[field+"_country_code"]:code}))}/> : typeof combined[field] === "object" || typeof combined[field] === "boolean" ? <span className="whitespace-pre-wrap break-words">{text(combined[field]) || "—"}</span> : field === "notes" || field === "address" || text(combined[field]).includes("\n") ? <textarea className="min-h-24 w-full rounded-md border bg-background p-2 text-sm" aria-label={`Combined ${label(field)}`} disabled={saving} value={text(combined[field])} onChange={event => setOverrides(current => ({ ...current, [field]: event.target.value }))}/> : <Input aria-label={`Combined ${label(field)}`} disabled={saving} value={text(combined[field])} onChange={event => setOverrides(current => ({ ...current, [field]: event.target.value }))}/>}</td></tr>)}</tbody></table></div>
    </div>
    <footer className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-t pt-4"><p className="text-sm text-muted-foreground">Keep #{winnerId}; archive {records.length - 1} duplicate(s) after combining details.</p><div className="flex gap-2"><Button type="button" variant="outline" disabled={saving} onClick={onClose}>Cancel</Button><Button type="button" disabled={saving || records.length < 2 || !winnerId} onClick={() => void submit()}>{saving ? "Merging…" : "Merge records"}</Button></div></footer>
  </DialogContent></Dialog>;
}
