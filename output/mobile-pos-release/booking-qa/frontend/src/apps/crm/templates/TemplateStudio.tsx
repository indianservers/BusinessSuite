import { Button } from "@/components/ui/button";
import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowDown, ArrowUp, Check, Copy, Download, Eye, FileText, GripVertical, LayoutTemplate, Mail, Plus, Printer, Redo2, Save, Search, Trash2, Undo2, X } from 'lucide-react';
import { api } from '@/services/api';
import { useAuthStore } from '@/store/authStore';
import { block, blockLabels, categories, payload, presets, starter, types, type Block, type BlockType, type Category, type Field, type Rendered, type Template } from './template-presets';
import './template-studio.css';
import TemplateGallery from './TemplateGallery';
import TemplateDesignCanvas from '@/shared/template-design/TemplateDesignCanvas';
import { templateModules } from './gallery-catalog';

const ROOT = '/crm/template-studio';
type Line = { description: string; quantity: string; rate: string; amount: string };
type MergeResult = Rendered & { record_id: number; name: string };
function errorText(e: unknown) {
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === 'string' ? detail : 'The request failed. Your design is retained; please try again.';
}
function download(html: string, name: string) {
  const url = URL.createObjectURL(new Blob([html], { type: 'text/html;charset=utf-8' }));
  const a = document.createElement('a'); a.href = url; a.download = name.replace(/[^\w .-]/g, '_') + '.html'; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function TemplateStudio() {
  const location = useLocation();
  const initialCategory: Category = location.pathname.includes('email-templates') ? 'email' : location.pathname.includes('mail-merge') ? 'mail_merge' : location.pathname.includes('inventory-templates') ? 'inventory' : 'email';
  const scope = useAuthStore(s => `${s.user?.access?.companyId}:${s.user?.id}`);
  const qc = useQueryClient();
  const metadata = useQuery({ queryKey: ['template-studio-metadata', scope], queryFn: async () => (await api.get<{ fields: Field[]; can_edit: boolean; can_publish_email: boolean }>(ROOT + '/metadata')).data });
  const library = useQuery({ queryKey: ['template-studio-library', scope], queryFn: async () => (await api.get<{ items: Template[] }>(ROOT + '/templates')).data.items });
  const [category, setCategory] = useState<Category>(initialCategory);
  const [draft, setDraft] = useState<Template | null>(null);
  const [baseline, setBaseline] = useState('');
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [folder, setFolder] = useState('all');
  const [moduleFilter, setModuleFilter] = useState('all');
  const [selected, setSelected] = useState('');
  const [tab, setTab] = useState<'elements' | 'fields' | 'layers'>('elements');
  const [fieldSearch, setFieldSearch] = useState('');
  const [sample, setSample] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [zoom, setZoom] = useState(85);
  const [preview, setPreview] = useState(false);
  const [rendered, setRendered] = useState<Rendered | null>(null);
  const [renderError, setRenderError] = useState('');
  const [rendering, setRendering] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [lines, setLines] = useState<Line[]>([]);
  const [showData, setShowData] = useState(false);
  const [mergeIds, setMergeIds] = useState('');
  const [recordSearch, setRecordSearch] = useState('');
  const [mergeResults, setMergeResults] = useState<MergeResult[]>([]);
  const [mergeIndex, setMergeIndex] = useState(0);
  const history = useRef<Template[]>([]), future = useRef<Template[]>([]);
  const dragging = useRef<string>('');
  const textarea = useRef<HTMLTextAreaElement>(null);
  const subjectInput = useRef<HTMLInputElement>(null);
  const fieldTarget = useRef<'text' | 'subject'>('text');
  const mergeChoices = useQuery({ queryKey: ['template-studio-records', scope, draft?.module, recordSearch], enabled: draft?.category === 'mail_merge', queryFn: async () => (await api.get<{items: {id: number; name: string}[]}>(ROOT + '/records', {params: {module: draft?.module, search: recordSearch}})).data.items });
  const canEdit = metadata.data?.can_edit === true;
  const dirty = Boolean(draft && JSON.stringify(draft) !== baseline);
  const selectedBlock = draft?.design.blocks.find(b => b.id === selected);
  const renderKey = JSON.stringify({ draft, values, lines, sample });
  const renderedKey = useRef('');

  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => { if (dirty) { e.preventDefault(); e.returnValue = ''; } };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);
  useEffect(() => {
    // Clear all tenant-specific editor state immediately on an account / organization change.
    setDraft(null); setValues({}); setLines([]); setMergeResults([]); setRendered(null);
  }, [scope]);
  useEffect(() => {
    if (!draft) return;
    const controller = new AbortController();
    setRendering(true);
    const timer = setTimeout(async () => {
      try {
        const response = await api.post<Rendered>(ROOT + '/render', { template: payload(draft), values, lines, sample }, { signal: controller.signal });
        if (!controller.signal.aborted) { setRendered(response.data); renderedKey.current = renderKey; setRenderError(''); setRendering(false); }
      } catch (e) { if (!controller.signal.aborted) { setRenderError(errorText(e)); setRendering(false); } }
    }, 200);
    return () => { clearTimeout(timer); controller.abort(); };
  // renderKey includes every value sent to the renderer.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [renderKey]);

  function change(next: Template) {
    if (!draft || !canEdit) return;
    history.current = [...history.current.slice(-49), draft]; future.current = [];
    setDraft(next); setNotice(''); setMergeResults([]);
  }
  function patchBlock(changes: Partial<Block>) {
    if (draft) change({ ...draft, design: { ...draft.design, blocks: draft.design.blocks.map(b => b.id === selected ? { ...b, ...changes } : b) } });
  }
  function open(template: Template) {
    if (dirty && !window.confirm('Discard the unsaved changes to this design?')) return;
    const copy = structuredClone(template);
    setDraft(copy); setBaseline(JSON.stringify(copy)); setSelected(copy.design.blocks[0]?.id || '');
    setNotice(''); setError(''); setValues({}); setLines([]); setMergeResults([]); setRendered(null); setRenderError(''); setPreview(false); setSample(false); setMergeIds(''); setRecordSearch('');
    history.current = []; future.current = [];
  }
  function reorder(id: string, target: string) {
    if (!draft || id === target) return;
    const blocks = [...draft.design.blocks]; const from = blocks.findIndex(b => b.id === id); const to = blocks.findIndex(b => b.id === target);
    if (from < 0 || to < 0) return;
    const [moving] = blocks.splice(from, 1); blocks.splice(to, 0, moving); change({ ...draft, design: { ...draft.design, blocks } });
  }
  function add(type: BlockType) {
    if (!draft) return;
    const next = block(type); const blocks = [...draft.design.blocks]; const index = blocks.findIndex(b => b.id === selected);
    blocks.splice(index < 0 ? blocks.length : index + 1, 0, next);
    change({ ...draft, design: { ...draft.design, blocks } }); setSelected(next.id); fieldTarget.current = 'text';
  }
  function insert(key: string) {
    if (!draft || !canEdit) return;
    const token = `{{${key}}}`;
    if (fieldTarget.current === 'subject' && draft.category === 'email') {
      const el = subjectInput.current; const start = el?.selectionStart ?? draft.subject.length; const end = el?.selectionEnd ?? start;
      change({ ...draft, subject: draft.subject.slice(0, start) + token + draft.subject.slice(end) });
      requestAnimationFrame(() => { el?.focus(); el?.setSelectionRange(start + token.length, start + token.length); });
    } else if (selectedBlock && !['items', 'totals', 'divider', 'spacer'].includes(selectedBlock.type)) {
      const el = textarea.current; const start = el?.selectionStart ?? selectedBlock.text.length; const end = el?.selectionEnd ?? start;
      patchBlock({ text: selectedBlock.text.slice(0, start) + token + selectedBlock.text.slice(end), html: '' });
      requestAnimationFrame(() => { el?.focus(); el?.setSelectionRange(start + token.length, start + token.length); });
    } else { add('text'); setNotice('Select the new text block, then insert a placeholder.'); }
  }
  async function save() {
    if (!draft) return;
    setBusy(true); setError('');
    try {
      const response = draft.id ? await api.put<Template>(`${ROOT}/templates/${draft.id}`, payload(draft)) : await api.post<Template>(ROOT + '/templates', payload(draft));
      const saved = response.data; setDraft(saved); setBaseline(JSON.stringify(saved)); setNotice('Template saved');
      history.current = []; future.current = [];
      await qc.invalidateQueries({ queryKey: ['template-studio-library', scope] });
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  async function publish() {
    if (!draft?.id || dirty) return;
    setBusy(true); setError('');
    try { await api.post(`${ROOT}/templates/${draft.id}/publish-email`); setNotice('Published to the email composer.'); await qc.invalidateQueries({ queryKey: ['communication-templates'] }); }
    catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  async function remove(template: Template) {
    if (!window.confirm(`Delete “${template.name}”? Published email copies remain available in the email composer.`)) return;
    setBusy(true); setError('');
    try { await api.delete(`${ROOT}/templates/${template.id}`); await qc.invalidateQueries({ queryKey: ['template-studio-library', scope] }); }
    catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  async function merge() {
    if (!draft?.id || dirty) return;
    const ids = mergeIds.split(/[\s,]+/).filter(Boolean).map(Number);
    if (!ids.length || ids.length > 50 || ids.some(id => !Number.isSafeInteger(id) || id <= 0)) { setError('Choose between 1 and 50 records to merge.'); return; }
    setBusy(true); setError('');
    try {
      const entity = { lead: 'leads', contact: 'contacts', account: 'accounts', deal: 'deals', quotation: 'quotations', task: 'tasks', meeting: 'meetings', call: 'calls', campaign: 'campaigns', ticket: 'tickets' }[draft.module];
      const response = await api.post<{ items: MergeResult[] }>(`${ROOT}/templates/${draft.id}/merge`, { entity, record_ids: ids, values });
      setMergeResults(response.data.items); setMergeIndex(0); setPreview(true); setSample(false); setNotice(`Created ${response.data.items.length} personalized previews.`);
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  const currentRender = mergeResults[mergeIndex] || rendered;
  const renderCurrent = mergeResults.length > 0 || (!rendering && renderedKey.current === renderKey && !renderError);
  const fields = metadata.data?.fields || [];
  const used = new Set(((draft?.subject || '') + ' ' + (draft?.design.blocks.map(b => b.type === 'totals' ? '{{document.subtotal}} {{document.discount}} {{document.tax}} {{document.total}} {{document.balance}}' : b.text).join(' ') || '')).match(/\{\{\s*([a-z][a-z0-9_.]*)\s*\}\}/g)?.map(t => t.replace(/[{}\s]/g, '')) || []);
  const filtered = (library.data || []).filter(t => t.category === category && (moduleFilter === 'all' || t.module === moduleFilter) && (filter === 'all' || t.document_type === filter) && (folder === 'all' || t.folder === folder) && `${t.name} ${t.subject} ${t.folder}`.toLowerCase().includes(search.toLowerCase()));
  const folders = [...new Set((library.data || []).filter(t => t.category === category).map(t => t.folder))];
  const icon = category === 'email' ? <Mail size={22}/> : <FileText size={22}/>;
  const alerts = <>{error && <p className="ts-error" role="alert">{error}</p>}{notice && <p className="ts-notice" role="status"><Check size={15}/>{notice}</p>}</>;

  if (!draft) return <main className="template-studio ts-library">
    <header className="ts-library-heading"><div className="ts-eyebrow"><LayoutTemplate size={16}/> CRM TEMPLATE STUDIO</div><h1>Make every message yours.</h1><p>Design emails, business documents and personalized letters. Start with a layout, then make it your own.</p><div className="ts-header-actions"><Button type="submit" variant="default" className="ts-primary" disabled={!canEdit} onClick={() => open(starter(category))}><Plus size={16}/>Create template</Button><Link to="/crm/pipeline-templates">Business & pipeline presets →</Link><Link to="/crm/communication-hub?section=templates">Existing email templates →</Link></div></header>
    <nav className="ts-category-tabs" aria-label="Template categories">{categories.map(c => <button key={c.key} aria-current={category === c.key ? 'page' : undefined} onClick={() => { setCategory(c.key); setFilter('all'); setFolder('all'); }}>{c.label}<span>{c.description}</span></button>)}</nav>
    {alerts}{metadata.isError && <p role="alert" className="ts-error">Could not load editor permissions. <Button type="submit" variant="outline" onClick={() => void metadata.refetch()}>Retry</Button></p>}
    {category === 'email' && <TemplateGallery onChoose={open} canEdit={canEdit}/>}
    <section><div className="ts-section-title"><div><h2>Start with a design</h2><p>Ready to customize · all text, branding and placeholders are editable</p></div>{icon}</div><div className="ts-preset-grid">{presets(category).map((t, i) => <button className="ts-preset" key={t.name} onClick={() => open(t)}><div className={`ts-thumbnail ts-thumbnail-${i % 3}`}><div className="ts-mini-brand">YOUR COMPANY <span>✦</span></div><div className="ts-mini-rule"/><strong>{category === 'email' ? ['Welcome aboard.', 'Let’s reconnect.', 'A friendly reminder.', 'Let’s meet.', 'Thank you.', 'Something new.'][i] : types[category].find(x => x.key === t.document_type)?.label}</strong><div className="ts-mini-lines"><i/><i/><i/></div>{category === 'inventory' ? <div className="ts-mini-table"><i/><i/><i/></div> : <div className="ts-mini-button"/>}<div className="ts-mini-lines"><i/><i/></div></div><div className="ts-preset-caption"><span>{t.name}</span><span>Customize ↗</span></div></button>)}</div></section>
    <section><div className="ts-section-title"><div><h2>Your templates <span data-count-badge data-count-tone="purple" className="ts-count">{filtered.length}</span></h2><p>Saved for your organization</p></div></div><div className="ts-library-filters"><label><Search size={16}/><input aria-label="Search templates" placeholder="Search by template name, subject or folder…" value={search} onChange={e => setSearch(e.target.value)}/></label><select aria-label="Filter saved template module" value={moduleFilter} onChange={e => setModuleFilter(e.target.value)}><option value="all">All modules</option>{[...templateModules,['invoice','Invoices'] as const].map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select><select aria-label="Filter document type" value={filter} onChange={e => setFilter(e.target.value)}><option value="all">All document types</option>{types[category].map(t => <option key={t.key} value={t.key}>{t.label}</option>)}</select><select aria-label="Filter folder" value={folder} onChange={e => setFolder(e.target.value)}><option value="all">All folders</option>{folders.map(f => <option key={f}>{f}</option>)}</select></div>
      {library.isLoading ? <p role="status">Loading saved templates…</p> : library.isError ? <p role="alert" className="ts-error">Could not load templates. <button onClick={() => void library.refetch()}>Try again</button></p> : filtered.length ? <div className="ts-saved-grid">{filtered.map(t => <article key={t.id}><div className="ts-saved-icon">{t.category === 'email' ? <Mail/> : <FileText/>}</div><div><h3>{t.name}</h3><p>{t.folder} · {t.document_type.replace('_', ' ')} · v{t.version}</p><span className={`ts-badge ${t.status}`}>{t.status}</span></div><div className="ts-card-actions"><Button type="submit" variant="outline" onClick={() => open(t)}>Open</Button><button aria-label={`Clone ${t.name}`} disabled={!canEdit} onClick={() => open({ ...structuredClone(t), id: undefined, email_template_id: undefined, name: t.name + ' copy', version: 1, status: 'draft' })}><Copy size={16}/></button><button aria-label={`Delete ${t.name}`} disabled={!canEdit || busy} onClick={() => void remove(t)}><Trash2 size={16}/></button></div></article>)}</div> : <div className="ts-empty"><LayoutTemplate size={30}/><h3>{search || filter !== 'all' || folder !== 'all' ? 'No matching templates' : 'Your next great template starts here'}</h3><p>{search ? 'Try a different name or folder.' : 'Choose a starter above or create a template to build your library.'}</p></div>}
    </section>
  </main>;

  return <main className="template-studio ts-editor">
    <header className="ts-editor-header"><button className="ts-back" onClick={() => { if (!dirty || window.confirm('Discard unsaved changes?')) { setDraft(null); setError(''); setNotice(''); } }}>← Library</button><div className="ts-design-name"><input aria-label="Template name" maxLength={180} placeholder="e.g. Monthly invoice · Modern purple" value={draft.name} disabled={!canEdit || busy} onChange={e => change({ ...draft, name: e.target.value })}/><span>{dirty ? 'Unsaved changes' : draft.id ? `Saved · version ${draft.version}` : 'New design'} · {categories.find(c => c.key === draft.category)?.label}</span></div><div className="ts-header-actions"><button title="Undo" aria-label="Undo" disabled={!history.current.length || !canEdit || busy} onClick={() => { const prev = history.current.pop(); if (prev) { future.current.push(draft); setDraft(prev); } }}><Undo2 size={17}/></button><button title="Redo" aria-label="Redo" disabled={!future.current.length || !canEdit || busy} onClick={() => { const next = future.current.pop(); if (next) { history.current.push(draft); setDraft(next); } }}><Redo2 size={17}/></button><button aria-pressed={preview} onClick={() => { setPreview(!preview); setMergeResults([]); }}><Eye size={16}/>{preview ? 'Edit design' : 'Preview'}</button><button className="ts-primary" disabled={!canEdit || busy || draft.name.trim().length < 2 || !draft.design.blocks.length} onClick={() => void save()}><Save size={16}/>{busy ? 'Working…' : 'Save template'}</button></div></header>
    {alerts}
    <div className="ts-settings"><label>Folder<input placeholder="e.g. Sales / Customer onboarding" value={draft.folder} maxLength={100} disabled={!canEdit || busy} onChange={e => change({ ...draft, folder: e.target.value })}/></label><label>Module<select aria-label="Template module" value={draft.module} disabled={!canEdit || busy} onChange={e => { change({ ...draft, module: e.target.value }); setMergeIds(''); setRecordSearch(''); }}>{([...templateModules, ...(draft.category === 'email' ? [['invoice', 'Invoices'] as const] : [])]).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><label>Status<select aria-label="Template status" value={draft.status} disabled={!canEdit || busy} onChange={e => change({ ...draft, status: e.target.value as 'draft' | 'ready' })}><option value="draft">Draft</option><option value="ready">Ready to use</option></select></label>{draft.category === 'email' && <label className="ts-subject">Email subject<input ref={subjectInput} aria-label="Email subject" placeholder="e.g. Welcome to our community, {{name}}" value={draft.subject} maxLength={240} disabled={!canEdit || busy} onFocus={() => { fieldTarget.current = 'subject'; }} onChange={e => change({ ...draft, subject: e.target.value })}/></label>}</div>
    <div className="ts-workspace">
      <aside className="ts-left"><nav className="ts-tool-tabs" aria-label="Design tools">{(['elements', 'fields', 'layers'] as const).map(t => <button key={t} aria-pressed={tab === t} onClick={() => setTab(t)}>{t === 'fields' ? 'Placeholders' : t[0].toUpperCase() + t.slice(1)}</button>)}</nav>
        {tab === 'elements' ? <><h2>Build your design</h2><p className="ts-hint">Double-click text on the canvas to edit. Add blocks, then drag or use layer arrows to rearrange.</p><div className="ts-elements">{(Object.entries(blockLabels) as [BlockType, string][]).filter(([type]) => draft.category !== 'email' || !['items', 'totals'].includes(type)).map(([type, label]) => <button key={type} disabled={!canEdit || busy || draft.design.blocks.length >= 100} onClick={() => add(type)}><Plus size={17}/>{label}</button>)}</div><h2>Page style</h2><label>Brand color<input type="color" aria-label="Brand color" value={draft.design.accent} disabled={!canEdit || busy} onChange={e => change({ ...draft, design: { ...draft.design, accent: e.target.value } })}/></label><label>Paper color<input type="color" aria-label="Paper color" value={draft.design.background} disabled={!canEdit || busy} onChange={e => change({ ...draft, design: { ...draft.design, background: e.target.value } })}/></label><label>Font family<select value={draft.design.font} disabled={!canEdit || busy} onChange={e => change({ ...draft, design: { ...draft.design, font: e.target.value } })}>{['Arial', 'Georgia', 'Verdana', 'Times New Roman'].map(f => <option key={f}>{f}</option>)}</select></label></> : tab === 'fields' ? <><h2>Personalize every copy</h2><p className="ts-hint">Insert at the cursor in your selected text block or subject. Examples are sample data.</p><input aria-label="Search placeholders" placeholder="Find a name, amount, date…" value={fieldSearch} onChange={e => setFieldSearch(e.target.value)}/><div className="ts-field-list">{fields.filter(f => `${f.label} ${f.key} ${f.group}`.toLowerCase().includes(fieldSearch.toLowerCase())).map(f => <button key={f.key} disabled={!canEdit || busy} onMouseDown={e => e.preventDefault()} onClick={() => insert(f.key)}><span>{f.group} · {f.label}</span><code>{`{{${f.key}}}`}</code><small>e.g. {f.sample}</small></button>)}</div></> : <><h2>Layers</h2><p className="ts-hint">Top to bottom · select a layer to edit it.</p>{draft.design.blocks.map((b, i) => <div className={`ts-layer ${selected === b.id ? 'selected' : ''}`} key={b.id} draggable={canEdit && !busy} onDragStart={() => { dragging.current = b.id; }} onDragOver={e => e.preventDefault()} onDrop={() => reorder(dragging.current, b.id)}><button onClick={() => { setSelected(b.id); fieldTarget.current = 'text'; }}><GripVertical size={14}/>{blockLabels[b.type]}</button><button aria-label={`Move ${blockLabels[b.type]} up`} disabled={!canEdit || busy || i === 0} onClick={() => reorder(b.id, draft.design.blocks[i - 1].id)}><ArrowUp size={13}/></button><button aria-label={`Move ${blockLabels[b.type]} down`} disabled={!canEdit || busy || i === draft.design.blocks.length - 1} onClick={() => reorder(b.id, draft.design.blocks[i + 1].id)}><ArrowDown size={13}/></button></div>)}</>}
      </aside>
      <section className="ts-canvas-area" aria-label="Visual template canvas"><div className="ts-canvas-toolbar"><span>{draft.category === 'email' ? 'Email · responsive' : 'A4 · flowing document'}</span><div><label><input type="checkbox" checked={sample} onChange={e => { setSample(e.target.checked); setMergeResults([]); }}/>Sample data</label><button aria-pressed={mobile} onClick={() => setMobile(!mobile)}>{mobile ? 'Desktop' : 'Mobile'}</button><select aria-label="Canvas zoom" value={zoom} onChange={e => setZoom(Number(e.target.value))}>{[50, 65, 75, 85, 100, 125].map(z => <option key={z} value={z}>{z}%</option>)}</select></div></div>
        {renderError && <p className="ts-error" role="alert">{renderError}</p>}
        {sample && !mergeResults.length && <div className="ts-sample-banner">Sample data preview · example names and amounts are for design only</div>}
        {mergeResults.length > 0 && <div className="ts-merge-switch"><label>Personalized document<select aria-label="Merged recipient" value={mergeIndex} onChange={e => setMergeIndex(Number(e.target.value))}>{mergeResults.map((m, i) => <option key={m.record_id} value={i}>{m.name} · #{m.record_id}</option>)}</select></label></div>}
        <div className="ts-scroll-canvas"><div style={{ zoom: zoom / 100, width: mobile ? 375 : draft.category === 'email' ? 640 : 794, maxWidth: '100%', margin: '24px auto' }}>
          {preview ? <iframe title="Template preview" sandbox="" srcDoc={currentRender?.html || ''} className="ts-preview-frame"/> : <TemplateDesignCanvas design={draft.design} renderedBlocks={rendered?.blocks || null} selected={selected} labels={blockLabels} readOnly={!canEdit || busy} busy={busy} onSelect={id => {setSelected(id); fieldTarget.current = 'text';}} onEdit={() => setSample(false)} onChange={(id, changes) => change({...draft, design: {...draft.design, blocks: draft.design.blocks.map(b => b.id === id ? {...b, ...changes} : b)}})} onMove={reorder} onAddText={() => add('text')}/>}
        </div></div>
        <footer className="ts-canvas-footer"><span>{draft.design.blocks.length} blocks · {used.size} placeholders</span><span role="status">{rendering ? 'Updating preview…' : renderError ? 'Preview needs attention' : 'Preview up to date'}</span></footer>
      </section>
      <aside className="ts-right"><h2>{selectedBlock ? blockLabels[selectedBlock.type] : 'Select a block'}</h2>{selectedBlock && <fieldset disabled={!canEdit || busy} className="ts-block-properties">
        {!['divider', 'spacer', 'items', 'totals'].includes(selectedBlock.type) && <label>{selectedBlock.type === 'image' ? 'Alternative text' : 'Plain text · double-click the canvas to format'}<textarea ref={textarea} aria-label="Block content" placeholder="Write here. Insert {{name}} or another field from Placeholders." value={selectedBlock.text} rows={7} maxLength={15000} onFocus={() => { fieldTarget.current = 'text'; }} onChange={e => patchBlock({ text: e.target.value, html: '' })}/></label>}
        {['image', 'button'].includes(selectedBlock.type) && <label>{selectedBlock.type === 'image' ? 'Image URL' : 'Button destination'}<input type="url" placeholder={selectedBlock.type === 'image' ? 'https://your-company.com/logo.png' : 'https://your-company.com/get-started'} value={selectedBlock.url} onChange={e => patchBlock({ url: e.target.value })}/><small>Use a public HTTPS URL.</small></label>}
        <div className="ts-property-row"><label>Text size<input type="number" min={10} max={64} value={selectedBlock.size} onChange={e => patchBlock({ size: Math.max(10, Math.min(64, Number(e.target.value) || 10)) })}/></label><label>Text color<input type="color" aria-label="Text color" value={selectedBlock.color} onChange={e => patchBlock({ color: e.target.value })}/></label></div>
        {selectedBlock.type === 'columns' && <label>Columns<select aria-label="Column count" value={selectedBlock.columns || 2} onChange={e => patchBlock({columns: Number(e.target.value) as 2 | 3})}><option value={2}>Two columns</option><option value={3}>Three columns</option></select><small>Separate column content with a line containing ---.</small></label>}<label>Alignment<select value={selectedBlock.align} onChange={e => patchBlock({ align: e.target.value as Block['align'] })}><option value="left">Left</option><option value="center">Center</option><option value="right">Right</option></select></label><label>Block spacing<input type="range" min={0} max={80} value={selectedBlock.padding} onChange={e => patchBlock({ padding: Number(e.target.value) })}/><small>{selectedBlock.padding}px above and below</small></label><label className="ts-checkbox"><input type="checkbox" checked={selectedBlock.bold} onChange={e => patchBlock({ bold: e.target.checked })}/>Bold text</label><div className="ts-property-row"><Button type="submit" variant="outline" onClick={() => { const copy = { ...selectedBlock, id: crypto.randomUUID() }; const blocks = [...draft.design.blocks]; blocks.splice(blocks.findIndex(b => b.id === selected) + 1, 0, copy); change({ ...draft, design: { ...draft.design, blocks } }); setSelected(copy.id); }} disabled={draft.design.blocks.length >= 100}><Copy size={15}/>Duplicate</Button><button onClick={() => { change({ ...draft, design: { ...draft.design, blocks: draft.design.blocks.filter(b => b.id !== selected) } }); setSelected(''); }}><Trash2 size={15}/>Remove</button></div>
      </fieldset>}
        <div className="ts-export"><h2>Preview & output</h2><p className="ts-hint">HTML keeps the design. Print opens the browser’s Save as PDF option.</p><button onClick={() => setShowData(!showData)} aria-expanded={showData}>{showData ? 'Hide' : 'Edit'} merge values & line items</button>
          {currentRender?.unresolved.length ? <p className="ts-warning">Unfilled: {currentRender.unresolved.map(k => `{{${k}}}`).join(', ')}</p> : <p className="ts-hint">{sample ? 'Example values are shown.' : 'All text placeholders are filled.'}</p>}
          <Button type="submit" variant="outline" disabled={!currentRender || !renderCurrent || (currentRender.unresolved.length > 0 && !sample)} onClick={() => currentRender && download(currentRender.html, draft.name + (sample ? ' - SAMPLE' : ''))}><Download size={15}/>{sample ? 'Export sample HTML' : 'Export HTML'}</Button><button disabled={!currentRender || !renderCurrent || (currentRender.unresolved.length > 0 && !sample)} onClick={() => { setPreview(true); setTimeout(() => { const frame = document.querySelector<HTMLIFrameElement>('.ts-print-frame'); if (frame?.contentWindow) { frame.contentWindow.focus(); frame.contentWindow.print(); } }, 100); }}><Printer size={15}/>{sample ? 'Print sample / PDF' : 'Print / PDF'}</button>
          {draft.category === 'email' && <><button disabled={!metadata.data?.can_publish_email || !draft.id || dirty || draft.status !== 'ready' || busy} onClick={() => void publish()}><Mail size={15}/>Publish to email composer</button><p className="ts-hint">Save as “Ready to use” first. The composer asks you to fill every missing placeholder before sending.</p></>}
          {draft.category === 'mail_merge' && <><h2>Merge CRM records</h2><p className="ts-hint">Save your template, then choose up to 50 {draft.module} records to personalize.</p><input aria-label="Search merge recipients" placeholder="Search records by name…" value={recordSearch} onChange={e => setRecordSearch(e.target.value)}/><div className="ts-recipient-list">{mergeChoices.isLoading ? <p role="status">Loading records…</p> : mergeChoices.isError ? <p role="alert">Could not load records. <Button type="submit" variant="outline" onClick={() => void mergeChoices.refetch()}>Retry</Button></p> : mergeChoices.data?.length ? mergeChoices.data.map(record => { const ids = mergeIds.split(',').filter(Boolean); return <label key={record.id}><input type="checkbox" checked={ids.includes(String(record.id))} disabled={!ids.includes(String(record.id)) && ids.length >= 50} onChange={e => { setMergeIds((e.target.checked ? [...ids, String(record.id)] : ids.filter(id => id !== String(record.id))).join(',')); setMergeResults([]); }}/>{record.name}</label>; }) : <p>No matching records in this module.</p>}</div><small>{mergeIds.split(',').filter(Boolean).length} selected</small><button disabled={!draft.id || dirty || busy} onClick={() => void merge()}>Generate personalized copies</button>{mergeResults.length > 0 && <Button type="submit" variant="outline" onClick={() => { const complete = mergeResults.filter(m => !m.unresolved.length); if (!complete.length) { setError('Fill the missing placeholders and merge again before exporting.'); return; } const sections = complete.map(m => `<section style="break-after:page">${m.body}</section>`).join(''); download(`<!doctype html><html><head><meta charset="utf-8"><title>Mail merge</title><style>@page{size:A4;margin:12mm}body{margin:0}</style></head><body>${sections}</body></html>`, draft.name + ' - merged'); setNotice(`Exported ${complete.length} complete documents. ${mergeResults.length - complete.length} incomplete documents excluded.`); }}>Export complete merged copies</Button>}</>}
        </div>
      </aside>
    </div>
    {showData && <section className="ts-data-panel"><div className="ts-section-title"><div><h2>Merge values & line items</h2><p>Use real values for export. Sample data is only used when its toggle is enabled.</p></div><button aria-label="Close merge values" onClick={() => setShowData(false)}><X size={18}/></button></div><div className="ts-value-grid">{[...used].map(key => <label key={key}>{fields.find(f => f.key === key)?.label || key}<input aria-label={`Value for ${key}`} placeholder={fields.find(f => f.key === key)?.sample || `Enter ${key}`} value={values[key] || ''} maxLength={15000} onChange={e => { setValues({ ...values, [key]: e.target.value }); setMergeResults([]); }}/><code>{`{{${key}}}`}</code></label>)}</div>{draft.design.blocks.some(b => b.type === 'items') && <><h3>Line items</h3><p className="ts-hint">Enter display amounts and matching totals above. Tax and discounts come from your source document.</p>{lines.map((line, i) => <div key={i} className="ts-line-row">{(['description', 'quantity', 'rate', 'amount'] as const).map(key => <label key={key}>{key}<input aria-label={`Line ${i + 1} ${key}`} value={line[key]} maxLength={key === 'description' ? 500 : 30} onChange={e => setLines(lines.map((l, idx) => idx === i ? { ...l, [key]: e.target.value } : l))}/></label>)}<button aria-label={`Remove line ${i + 1}`} onClick={() => setLines(lines.filter((_, idx) => idx !== i))}><Trash2 size={16}/></button></div>)}<Button type="submit" variant="default" disabled={lines.length >= 100} onClick={() => setLines([...lines, { description: '', quantity: '1', rate: '0.00', amount: '0.00' }])}><Plus size={15}/>Add line item</Button></>}</section>}
    <iframe title="Print template" className="ts-print-frame" sandbox="allow-same-origin allow-modals" srcDoc={currentRender?.html || ''}/>
  </main>;
}
