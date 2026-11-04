import { CurrencySelect } from "@/lib/validation/business";
import { defaultText, defaultNumber, defaultId, defaultOwner, defaultPaymentTerms, defaultDateAfter, formDefaults, displayDate, displayNumber } from "@/lib/form-defaults";
import BranchAvailability from "@/shared/BranchAvailability";
import { NativeSelect } from "@/components/ui/native-select";
import CompactForm from "@/components/forms/CompactForm";
import { ScheduleFields, newDefaultSchedule } from "@/shared/follow-ups/ScheduleFields";
import { useEffect, useId, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { ImagePlus, Package, Plus, Repeat2, Save, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/services/api";
import { catalogApi, catalogChanged, catalogError, type CatalogItem, type CatalogKind, type CatalogSource } from "./api";
import "./catalog.css";

const empty = (kind: CatalogKind): Omit<CatalogItem, "id"> => ({ kind, name: "", code: "", category: "", description: "", price: 0, currency: defaultText("currency"), tax: defaultNumber("tax_rate"), unit: defaultText("unit_of_measure"), status: "Active", workspace_id: null, images: [], custom_fields: {}, pricing_options: [], version: 0 });
export default function CatalogEditor({ source, initial, defaultKind = "product", close, saved }: { source: CatalogSource; initial?: CatalogItem; defaultKind?: CatalogKind; close: () => void; saved: (item: CatalogItem) => void }) {
  const [draft, setDraft] = useState<Omit<CatalogItem, "id"> & { id?: number }>(() => initial || empty(defaultKind));
  const [priceIncludesTax, setPriceIncludesTax] = useState(() => !initial && Boolean(formDefaults().tax_inclusive));
  const [workspaces, setWorkspaces] = useState<{ id: number; name: string }[]>([]);
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [image, setImage] = useState(""), [field, setField] = useState(""), [fieldValue, setFieldValue] = useState("");
  const submitting = useRef(false);
  const unitListId = useId();
  const [followUpOptions, setFollowUpOptions] = useState<{ employees: { id: number; name: string }[]; teams: { id: number; name: string }[] }>({ employees: [], teams: [] });
  useEffect(() => { let active = true; api.get("/follow-ups/options", { progress: false }).then(({ data }) => { if (active) setFollowUpOptions(data); }).catch(() => {}); return () => { active = false; }; }, []);
  const [destination, setDestination] = useState<number | undefined>();
  const [branchReady, setBranchReady] = useState(!!initial);
  useEffect(() => {
    if (initial) return;
    let active = true;
    api.get("/branches/context", { progress: false }).then(({ data }) => {
      if (!active) return;
      setDestination(typeof data.selected === "number" ? (data.branches.some((branch: { id: number; can_write: boolean }) => branch.id === data.selected && branch.can_write) ? data.selected : undefined) : data.default_branch_id ?? undefined);
      setBranchReady(true);
    }).catch(e => { if (active) setError(catalogError(e)); });
    return () => { active = false; };
  }, [initial]);
  const [uploading, setUploading] = useState(false);
  async function uploadImage(file?: File) {
    if (!file || uploading) return;
    if (file.size > 2 * 1024 * 1024) { setError("Images must be 2 MB or smaller."); return; }
    setUploading(true); setError("");
    try {
      const body = new FormData(); body.append("file", file);
      const response = await api.post<{ url: string }>("/catalog/images", body, { params: { source, kind: draft.kind } });
      setDraft(current => ({ ...current, images: [...current.images, response.data.url].slice(0, 20) }));
    } catch (error) { setError(catalogError(error)); }
    finally { setUploading(false); }
  }
  useEffect(() => { let active = true; api.get("/project-management/workspaces", { progress: false }).then(r => { if (active) setWorkspaces(r.data); }).catch(() => {}); return () => { active = false; }; }, []);
  const patch = <K extends keyof typeof draft>(key: K, value: typeof draft[K]) => setDraft(v => ({ ...v, [key]: value }));
  async function submit(event: React.FormEvent) {
    event.preventDefault(); if (submitting.current || uploading) return;
    if (!initial && (!branchReady || !destination)) { setError("No writable destination branch is available. Check your branch access."); return; }
    submitting.current = true; setBusy(true); setError("");
    try { const response = await catalogApi.save(source, { ...draft, price: priceIncludesTax ? Math.round(draft.price / (1 + draft.tax / 100) * 100) / 100 : draft.price }, destination); catalogChanged(); saved(response.data); }
    catch (e) { setError(catalogError(e)); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <Dialog.Root open onOpenChange={open => { if (!open && !busy && !uploading) close(); }}><Dialog.Portal><Dialog.Overlay className="sc-overlay"/><Dialog.Content className="sc-dialog"><header className="sc-dialog-heading"><span className="sc-icon"><Package size={22}/></span><div><Dialog.Title>{initial ? "Edit" : "New"} product or service</Dialog.Title><Dialog.Description>One shared catalog for sales and project delivery.</Dialog.Description></div><Dialog.Close asChild><button type="button" disabled={busy || uploading} aria-label="Close catalog editor"><X size={20}/></button></Dialog.Close></header><CompactForm onSubmit={submit}><fieldset disabled={busy || uploading} className="sc-form"><div className="sc-form-grid" data-form-section-label="Basic details">
    <BranchAvailability value={draft.branch_availability} editing={!!initial} disabled={busy} onChange={value => patch("branch_availability", value)}/>
    <label>Type<NativeSelect aria-label="Type" disabled={!!initial} value={draft.kind} onChange={e => patch("kind", e.target.value as CatalogKind)}><option value="product">Product</option><option value="service">Service</option></NativeSelect></label><label>Status<NativeSelect aria-label="Status" value={draft.status} onChange={e => patch("status", e.target.value as CatalogItem["status"])}><option>Active</option><option>Archived</option></NativeSelect></label>
    <label>Name<input required maxLength={180} autoFocus value={draft.name} onChange={e => patch("name", e.target.value)} placeholder="e.g. Business Suite Enterprise"/></label><label>SKU / Code<input required maxLength={80} value={draft.code} onChange={e => patch("code", e.target.value)} placeholder="e.g. BS-ENT-01"/></label>
    <label>Category<input maxLength={120} value={draft.category} onChange={e => patch("category", e.target.value)} placeholder="Software, consulting, hardware…"/></label><label>Unit<input required maxLength={40} value={draft.unit} onChange={e => patch("unit", e.target.value)} placeholder="unit, hour, seat…"/></label>
    <label>Base price {priceIncludesTax ? "(tax included)" : "(before tax)"}<input required type="number" min="0" max="9999999999" step="0.01" value={draft.price} onChange={e => patch("price", Number(e.target.value))}/></label><label>Currency<CurrencySelect value={draft.currency} onChange={value => patch("currency", value)}/></label>
    <label>Price tax treatment<NativeSelect aria-label="Price tax treatment" value={priceIncludesTax ? "inclusive" : "exclusive"} onChange={e => setPriceIncludesTax(e.target.value === "inclusive")}><option value="exclusive">Tax exclusive</option><option value="inclusive">Tax inclusive</option></NativeSelect></label><label>Tax %<input required type="number" min="0" max="100" step="0.01" value={draft.tax} onChange={e => patch("tax", Number(e.target.value))}/></label><label>Visibility<NativeSelect aria-label="Visibility" value={draft.workspace_id || ""} onChange={e => patch("workspace_id", e.target.value ? Number(e.target.value) : null)}><option value="">Organization catalog</option>{draft.workspace_id && !workspaces.some(w => w.id === draft.workspace_id) && <option value={draft.workspace_id}>Current workspace #{draft.workspace_id}</option>}{workspaces.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}</NativeSelect></label>
    <label className="sc-span">Description<textarea rows={3} maxLength={50000} value={draft.description} onChange={e => patch("description", e.target.value)} placeholder="What is included, who it is for, and how it is delivered."/></label>
    <label>Barcode<input maxLength={120} value={draft.barcode || ""} onChange={e => patch("barcode", e.target.value)}/></label><label>HSN / SAC (tax code)<input maxLength={30} value={draft.hsn_code || ""} onChange={e => patch("hsn_code", e.target.value)}/></label>
    <label>Purchase / delivery cost<input type="number" min="0" max="9999999999" step="0.01" value={draft.cost ?? 0} onChange={e => patch("cost", Number(e.target.value))}/></label><label>MRP<input type="number" min="0" max="9999999999" step="0.01" value={draft.mrp ?? 0} onChange={e => patch("mrp", Number(e.target.value))}/></label>
    {draft.kind === "product" && <><label>Reorder level<input type="number" min="0" max="9999999999" step="0.001" value={draft.reorder_level ?? 0} onChange={e => patch("reorder_level", Number(e.target.value))}/></label><label>Inventory tracking<NativeSelect value={draft.track_inventory === false ? "off" : "on"} onChange={e => patch("track_inventory", e.target.value === "on")}><option value="on">Track stock</option><option value="off">Do not track stock</option></NativeSelect></label></>}
    </div><section className="sc-section"><header><div><Repeat2 size={17}/><h3>Pricing options</h3><small>One-time or recurring</small></div><button type="button" onClick={() => patch("pricing_options", [...draft.pricing_options, { id: crypto.randomUUID(), name: "", amount: draft.price, currency: draft.currency, interval: "once" }])}><Plus size={15}/>Add price</button></header>{draft.pricing_options.map((price, index) => <div className="sc-price-row" key={price.id}><label>Price name<input required maxLength={100} value={price.name} onChange={e => patch("pricing_options", draft.pricing_options.map((p, i) => i === index ? { ...p, name: e.target.value } : p))} placeholder="Monthly retainer"/></label><label>Amount<input required type="number" min="0" max="9999999999" step="0.01" value={price.amount} onChange={e => patch("pricing_options", draft.pricing_options.map((p, i) => i === index ? { ...p, amount: Number(e.target.value) } : p))}/></label><label>Currency<input required pattern="[A-Z]{3}" maxLength={3} value={price.currency} onChange={e => patch("pricing_options", draft.pricing_options.map((p, i) => i === index ? { ...p, currency: e.target.value.toUpperCase() } : p))}/></label><label>Billing<NativeSelect aria-label="Billing" value={price.interval} onChange={e => patch("pricing_options", draft.pricing_options.map((p, i) => i === index ? { ...p, interval: e.target.value as typeof p.interval } : p))}>{["once", "day", "week", "month", "year"].map(interval => <option key={interval} value={interval}>{interval === "once" ? "One-time" : `Every ${interval}`}</option>)}</NativeSelect></label><button type="button" aria-label={`Remove pricing option ${index + 1}`} onClick={() => patch("pricing_options", draft.pricing_options.filter((_, i) => i !== index))}><Trash2 size={15}/></button></div>)}{!draft.pricing_options.length && <p className="sc-muted">The base price applies unless you add another pricing option.</p>}</section>
    <section data-form-section-label="Schedule customer follow-up"><p className="sc-muted">Set the default follow-up for each customer who buys this product or uses this service. The schedule starts from their purchase, delivery or service completion.</p><ScheduleFields template value={draft.follow_up || { ...newDefaultSchedule(), reference: draft.kind === "service" ? "completion" : "purchase" }} employees={followUpOptions.employees} teams={followUpOptions.teams} onChange={value => patch("follow_up", value)}/></section>
    <section className="sc-section"><header><div><ImagePlus size={17}/><h3>Images</h3></div></header><label>Upload image (PNG, JPEG or WebP, up to 2 MB)<input type="file" accept="image/png,image/jpeg,image/webp" disabled={busy || uploading || draft.images.length >= 20} onChange={event => { void uploadImage(event.target.files?.[0]); event.target.value = ""; }}/></label>{uploading && <p role="status">Uploading image…</p>}<div className="sc-inline"><input aria-label="Image URL" value={image} onChange={e => setImage(e.target.value)} placeholder="https://…"/><button type="button" disabled={!image.trim() || draft.images.length >= 20} onClick={() => { patch("images", [...draft.images, image.trim()]); setImage(""); }}>Add image</button></div><div className="sc-image-strip">{draft.images.map((url, index) => <div key={index}><img src={url} alt={`Item image ${index + 1}`} referrerPolicy="no-referrer"/><button type="button" aria-label={`Remove image ${index + 1}`} onClick={() => patch("images", draft.images.filter((_, i) => i !== index))}><X size={13}/></button></div>)}</div></section>
    <section className="sc-section"><header><div><h3>Custom fields</h3></div></header><div className="sc-inline"><input aria-label="Custom field name" maxLength={100} placeholder="Field name" value={field} onChange={e => setField(e.target.value)}/><input aria-label="Custom field value" placeholder="Value" value={fieldValue} onChange={e => setFieldValue(e.target.value)}/><button type="button" disabled={!field.trim()} onClick={() => { patch("custom_fields", { ...draft.custom_fields, [field.trim()]: fieldValue }); setField(""); setFieldValue(""); }}>Add field</button></div>{Object.entries(draft.custom_fields).map(([name, value]) => <div className="sc-custom-row" key={name}><span>{name}</span><input aria-label={`Custom field ${name}`} value={String(value ?? "")} onChange={e => patch("custom_fields", { ...draft.custom_fields, [name]: e.target.value })}/><button type="button" aria-label={`Remove custom field ${name}`} onClick={() => { const next = { ...draft.custom_fields }; delete next[name]; patch("custom_fields", next); }}><X size={15}/></button></div>)}</section>
    </fieldset>{error && <p className="sc-error" role="alert">{error}</p>}<footer className="sc-form-footer"><Button type="button" variant="outline" disabled={busy || uploading} onClick={close}>Cancel</Button><Button type="submit" disabled={busy || uploading || (!initial && (!branchReady || !destination))}><Save size={16}/>{busy ? "Saving…" : "Save item"}</Button></footer></CompactForm></Dialog.Content></Dialog.Portal></Dialog.Root>;
}
