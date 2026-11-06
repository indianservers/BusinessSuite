import { api } from "@/services/api";
import { useEffect, useId, useState } from "react";
import { Root as Popover, Content as PopoverContent, Trigger as PopoverTrigger } from "@radix-ui/react-popover";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { PhoneInput } from "@/lib/validation/PhoneInput";
import RecordLookup from '@/apps/customization/RecordLookup';

export type Placement = "create" | "edit" | "quick_create" | "detail";
export type FieldDefinition = Record<string, unknown>;
export function fieldOptions(raw: unknown): string[] {
  if (raw && typeof raw === "object" && !Array.isArray(raw)) return fieldOptions((raw as FieldDefinition).values);
  return Array.isArray(raw) ? raw.map(String) : typeof raw === "string" ? raw.split(/[\n,]/).map(v => v.trim()).filter(Boolean) : [];
}
export function fieldSettings(field: FieldDefinition): FieldDefinition {
  const options = field.options ?? field.options_json;
  return options && typeof options === "object" && !Array.isArray(options) ? ((options as FieldDefinition).ui as FieldDefinition || {}) : {};
}
export function fieldShown(field: FieldDefinition, placement: Placement) {
  if ((field.isVisible ?? field.is_visible ?? field.visible) === false || (field.isActive ?? field.is_active) === false || field.archived === true) return false;
  const places = field.places ?? fieldSettings(field).places;
  return !Array.isArray(places) || places.includes(placement);
}

