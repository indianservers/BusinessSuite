import {useRef,useState} from 'react';
import {api} from '@/services/api';
import ToolCallPreview from './ToolCallPreview';

export default function SkillTestPanel({skill}:{skill:any}){
 const [text,setText]=useState(''),[provider,setProvider]=useState('local'),[busy,setBusy]=useState(false),[error,setError]=useState(''),[result,setResult]=useState<any>(null),[conversation,setConversation]=useState<number|null>(null);
 const pending=useRef<{signature:string;key:string;conversation?:number}|null>(null);
 async function prepare(){setBusy(true);setError('');try{
  const signature=JSON.stringify({text,provider,id:skill.id,revision:skill.revision,workspace_id:skill.workspace_id});
  if(pending.current?.signature!==signature)pending.current={signature,key:crypto.randomUUID()};
  const attempt=pending.current;
  if(!attempt.conversation){const c=await api.post('/ai-operator/suite/conversations',{title:`Skill test: ${skill.name}`.slice(0,160),workspace_id:skill.workspace_id||null});attempt.conversation=c.data.id}
  setConversation(attempt.conversation!);
  const r=await api.post('/ai-operator/suite/commands',{request_key:attempt.key,text,provider,conversation_id:attempt.conversation,workspace_id:skill.workspace_id||null,test_skill_id:skill.id,test_skill_revision:skill.revision,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone||'Asia/Kolkata'},{timeout:150000});setResult(r.data);
 }catch(e:any){setError(typeof e.response?.data?.detail==='string'?e.response.data.detail:'Could not prepare the test. Your message is preserved; retry with the same settings.')}finally{setBusy(false)}}
 return <section className="bot-result-card" aria-label="Skill testing"><h4>Test {skill.name} · revision {skill.revision}</h4><p>Uses authorized live reads. Writes remain drafts and cannot be approved in this test conversation. Inspect the answer, sources, questions and proposed actions; no automatic quality score is assigned.</p>
 <label>Sample message<textarea aria-label="Skill test message" rows={3} maxLength={6000} disabled={busy} value={text} onChange={e=>setText(e.target.value)}/></label>
 <label>Test intelligence<select aria-label="Skill test intelligence" disabled={busy} value={provider} onChange={e=>setProvider(e.target.value)}>{['local','preferred','gemini','openai','claude'].map(p=><option key={p} value={p}>{p==='local'?'Server local':p==='preferred'?'Server default':p}</option>)}</select></label>
 <button type="button" disabled={busy||!text.trim()} onClick={()=>void prepare()}>{busy?'Preparing test…':'Prepare skill test'}</button>
 {result&&<article aria-label="Skill test result"><p>Run #{result.id} · {result.status} · Skill revision {skill.revision}</p><p>{result.plan?.summary}</p>{result.plan?.question&&<p>{result.plan.question}</p>}<ToolCallPreview toolCalls={(result.plan?.steps||[]).map((step:any)=>({...step,name:step.tool}))}/><p>Proposals shown here have not been executed.</p></article>}
 {conversation&&<a href={`/?bot_conversation=${conversation}${skill.workspace_id?'&workspace='+skill.workspace_id:''}`}>Open test conversation and follow up</a>}{error&&<p role="alert">{error}</p>}</section>
}
