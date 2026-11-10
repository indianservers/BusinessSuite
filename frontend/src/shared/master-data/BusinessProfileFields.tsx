export function profileText(value: unknown): string {
  return Array.isArray(value) ? value.join(", ") : typeof value === "string" ? value : "";
}

export default function BusinessProfileFields({services, types, onChange, disabled = false}: {
  services: unknown; types: unknown; onChange: (field: "services_offered" | "business_types", value: string) => void; disabled?: boolean;
}) {
  const selected = profileText(types).split(",").map(value => value.trim());
  return <div className="col-span-full md-span grid gap-3">
    <label className="grid gap-1 text-sm font-medium">Services offered
      <textarea aria-label="Services offered" className="min-h-20 w-full rounded-md border border-border bg-background px-3 py-2 text-foreground" rows={2} maxLength={12000} disabled={disabled} value={profileText(services)} placeholder="e.g. Accounting, Consulting, Software development" onChange={event => onChange("services_offered", event.target.value)}/>
      <small className="text-muted-foreground font-normal">Services this customer provides. Separate multiple services with commas or new lines.</small>
    </label>
    <fieldset disabled={disabled} className="grid gap-2"><legend className="text-sm font-medium">Business type</legend>
      <div className="flex flex-wrap gap-4">{[["B2B", "Business to business"], ["B2C", "Business to consumer"], ["B2G", "Business to government"]].map(([value, label]) => <label key={value} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={selected.includes(value)} onChange={event => onChange("business_types", (event.target.checked ? [...selected.filter(Boolean), value] : selected.filter(item => item !== value)).join(", "))}/><span>{value} <small>({label})</small></span></label>)}</div>
      <small className="text-muted-foreground">Optional. Select all that apply.</small>
    </fieldset>
  </div>;
}
