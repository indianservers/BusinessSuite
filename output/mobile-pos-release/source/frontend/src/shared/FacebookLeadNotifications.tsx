import {useState} from 'react';
import {api} from '@/services/api';
import {Button} from '@/components/ui/button';
import {Input} from '@/components/ui/input';
import {message} from '@/apps/power-apps/applications/integrations/integrationApi';

export default function FacebookLeadNotifications({job,environment,onSaved}:{
  job:{id:number;version:number;automatic:boolean;notification_url?:string};environment:string;onSaved:()=>Promise<unknown>;
}){
  const [pageId,setPageId]=useState(''),[secret,setSecret]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [result,setResult]=useState<{callback_url:string;verify_token:string;instructions:string}>();
  async function configure(){
    setBusy(true);setError('');
    try{
      const {data}=await api.post(`/power-apps/integrations/sync/jobs/${job.id}/facebook-hook`,{
        expected_version:job.version,page_id:pageId,app_secret:secret,
      },{params:{environment}});
      setResult(data);setSecret('');await onSaved();
    }catch(e){setError(message(e));}finally{setBusy(false);}
  }
  async function disable(){
    setBusy(true);setError('');
    try{await api.delete(`/power-apps/integrations/sync/jobs/${job.id}/facebook-hook`,{
      params:{environment,expected_version:job.version},
    });setResult(undefined);await onSaved();}catch(e){setError(message(e));}finally{setBusy(false);}
  }
  return <details className="rounded border p-3"><summary className="cursor-pointer font-medium">Facebook instant notifications</summary>
    <div className="space-y-3 pt-3">
      <p>Signed notifications wake the sync worker when this form receives a lead. Scheduled polling also recovers missed notifications.</p>
      {!job.automatic&&<p>Enable automatic sync before configuring notifications.</p>}
      {job.notification_url&&<><label>Current callback URL<Input readOnly value={job.notification_url}/></label><Button variant="outline" disabled={busy} onClick={()=>void disable()}>Disable notifications</Button></>}
      <label>Facebook Page ID<Input value={pageId} onChange={e=>setPageId(e.target.value)} disabled={busy}/></label>
      <label>Meta app secret<Input type="password" autoComplete="new-password" value={secret} onChange={e=>setSecret(e.target.value)} disabled={busy}/></label>
      <Button disabled={busy||!job.automatic||!/^\d{1,40}$/.test(pageId)||secret.length<16} onClick={()=>void configure()}>{job.notification_url?'Rotate notification credentials':'Configure notifications'}</Button>
      {error&&<p role="alert">{error}</p>}
      {result&&<section className="space-y-2" aria-label="Facebook webhook setup">
        <label>Callback URL<Input readOnly value={result.callback_url}/></label>
        <label>Verify token — copy now; shown only in this session<Input readOnly value={result.verify_token}/></label>
        <p>{result.instructions}</p>
      </section>}
    </div>
  </details>;
}
