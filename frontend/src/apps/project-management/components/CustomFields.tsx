import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Columns3, Plus, Check, Pencil } from "lucide-react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PhoneInput } from "@/lib/validation/PhoneInput";
import { numericFieldTypes } from "./customFieldTypes";
import { workspaceError } from "../pages/workspaceTypes";
export type CustomField = {id:number;name:string;field_type:string;options:string[];project_id:number|null;project_name?:string;entity_type:"task"|"project"|"both";task_type?:string;archived?:boolean;can_manage?:boolean;value?:string|number|boolean|null;country_code?:string|null};
export type FieldRecord = {fields:CustomField[];can_edit:boolean;can_manage:boolean};
export type FieldDraft = Record<string, {value:string|number|boolean|null;country_code?:string}>;
export const fieldPath = (entity:"task"|"project",id:number) => `/project-management/${entity === "task" ? `tasks/${id}/custom-fields` : `projects/${id}/field-values`}`;
export function FieldInput({field,value,onChange,disabled=false}:{field:CustomField;value:FieldDraft[string];onChange:(value:FieldDraft[string])=>void;disabled?:boolean}) {
 const raw=value?.value ?? "";
 const set=(v:string|boolean)=>onChange({ ...value,value:typeof v === "string" && v === "" ? null : numericFieldTypes.includes(field.field_type)?Number(v):v });
 const cls="h-10 w-full rounded-lg border bg-background px-3 text-sm";
 if(field.field_type==="dropdown")return <select aria-label={field.name} className={cls} disabled={disabled} value={String(raw)} onChange={e=>set(e.target.value)}><option value="">Not set</option>{field.options.map(o=><option key={o}>{o}</option>)}</select>;
 if(field.field_type==="checkbox")return <label className="flex h-10 items-center gap-2 text-sm"><input aria-label={field.name} type="checkbox" disabled={disabled} checked={raw===true} onChange={e=>set(e.target.checked)}/>{raw===true?"Yes":"No"}</label>;
 if(field.field_type==="phone")return <PhoneInput label={field.name} value={String(raw)} countryCode={value?.country_code ?? "+91"} disabled={disabled} onChange={v=>onChange({...value,value:v||null,country_code:value?.country_code ?? "+91"})} onCountryCodeChange={v=>onChange({...value,country_code:v})}/>;
 if(field.field_type==="long_text")return <textarea aria-label={field.name} className="min-h-20 w-full rounded-lg border bg-background p-3 text-sm" disabled={disabled} maxLength={20000} value={String(raw)} onChange={e=>set(e.target.value)}/>;
 return <Input aria-label={field.name} disabled={disabled} type={numericFieldTypes.includes(field.field_type)?"number":field.field_type==="date"?"date":field.field_type==="email"?"email":field.field_type==="website"?"url":"text"} min={["rating","progress"].includes(field.field_type)?0:undefined} max={field.field_type==="rating"?5:field.field_type==="progress"?100:undefined} step={field.field_type==="rating"?1:"any"} maxLength={4000} value={String(raw)} onChange={e=>set(e.target.value)}/>;
}
export function FieldValue({field}:{field:CustomField}) {
 if(field.value == null || field.value === "")return <span className="text-muted-foreground">—</span>;
 if(field.field_type==="checkbox")return <span>{field.value?"✓ Yes":"No"}</span>;
 if(field.field_type==="dropdown")return <span className="inline-block rounded-md bg-primary/10 px-2 py-1 text-xs font-medium text-primary">{String(field.value)}</span>;
 if(field.field_type==="progress")return <span className="flex min-w-20 items-center gap-2"><span className="h-1.5 w-14 overflow-hidden rounded bg-muted"><span className="block h-full bg-primary" style={{width:`${field.value}%`}}/></span>{field.value}%</span>;
 return <span className="break-words">{field.field_type==="rating"?`${"★".repeat(Number(field.value))} ${field.value}/5`:field.field_type==="phone"?`${field.country_code || ""} ${field.value}`:String(field.value)}</span>;
}
export function CustomFieldCell({entity,id,field,canEdit,onSaved}:{entity:"task"|"project";id:number;field:CustomField;canEdit:boolean;onSaved:()=>void}) {
 const [editing,setEditing]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState("");
 const [draft,setDraft]=useState<FieldDraft[string]>({value:field.value??null,country_code:field.country_code||undefined});
 if(!editing)return canEdit?<button type="button" className="group flex min-h-8 max-w-64 items-center gap-2 rounded px-1 text-left hover:bg-muted" aria-label={`Edit ${field.name}`} onClick={e=>{e.stopPropagation();setDraft({value:field.value??null,country_code:field.country_code||undefined});setEditing(true);}}><FieldValue field={field}/><Pencil className="h-3 w-3 shrink-0 opacity-0 group-hover:opacity-60"/></button>:<FieldValue field={field}/>;
 return <div className="min-w-48 space-y-2" onClick={e=>e.stopPropagation()}><FieldInput field={field} value={draft} onChange={setDraft} disabled={busy}/>{error&&<p role="alert" className="text-xs text-destructive">{error}</p>}<div className="flex gap-1"><Button type="button" size="sm" disabled={busy} onClick={async()=>{setBusy(true);setError("");try{await api.put(`${fieldPath(entity,id)}/${field.id}`,draft);onSaved();setEditing(false);}catch(e){setError(workspaceError(e));}finally{setBusy(false);}}}><Check className="h-3 w-3"/>Save</Button><Button type="button" variant="ghost" size="sm" disabled={busy} onClick={()=>setEditing(false)}>Cancel</Button></div></div>;
}
export function RecordCustomFields({entity,id}:{entity:"task"|"project";id:number}) {
 const [data,setData]=useState<FieldRecord|null>(null),[error,setError]=useState("");
 async function load(){try{setData((await api.get<FieldRecord>(fieldPath(entity,id))).data);setError("");}catch(e){setError(workspaceError(e));}}
 useEffect(()=>{let active=true;setData(null);api.get<FieldRecord>(fieldPath(entity,id)).then(r=>{if(active)setData(r.data);}).catch(e=>{if(active)setError(workspaceError(e));});return()=>{active=false;};},[entity,id]);
 return <section className="space-y-4 rounded-xl border bg-card p-5" aria-label={`${entity} custom fields`}><div className="flex items-center justify-between gap-3"><div className="flex items-center gap-2"><Columns3 className="h-4 w-4 text-primary"/><h2 className="font-semibold">Custom fields</h2><span className="text-xs text-muted-foreground">{data?.fields.length ?? ""}</span></div><Link className="text-xs text-primary hover:underline" to={`/pms/custom-fields?entity=${entity}`}>Manage fields</Link></div>{error&&<p role="alert" className="text-sm text-destructive">{error}</p>}{!data&&!error&&<p role="status" className="text-sm text-muted-foreground">Loading fields…</p>}<div className="grid gap-4 sm:grid-cols-2">{data?.fields.map(f=><div key={f.id} className="min-w-0 rounded-lg border bg-muted/10 p-3"><p className="mb-1 text-xs font-medium text-muted-foreground">{f.name}</p><CustomFieldCell entity={entity} id={id} field={f} canEdit={data.can_edit} onSaved={()=>void load()}/></div>)}</div>{data&&!data.fields.length&&<p className="text-sm text-muted-foreground">Add fields such as Financial Year, client reference or review date from the field library.</p>}</section>;
}
export function CustomFieldsForm({entity,projectId,workType="",values,onChange}:{entity:"task"|"project";projectId?:number;workType?:string;values:FieldDraft;onChange:(v:FieldDraft)=>void}) {
 const [fields,setFields]=useState<CustomField[]>([]),[error,setError]=useState("");
 useEffect(()=>{let active=true;setFields([]);setError("");const path=projectId?`/project-management/projects/${projectId}/custom-fields?entity=${entity}`:"/project-management/custom-fields";api.get<{fields:CustomField[]}>(path).then(({data})=>{if(active)setFields(data.fields.filter(f=>(f.entity_type===entity||f.entity_type==="both")&&(!f.project_id||f.project_id===projectId)&&(entity!=="task"||!f.task_type||f.task_type===workType)));}).catch(e=>{if(active)setError(workspaceError(e));});return()=>{active=false;};},[entity,projectId,workType]);
 return <section className="space-y-3 rounded-xl border bg-primary/[0.025] p-4"><div className="flex items-center justify-between"><h3 className="flex items-center gap-2 text-sm font-semibold"><Columns3 className="h-4 w-4 text-primary"/>Custom fields</h3><Link to={`/pms/custom-fields?entity=${entity}`} target="_blank" rel="noopener noreferrer" className="text-xs text-primary">Manage <Plus className="inline h-3 w-3"/></Link></div>{error&&<p role="alert" className="text-sm text-destructive">{error}</p>}<div className="grid gap-4 sm:grid-cols-2">{fields.map(f=><label key={f.id} className="space-y-1 text-sm"><span>{f.name}</span><FieldInput field={f} value={values[f.id]} onChange={v=>onChange({...values,[f.id]:v})}/></label>)}</div>{!error&&!fields.length&&<p className="text-xs text-muted-foreground">Your firm’s fields will appear here once added to the library.</p>}</section>;
}
export function useCustomFieldRecords(entity:"task"|"project",ids:number[]) {
 const [records,setRecords]=useState<Record<string,FieldRecord>>({}),[error,setError]=useState("");const [revision,setRevision]=useState(0);const key=ids.join(",");
 useEffect(()=>{let active=true;setRecords({});setError("");if(ids.length)void (async()=>{try{const result:Record<string,FieldRecord>={};for(let offset=0;offset<ids.length;offset+=100){const {data}=await api.post<{records:Record<string,FieldRecord>}>("/project-management/custom-fields/records",{entity,ids:ids.slice(offset,offset+100)});Object.assign(result,data.records);}if(active)setRecords(result);}catch(e){if(active)setError(workspaceError(e));}})();return()=>{active=false;};},[entity,key,revision]);
 return {records,error,reload:()=>setRevision(v=>v+1)};
}
