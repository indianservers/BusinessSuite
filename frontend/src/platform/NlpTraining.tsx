import {useEffect,useState} from 'react';
import {platformApi as api} from '@/services/platform-api';
import {Alert,message,useData,download,type Data} from './shared';

const ROOT='/platform/nlp-training';
export default function NlpTraining(){
 const result=useData<Data>(ROOT);
 const [file,setFile]=useState<File>();const [name,setName]=useState('Training commands');
 const [selected,setSelected]=useState('');const [epochs,setEpochs]=useState(220);
 const [checked,setChecked]=useState<Record<number,boolean>>({});const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');const [notice,setNotice]=useState('');
 const data=result.data;const running=(data?.jobs||[]).some((j:Data)=>['queued','training'].includes(j.status)||['queued','running'].includes(j.evaluation?.state));
 useEffect(()=>{if(!running)return;const timer=setInterval(result.refresh,3000);return()=>clearInterval(timer)},[running]);
 async function act(work:()=>Promise<unknown>,text:string){setBusy(true);setError('');setNotice('');try{await work();setNotice(text);result.refresh()}catch(e){setError(message(e))}finally{setBusy(false)}}
 return <section className="po-panel"><p className="po-muted">PLATFORM ADMINISTRATOR ONLY</p><h1>NLP training</h1>
 <p>Upload reviewed examples for CRM, PMS, Sales and HRMS. Models train and stay on the server/local machine.</p>
 <div className="po-notice">Model folder: <strong>{data?.storage||'C:\\Indian Servers\\ERPTrainedModel'}</strong>. Use synthetic or fully anonymized examples. Platform training does not import customer query histories.</div>
 <Alert error={error||result.error}/>{notice&&<p role="status" className="po-notice">{notice}</p>}
 <div className="po-actions"><button onClick={()=>void act(()=>download(ROOT+'/template','nlp-training-template.xlsx'),'Template downloaded')}>Download Excel template · 480 samples</button><button onClick={result.refresh}>Refresh</button></div>
 <h2>1. Upload Excel</h2><p>Commands sheet columns: module, query, intent, split. Choose train, validation or test. All supported labels are listed in the Intents sheet. Up to 4,000 rows per workbook.</p>
 <form className="po-form" onSubmit={e=>{e.preventDefault();if(!file)return;const form=new FormData();form.append('file',file);form.append('name',name);void act(()=>api.post(ROOT+'/datasets',form),'Workbook validated; review every row before approval')}}>
 <label>Dataset name<input required maxLength={180} value={name} onChange={e=>setName(e.target.value)}/></label>
 <label>Training Excel file<input type="file" accept=".xlsx" required onChange={e=>setFile(e.target.files?.[0])}/></label>
 <button className="po-primary" disabled={busy||!file}>Upload and validate</button></form>
 <h2>2. Review datasets</h2>{(data?.datasets||[]).filter((d:Data)=>d.status!=='deleted').map((d:Data)=><article className="po-panel" key={d.id}><strong>{d.name} · #{d.id}</strong><p>{d.counts?.total} distinct examples · {d.status} · {Object.entries(d.counts?.modules||{}).map(([k,v])=>`${k}: ${v}`).join(' / ')}</p>
 {d.status==='pending'&&<><label><input type="checkbox" checked={!!checked[d.id]} onChange={e=>setChecked({...checked,[d.id]:e.target.checked})}/> I reviewed every uploaded row and removed all customer, personal and secret data.</label><button disabled={busy||!checked[d.id]} onClick={()=>void act(()=>api.post(`${ROOT}/datasets/${d.id}/approve`,{privacy_reviewed:true}),'Dataset approved')}>Approve dataset #{d.id}</button></>}
 <button disabled={busy} onClick={()=>void act(()=>api.delete(`${ROOT}/datasets/${d.id}`),'Dataset removed from future training')}>Remove dataset #{d.id}</button></article>)}
 <h2>3. Train on server</h2><form className="po-form" onSubmit={e=>{e.preventDefault();void act(()=>api.post(ROOT+'/jobs',{dataset_id:Number(selected),epochs,request_key:crypto.randomUUID()}),'Training queued on server')}}>
 <label>Approved dataset<select required value={selected} onChange={e=>setSelected(e.target.value)}><option value="">Select approved dataset</option>{(data?.datasets||[]).filter((d:Data)=>d.status==='approved').map((d:Data)=><option key={d.id} value={d.id}>{d.name} · #{d.id}</option>)}</select></label>
 <label>Epochs<input type="number" min={50} max={400} value={epochs} onChange={e=>setEpochs(Number(e.target.value))}/></label><button className="po-primary" disabled={busy||!selected||running}>Start TensorFlow training</button></form>
 <h2>4. Evaluate candidates & release</h2><p>Active model: {data?.active_job_id?`run #${data.active_job_id}`:'authored base model'}. Training accuracy measures seen examples; frozen wording and canonical action tests are separate release checks.</p>
 <p>{data?.learning_policy}</p><p>Policy: {data?.release_policy||'action-model-release-v1'} · All gates must pass before activation. Signed artifacts are checked again when activated. Sales remains experimental.</p>
 {data?.active_integrity&&<p role={data.active_integrity==='invalid'?'alert':'status'}>Active artifact integrity: {data.active_integrity}. {data.active_integrity==='invalid'?'The runtime refuses the altered platform artifacts. Restore a verified release or the authored base model.':''}</p>}
 {(data?.jobs||[]).map((j:Data)=><article className="po-panel" key={j.id}><h3>Run #{j.id} · {j.status}</h3><p>{j.name} · {j.epochs} epochs</p>{j.error&&<Alert error={j.error}/>}<details><summary>Training and evaluation metrics</summary><pre style={{whiteSpace:'pre-wrap'}}>{j.metrics?JSON.stringify(j.metrics,null,2):''}</pre></details>
 {j.evaluation&&<p role="status">Evaluation: {j.evaluation.state}{j.evaluation.error?` · ${j.evaluation.error}`:''}</p>}
 {j.release&&<section aria-label={`Release gates for run ${j.id}`}><h4>{j.release.passed?'Release gates passed':'Release blocked'}</h4><ul>{j.release.checks.map((c:Data)=><li key={c.name}>{c.passed?'Passed':'Blocked'} · {c.name} · {typeof c.actual==='object'?JSON.stringify(c.actual):String(c.actual)} · {c.required}</li>)}</ul><p>{j.release.limitations}</p></section>}
 {j.status==='succeeded'&&<><button disabled={busy||running||(data?.active_job_id===j.id&&!!j.release)} onClick={()=>void act(()=>api.post(`${ROOT}/jobs/${j.id}/evaluate`),'Server evaluation queued; active model unchanged')}>Evaluate candidate #{j.id}</button><button disabled={busy||running||data?.active_job_id===j.id||!j.release?.passed} onClick={()=>void act(()=>api.post(`${ROOT}/jobs/${j.id}/activate`),`Run #${j.id} activated`)}>Activate model #{j.id}</button></>}</article>)}
 {data?.previous_job_id&&<button disabled={busy||running} onClick={()=>void act(()=>api.post(ROOT+'/rollback'),`Restored verified run #${data.previous_job_id}`)}>Roll back to verified model #{data.previous_job_id}</button>}
 {data?.active_job_id&&<button disabled={busy} onClick={()=>void act(()=>api.post(ROOT+'/reset'),'Authored base model restored')}>Restore authored base model</button>}
 </section>
}
