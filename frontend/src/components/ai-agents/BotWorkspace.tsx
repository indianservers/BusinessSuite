import {useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {Download,FileText,Paperclip,Trash2} from 'lucide-react';
import type {Run} from './ActionBot';
import BotFeedback from './BotFeedback';
import BotArtifacts,{ArtifactView} from './BotArtifacts';
import SavedAgents from './SavedAgents';
import AgentSchedules from './AgentSchedules';
import AgentWorkflows from './AgentWorkflows';
import SkillLibrary from './SkillLibrary';
import {WorkspaceChats,WorkspaceTools,WorkspaceConnections,WorkspaceKnowledge,WorkspaceActivity} from './WorkspacePanels';

export type BotAttachment={id:number;name:string;size:number;format:string;preview:string[][];row_count:number;notes:string[];excerpt:string};
export type DraftChange={step:number;field:string;value:unknown};
const fields=new Set(['title','name','subject','description','priority','due_date','start_date','owner_user_id','assignee_user_id','reason','from_date','to_date','content']);
const editableTools=new Set(['crm.create_task','crm.update_task','pms.create_task','pms.create_project','pms.create_milestone','hrms.create_ticket','hrms.request_leave']);

export default function BotWorkspace({module,workspaceId,projectId,conversationId,conversations,onUseAgent,onOpenConversation,onEditArtifact,run,attachments,selected,busy,openFilesRequest,onUpdate,onSelect,onRevise,onDirty,onUpload,onDelete,onDownload,onPrepare}:{module?:string;workspaceId?:number;projectId?:number;conversationId?:number|null;conversations:{id:number;title:string}[];onUseAgent:(id:number)=>void;onOpenConversation:(id:number)=>void;onEditArtifact:(id:number)=>void;run:Run|null;attachments:BotAttachment[];selected:number[];busy:boolean;openFilesRequest:number;onUpdate:(run:Run)=>void;onSelect:(id:number)=>void;onRevise:(changes:DraftChange[])=>Promise<boolean>;onDirty:(dirty:boolean)=>void;onUpload:(files:FileList|null)=>void;onDelete:(id:number)=>void;onDownload:(file:BotAttachment)=>void;onPrepare:(id:number)=>void}){
 const [tab,setTab]=useState<'results'|'review'|'files'|'artifacts'|'agents'|'schedules'|'workflows'|'chats'|'skills'|'tools'|'connections'|'knowledge'|'activity'>('results');
 const [fileFocus,setFileFocus]=useState<number|null>(null);
 const [edits,setEdits]=useState<Record<string,string>>({});
 const dirty=Object.keys(edits).length>0;
 useEffect(()=>{setEdits({});onDirty(false)},[run?.id]);
 useEffect(()=>{onDirty(dirty)},[dirty]);
 useEffect(()=>{if(openFilesRequest)setTab('files')},[openFilesRequest]);
 useEffect(()=>{if(tab==='files'&&fileFocus){const frame=requestAnimationFrame(()=>document.getElementById(`bot-attachment-${fileFocus}`)?.scrollIntoView({block:'nearest'}));return()=>cancelAnimationFrame(frame)}},[tab,fileFocus]);
 const canEdit=run?.status==='awaiting_approval';
 const artifactTools=new Set(['crm','pms','hrms'].flatMap(m=>[m+'.create_artifact',m+'.edit_artifact']));
 function edit(key:string,value:string){setEdits(old=>({...old,[key]:value}));onDirty(true)}
 async function save(){
  const changes=Object.entries(edits).map(([key,value])=>{const [step,field]=key.split(':');const original=run?.plan?.steps[Number(step)-1].payload[field];return {step:Number(step),field,value:typeof original==='number'||field.endsWith('_user_id')?value?Number(value):null:field.endsWith('_date')&&!value?null:value}});
  if(await onRevise(changes)){setEdits({});onDirty(false)}
 }
 return <aside className="bot-workspace" aria-label="Bot workspace">
  <div className="bot-workspace-tabs" role="tablist" aria-label="Workspace views">{(['results','review','files','artifacts','chats','agents','skills','tools','connections','knowledge','schedules','workflows','activity'] as const).map(value=><button type="button" key={value} role="tab" aria-selected={tab===value} disabled={dirty&&tab!==value} onClick={()=>setTab(value)}>{value==='results'?'Results':value==='review'?'Review & edit':value==='artifacts'?'Artifacts':value==='agents'?'Agents':value==='schedules'?'Schedules':value==='workflows'?'Workflows':value==='chats'?'Chats':value==='skills'?'Skills':value==='tools'?'Tools':value==='connections'?'Connections':value==='knowledge'?'Knowledge':value==='activity'?'Activity':`Files (${attachments.length})`}</button>)}</div>
  <div className="bot-workspace-content" role="tabpanel" aria-label={tab}>
   {tab==='results'&&<>
    <h3>Work in progress & results</h3>
    {run?.workflow_steps?.length?<ol className="bot-workspace-progress" aria-label="Workspace workflow steps">{run.workflow_steps.map(step=><li key={step.step}><div><strong>{step.step}. {step.tool.replace(/[._]/g,' ')}</strong><span>{step.status.replace(/_/g,' ')}</span></div><small>{step.depends_on.length?`After step ${step.depends_on.join(', ')}`:'Ready first'}{step.attempts?` · ${step.attempts} attempts`:''}</small></li>)}</ol>:null}
    {(run?.result as any)?.artifact_context?.id&&!run?.receipts?.some(r=>r.artifact_id===(run.result as any).artifact_context.id)&&<ArtifactView key={`${run?.id}-context`} id={(run?.result as any).artifact_context.id} onEdit={onEditArtifact}/>}
    {run?.receipts?.filter(r=>r.artifact_id).map(r=><ArtifactView key={`${r.artifact_id}:${r.artifact_revision}`} id={r.artifact_id!} onEdit={onEditArtifact}/>)}
    {run?.result_cards?.filter(card=>!card.artifact_id).map(card=><article className="bot-result-card" key={card.id}><small>{card.kind==='draft'?'Proposed action':card.kind==='record'?'Execution receipt':'Answer'} · {card.status.replace(/_/g,' ')}</small><h4>{card.title}</h4>{card.body&&<p>{card.body}</p>}{card.record_id&&<p>Record #{card.record_id}</p>}{card.href&&<Link to={card.href}>Open record in module</Link>}</article>)}
    {run&&['answered','succeeded','failed','paused','awaiting_approval','needs_clarification'].includes(run.status)&&<BotFeedback key={run.id} run={run} onUpdate={onUpdate}/>}
    {!run&&<p>Ask the bot for a report or an action. Its progress and results will appear here.</p>}
    {!!run?.plan?.steps.length&&canEdit&&<button type="button" className="bot-workspace-secondary" onClick={()=>setTab('review')}>Review and edit draft</button>}
   </>}
   {tab==='review'&&<>
    <h3>Review the exact changes</h3><p>Saving edits creates a new server draft. Approval remains a separate step.</p>
    {run?.plan?.steps.map((step,index)=><fieldset key={`${run.id}-${index}`} className="bot-draft-step"><legend>{index+1}. {step.tool.replace(/[._]/g,' ')}</legend>{Object.entries(step.payload).filter(([key])=>!['preview_token','request_id','request_key'].includes(key)).map(([field,value])=>{
     const key=`${index+1}:${field}`;const editing=canEdit&&(editableTools.has(step.tool)||artifactTools.has(step.tool))&&fields.has(field)&&(typeof value==='string'||typeof value==='number'||value==null);
     return <label key={field}><span>{field.replace(/_/g,' ')}</span>{editing?(field==='content'?<textarea aria-label={`Step ${index+1} ${field}`} disabled={busy} rows={10} maxLength={20000} value={edits[key]??String(value??'')} onChange={e=>edit(key,e.target.value)}/>:field==='priority'?<select aria-label={`Step ${index+1} ${field}`} disabled={busy} value={edits[key]??String(value??'')} onChange={e=>edit(key,e.target.value)}>{['Low','Medium','High','Urgent','Critical'].map(v=><option key={v}>{v}</option>)}</select>:<input aria-label={`Step ${index+1} ${field}`} disabled={busy} type={typeof value==='number'||field.endsWith('_user_id')?'number':'text'} maxLength={field==='content'?20000:field==='description'?8000:1000} value={edits[key]??String(value??'')} onChange={e=>edit(key,e.target.value)}/>):<p>{typeof value==='object'?JSON.stringify(value):String(value)}</p>}</label>
    })}{canEdit&&editableTools.has(step.tool)&&!('priority' in step.payload)&&['crm.create_task','crm.update_task','pms.create_task','hrms.create_ticket'].includes(step.tool)&&<label><span>priority</span><select aria-label={`Step ${index+1} priority`} disabled={busy} value={edits[`${index+1}:priority`]||'Medium'} onChange={e=>edit(`${index+1}:priority`,e.target.value)}>{['Low','Medium','High'].map(v=><option key={v}>{v}</option>)}</select></label>}{canEdit&&editableTools.has(step.tool)&&!('due_date' in step.payload)&&['crm.create_task','crm.update_task','pms.create_task'].includes(step.tool)&&<label><span>due date</span><input aria-label={`Step ${index+1} due_date`} placeholder="YYYY-MM-DD" disabled={busy} value={edits[`${index+1}:due_date`]||''} onChange={e=>edit(`${index+1}:due_date`,e.target.value)}/></label>}</fieldset>)}
    {dirty&&<div className="bot-draft-actions"><button type="button" className="action-bot-approve" disabled={busy} onClick={()=>void save()}>Save edits for new review</button><button type="button" disabled={busy} onClick={()=>{setEdits({});onDirty(false)}}>Discard unsaved edits</button></div>}
    {!run?.plan?.steps.length&&<p>No action draft is awaiting review.</p>}
   </>}
   {tab==='chats'&&<WorkspaceChats items={conversations} onOpen={onOpenConversation}/>}
   {tab==='skills'&&<SkillLibrary workspaceId={workspaceId}/>}
   {tab==='tools'&&<WorkspaceTools module={module}/>}
   {tab==='connections'&&<WorkspaceConnections/>}
   {tab==='knowledge'&&<WorkspaceKnowledge conversationId={conversationId} module={module} workspaceId={workspaceId} projectId={projectId} onShowFiles={id=>{setFileFocus(id||null);setTab('files')}}/>}
   {tab==='activity'&&<WorkspaceActivity workspaceId={workspaceId} onOpen={onOpenConversation}/>}
   {tab==='workflows'&&<AgentWorkflows workspaceId={workspaceId} onOpenConversation={onOpenConversation}/>}
   {tab==='schedules'&&<AgentSchedules workspaceId={workspaceId} onOpenConversation={onOpenConversation}/>}
   {tab==='agents'&&<SavedAgents module={module} workspaceId={workspaceId} projectId={projectId} onUse={onUseAgent}/>}
   {tab==='artifacts'&&<BotArtifacts key={`${module}:${workspaceId}`} module={module} workspaceId={workspaceId} refresh={`${run?.id}:${run?.status}`} onEdit={onEditArtifact}/>}
   {tab==='files'&&<>
    <h3>Conversation files</h3><p>Stored and parsed on the server. Uploading does not execute actions. Selected files accompany your next request; connected providers receive redacted context only when selected.</p>
    <label className="bot-upload"><Paperclip size={16}/>Upload Excel or document<input aria-label="Upload bot files" type="file" multiple accept=".xlsx,.csv,.txt,.docx,.pdf" disabled={busy} onChange={e=>{onUpload(e.target.files);e.target.value=''}}/></label><small>Up to 5 MB per file · XLSX, CSV, TXT, DOCX, text PDF</small>
    {attachments.map(file=><article id={`bot-attachment-${file.id}`} className="bot-file-card" key={file.id}><header><FileText size={18}/><strong>{file.name}</strong><label><input type="checkbox" aria-label={`Use ${file.name} in next request`} checked={selected.includes(file.id)} disabled={busy} onChange={()=>onSelect(file.id)}/>Use as context</label><span>{Math.ceil(file.size/1024)} KB</span></header>{file.preview.length?<div className="bot-file-table"><table><tbody>{file.preview.map((row,i)=><tr key={i}>{row.map((cell,j)=>i===0?<th key={j}>{cell}</th>:<td key={j}>{cell}</td>)}</tr>)}</tbody></table></div>:<p>{file.excerpt}</p>}{file.notes.map(note=><p className="bot-file-note" key={note}>{note}</p>)}<div className="bot-file-actions"><button type="button" disabled={busy} onClick={()=>onDownload(file)}><Download size={13}/>Download</button><button type="button" disabled={busy} onClick={()=>onDelete(file.id)}><Trash2 size={13}/>Remove</button>{['.xlsx','.csv'].includes(file.format)&&<button type="button" disabled={busy} onClick={()=>onPrepare(file.id)}>Prepare reviewed actions</button>}</div></article>)}
    {!attachments.length&&<p>Attach a file to give this conversation private source context. Table drafts use module and title columns, with optional project_id, priority, due_date and description.</p>}
   </>}
  </div>
 </aside>
}
