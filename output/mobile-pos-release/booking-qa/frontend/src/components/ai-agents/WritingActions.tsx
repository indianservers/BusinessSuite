import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Check, Copy, Loader2, Sparkles } from 'lucide-react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { api } from '@/services/api';
import { useAuthStore } from '@/store/authStore';
import { actionBotContext, type BotModule } from './action-bot-context';
import { documentActions, pageWritingContext, pageWritingPath, visibleWritingSource, type WritingAction, type WritingSource } from './page-ai-actions';
import './writing-actions.css';

type Draft = {text:string;subject:string;missing_details:string[];engine:string;method:string};
type Props = { actions?: WritingAction[]; source?: ()=>WritingSource; onApply?: (text:string,subject?:string)=>boolean|void; module?:BotModule; compact?:boolean; disabled?:boolean; presentation?:'buttons'|'menu' };

/** Direct action buttons; deliberately independent of chatbot conversations. */
export default function WritingActions({actions: supplied,source,onApply,module: suppliedModule,compact=false,disabled=false,presentation='buttons'}:Props) {
  const location=useLocation(),user=useAuthStore(s=>s.user);
  const pagePath=pageWritingPath(location.pathname,location.search);
  const context=pageWritingContext(pagePath),module=suppliedModule||context?.module;
  const actions=supplied||context?.actions||[];
  const [action,setAction]=useState<WritingAction|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const [draft,setDraft]=useState<Draft|null>(null),[text,setText]=useState(''),[subject,setSubject]=useState('');
  const [input,setInput]=useState<WritingSource>({text:'',title:''}),[tone,setTone]=useState('professional'),[language,setLanguage]=useState('Hindi');
  const [sourceOpen,setSourceOpen]=useState(false);
  const [provider,setProvider]=useState('local'),[providers,setProviders]=useState<{provider:string;enabled:boolean;data_sharing_allowed:boolean;has_key:boolean}[]>([]);
  const menuTrigger=useRef<HTMLButtonElement>(null);
  const controller=useRef<AbortController|null>(null),serial=useRef(0),textarea=useRef<HTMLTextAreaElement|null>(null),original=useRef('');
  const parameters=new URLSearchParams(location.search);
  const recordScope=['workspace','workspace_id','project','projectId','project_id','task','taskId','recordId','recordType','id','lead','contact','company','deal'].map(key=>parameters.get(key)||'').join(':');
  const scope=[pagePath,recordScope,user?.id,user?.access?.companyId].join(':');
  function reset(){serial.current++;controller.current?.abort();setAction(null);setDraft(null);setError('');setBusy(false);setProvider('local');setProviders([]);textarea.current=null;}
  useEffect(()=>{reset();const changed=()=>reset();window.addEventListener('suite:organization-changed',changed);window.addEventListener('suite:branch-changed',changed);return()=>{serial.current++;controller.current?.abort();window.removeEventListener('suite:organization-changed',changed);window.removeEventListener('suite:branch-changed',changed);};},[scope]);
  useEffect(()=>{
    const focus=(event:FocusEvent)=>{const el=event.target;if(el instanceof HTMLTextAreaElement&&!el.closest('[data-ai-writing],.suite-action-bot')&&!el.disabled&&!el.readOnly){textarea.current=el;original.current=el.value;}};
    document.addEventListener('focusin',focus);return()=>document.removeEventListener('focusin',focus);
  },[]);
  useEffect(()=>{
    if(!action)return;let active=true;setProviders([]);
    const workspace=actionBotContext(location.pathname,location.search).workspace_id;
    api.get('/ai-operator/suite/providers',{params:{workspace_id:workspace||undefined},progress:false}).then(r=>{if(active)setProviders(r.data.items||[]);}).catch(()=>{if(active)setProviders([]);});
    return()=>{active=false;};
  },[scope,action?.id]);
  if(!user||!module||!actions.length)return null;

  async function generate(selected:WritingAction,values:WritingSource,nextTone=tone,nextLanguage=language,selectedProvider=provider){
    controller.current?.abort();const abort=new AbortController();controller.current=abort;const request=++serial.current;
    setBusy(true);setError('');setNotice('');setDraft(null);setText('');setSubject('');
    try {
      const r=await api.post<Draft>('/ai-operator/writing/draft',{action:selected.id,module,provider:selectedProvider,text:values.text,title:values.title,recipient:values.recipient||'',tone:nextTone,language:nextLanguage,workspace_id:actionBotContext(location.pathname,location.search).workspace_id},{signal:abort.signal,readOnlyPreview:true,progress:false});
      if(request!==serial.current)return;
      const result=r.data;
      setDraft(result);setText(result.text);setSubject(result.subject);setNotice('');
    }catch(e:any){if(request!==serial.current||abort.signal.aborted)return;setNotice('');const detail=e?.response?.data?.detail;setError(typeof detail==='string'?detail:detail?.message||e?.message||'Could not prepare this draft. Your source text is preserved.');}
    finally{if(request===serial.current)setBusy(false);}
  }
  function start(selected:WritingAction){
    const values=source?source():visibleWritingSource(textarea.current);
    if(textarea.current)original.current=textarea.current.value;
    setProvider('local');setAction(selected);setInput(values);setSourceOpen(!values.text);setDraft(null);setNotice('');void generate(selected,values,tone,language,'local');
  }
  function apply(){
    if(!text.trim())return;
    if(onApply){if(onApply(text,subject)===false){setError('The editor changed or cannot accept this replacement. Select plain text without images or tables and retry, or copy the draft.');return;}setNotice('Inserted into the editor. Review before saving or sending.');return;}
    const target=textarea.current;
    if(!target?.isConnected||target.disabled||target.readOnly){setError('Focus an editable message or description field before using an AI button. You can also copy this draft.');return;}
    if(target.value!==original.current){setError('The original field changed while this draft was open. Copy your draft or close and generate again to preserve those edits.');return;}
    if(target.maxLength>0&&text.length>target.maxLength){setError(`This field allows ${target.maxLength} characters. Shorten the draft before inserting.`);return;}
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value')!.set!.call(target,text);
    target.dispatchEvent(new Event('input',{bubbles:true}));original.current=text;
    setNotice('Inserted into the editor. Review before saving or sending.');
  }
  return <div data-ai-writing className={`writing-actions ${compact?'writing-actions-compact':''}`}>
    {presentation==='menu' ? <DropdownMenu.Root modal={false}><DropdownMenu.Trigger asChild><button type="button" ref={menuTrigger} className="writing-menu-trigger" disabled={disabled}><Sparkles size={13} aria-hidden="true"/>AI writing</button></DropdownMenu.Trigger><DropdownMenu.Portal><DropdownMenu.Content data-ai-writing className="writing-menu-content" align="end" sideOffset={6} collisionPadding={12} aria-label="AI writing actions" onCloseAutoFocus={event=>{if(action)event.preventDefault();}}>{actions.map(item=><DropdownMenu.Item key={item.id} className="writing-menu-item" onSelect={()=>start(item)}>{item.label}</DropdownMenu.Item>)}</DropdownMenu.Content></DropdownMenu.Portal></DropdownMenu.Root> : <div className="writing-action-buttons" role="group" aria-label="AI writing actions">{actions.map(item=><button key={item.id} type="button" disabled={disabled} onClick={()=>start(item)}><Sparkles size={13}/>{item.label}</button>)}</div>}
    <Dialog open={!!action} onOpenChange={open=>{if(!open)reset();}}><DialogContent data-ai-writing className="writing-draft-dialog" onCloseAutoFocus={event=>{if(presentation==='menu'){event.preventDefault();menuTrigger.current?.focus();}}}>
      <DialogTitle><Sparkles size={18}/>{action?.label}</DialogTitle>
      <p className="writing-help">Runs on the server. Local mode uses fact-preserving drafting; a selected cloud provider receives the supplied source when you generate. Review before inserting, saving or sending.</p>
      <details open={sourceOpen}><summary onClick={e=>{e.preventDefault();setSourceOpen(value=>!value);}}>Source details</summary><label>Topic / record<input aria-label="AI draft topic" value={input.title} maxLength={200} onChange={e=>setInput({...input,title:e.target.value})}/></label><label>Recipient<input aria-label="AI draft recipient" value={input.recipient||''} maxLength={120} onChange={e=>setInput({...input,recipient:e.target.value})}/></label><label>Notes or selected record details<textarea aria-label="AI source details" value={input.text} maxLength={16000} onChange={e=>setInput({...input,text:e.target.value})}/></label></details>
      <div className="writing-options"><label>Intelligence<select aria-label="AI writing provider" value={provider} disabled={busy} onChange={e=>{serial.current++;controller.current?.abort();setProvider(e.target.value);setDraft(null);setText('');setSubject('');setError('');setNotice('Select Regenerate to use this provider.');}}><option value="local">Local · server drafting</option>{providers.filter(p=>p.enabled&&p.data_sharing_allowed&&p.has_key).map(p=><option key={p.provider} value={p.provider}>{p.provider==='gemini'?'Gemini':p.provider==='openai'?'OpenAI':'Claude'}</option>)}</select></label><label>Tone<select aria-label="AI draft tone" value={tone} onChange={e=>setTone(e.target.value)}><option value="professional">Professional</option><option value="friendly">Friendly</option><option value="formal">Formal</option></select></label>{action?.id==='translate'&&<label>Translate to<input aria-label="AI target language" value={language} maxLength={60} onChange={e=>setLanguage(e.target.value)}/></label>}<Button type="button" variant="outline" disabled={busy} onClick={()=>action&&void generate(action,input)}>{busy?<Loader2 className="animate-spin" size={14}/>:<Sparkles size={14}/>}Regenerate</Button></div>
      {busy&&<p role="status" className="writing-help">{notice||'Preparing your draft…'}</p>}
      {error&&<p role="alert" className="writing-error">{error}</p>}
      {draft&&<><label>Subject / title<input aria-label="AI draft subject" value={subject} onChange={e=>setSubject(e.target.value)}/></label><label>Editable draft<textarea aria-label="AI generated draft" className="writing-result" value={text} onChange={e=>setText(e.target.value)}/></label>{draft.missing_details.length>0&&<ul className="writing-missing">{draft.missing_details.map(item=><li key={item}>{item}</li>)}</ul>}<div className="writing-footer"><Button type="button" disabled={!text.trim()} onClick={apply}><Check size={14}/>Insert into editor</Button><Button type="button" variant="outline" onClick={()=>void navigator.clipboard.writeText(text).then(()=>setNotice('Draft copied.'),()=>setError('Clipboard access failed. Select and copy the draft text.'))}><Copy size={14}/>Copy draft</Button><Button type="button" variant="ghost" onClick={()=>void navigator.clipboard.writeText(subject).then(()=>setNotice('Subject copied.'),()=>setError('Clipboard access failed.'))}>Copy subject</Button></div></>}
      {!busy&&notice&&<p role="status" className="writing-help">{notice}</p>}
    </DialogContent></Dialog>
  </div>;
}

export function EditorWritingActions({text,title,onApply,disabled=false}:{text:()=>string;title?:string;onApply:(text:string)=>boolean|void;disabled?:boolean}){
  const location=useLocation(),context=pageWritingContext(pageWritingPath(location.pathname,location.search));
  const snapshot=useRef('');
  if(!context)return null;
  const actions=Array.from(new Map([...context.actions.slice(0,2),...documentActions].map(action=>[action.id,action])).values());
  return <WritingActions compact disabled={disabled} module={context.module} actions={actions} source={()=>{snapshot.current=text();return {text:snapshot.current,title:title||''};}} onApply={value=>{
    if(disabled||text()!==snapshot.current)return false;
    const result=onApply(value);snapshot.current=text();return result;
  }}/>;
}
