import {useEffect,useRef,useState} from 'react';
import {api} from '@/services/api';
import SlidePreview,{type ArtifactSlide} from './SlidePreview';
import {ArtifactChartConfig,type ArtifactChart} from './ArtifactCharts';

const ROOT='/ai-operator/suite/artifact-templates';
export type TemplateBody={title:string;kind:string;content:string;columns:string[];rows:string[][];slides?:ArtifactSlide[];chart?:ArtifactChart|null};
export type TemplateDefinition={name:string;body:TemplateBody;source_artifact_id?:number|null;source_revision?:number|null;template_id?:number|null;expected_revision?:number|null};
export function templateBody(item:any):TemplateBody{return {title:item.title,kind:item.kind,content:item.content||'',columns:item.columns||[],rows:item.rows||[],...(item.slides?.length?{slides:item.slides}:{}),...(item.chart?{chart:item.chart}:{})}}
function errorMessage(e:any){return typeof e.response?.data?.detail==='string'?e.response.data.detail:'Check the template fields, placeholders, size limits and your current access.'}

function BodyView({body}:{body:TemplateBody}){
 return <><h4>{body.title}</h4>{body.content&&<p className="bot-artifact-content">{body.content}</p>}{body.kind==='presentation'&&<SlidePreview slides={body.slides||[]}/>} {body.kind==='table'&&<div className="bot-file-table"><table><thead><tr>{body.columns.map((v,i)=><th key={i}>{v}</th>)}</tr></thead><tbody>{body.rows.map((row,i)=><tr key={i}>{row.map((v,j)=><td key={j}>{v}</td>)}</tr>)}</tbody></table></div>}</>
}

function BodyEditor({body,disabled=false,onChange}:{body:TemplateBody;disabled?:boolean;onChange?:(body:TemplateBody)=>void}){
 return <fieldset disabled={disabled}><legend>{body.kind} structure</legend><label>Artifact title<input aria-label="Template artifact title" maxLength={160} value={body.title} onChange={e=>onChange?.({...body,title:e.target.value})}/></label>
  {body.kind==='presentation'?<SlidePreview label="Template" slides={body.slides||[]} disabled={disabled} onChange={onChange?slides=>onChange({...body,slides}):undefined}/>:<label>Content<textarea aria-label="Template content" rows={7} maxLength={20000} value={body.content} onChange={e=>onChange?.({...body,content:e.target.value})}/></label>}
  {body.kind==='table'&&<><div className="bot-file-table"><table><thead><tr>{body.columns.map((column,i)=><th key={i}><input aria-label={`Template column ${i+1}`} maxLength={100} value={column} onChange={e=>onChange?.({...body,columns:body.columns.map((v,j)=>i===j?e.target.value:v)})}/></th>)}</tr></thead><tbody>{body.rows.map((row,i)=><tr key={i}>{row.map((cell,j)=><td key={j}><input aria-label={`Template row ${i+1} column ${j+1}`} maxLength={500} value={cell} onChange={e=>onChange?.({...body,rows:body.rows.map((r,n)=>n===i?r.map((v,k)=>k===j?e.target.value:v):r)})}/></td>)}</tr>)}</tbody></table></div>{onChange&&<button type="button" disabled={disabled||body.rows.length>=100} onClick={()=>onChange({...body,rows:[...body.rows,body.columns.map(()=> '')]})}>Add template row</button>}</>}
 {body.kind==='table'&&onChange&&<ArtifactChartConfig columns={body.columns} chart={body.chart} disabled={disabled} label="Template" onChange={chart=>onChange({...body,chart})}/>}
 </fieldset>
}

