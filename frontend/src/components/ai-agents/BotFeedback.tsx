import {useEffect,useRef,useState} from 'react';
import {api} from '@/services/api';
import type {Run} from './ActionBot';

export default function BotFeedback({run,onUpdate}:{run:Run;onUpdate:(run:Run)=>void}){
 const [rating,setRating]=useState(''),[correction,setCorrection]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const live=useRef(true),pending=useRef<{signature:string;key:string}|null>(null);
 useEffect(()=>{live.current=true;return()=>{live.current=false}},[]);
 useEffect(()=>{setRating('');setCorrection('');setError('');pending.current=null},[run.id]);
 async function save(){
  const body={rating,correction,revision:run.result?.feedback?.revision||0};const signature=JSON.stringify(body);
  if(pending.current?.signature!==signature)pending.current={signature,key:crypto.randomUUID()};setBusy(true);setError('');
  try{const response=await api.post<Run>(`/ai-operator/suite/runs/${run.id}/feedback`,{...body,request_key:pending.current.key});if(live.current){onUpdate(response.data);setRating('');setCorrection('');pending.current=null}}
  catch(e:any){if(live.current)setError(typeof e.response?.data?.detail==='string'?e.response.data.detail:'Feedback could not be saved. Retry the unchanged feedback.')}
  finally{if(live.current)setBusy(false)}
 }
 return <section className="bot-result-card" aria-label="Bot feedback"><h4>Help improve the bot</h4><p>Feedback is saved privately for review. It does not change or approve actions, and is not trained automatically.</p>
  {run.result?.feedback&&<small role="status">Feedback saved · pending review</small>}
  <div className="bot-file-actions"><button type="button" disabled={busy} aria-pressed={rating==='helpful'} onClick={()=>setRating('helpful')}>Helpful</button><button type="button" disabled={busy} aria-pressed={rating==='needs_correction'} onClick={()=>setRating('needs_correction')}>Needs correction</button></div>
  {rating&&<><label>What should it understand better?<textarea aria-label="Bot feedback correction" rows={3} maxLength={2000} disabled={busy} value={correction} onChange={e=>setCorrection(e.target.value)}/></label><button type="button" className="bot-workspace-secondary" disabled={busy} onClick={()=>void save()}>Save feedback for review</button></>}
  {error&&<p role="alert">{error}</p>}
 </section>
}
