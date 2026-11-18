import {effectiveEmployeeCategories} from '@/shared/employee-category-taxonomy';
import POSServiceScheduling from "@/apps/srm/industry/POSServiceScheduling";
import { selectedPackContext } from "@/lib/pack-context";
import { recordScope } from "@/lib/record-scope";
import { useAuthStore } from "@/store/authStore";
import { useRecordScopeOwner } from "@/hooks/use-record-scope-owner";
import { useBusinessTerms } from '@/hooks/use-business-terms';
import {useRecordAutosave,useRecordDraft} from "@/hooks/use-record-autosave";
import { parseCatalogTags } from "./catalog-tags";
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
import { toast } from "@/hooks/use-toast";
import { catalogApi, catalogChanged, catalogError, type CatalogItem, type CatalogKind, type CatalogSource, type CatalogFeatures } from "./api";
import "./catalog.css";
import CatalogMobileFields, {type CatalogScheduleDraft,type CatalogMobileSection} from "./CatalogMobileFields";
import { useMobile } from "@/components/mobile/useMobile";
import "./catalog-editor-mobile.css";

const empty = (kind: CatalogKind): Omit<CatalogItem, "id"> => ({ kind, name: "", code: "", category: "", description: "", price: 0, currency: defaultText("currency"), tax: defaultNumber("tax_rate"), unit: defaultText("unit_of_measure"), status: "Active", workspace_id: null, images: [], custom_fields: {}, pricing_options: [], version: 0 });
export default function CatalogEditor({ source, initial, defaultKind = "product", features, close, saved }: { source: CatalogSource; initial?: CatalogItem; defaultKind?: CatalogKind; features?: CatalogFeatures; close: () => void; saved: (item: CatalogItem,configure?:boolean) => void }) {
  const owns=useRecordScopeOwner();
  const mobile=useMobile();
  const dialogRef=useRef<HTMLDivElement>(null);
  const [mobileStep,setMobileStep]=useState(1),[mobileSection,setMobileSection]=useState<CatalogMobileSection>('details'),[mobileRow,setMobileRow]=useState(0);
  const [mobileSchedule,setMobileSchedule]=useState<CatalogScheduleDraft>({mode:'none',duration:30,categories:'',subcategories:String(initial?.custom_fields.employee_subcategories||'')});
  const policySnapshot=useRef('');
  useEffect(()=>{if(!mobile||initial?.kind!=='service')return;let active=true;void api.get('/srm/service-checkout/options',{params:{service_id:initial.id},progress:false,recordCache:false}).then(({data})=>{if(!active||!owns())return;const p=data.policy;if(p){const next={mode:p.active?(p.booking_required?'required':'optional'):'none',duration:p.default_duration_minutes,categories:JSON.stringify(p.employee_categories||[]),subcategories:String(initial.custom_fields.employee_subcategories||''),revision:p.revision,policyId:p.id};setMobileSchedule(next);policySnapshot.current=JSON.stringify(next);}}).catch(()=>{});return()=>{active=false;};},[mobile,initial?.id]);
  useEffect(()=>{
    const viewport=window.visualViewport;
    const measure=()=>{dialogRef.current?.style.setProperty('--catalog-viewport-height',`${viewport?.height||window.innerHeight}px`);dialogRef.current?.style.setProperty('--catalog-viewport-top',`${viewport?.offsetTop||0}px`);};
    measure();viewport?.addEventListener('resize',measure);viewport?.addEventListener('scroll',measure);window.addEventListener('resize',measure);
    return()=>{viewport?.removeEventListener('resize',measure);viewport?.removeEventListener('scroll',measure);window.removeEventListener('resize',measure);};
  },[]);
  const selectedContext=!!features?.selected_context||selectedPackContext()!==null;
  const supports=(key:keyof CatalogFeatures)=>!selectedContext||features?.[key]===true;
  const canConfigure=!selectedContext||features?.scheduling_configure===true;
  const [pharmaWarehouses,setPharmaWarehouses]=useState<{id:number;warehouse_name:string}[]>([]);
  const [pharmaWarehouseError,setPharmaWarehouseError]=useState("");
  useEffect(()=>{if(source!=="srm"||features?.pharma_lot_tracking!==true)return;let active=true;void api.get("/srm/pharma/options",{recordCache:false}).then(result=>{if(active)setPharmaWarehouses(result.data.warehouses||[]);}).catch(error=>{if(active)setPharmaWarehouseError(catalogError(error));});return()=>{active=false;};},[source,features?.pharma_lot_tracking]);
  const initialBranch=useRef(sessionStorage.getItem("suite-branch"));
  const { term } = useBusinessTerms();
  const [draft, setDraft] = useState<Omit<CatalogItem, "id"> & { id?: number }>(() => initial || empty(defaultKind));
  const [priceInput, setPriceInput] = useState(() => String(initial?.price ?? 0));
  const [tagText,setTagText] = useState((initial?.tags||[]).join(", "));
  const [priceIncludesTax, setPriceIncludesTax] = useState(() => !initial && Boolean(formDefaults().tax_inclusive));
  const [workspaces, setWorkspaces] = useState<{ id: number; name: string }[]>([]);
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [image, setImage] = useState(""), [field, setField] = useState(""), [fieldValue, setFieldValue] = useState("");
  const submitting = useRef(false);
  const unitListId = useId();
  const [followUpOptions, setFollowUpOptions] = useState<{ employees: { id: number; name: string }[]; teams: { id: number; name: string }[] }>({ employees: [], teams: [] });
  useEffect(() => { if(!supports("follow_ups"))return;let active = true; api.get("/follow-ups/options", { progress: false, recordCache: false }).then(({ data }) => { if (active && owns()) setFollowUpOptions(data); }).catch(() => {}); return () => { active = false; }; }, []);
  const [destination, setDestination] = useState<number | undefined>();
  const [branchReady, setBranchReady] = useState(!!initial);
  useEffect(() => {
    if (initial) return;
    let active = true;
    api.get("/branches/context", { progress: false, recordCache: false }).then(({ data }) => {
      // The native interceptor may select the first verified branch. Remount
      // the page under that authority instead of accepting data into its old owner.
      if(active && !initialBranch.current && data.selected != null && sessionStorage.getItem("suite-branch") === String(data.selected)) window.dispatchEvent(new Event("suite:branch-changed"));
      if (!active || !owns()) return;
      setDestination(typeof data.selected === "number" ? (data.branches.some((branch: { id: number; can_write: boolean }) => branch.id === data.selected && branch.can_write) ? data.selected : undefined) : data.default_branch_id ?? undefined);
      setBranchReady(true);
    }).catch(e => { if (active && owns()) setError(catalogError(e)); });
    return () => { active = false; };
  }, [initial]);
  const [uploading, setUploading] = useState(false);
  async function uploadImage(file?: File) {
    if (!file || uploading || !supports("image_upload")) return;
    if (file.size > 2 * 1024 * 1024) { setError("Images must be 2 MB or smaller."); return; }
    setUploading(true); setError("");
    try {
      const body = new FormData(); body.append("file", file);
      const response = await api.post<{ url: string }>("/catalog/images", body, { params: { source, kind: draft.kind } });
      if(!owns())return;
      setDraft(current => ({ ...current, images: [...current.images, response.data.url].slice(0, 20) }));
    } catch (error) { if(owns())setError(catalogError(error)); }
    finally { if(owns())setUploading(false); }
  }
  useEffect(() => { if(!supports("workspaces"))return;let active = true; api.get("/project-management/workspaces", { progress: false, recordCache: false }).then(r => { if (active && owns()) setWorkspaces(r.data); }).catch(() => {}); return () => { active = false; }; }, []);
  const patch = <K extends keyof typeof draft>(key: K, value: typeof draft[K]) => setDraft(v => ({ ...v, [key]: value }));
  async function submit(event?: React.FormEvent,automatic=false) {
    const configure=(event?.nativeEvent as SubmitEvent|undefined)?.submitter?.getAttribute("data-configure-service")==="true";
    event?.preventDefault(); event?.stopPropagation(); if (submitting.current || uploading) return false;
    if (!initial && (!branchReady || !destination)) { setError("No writable destination branch is available. Check your branch access."); return false; }
    if (!priceInput.trim() || !Number.isFinite(draft.price) || draft.price < 0 || draft.price > 9999999999) { setError("Base price must be between 0 and 9,999,999,999."); return false; }
    if(mobile){
      const invalidPrice=draft.pricing_options.findIndex(p=>!p.name.trim()||!Number.isFinite(p.amount)||p.amount<0||!/^[A-Z]{3}$/.test(p.currency));
      if(invalidPrice>=0){setMobileStep(2);setMobileSection('pricing');setMobileRow(invalidPrice);setError('Complete the price name, amount and currency.');return false;}
      if(draft.kind==='service'&&canConfigure&&mobileSchedule.mode!=='none'&&(!Number.isInteger(mobileSchedule.duration)||mobileSchedule.duration<5||mobileSchedule.duration>720)){setMobileStep(1);setError('Duration must be 5–720 whole minutes.');return false;}
      const categories=effectiveEmployeeCategories(mobileSchedule.categories,mobileSchedule.subcategories);
      if(categories.length>20||categories.some(x=>x.length>80)){setMobileStep(1);setError('Use up to 20 employee categories, each at most 80 characters.');return false;}
    }
    submitting.current = true; setBusy(!automatic); setError("");
    const payload={...draft};
    if(mobile&&draft.kind==='service')payload.custom_fields={...payload.custom_fields,employee_subcategories:mobileSchedule.subcategories};
    if(selectedContext&&!supports("follow_ups")&&initial?.follow_up&&JSON.stringify(payload.follow_up)===JSON.stringify(initial.follow_up))delete payload.follow_up;
    try { const response = await catalogApi.save(source, { ...payload, tags: parseCatalogTags(tagText), price: priceIncludesTax ? Math.round(draft.price / (1 + draft.tax / 100) * 100) / 100 : draft.price }, destination); if(!owns())return false;
      if(mobile&&source==='srm'&&draft.kind==='service'&&canConfigure&&!automatic&&(mobileSchedule.mode!=='none'||mobileSchedule.policyId)&&JSON.stringify(mobileSchedule)!==policySnapshot.current){
        // Retain the saved item id before configuring so a retry cannot create a duplicate.
        setDraft(current=>({...current,id:response.data.id,version:response.data.version}));
        try{
          const current=mobileSchedule.policyId?await api.get('/srm/service-checkout/options',{params:{service_id:response.data.id},recordCache:false,progress:false}):null;
          const existing=current?.data.policy;
          const result=await api.put('/srm/service-checkout/policies',{service_product_id:response.data.id,...(mobileSchedule.revision?{expected_revision:mobileSchedule.revision}:{}),default_duration_minutes:mobileSchedule.duration,min_duration_minutes:existing?.min_duration_minutes||5,max_duration_minutes:existing?.max_duration_minutes||720,allow_duration_override:existing?.allow_duration_override??false,booking_required:mobileSchedule.mode==='required',active:mobileSchedule.mode!=='none',employee_categories:[...new Set(effectiveEmployeeCategories(mobileSchedule.categories,mobileSchedule.subcategories))]});
          const next={...mobileSchedule,revision:result.data.revision,policyId:result.data.id};setMobileSchedule(next);policySnapshot.current=JSON.stringify(next);
        }catch(error){setError('Item saved. Scheduling needs attention: '+catalogError(error));setMobileStep(1);return false;}
      }
      catalogChanged(); if(automatic){savedSnapshot.current=JSON.stringify({draft:watchedDraft,tagText,priceIncludesTax});setDraft(current=>({...current,version:response.data.version}));}else{clearDraft();toast({title: initial ? "Item saved" : "Item created"});saved(response.data,configure);}return true; }
    catch (e) { if(owns())setError(e instanceof Error && e.message.startsWith("Use up to") ? e.message : catalogError(e));return false; }
    finally { if(owns()){submitting.current = false; setBusy(false);} }
  }
  const {version:ignoredVersion,...watchedDraft}=draft;
  const savedSnapshot=useRef<string>();
  const clearDraft=useRecordDraft(`catalog:v2:${recordScope(useAuthStore.getState().user)}:${source}:new`,{draft,tagText,priceIncludesTax,mobileSchedule},value=>{if(value.mobileSchedule)setMobileSchedule(value.mobileSchedule);setDraft(value.draft);setPriceInput(String(value.draft.price));setTagText(value.tagText);setPriceIncludesTax(value.priceIncludesTax);},!initial&&branchReady);
  useEffect(()=>{if(initial&&savedSnapshot.current===undefined)savedSnapshot.current=JSON.stringify({draft:watchedDraft,tagText,priceIncludesTax});},[initial,watchedDraft,tagText,priceIncludesTax]);
  const auto=useRecordAutosave({value:{draft:watchedDraft,tagText,priceIncludesTax},enabled:!!initial&&!busy&&!uploading,dirty:savedSnapshot.current!==undefined&&savedSnapshot.current!==JSON.stringify({draft:watchedDraft,tagText,priceIncludesTax}),save:()=>submit(undefined,true)});
  return <Dialog.Root open onOpenChange={open => { if (!open && !busy && !uploading) close(); }}><Dialog.Portal><Dialog.Overlay className="sc-overlay"/><Dialog.Content ref={dialogRef} className="sc-dialog sc-catalog-editor"><header className="sc-dialog-heading"><span className="sc-icon"><Package size={22}/></span><div><Dialog.Title>{initial ? "Edit" : "Add"} {draft.kind === "service" ? term('service').toLowerCase() : "product"}</Dialog.Title><Dialog.Description>{mobile?'Complete essentials and save. The second page is optional.':'Products have stock details; services have optional appointments. Assign employees and booking times in the POS cart.'}</Dialog.Description></div><Dialog.Close asChild><button type="button" disabled={busy || uploading} aria-label="Close catalog editor"><X size={20}/></button></Dialog.Close></header><CompactForm compactTabs={!mobile} onInvalidCapture={mobile?event=>setMobileStep(Number((event.target as HTMLElement).closest('[data-catalog-step]')?.getAttribute('data-catalog-step')||1)):undefined} onSubmit={submit}>{mobile?<CatalogMobileFields draft={draft} patch={patch} priceInput={priceInput} setPrice={v=>{setPriceInput(v);patch('price',Number(v));}} tags={tagText} setTags={setTagText} inclusive={priceIncludesTax} setInclusive={setPriceIncludesTax} step={mobileStep} setStep={setMobileStep} section={mobileSection} setSection={setMobileSection} schedule={mobileSchedule} setSchedule={setMobileSchedule} busy={busy||uploading} editing={!!initial} canConfigure={source==='srm'&&canConfigure} supports={supports} features={features} workspaces={workspaces} warehouses={pharmaWarehouses} employees={followUpOptions.employees} teams={followUpOptions.teams} row={mobileRow} setRow={setMobileRow} image={image} setImage={setImage} uploading={uploading} upload={file=>{void uploadImage(file);}} customName={field} setCustomName={setField} customValue={fieldValue} setCustomValue={setFieldValue} selectedContext={selectedContext}/>:<fieldset disabled={busy || uploading} className="sc-form"><div className="sc-form-grid" data-form-section-label="Basic details">
    {selectedContext?<p className="sc-muted">Business context availability is managed in Business Pack settings.</p>:<BranchAvailability value={draft.branch_availability} editing={!!initial} disabled={busy} onChange={value => patch("branch_availability", value)}/>}
    <label>Type<NativeSelect aria-label="Type" disabled={!!initial} value={draft.kind} onChange={e => patch("kind", e.target.value as CatalogKind)}><option value="product">Product</option><option value="service">{term("service")}</option></NativeSelect></label><label>Status<NativeSelect aria-label="Status" value={draft.status} onChange={e => patch("status", e.target.value as CatalogItem["status"])}><option>Active</option><option>Archived</option></NativeSelect></label>
    <label>{draft.kind === "service" ? "Service name" : "Product name"}<input required maxLength={180} autoFocus value={draft.name} onChange={e => patch("name", e.target.value)} placeholder={draft.kind === "service" ? "e.g. General consultation" : "e.g. Digital thermometer"}/></label><label>{draft.kind === "service" ? "Service code" : "SKU / Product code"}<input required maxLength={80} value={draft.code} onChange={e => patch("code", e.target.value)} placeholder="e.g. BS-ENT-01"/></label>
    <label>Category<input maxLength={120} value={draft.category} onChange={e => patch("category", e.target.value)} placeholder="Software, consulting, hardware…"/></label><label>{draft.kind === "service" ? "Billing unit" : "Stock unit"}<input required maxLength={40} value={draft.unit} onChange={e => patch("unit", e.target.value)} placeholder={draft.kind === "service" ? "consultation, session, hour…" : "piece, box, unit…"}/></label>
    <label>Base price {priceIncludesTax ? "(tax included)" : "(before tax)"}<input required type="number" min="0" max="9999999999" step="0.01" value={priceInput} onChange={e => {setPriceInput(e.target.value);patch("price", Number(e.target.value));}}/></label><label>Currency<CurrencySelect value={draft.currency} onChange={value => patch("currency", value)}/></label>
    <label>Price tax treatment<NativeSelect aria-label="Price tax treatment" value={priceIncludesTax ? "inclusive" : "exclusive"} onChange={e => setPriceIncludesTax(e.target.value === "inclusive")}><option value="exclusive">Tax exclusive</option><option value="inclusive">Tax inclusive</option></NativeSelect></label><label>Tax %<input required type="number" min="0" max="100" step="0.01" value={draft.tax} onChange={e => patch("tax", Number(e.target.value))}/></label><label>Visibility<NativeSelect aria-label="Visibility" disabled={!supports("workspaces")} value={draft.workspace_id || ""} onChange={e => patch("workspace_id", e.target.value ? Number(e.target.value) : null)}><option value="">Organization catalog</option>{draft.workspace_id && !workspaces.some(w => w.id === draft.workspace_id) && <option value={draft.workspace_id}>Current workspace #{draft.workspace_id}</option>}{workspaces.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}</NativeSelect></label>
    <label className="sc-span">Description<textarea rows={3} maxLength={50000} value={draft.description} onChange={e => patch("description", e.target.value)} placeholder="What is included, who it is for, and how it is delivered."/></label>
    <label>{draft.kind === "service" ? "Service barcode (optional)" : "Product barcode"}<input maxLength={120} value={draft.barcode || ""} onChange={e => patch("barcode", e.target.value)}/></label><label>{draft.kind === "service" ? "SAC (service tax code)" : "HSN (product tax code)"}<input maxLength={30} value={draft.hsn_code || ""} onChange={e => patch("hsn_code", e.target.value)}/></label>
    <label>{draft.kind === "service" ? "Service delivery cost" : "Purchase cost"}<input type="number" min="0" max="9999999999" step="0.01" value={draft.cost ?? 0} onChange={e => patch("cost", Number(e.target.value))}/></label>{draft.kind === "product" && <label>MRP<input type="number" min="0" max="9999999999" step="0.01" value={draft.mrp ?? 0} onChange={e => patch("mrp", Number(e.target.value))}/></label>}
    {draft.kind === "product" && <><label>Reorder level<input type="number" min="0" max="9999999999" step="0.001" value={draft.reorder_level ?? 0} onChange={e => patch("reorder_level", Number(e.target.value))}/></label><label>Inventory tracking<NativeSelect value={draft.track_inventory === false ? "off" : "on"} onChange={e => patch("track_inventory", e.target.value === "on")}><option value="on">Track stock</option><option value="off">Do not track stock</option></NativeSelect></label></>}
    {draft.kind === "product" && source === "srm" && features?.pharma_lot_tracking === true && <label>Batch and expiry tracking<NativeSelect className="min-w-0 w-full max-w-full" aria-label="Batch and expiry tracking" value={draft.pharma_lot_tracking ? "on" : "off"} onChange={e => patch("pharma_lot_tracking", e.target.value === "on")}><option value="off">Standard stock</option><option value="on">Medicine lots · FEFO</option></NativeSelect><small>Only explicitly received lots can be sold. Existing stock is not assigned to a batch automatically.</small></label>}
    {draft.kind === "product" && source === "srm" && features?.pharma_lot_tracking === true && <label>Medicine warehouse<NativeSelect className="min-w-0 w-full max-w-full" aria-label="Medicine warehouse" value={draft.pharma_warehouse_id??""} onChange={e=>patch("pharma_warehouse_id",e.target.value?Number(e.target.value):null)}><option value="">Choose available warehouse</option>{pharmaWarehouses.map(row=><option key={row.id} value={row.id}>{row.warehouse_name}</option>)}</NativeSelect>{pharmaWarehouseError&&<small role="alert">{pharmaWarehouseError}</small>}</label>}
    </div>    {draft.kind==="service"&&canConfigure&&<section className="sc-section" data-form-section-label="Basic details"><h3>Optional appointment scheduling &amp; resources</h3>{initial?.id?<POSServiceScheduling productId={initial.id} lineKey={`catalog-${initial.id}`} configurationOnly onChange={()=>{}}/>:<p className="sc-muted">Save and configure scheduling to set optional appointment rules and multiple eligible employee categories. You can also configure these in the POS cart. Add the service again for another employee or appointment.</p>}</section>}<section className="sc-section"><header><div><Repeat2 size={17}/><h3>Pricing options</h3><small>One-time or recurring</small></div><button type="button" onClick={() => patch("pricing_options", [...draft.pricing_options, { id: crypto.randomUUID(), name: "", amount: draft.price, currency: draft.currency, interval: "once" }])}><Plus size={15}/>Add price</button></header>{draft.pricing_options.map((price, index) => <div className="sc-price-row" key={price.id}><label>Price name<input required maxLength={100} value={price.name} onChange={e => patch("pricing_options", draft.pricing_options.map((p, i) => i === index ? { ...p, name: e.target.value } : p))} placeholder="Monthly retainer"/></label><label>Amount<input required type="number" min="0" max="9999999999" step="0.01" value={price.amount} onChange={e => patch("pricing_options", draft.pricing_options.map((p, i) => i === index ? { ...p, amount: Number(e.target.value) } : p))}/></label><label>Currency<input required pattern="[A-Z]{3}" maxLength={3} value={price.currency} onChange={e => patch("pricing_options", draft.pricing_options.map((p, i) => i === index ? { ...p, currency: e.target.value.toUpperCase() } : p))}/></label><label>Billing<NativeSelect aria-label="Billing" value={price.interval} onChange={e => patch("pricing_options", draft.pricing_options.map((p, i) => i === index ? { ...p, interval: e.target.value as typeof p.interval } : p))}>{["once", "day", "week", "month", "year"].map(interval => <option key={interval} value={interval}>{interval === "once" ? "One-time" : `Every ${interval}`}</option>)}</NativeSelect></label><button type="button" aria-label={`Remove pricing option ${index + 1}`} onClick={() => patch("pricing_options", draft.pricing_options.filter((_, i) => i !== index))}><Trash2 size={15}/></button></div>)}{!draft.pricing_options.length && <p className="sc-muted">The base price applies unless you add another pricing option.</p>}</section>
    <section data-form-section-label={`Schedule ${term('customer').toLowerCase()} follow-up`}><p className="sc-muted">Set the default follow-up for each customer who buys this product or uses this service. The schedule starts from their purchase, delivery or service completion.</p>{supports("follow_ups")?<ScheduleFields template value={draft.follow_up || { ...newDefaultSchedule(), reference: draft.kind === "service" ? "completion" : "purchase" }} employees={followUpOptions.employees} teams={followUpOptions.teams} onChange={value => patch("follow_up", value)}/>:<p className="sc-muted">{initial?.follow_up?"Existing follow-up configuration is preserved and read only in this business context.":"Follow-up configuration is unavailable in this business context."}</p>}</section>
    <section className="sc-section"><header><div><ImagePlus size={17}/><h3>Images</h3></div></header><label>Upload image (PNG, JPEG or WebP, up to 2 MB)<input type="file" accept="image/png,image/jpeg,image/webp" disabled={busy || uploading || draft.images.length >= 20 || !supports("image_upload")} onChange={event => { void uploadImage(event.target.files?.[0]); event.target.value = ""; }}/></label>{uploading && <p role="status">Uploading image…</p>}<div className="sc-inline"><input aria-label="Image URL" value={image} onChange={e => setImage(e.target.value)} placeholder="https://…"/><button type="button" disabled={!image.trim() || draft.images.length >= 20} onClick={() => { patch("images", [...draft.images, image.trim()]); setImage(""); }}>Add image</button></div><div className="sc-image-strip">{draft.images.map((url, index) => <div key={index}><img src={url} alt={`Item image ${index + 1}`} referrerPolicy="no-referrer"/><button type="button" aria-label={`Remove image ${index + 1}`} onClick={() => patch("images", draft.images.filter((_, i) => i !== index))}><X size={13}/></button></div>)}</div></section>
    <section className="sc-section"><label>Tags (comma-separated)<input aria-label="Catalog tags" value={tagText} maxLength={1000} onChange={event=>setTagText(event.target.value)} placeholder="e.g. recurring, priority, consulting"/></label><p className="sc-muted">Up to 20 shared tags. Use tags to organize products and services across modules.</p></section>
    <section className="sc-section"><header><div><h3>Custom fields</h3></div></header><div className="sc-inline"><input aria-label="Custom field name" maxLength={100} placeholder="Field name" value={field} onChange={e => setField(e.target.value)}/><input aria-label="Custom field value" placeholder="Value" value={fieldValue} onChange={e => setFieldValue(e.target.value)}/><button type="button" disabled={!field.trim()} onClick={() => { patch("custom_fields", { ...draft.custom_fields, [field.trim()]: fieldValue }); setField(""); setFieldValue(""); }}>Add field</button></div>{Object.entries(draft.custom_fields).map(([name, value]) => <div className="sc-custom-row" key={name}><span>{name}</span><input aria-label={`Custom field ${name}`} value={String(value ?? "")} onChange={e => patch("custom_fields", { ...draft.custom_fields, [name]: e.target.value })}/><button type="button" aria-label={`Remove custom field ${name}`} onClick={() => { const next = { ...draft.custom_fields }; delete next[name]; patch("custom_fields", next); }}><X size={15}/></button></div>)}</section>

    </fieldset>}{error && <p className="sc-error" role="alert">{error}</p>}<footer className="sc-form-footer"><span role="status">{initial?auto.message:"Draft saved automatically"}</span><Button type="button" variant="outline" disabled={busy || uploading} onClick={close}>Cancel</Button>{!mobile&&!initial&&draft.kind==="service"&&canConfigure&&<Button type="submit" variant="outline" data-configure-service="true" disabled={busy||uploading||!branchReady||!destination}>Save and configure scheduling</Button>}<Button type="submit" data-save-action disabled={busy || auto.saving || uploading || (!initial && (!branchReady || !destination))}><Save size={16}/>{busy ? "Saving…" : mobile?(draft.kind==="service"?"Save service":"Save product"):"Save item"}</Button></footer></CompactForm></Dialog.Content></Dialog.Portal></Dialog.Root>;
}
