import {useMemo, useRef, useState} from 'react';
import {keepPreviousData, useQuery} from '@tanstack/react-query';
import {FileText, Download, Printer, Search} from 'lucide-react';
import {Dialog, DialogContent, DialogTitle, DialogDescription} from '@/components/ui/dialog';
import {Button} from '@/components/ui/button';
import {api} from '@/services/api';
import {useRecordScope, recordError} from '@/shared/records/Record360Workspace';
import {galleryCatalog, galleryTemplate} from '@/apps/crm/templates/gallery-catalog';
import {payload, starter, type Template, type Rendered} from '@/apps/crm/templates/template-presets';
import './record-template-picker.css';

export type TemplateRecordEntity = 'lead' | 'contact' | 'account' | 'deal' | 'invoice';
type Props = {entity:TemplateRecordEntity; recordId:number; source?:'crm'|'srm'};
type Populated = Rendered & {template_name:string; record_name:string; snapshot:boolean; document_status?:string; filled_fields:string[]};
type Choice = {key:string; template:Template; saved:boolean};

function starters(entity: TemplateRecordEntity): Template[] {
  if (entity === 'invoice') {
    const invoice = {...starter('inventory','invoice'), module:'invoice'};
    const reminder = {...starter('email','email','Invoice payment reminder','Hello {{name}},\n\nA reminder about invoice {{document.number}} for {{document.currency}} {{document.total}}. The balance due is {{document.currency}} {{document.balance}}, payable by {{document.due_date}}.\n\nPlease reply if you need any clarification.'), module:'invoice',subject:'Invoice {{document.number}} · payment reminder'};
    reminder.design.blocks = reminder.design.blocks.filter(block => block.type !== 'button');
    return [invoice, reminder];
  }
  const letter = {...starter('mail_merge','letter'), module:entity};
  return [...galleryCatalog.filter(entry => entry.module === entity).map(galleryTemplate), letter];
}

export default function RecordTemplatePicker({entity, recordId, source='crm'}:Props) {
  const scope = useRecordScope();
  const [open,setOpen] = useState(false);
  return <><Button variant="outline" size="sm" onClick={()=>setOpen(true)}><FileText size={15}/>Use template</Button>
    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="record-template-dialog"><DialogTitle>Choose a template</DialogTitle><DialogDescription>Fill a template with this record’s actual details. Review the result before exporting.</DialogDescription>
      {open && <RecordTemplateWorkspace key={`${scope}:${source}:${entity}:${recordId}`} entity={entity} recordId={recordId} source={source}/>}
    </DialogContent></Dialog></>;
}