/** One typed control for create, edit, preview and detail surfaces. No coercion of saved values on mount. */
export default function FieldControl({ field, value, onChange, disabled = false }: { field: FieldDefinition; value: unknown; onChange: (value: unknown) => void; disabled?: boolean }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const settings = fieldSettings(field);
  const label = String(field.fieldName || field.field_label || field.label || field.name || "Custom field");
  const type = String(field.fieldType || field.field_type || "text").toLowerCase().replace(/ /g,"_");
  const lookup = type === "user" || type === "owner" || type === 'user_lookup';
  const [people,setPeople]=useState<{value:string;label:string}[]>([]),[lookupError,setLookupError]=useState("");
  useEffect(()=>{
    if(!lookup)return;
    const controller=new AbortController();
    const timer=setTimeout(()=>{api.get<{items:Record<string,unknown>[]}>("/crm/owners",{params:{per_page:100,search:query},signal:controller.signal}).then(({data})=>{setPeople((data.items||[]).map(p=>({value:String(p.id),label:String(p.name||p.full_name||p.email||p.id)})));setLookupError("");}).catch(()=>{if(!controller.signal.aborted)setLookupError("People could not be loaded. Try searching again.");});},200);
    return()=>{clearTimeout(timer);controller.abort();};
  },[lookup,query]);
  const options = lookup ? people.map(p=>p.value) : fieldOptions(field.options ?? field.options_json);
  const optionLabel=(option:string)=>lookup ? people.find(p=>p.value===option)?.label || `User #${option}` : option;
  const required = Boolean(field.isRequired ?? field.is_required ?? field.required);
  const locked = disabled || field.editable === false;
  const cls = "min-h-10 w-full rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60";
  const common = { "aria-label": label, disabled: locked, required, className: cls };
  if (type === "phone") {
    const pair = value && typeof value === "object" ? value as FieldDefinition : {};
    return <PhoneInput label={label} disabled={locked} value={String(pair.national_number ?? value ?? "")} countryCode={String(pair.country_code ?? (value ? "" : "+91"))} onChange={number => onChange({ national_number: number, country_code: pair.country_code ?? "+91" })} onCountryCodeChange={code => onChange({ national_number: pair.national_number ?? value ?? "", country_code: code })}/>;
  }
  if (type === "radio") return <div role="radiogroup" aria-label={label} aria-required={required} className="flex flex-wrap gap-2">{[...new Set([...options, ...(value != null && value !== "" ? [String(value)] : [])])].map(option => <label key={option} className="flex min-h-10 cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm has-[:checked]:border-primary has-[:checked]:bg-primary/5"><input name={id} type="radio" value={option} checked={value === option} disabled={locked} required={required} onChange={() => onChange(option)}/>{option}</label>)}{!required && value != null && value !== "" && <button type="button" disabled={locked} className="text-xs text-muted-foreground underline" onClick={() => onChange(null)}>Clear</button>}</div>;
  if (type === "dropdown" || type === "select") return <NativeSelect {...common} value={String(value ?? "")} onChange={e => onChange(e.target.value || null)}><option value="">Select {label.toLowerCase()}</option>{[...new Set([...options, ...(value != null && value !== "" ? [String(value)] : [])])].map(option => <option key={option}>{option}</option>)}</NativeSelect>;
  if (type === 'lookup') return <RecordLookup module={String(field.lookup_module || '')} label={label} value={value} onChange={onChange} disabled={locked} />;
  if (['formula', 'rollup', 'auto_number'].includes(type)) return <Input aria-label={label} readOnly value={String(value ?? '')} placeholder="Calculated after saving" />;
  if (["combobox", "multi_select", "picklist", "multi_picklist", "user", "owner", "user_lookup"].includes(type)) {
    const multi = type === "multi_select" || type === "multi_picklist";
    const selected = Array.isArray(value) ? value.map(String) : value == null || value === "" ? [] : multi ? String(value).split(",").map(v => v.trim()) : [String(value)];
    const choices = [...new Set([...options, ...selected])].filter(option => optionLabel(option).toLowerCase().includes(query.toLowerCase()));
    return <Popover open={open} onOpenChange={next => { setOpen(next); setQuery(""); }}><PopoverTrigger asChild><Button type="button" variant="outline" disabled={locked} role="combobox" aria-label={label} aria-expanded={open} aria-controls={`${id}-options`} className="min-h-10 h-auto w-full justify-between whitespace-normal text-left font-normal"><span>{selected.length ? selected.map(optionLabel).join(", ") : `Select ${label.toLowerCase()}`}</span><span aria-hidden>⌄</span></Button></PopoverTrigger><PopoverContent align="start" className="z-[200] w-80 max-w-[90vw] rounded-md border bg-popover p-2 text-popover-foreground"><Input autoFocus aria-label={`Search ${label}`} placeholder="Search options…" value={query} onChange={e => setQuery(e.target.value)}/><div id={`${id}-options`} role="listbox" aria-label={label} aria-multiselectable={multi || undefined} className="mt-2 max-h-56 overflow-y-auto">{choices.map(option => <button key={option} type="button" role="option" aria-selected={selected.includes(option)} className="flex min-h-10 w-full items-center gap-2 rounded px-2 text-left text-sm hover:bg-muted focus:bg-muted" onClick={() => { onChange(multi ? selected.includes(option) ? selected.filter(v => v !== option) : [...selected, option] : lookup ? Number(option) : option); if (!multi) setOpen(false); }}><span aria-hidden className="w-4">{selected.includes(option) ? "✓" : ""}</span>{optionLabel(option)}</button>)}{lookupError && <p role="alert" className="p-2 text-xs text-destructive">{lookupError}</p>}{!choices.length && <p className="p-3 text-sm text-muted-foreground">No matching options</p>}</div>{!required && selected.length > 0 && <Button type="button" variant="ghost" size="sm" onClick={() => { onChange(multi ? [] : null); setOpen(false); }}>Clear selection</Button>}</PopoverContent></Popover>;
  }
  if (type === "checkbox" || type === "boolean") return <label className="flex min-h-10 items-center gap-2 text-sm"><input aria-label={label} type="checkbox" disabled={locked} checked={value === true || value === "true"} onChange={e => onChange(e.target.checked)}/>Yes</label>;
  if (type === "long_text" || type === "textarea") return <textarea {...common} rows={3} placeholder={String(settings.placeholder || "")} value={String(value ?? "")} onChange={e => onChange(e.target.value)}/>;
  const inputType = ["number", "currency", "money", "decimal", "integer", "user", "owner", "rating", "progress"].includes(type) ? "number" : type === "datetime" ? "datetime-local" : type === "website" ? "url" : ["email", "url", "date"].includes(type) ? type : "text";
  return <Input {...common} type={inputType} step="any" placeholder={String(settings.placeholder || "")} value={String(value ?? "")} onChange={e => onChange(e.target.value === "" ? null : inputType === "number" ? Number(e.target.value) : e.target.value)}/>;
}
