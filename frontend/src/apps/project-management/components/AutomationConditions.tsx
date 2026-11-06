import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";

export type Condition = { all: Condition[] } | { any: Condition[] } | { field: string; operator: string; value?: string | number | (string | number)[] };
const leaf = (): Condition => ({ field: "priority", operator: "equals", value: "High" });
const fields = ["status", "priority", "work_type", "title", "due_date", "assignee_user_id"];
const labels: Record<string, string> = { work_type: "Work type", due_date: "Due date", assignee_user_id: "Primary assignee ID" };

export default function AutomationConditions({ value, onChange, depth = 0, path = "Conditions" }: {
  value: Condition | null; onChange: (value: Condition | null) => void; depth?: number; path?: string;
}) {
  if (!value) return <Button type="button" variant="outline" onClick={() => onChange({ all: [leaf()] })}>Add conditions</Button>;
  if ("all" in value || "any" in value) {
    const key = "all" in value ? "all" : "any";
    const children = "all" in value ? value.all : value.any;
    return <fieldset className="space-y-3 rounded border p-3 min-w-0"><legend className="text-sm">{path}</legend>
      <NativeSelect aria-label={`${path} match`} value={key} onChange={e => onChange(e.target.value === "all" ? { all: children } : { any: children })}>
        <option value="all">Match all (AND)</option><option value="any">Match any (OR)</option>
      </NativeSelect>
      {children.map((child, index) => <div key={index} className="space-y-2">
        <AutomationConditions value={child} depth={depth + 1} path={`${path} ${index + 1}`} onChange={next => {
          const updated = next ? children.map((c, i) => i === index ? next : c) : children.filter((_, i) => i !== index);
          onChange(updated.length ? key === "all" ? { all: updated } : { any: updated } : null);
        }} />
      </div>)}
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" disabled={children.length >= 10} onClick={() => onChange(key === "all" ? { all: [...children, leaf()] } : { any: [...children, leaf()] })}>Add condition</Button>
        {depth < 3 && <Button type="button" variant="outline" disabled={children.length >= 10} onClick={() => onChange(key === "all" ? { all: [...children, { any: [leaf()] }] } : { any: [...children, { all: [leaf()] }] })}>Add group</Button>}
        <Button type="button" variant="outline" onClick={() => onChange(null)}>Remove group</Button>
      </div>
    </fieldset>;
  }
  const noValue = ["is_empty", "is_not_empty"].includes(value.operator);
  const operators = ["equals", "not_equals", "in", "not_in", "is_empty", "is_not_empty", ...(value.field === "title" ? ["contains"] : []), ...(value.field === "due_date" ? ["date_before", "date_after"] : [])];
  return <div className="grid gap-2 rounded border p-2 min-w-0">
    <NativeSelect aria-label={`${path} field`} value={value.field} onChange={e => onChange({ field: e.target.value, operator: "equals", value: "" })}>
      {fields.map(field => <option key={field} value={field}>{labels[field] || field[0].toUpperCase() + field.slice(1)}</option>)}
    </NativeSelect>
    <NativeSelect aria-label={`${path} operator`} value={value.operator} onChange={e => onChange({ ...value, operator: e.target.value, value: ["in", "not_in"].includes(e.target.value) ? [] : "" })}>
      {operators.map(op => <option key={op} value={op}>{op.replace(/_/g, " ")}</option>)}
    </NativeSelect>
    {!noValue && <Input aria-label={`${path} value`} placeholder={["in", "not_in"].includes(value.operator) ? "Comma-separated values" : "Value"} value={Array.isArray(value.value) ? value.value.join(",") : value.value ?? ""} onChange={e => {
      const raw = e.target.value;
      const convert = (text: string) => value.field === "assignee_user_id" && text.trim() ? Number(text) : text;
      onChange({ ...value, value: ["in", "not_in"].includes(value.operator) ? raw.split(",").map(v => convert(v.trim())) : convert(raw) });
    }} />}
    <Button type="button" variant="outline" onClick={() => onChange(null)}>Remove condition</Button>
  </div>;
}