function RecordTemplateWorkspace({entity, recordId, source='crm'}:Props) {
  const scope = useRecordScope();
  const [search,setSearch] = useState('');
  const [category,setCategory] = useState('all');
  const [selected,setSelected] = useState('');
  const [values,setValues] = useState<Record<string,string>>({});
  const printFrame = useRef<HTMLIFrameElement>(null);
  const base = `/record-templates/${entity}/${recordId}`;
  const library = useQuery({queryKey:['record-templates',scope,source,entity,recordId],retry:false,queryFn:async({signal})=>(await api.get<{items:Template[];record_name:string}>(base,{params:{source},signal})).data});
  const builtin = useMemo(()=>starters(entity),[entity]);
  const choices:Choice[] = [...(library.data?.items || []).map(template=>({key:`saved-${template.id}`,template,saved:true})),...builtin.map((template,index)=>({key:`starter-${index}`,template,saved:false}))];
  const choice = choices.find(item => item.key === selected);
  // Invalidate output immediately when the template or extra values change.
  const valueKey = JSON.stringify(values);
  const preview = useQuery({queryKey:['record-template-preview',scope,source,entity,recordId,selected,valueKey],enabled:!!library.data&&!!choice,retry:false,placeholderData:keepPreviousData,queryFn:async({signal})=>(await api.post<Populated>(base+'/render',{
    ...(choice!.saved ? {template_id:choice!.template.id} : {template:payload(choice!.template)}),values,
  },{params:{source},signal})).data});
  const current = preview.data;
  const extraFields = [...new Set([...(current?.unresolved||[]),...Object.keys(values)])];
  const complete = !!current && current.unresolved.length === 0 && !preview.isFetching && !preview.isError;
  const filtered = choices.filter(item=>(category==='all'||item.template.category===category)&&`${item.template.name} ${item.template.subject} ${item.template.folder}`.toLowerCase().includes(search.toLowerCase()));
  function exportHtml() {
    if (!complete || !current) return;
    const url = URL.createObjectURL(new Blob([current.html],{type:'text/html;charset=utf-8'}));
    const link=document.createElement('a');link.href=url;link.download=`${current.record_name} - ${current.template_name}`.replace(/[^\w .-]/g,'_')+'.html';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  return <div className="record-template-workspace">
    <aside className="record-template-choices"><p className="record-template-name">{library.data?.record_name || 'Record templates'}</p>
      <label><Search size={14}/><input aria-label="Search record templates" placeholder="Find a template…" value={search} onChange={event=>setSearch(event.target.value)}/></label>
      <select aria-label="Record template category" value={category} onChange={event=>setCategory(event.target.value)}><option value="all">All template types</option><option value="email">Email</option><option value="mail_merge">Mail merge</option>{entity==='invoice'&&<option value="inventory">Invoice documents</option>}</select>
      {library.isLoading&&<p role="status">Loading templates…</p>}
      {library.isError&&<p role="alert">{recordError(library.error)} <button onClick={()=>void library.refetch()}>Retry</button></p>}
      {library.data&&<div className="record-template-list">{filtered.map(item=><button key={item.key} aria-pressed={selected===item.key} onClick={()=>{setValues({});setSelected(item.key);}}><strong>{item.template.name}</strong><small>{item.saved?'Your organization':'Starter design'} · {item.template.category==='inventory'?'Invoice':item.template.category==='mail_merge'?'Mail merge':'Email'}</small></button>)}{!filtered.length&&<p>No templates match your search.</p>}</div>}
    </aside>
    <section className="record-template-output" aria-label="Populated template">
      {!choice&&<div className="record-template-empty"><FileText size={32}/><h3>Start with a template</h3><p>Names, addresses, company details and other available fields fill automatically.</p></div>}
      {preview.isFetching&&<p role="status">Filling placeholders from the record…</p>}
      {preview.isError&&<p role="alert">{recordError(preview.error)} <button onClick={()=>void preview.refetch()}>Retry</button></p>}
      {current&&<><header><div><h3>{current.template_name}</h3><p>{current.snapshot?'Uses the issued invoice’s billing snapshots.':'Filled from the current record.'}{current.document_status==='draft'?' Draft invoice · preview only.':''}</p></div><div className="record-template-output-actions"><Button size="sm" variant="outline" disabled={!complete} onClick={exportHtml}><Download size={14}/>Export HTML</Button><Button size="sm" variant="outline" disabled={!complete} onClick={()=>{printFrame.current?.contentWindow?.focus();printFrame.current?.contentWindow?.print();}}><Printer size={14}/>Print / PDF</Button></div></header>
        {choice?.template.category==='email'&&<p className="record-template-subject"><strong>Subject:</strong> {current.subject}</p>}
        {extraFields.length>0&&<div className="record-template-missing"><h4>Complete missing details</h4><p>These details are not available on this record. Enter them before exporting.</p>{extraFields.filter(key=>key!=='document.items').map(key=><label key={key}>{key}<input aria-label={`Fill ${key}`} placeholder={`Enter ${key.replace(/[._]/g,' ')}`} value={values[key]||''} maxLength={15000} onChange={event=>setValues({...values,[key]:event.target.value})}/></label>)}{current.unresolved.includes('document.items')&&<p>Add invoice lines to the invoice before exporting this layout.</p>}</div>}
        <iframe title="Record template preview" sandbox="" srcDoc={current.html}/>
        <iframe ref={printFrame} title="Print record template" sandbox="allow-same-origin allow-modals" srcDoc={current.html} className="record-template-print"/>
      </>}
    </section>
  </div>;
}
