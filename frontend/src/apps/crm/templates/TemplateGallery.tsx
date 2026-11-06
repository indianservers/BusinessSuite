import {useQuery} from '@tanstack/react-query';
import {api} from '@/services/api';
import { useMemo, useState } from 'react';
import { ArrowRight, Check, Search } from 'lucide-react';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { galleryCatalog, galleryTemplate, templateModules, galleryCollections, galleryLayouts, type GalleryEntry } from './gallery-catalog';
import {payload, type Rendered, type Template } from './template-presets';
import './template-gallery.css';

export default function TemplateGallery({ onChoose, canEdit }: { onChoose: (template: Template) => void; canEdit: boolean }) {
  const [module, setModule] = useState('all');
  const [goal, setGoal] = useState('all');
  const [collection, setCollection] = useState('all');
  const [layout, setLayout] = useState('all');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<GalleryEntry | null>(null);
  const [device, setDevice] = useState<'desktop' | 'mobile'>('desktop');
  const [samples, setSamples] = useState(true);
  const goals = useMemo(() => [...new Set(galleryCatalog.filter(e => module === 'all' || e.module === module).map(e => e.goal))], [module]);
  const entries = galleryCatalog.filter(e => (module === 'all' || e.module === module) && (goal === 'all' || e.goal === goal) && (collection === 'all' || e.collection === collection) && (layout === 'all' || e.layout === layout) && `${e.title} ${e.goal} ${e.subject} ${e.message} ${e.module}`.toLowerCase().includes(search.trim().toLowerCase()));
  const preview = useQuery({queryKey:['crm-gallery-preview',selected?.id,samples],enabled:!!selected,queryFn:async()=>(await api.post<Rendered>('/crm/template-studio/render',{template:payload(galleryTemplate(selected!)),sample:samples})).data});
  function text(value: string) { return samples ? value.split('{{name}}').join('Ananya Rao').split('{{company}}').join('Northstar Technologies') : value; }
  return <section className="tg-gallery" aria-label="Email template gallery">
    <div className="ts-section-title"><div><div className="ts-eyebrow">DESIGNED AROUND YOUR NEXT STEP</div><h2>Find the right words. Move work forward.</h2><p>{galleryCatalog.length} original designs across {templateModules.length} CRM modules, with five distinct layouts. Preview the message before you customize.</p></div><span className="tg-original"><Check size={14}/>Original collection</span></div>
    <div className="tg-module-tabs" role="group" aria-label="Gallery modules"><button aria-pressed={module === 'all'} onClick={() => { setModule('all'); setGoal('all'); }}>All modules <span>{galleryCatalog.length}</span></button>{templateModules.map(([key, label]) => <button key={key} aria-pressed={module === key} onClick={() => { setModule(key); setGoal('all'); }}>{label}<span>{galleryCatalog.filter(e => e.module === key).length}</span></button>)}</div>
    <div className="tg-filters"><label><Search size={16}/><input aria-label="Search gallery" placeholder="Find a purpose, message or module…" value={search} onChange={e => setSearch(e.target.value)}/></label><label>Goal<select aria-label="Filter gallery goal" value={goal} onChange={e => setGoal(e.target.value)}><option value="all">Every goal</option>{goals.map(g => <option key={g}>{g}</option>)}</select></label><label>Category<select aria-label="Filter gallery category" value={collection} onChange={e => setCollection(e.target.value)}><option value="all">Every category</option>{galleryCollections.map(c=><option key={c}>{c}</option>)}</select></label><label>Layout<select aria-label="Filter gallery layout" value={layout} onChange={e=>setLayout(e.target.value)}><option value="all">Every layout</option>{galleryLayouts.map(l=><option key={l.key} value={l.key}>{l.label}</option>)}</select></label><button onClick={() => { setModule('all'); setGoal('all'); setCollection('all'); setLayout('all'); setSearch(''); }}>Reset gallery</button></div>
    <p role="status" className="tg-result-count">{entries.length} templates · Original copy, editable branding and personal fields</p>
    <div className="tg-grid">{entries.map(entry => <article key={entry.id} className={`tg-card tg-layout-${entry.layout}`} style={{'--tg-accent': entry.color} as React.CSSProperties}>
      <button className="tg-card-preview" aria-label={`Preview ${entry.title}`} onClick={() => { setSelected(entry); setDevice('desktop'); }}><div className="tg-paper"><span className="tg-paper-brand">YOUR COMPANY <i/></span><span className="tg-paper-rule"/><strong>{entry.title}</strong><p>{entry.message.split('\n\n')[1]}</p><span className="tg-paper-action">{entry.action} <ArrowRight size={11}/></span><span className="tg-paper-signature">Your customer success team</span></div></button>
      <div className="tg-card-info"><div className="tg-card-tags"><span>{templateModules.find(([key]) => key === entry.module)?.[1]}</span><span>{entry.collection}</span></div><h3>{entry.title}</h3><p>{entry.subject}</p><div className="tg-card-actions"><button aria-label={`Preview ${entry.title} details`} onClick={() => setSelected(entry)}>Preview</button><button disabled={!canEdit} aria-label={`Customize ${entry.title}`} onClick={() => onChoose(galleryTemplate(entry))}>Customize <ArrowRight size={13}/></button></div></div>
    </article>)}</div>
    {!entries.length && <div className="ts-empty"><h3>No matching designs</h3><p>Try another phrase or reset the gallery to explore all modules.</p></div>}
    <Dialog open={!!selected} onOpenChange={open => { if (!open) setSelected(null); }}><DialogContent className="tg-dialog"><DialogTitle>{selected?.title || 'Template preview'}</DialogTitle><DialogDescription>Preview uses fictional sample details. Customize the design, then save it to your organization’s library.</DialogDescription>{selected && <>
      <div className="tg-preview-toolbar"><div role="group" aria-label="Preview device"><button aria-pressed={device === 'desktop'} onClick={() => setDevice('desktop')}>Desktop</button><button aria-pressed={device === 'mobile'} onClick={() => setDevice('mobile')}>Mobile</button></div><label><input type="checkbox" checked={samples} onChange={e => setSamples(e.target.checked)}/>Show sample details</label></div>
      <div className="tg-preview-stage"><div className={`tg-email tg-email-${device}`} style={{'--tg-accent': selected.color} as React.CSSProperties}><div className="tg-inbox-subject"><span>SUBJECT</span>{text(selected.subject)}</div>{preview.isLoading ? <p role="status">Preparing preview…</p> : preview.isError ? <p role="alert">Could not load this preview. <button onClick={() => void preview.refetch()}>Retry</button></p> : <iframe title="Gallery design preview" sandbox="" srcDoc={preview.data?.html || ''} className="tg-rendered-preview"/>}</div></div>
      <div className="tg-preview-footer"><p>No message is sent. Choose this design to edit its content, brand and link destination.</p><button className="ts-primary" disabled={!canEdit} onClick={() => { const template = galleryTemplate(selected); setSelected(null); onChoose(template); }}>Customize this design <ArrowRight size={15}/></button></div>
    </>}</DialogContent></Dialog>
  </section>;
}
