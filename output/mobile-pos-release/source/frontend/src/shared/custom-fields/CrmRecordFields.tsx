import { isLocationField } from "@/shared/data-grid/record-location";
import { useAuthStore } from "@/store/authStore";
import { api } from "@/services/api";
import { useEffect, useRef, useState } from "react";
import { crmApi, type CRMApiRecord } from "@/apps/crm/api";
import FieldControl, { fieldSettings, fieldShown, fieldInPipeline, type Placement } from "./FieldControl";

export function useCrmFieldForm(entity: string, placement: Placement, recordId?: number, companySource?: string, refreshKey?: number|string) {
  const companyId=useAuthStore(s=>s.user?.access?.companyId);
  const initialValues=useRef<CRMApiRecord>({});
  const [fields, setFields] = useState<CRMApiRecord[]>([]), [values, setValues] = useState<CRMApiRecord>({});
  const [loading, setLoading] = useState(true), [error, setError] = useState("");
  useEffect(() => {
    let active = true; setLoading(true); setError(""); setValues({}); initialValues.current={};
    if(!entity){setFields([]);setLoading(false);return;}
    const request = entity === "employees" ? api.get<{items: CRMApiRecord[]}>("/employees/custom-fields/definitions", {params: {employee_id: recordId},recordCache:false}).then(r => [{data: {items: r.data.items}}, {data: {customFields: r.data.items}}] as const) : companySource ? api.get<{items: CRMApiRecord[]; customFields: CRMApiRecord[]}>("/master-data/companies/custom-fields", { params: { source: companySource, entity, record_id: recordId },recordCache:false }).then(r => [{data: {items: r.data.items}}, {data: {customFields: r.data.customFields}}] as const) : Promise.all([api.get<{items:CRMApiRecord[]}>("/crm/custom-fields",{params:{entityType:entity,per_page:100,sort_by:"position",sort_order:"asc"},recordCache:false}), recordId ? api.get<CRMApiRecord>(`/crm/${entity}/${recordId}`,{recordCache:false}) : Promise.resolve(null)]);
    request.then(([definitions, record]) => {
      if (!active) return;
      const recordData = record?.data as CRMApiRecord | undefined;
      setFields(definitions.data.items.filter(field => fieldShown(field, placement) && (entity !== "deals" || !recordId || fieldInPipeline(field, recordData?.pipeline_id || recordData?.pipelineId))));
      const existing = record?.data.customFields;
      if (Array.isArray(existing)) { const loaded=Object.fromEntries((existing as CRMApiRecord[]).map(f => [String(f.fieldKey || f.field_key || f.id), f.value]));initialValues.current=loaded;setValues(loaded); }
    }).catch(() => { if (active) setError("Custom fields could not be loaded. Reopen the form to try again."); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [entity, placement, recordId, companySource, companyId, refreshKey]);
  function validate() {
    if (loading) throw new Error("Wait for custom fields to load.");
    if (error) throw new Error(error);
    for (const field of fields) {
      const value = values[String(field.fieldKey || field.field_key || field.id)];
      if (field.editable !== false && Boolean(field.isRequired ?? field.is_required) && (value == null || value === "" || Array.isArray(value) && !value.length)) throw new Error(`${field.fieldName || field.label} is required.`);
    }
    return Object.fromEntries(fields.filter(field => field.editable !== false).map(field => {const key=String(field.fieldKey || field.field_key || field.id); return [key,values[key]];}).filter(([key,value])=>value !== undefined && (!recordId || JSON.stringify(value??null)!==JSON.stringify(initialValues.current[String(key)]??null))));
  }
  return { fields, values, setValues, loading, error, validate };
}

export default function CrmRecordFields({ state, errors={} }: { state: ReturnType<typeof useCrmFieldForm>; errors?:Record<string,string> }) {
  const groups = new Map<string, CRMApiRecord[]>();
  for (const field of state.fields) { const group = isLocationField(String(field.fieldName || field.label || field.fieldKey || field.field_key || "")) ? "Location" : String(fieldSettings(field).section || field.section || "Additional information"); groups.set(group, [...(groups.get(group) || []), field]); }
  return <div className="space-y-4">{state.loading && <p role="status" className="text-sm text-muted-foreground">Loading custom fields…</p>}{state.error && <p role="alert" className="text-sm text-destructive">{state.error}</p>}{Array.from(groups).sort(([a], [b]) => Number(a === "Location") - Number(b === "Location")).map(([group, fields]) => <section key={group} className="space-y-3 rounded-lg border p-4"><h3 className="text-sm font-semibold">{group}</h3><div className="grid gap-4 sm:grid-cols-2">{fields.map(field => { const key = String(field.fieldKey || field.field_key || field.id), ui = fieldSettings(field); return <div key={key} className={`space-y-1 ${String(field.fieldType || field.field_type) === "long_text" ? "sm:col-span-2" : ""}`}><p className="text-sm font-medium">{String(field.fieldName || field.label)}{Boolean(field.isRequired ?? field.is_required) && " *"}</p><FieldControl field={field} value={state.values[key]} onChange={value => state.setValues(current => ({ ...current, [key]: value as CRMApiRecord[string] }))}/>{errors[`custom.${key}`] && <p role="alert" tabIndex={-1} data-custom-field-error className="text-xs text-destructive">{errors[`custom.${key}`]}</p>}{Boolean(ui.help) && <p className="text-xs text-muted-foreground">{String(ui.help)}</p>}</div>; })}</div></section>)}</div>;
}

export function CrmFieldsReadOnly({entity,recordId,companySource}:{entity:string;recordId:number;companySource?:string}) {
  const state=useCrmFieldForm(entity,"detail",recordId,companySource);
  return <CrmRecordFields state={{...state,fields:state.fields.map(field=>({...field,editable:false}))}}/>;
}