export function ArtifactTemplateEditor({initial,initialReview,onSaved,onClose}:{initial:TemplateDefinition;initialReview?:any;onSaved:()=>void;onClose:()=>void}){
 const [name,setName]=useState(initial.name),[body,setBody]=useState<TemplateBody>(()=>structuredClone(initial.body)),[review,setReview]=useState<any>(initialReview||null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const definition={...initial,name,body};const signature=JSON.stringify(definition);
 const [reviewSignature,setReviewSignature]=useState(initialReview?signature:'');const request=useRef<{signature:string;key:string}|null>(null);
 const exact=!!review&&signature===reviewSignature;
 async function preview(){setBusy(true);setError('');try{
  if(review&&signature!==reviewSignature){await api.delete(`${ROOT}/reviews/${review.id}`);setReview(null)}
  if(request.current?.signature!==signature)request.current={signature,key:crypto.randomUUID()};
  const r=await api.post(ROOT+'/preview',{...definition,request_key:request.current.key});setReview(r.data);setReviewSignature(signature)
 }catch(e){setError(errorMessage(e))}finally{setBusy(false)}}
 async function confirm(){if(!review||!exact)return;setBusy(true);setError('');try{await api.post(`${ROOT}/reviews/${review.id}/confirm`,{preview_hash:review.preview_hash});onSaved()}catch(e){setError(errorMessage(e))}finally{setBusy(false)}}
 async function close(){setBusy(true);setError('');try{if(review)await api.delete(`${ROOT}/reviews/${review.id}`);onClose()}catch(e){setError(errorMessage(e))}finally{setBusy(false)}}
 return <section className="bot-draft-step" aria-label="Artifact template editor"><h4>{initial.template_id?'Review a template update':'Save a reusable private template'}</h4><p>This copies the selected text and data. Replace changing details with placeholders such as <code>{'{{customer}}'}</code> and <code>{'{{period}}'}</code>. Citations, chat history and action permissions are excluded.</p>
  <label>Template name<input aria-label="Artifact template name" maxLength={120} disabled={busy} value={name} onChange={e=>setName(e.target.value)}/></label><BodyEditor body={body} disabled={busy} onChange={setBody}/>
  <div className="bot-file-actions"><button type="button" disabled={busy||!name.trim()} onClick={()=>void preview()}>Preview private template</button><button type="button" disabled={busy} onClick={()=>void close()}>Discard template review</button></div>
  {review&&<section aria-label="Exact artifact template review"><h4>{review.definition.name}</h4><p>Private server template · {review.module} · {review.definition.template_id?`update from revision ${review.definition.expected_revision}`:`source artifact #${review.definition.source_artifact_id}, version ${review.definition.source_revision}`}</p><p>Variables: {review.variables.join(', ')||'None'}</p><BodyView body={review.definition.body}/><p>Review expires {new Date(review.expires_at).toLocaleString()}.</p>{!exact&&<p>The form changed. Preview again before saving.</p>}<button type="button" className="action-bot-approve" disabled={busy||!exact} onClick={()=>void confirm()}>Save this exact private template</button></section>}
  {error&&<p role="alert">{error}</p>}
 </section>
}

export default function ArtifactTemplates({module,workspaceId,refresh,onUse}:{module:string;workspaceId?:number;refresh?:string;onUse:(id:number,revision:number)=>void}){
 const [items,setItems]=useState<any[]>([]),[reviews,setReviews]=useState<any[]>([]),[editor,setEditor]=useState<{initial:TemplateDefinition;review?:any;key:string}|null>(null),[history,setHistory]=useState<{id:number;items:any[]}|null>(null),[historical,setHistorical]=useState<any>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function load(){const [a,r]=await Promise.all([api.get(ROOT,{params:{module,workspace_id:workspaceId}}),api.get(ROOT+'/reviews',{params:{module,workspace_id:workspaceId}})]);setItems(a.data.items||[]);setReviews(r.data.items||[])}
 useEffect(()=>{void load().catch(e=>setError(errorMessage(e)))},[module,workspaceId,refresh]);
 async function edit(id:number){setBusy(true);setError('');try{const {data}=await api.get(`${ROOT}/${id}`);setEditor({key:`template-${id}-${data.revision}`,initial:{name:data.name,body:data.body,template_id:id,expected_revision:data.current_revision}});setHistorical(null)}catch(e){setError(errorMessage(e))}finally{setBusy(false)}}
 async function versions(id:number){setBusy(true);setError('');try{const {data}=await api.get(`${ROOT}/${id}/versions`);setHistory({id,items:data.items||[]});setHistorical(null)}catch(e){setError(errorMessage(e))}finally{setBusy(false)}}
 async function view(id:number,revision:number){setBusy(true);setError('');try{const {data}=await api.get(`${ROOT}/${id}`,{params:{revision}});setHistorical(data)}catch(e){setError(errorMessage(e))}finally{setBusy(false)}}
 async function archive(id:number){setBusy(true);setError('');try{await api.delete(`${ROOT}/${id}`);setHistory(null);setHistorical(null);await load()}catch(e){setError(errorMessage(e))}finally{setBusy(false)}}
 return <section aria-label="Private artifact templates"><h3>Reusable artifact templates</h3><p>Save a template from an artifact’s version view. Reuse asks for missing values and prepares a separate artifact for review. Say <q>Use template &quot;Monthly customer report&quot;</q> or choose a template below. Updating or archiving a template blocks pending work based on its older definition; saved artifact copies remain independent.</p>
  {reviews.map(r=><article className="bot-result-card" key={r.id}><h4>Pending review: {r.definition.name}</h4><button type="button" disabled={busy||!!editor} onClick={()=>setEditor({key:`review-${r.id}`,initial:r.definition,review:r})}>Resume template review #{r.id}</button></article>)}
  {items.map(item=><article className="bot-result-card" key={item.id}><h4>{item.name}</h4><p>{item.module} · revision {item.revision} · variables: {item.variables.join(', ')||'None'}</p><div className="bot-file-actions"><button type="button" disabled={busy||!!editor} onClick={()=>onUse(item.id,item.revision)}>Use template #{item.id}</button><button type="button" disabled={busy||!!editor} onClick={()=>void edit(item.id)}>Edit template #{item.id}</button><button type="button" disabled={busy} onClick={()=>void versions(item.id)}>Template #{item.id} versions</button><button type="button" disabled={busy||!!editor} onClick={()=>void archive(item.id)}>Archive template #{item.id}</button></div></article>)}
  {editor&&<ArtifactTemplateEditor key={editor.key} initial={editor.initial} initialReview={editor.review} onSaved={()=>{setEditor(null);void load().catch(e=>setError(errorMessage(e)))}} onClose={()=>{setEditor(null);void load().catch(e=>setError(errorMessage(e)))}}/>}
  {history&&<section aria-label="Artifact template versions"><h4>Template #{history.id} history</h4>{history.items.map(v=><button type="button" disabled={busy} key={v.revision} onClick={()=>void view(history.id,v.revision)}>View template #{history.id} revision {v.revision}</button>)}</section>}
  {historical&&<section aria-label="Historical artifact template"><h4>{historical.name} · revision {historical.revision}</h4><BodyView body={historical.body}/></section>}
  {!items.length&&!reviews.length&&<p>No private artifact templates saved in this module and workspace.</p>}{error&&<p role="alert">{error}</p>}
 </section>
}
