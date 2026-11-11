import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {Link} from 'react-router-dom';
import {api} from '@/services/api';
import {Button} from '@/components/ui/button';
import {Input} from '@/components/ui/input';
import {useRecordScope} from '@/shared/records/Record360Workspace';
import {message} from '@/apps/power-apps/applications/integrations/integrationApi';

type Form={id:number;version:number;name:string;enabled:boolean;callback_url:string;received:number;last_test_at?:string;
  recent:{id:number;state:string;batch_id?:string;last_error?:string}[]};
export default function GoogleLeadForms(){
  const scope=useRecordScope();
  return <GoogleFormContent key={scope} scope={scope}/>;
}
function GoogleFormContent({scope}:{scope:string}){
  const [name,setName]=useState(''),[formId,setFormId]=useState(''),[country,setCountry]=useState(''),[automatic,setAutomatic]=useState(false);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[created,setCreated]=useState<{callback_url:string;google_key:string}>();
  const root='/power-apps/integrations/sync/lead-forms';
  const query=useQuery({queryKey:['google-lead-forms',scope],queryFn:async()=>(await api.get<{items:Form[]}>(root)).data.items,refetchInterval:30000});
  async function act(fn:()=>Promise<void>){setBusy(true);setError('');try{await fn();await query.refetch();}catch(e){setError(message(e));}finally{setBusy(false);}}
  return <details className="rounded-lg border p-4"><summary className="cursor-pointer font-semibold">Google Ads lead forms</summary>
    <div className="space-y-4 pt-4"><p>Receive Google form submissions in this CRM branch. The worker stages each lead in the import workspace and can import valid new leads automatically.</p>
      <label>Connection name<Input value={name} onChange={e=>setName(e.target.value)}/></label>
      <label>Google Ads form ID<Input value={formId} onChange={e=>setFormId(e.target.value)}/></label>
      <label>Calling code for national phone numbers (optional, for example +91)<Input value={country} onChange={e=>setCountry(e.target.value)}/></label>
      <label className="block"><input type="checkbox" checked={automatic} onChange={e=>setAutomatic(e.target.checked)}/> Automatically import valid new leads; review errors separately</label>
      <Button disabled={busy||!name.trim()||!/^\d{1,40}$/.test(formId)} onClick={()=>void act(async()=>{
        const {data}=await api.post(root,{name,form_id:formId,phone_country_code:country,apply_new_records:automatic});setCreated(data);setName('');setFormId('');
      })}>Create Google lead connection</Button>
      {created&&<section className="space-y-2" aria-label="Google lead form setup"><label>Webhook URL<Input readOnly value={created.callback_url}/></label>
        <label>Google key — copy now; shown only in this session<Input readOnly value={created.google_key}/></label>
        <p>Paste the URL and key into the Google Ads form’s webhook integration. Send test data to verify the connection. Test submissions are acknowledged without creating CRM leads.</p></section>}
      {error&&<p role="alert">{error}</p>}{query.isError&&<p role="alert">{message(query.error)}</p>}
      <Button variant="outline" disabled={busy||query.isFetching} onClick={()=>void query.refetch()}>Refresh Google lead connections</Button>
      {query.data?.map(form=><article key={form.id} className="rounded border p-3 space-y-2"><h3 className="font-semibold">{form.name}</h3>
        <p>{form.enabled?'Enabled':'Paused'} · {form.received} submissions{form.last_test_at?` · Test received ${new Date(form.last_test_at).toLocaleString()}`:''}</p>
        <label>Webhook URL<Input readOnly value={form.callback_url}/></label>
        <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy} onClick={()=>void act(async()=>{await api.put(root+'/'+form.id,{expected_version:form.version,enabled:!form.enabled});})}>{form.enabled?'Pause':'Resume'}</Button>
          <Button variant="outline" disabled={busy||!form.enabled} onClick={()=>void act(async()=>{await api.post(root+'/'+form.id+'/retry');})}>Retry submissions needing attention</Button></div>
        {form.recent.map(item=><p key={item.id}>{item.state}{item.batch_id&&<> · <Link className="underline" to={`/crm/import-data?batch=${item.batch_id}`}>Review import</Link></>}{item.last_error&&<span role="alert"> · {item.last_error}</span>}</p>)}
      </article>)}
    </div>
  </details>;
}
