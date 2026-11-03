import { NativeSelect } from "@/components/ui/native-select";
import { useState } from "react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { whatsappBase as base, whatsappError, type Template } from "./types";
import { usePreference,EmptyState } from '../center/shared';

export default function TemplatesPanel({ templates, admin, refresh }: { templates: Template[]; admin: boolean; refresh: () => Promise<void> }) {
  const [draft, setDraft] = useState({ name: "", language: "en_US", category: "UTILITY", body: "", samples: "" });
  const [busy, setBusy] = useState(false), [notice, setNotice] = useState("");
  const [search,setSearch]=useState(''),[status,setStatus]=useState('all'),[language,setLanguage]=useState('all'),[category,setCategory]=useState('all'),[favoriteOnly,setFavoriteOnly]=useState(false);
  const [favorites,setFavorites]=usePreference<string[]>('favorite-meta-templates',[]),[preview,setPreview]=useState<Template|null>(null),[values,setValues]=useState<Record<string,string>>({});
  const key=(template:Template)=>template.name+':'+template.language;
  const filtered=templates.filter(t=>(t.name+' '+(t.components?.find(c=>c.type==='BODY')?.text||'')).toLowerCase().includes(search.toLowerCase())&&(status==='all'||t.status===status)&&(language==='all'||t.language===language)&&(category==='all'||t.category===category)&&(!favoriteOnly||favorites.includes(key(t))));
  async function submit() {
    setBusy(true); setNotice("");
    try {
      const { samples, ...fields } = draft;
      await api.post(base + "/templates", { ...fields, sampleValues: samples ? samples.split("\n").map(s => s.trim()) : [] });
      setNotice("Submitted to Meta for review. You can send it after Meta approves it.");
      await refresh();
    } catch (error) { setNotice(whatsappError(error)); }
    finally { setBusy(false); }
  }
  return <div className="space-y-5">
    <div className="cc-section-title"><h2>WhatsApp template library</h2><span className="cc-help" role="status">{filtered.length} of {templates.length} templates</span></div>
    <div className="cc-filter-row"><input aria-label="Search Meta templates" placeholder="Search template name or text" value={search} onChange={e=>setSearch(e.target.value)}/><NativeSelect aria-label="Template approval status" value={status} onChange={e=>setStatus(e.target.value)}><option value="all">All statuses</option>{[...new Set(templates.map(t=>t.status))].map(s=><option key={s}>{s}</option>)}</NativeSelect><NativeSelect aria-label="Template language filter" value={language} onChange={e=>setLanguage(e.target.value)}><option value="all">All languages</option>{[...new Set(templates.map(t=>t.language))].map(s=><option key={s}>{s}</option>)}</NativeSelect><NativeSelect aria-label="Template category filter" value={category} onChange={e=>setCategory(e.target.value)}><option value="all">All categories</option>{[...new Set(templates.map(t=>t.category))].map(s=><option key={s}>{s}</option>)}</NativeSelect><label className="flex-row items-center"><input type="checkbox" checked={favoriteOnly} onChange={e=>setFavoriteOnly(e.target.checked)}/>Favourites</label></div>
    <p className="text-sm text-muted-foreground">These are templates from the connected Meta account. The hello_world sample is Meta’s demonstration template. Create your own approved templates for Indian Servers or your customer business.</p>
    <div className="cc-library-grid">{filtered.map(template => <article key={template.id || template.name + template.language} className="cc-library-card">
      <div className="flex flex-wrap justify-between gap-2"><h3 className="font-medium">{template.name}</h3><span className="text-xs">{template.status}</span></div>
      <p className="mt-1 text-xs text-muted-foreground">{template.language} · {template.category}</p>
      <p className="mt-3 whitespace-pre-wrap text-sm">{template.components?.find(c => c.type === "BODY")?.text}</p>
      <div className="cc-toolbar"><Button size="sm" variant="outline" onClick={()=>{setPreview(template);setValues({});}}>Preview template</Button><button aria-label={`${favorites.includes(key(template))?'Unfavorite':'Favorite'} template ${template.name}`} onClick={()=>setFavorites(favorites.includes(key(template))?favorites.filter(k=>k!==key(template)):[...favorites,key(template)])}>{favorites.includes(key(template))?'★':'☆'}</button></div>
      {template.status==='REJECTED'&&<p className="cc-form-warning">Review the category, wording and sample values in Meta’s template manager. Approval is required before use.</p>}
    </article>)}</div>
    {!filtered.length&&<EmptyState title={templates.length?'No templates match these filters':'No Meta templates yet'} description={templates.length?'Clear a filter or try another search.':'Prepare your first text template below. Meta approval is required before it can start conversations.'}/>}
    {preview&&<section className="cc-review"><div className="cc-section-title"><h3>Preview: {preview.name}</h3><Button variant="ghost" size="sm" onClick={()=>setPreview(null)}>Close preview</Button></div>{[...new Set(preview.components?.find(c=>c.type==='BODY')?.text?.match(/\{\{\d+\}\}/g)||[])].map(p=><label key={p}>Preview value for {p}<input value={values[p]||''} onChange={e=>setValues({...values,[p]:e.target.value})}/></label>)}<p className="whitespace-pre-wrap">{(preview.components?.find(c=>c.type==='BODY')?.text||'').replace(/\{\{\d+\}\}/g,p=>values[p]||p)}</p><small>Preview only. No message is sent.</small></section>}
    {admin && <section className="space-y-3 rounded-xl border p-4">
      <h3 className="font-medium">Submit a text template</h3>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-sm">Name<Input placeholder="order_update" value={draft.name} onChange={e => setDraft({ ...draft, name: e.target.value })} /></label>
        <label className="text-sm">Language code<Input value={draft.language} onChange={e => setDraft({ ...draft, language: e.target.value })} /></label>
        <label className="text-sm">Category<NativeSelect className="h-10 w-full rounded-md border bg-background px-3" value={draft.category} onChange={e => setDraft({ ...draft, category: e.target.value })}><option value="UTILITY">Utility</option><option value="MARKETING">Marketing</option></NativeSelect></label>
      </div>
      <label className="block text-sm">Message body<textarea className="mt-1 min-h-28 w-full rounded-md border bg-background p-3" maxLength={1024} placeholder="Hello {{1}}, your service request {{2}} has been updated." value={draft.body} onChange={e => setDraft({ ...draft, body: e.target.value })} /></label>
      <label className="block text-sm">Sample values, one per line in placeholder order<textarea className="mt-1 w-full rounded-md border bg-background p-3" value={draft.samples} onChange={e => setDraft({ ...draft, samples: e.target.value })} /></label>
      <Button disabled={busy || !draft.name || !draft.body.trim()} onClick={() => void submit()}>{busy ? "Submitting…" : "Submit to Meta"}</Button>
      {notice && <p role="status" className="text-sm">{notice}</p>}
    </section>}
  </div>;
}
