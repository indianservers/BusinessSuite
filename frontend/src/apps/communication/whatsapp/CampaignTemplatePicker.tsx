import {useQuery} from '@tanstack/react-query';
import {api} from '@/services/api';
import {NativeSelect} from '@/components/ui/native-select';
import {useCenterScope} from '../center/shared';
import {whatsappBase,templateSupported,templateParameters,type Template} from './types';

export default function CampaignTemplatePicker({value,onChange}:{value:string;onChange:(value:string)=>void}){
  const scope=useCenterScope();
  const templates=useQuery({queryKey:['whatsapp',scope,'campaign-templates'],queryFn:async()=>(await api.get<{items:Template[]}>(whatsappBase+'/templates')).data.items});
  let payload:any=null;try{payload=JSON.parse(value||'null');}catch{/* Existing invalid payload remains visible for correction. */}
  const approved=(templates.data||[]).filter(t=>t.status==='APPROVED'&&templateSupported(t));
  const selected=approved.find(t=>t.name===payload?.name&&t.language===payload?.language?.code);
  const fields=templateParameters(selected);
  const values=(payload?.components?.find((c:any)=>c.type==='body')?.parameters||[]).map((p:any)=>p.text||'');
  function choose(t:Template,parameters:string[]=[]){onChange(JSON.stringify({name:t.name,language:{code:t.language},...(templateParameters(t).length?{components:[{type:'body',parameters:templateParameters(t).map((_,i)=>({type:'text',text:parameters[i]||''}))}]}:{})}));}
  return <section className="space-y-2"><label>Approved WhatsApp campaign template<NativeSelect aria-label="Approved WhatsApp campaign template" loading={templates.isFetching} error={templates.isError} value={selected?selected.name+':'+selected.language:''} onChange={e=>{const t=approved.find(t=>t.name+':'+t.language===e.target.value);if(t)choose(t);else onChange('');}}><option value="">Choose approved template</option>{approved.map(t=><option key={t.name+t.language} value={t.name+':'+t.language}>{t.name} · {t.category} · {t.language}</option>)}</NativeSelect></label>{templates.isError&&<button type="button" onClick={()=>void templates.refetch()}>Retry templates</button>}{selected?.components?.filter(c=>c.text).map((c,i)=><p key={i}><small>{c.type}</small> {c.text?.replace(/\{\{\d+\}\}/g,p=>values[fields.indexOf(p)]||p)}</p>)}{fields.map((field,i)=><label className="block" key={field}>Value for {field}<input required aria-label={`Campaign value for ${field}`} className="w-full rounded border p-2" value={values[i]||''} onChange={e=>{const next=[...values];next[i]=e.target.value;choose(selected!,next);}}/></label>)}<small>Use customer variables such as {'{{name}}'} in template fields. Preview the eligible audience before launch. Templates are fetched from the connected account.</small>{value&&!selected&&<p role="alert">Select a currently supported approved template before saving this WhatsApp campaign.</p>}</section>;
}

export function CampaignTemplatePreview({templates,payload}:{templates:Template[];payload:any}){
 const template=templates.find(t=>t.name===payload?.name&&t.language===payload?.language?.code);
 if(!template)return <p>Approved template preview unavailable. Refresh templates before reviewing this campaign.</p>;
 const parameters=payload?.components?.find((c:any)=>c.type==='body')?.parameters||[];
 return <div><strong>{template.name} · {template.language}</strong>{template.components?.map((c,i)=><div key={i}><small>{c.type}</small>{c.text&&<p className="whitespace-pre-wrap">{c.text.replace(/\{\{(\d+)\}\}/g,(p,n)=>parameters[Number(n)-1]?.text||p)}</p>}{c.buttons?.map((b,j)=><p key={j}>{b.text||b.type} {b.url||b.phone_number||''}</p>)}</div>)}</div>;
}
