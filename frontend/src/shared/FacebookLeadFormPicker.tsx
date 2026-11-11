import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {Button} from '@/components/ui/button';
import {Input} from '@/components/ui/input';
import {NativeSelect} from '@/components/ui/native-select';
import {integrationApi,message} from '@/apps/power-apps/applications/integrations/integrationApi';

type Forms = {data?:{id:string;name?:string;status?:string}[];paging?:{next?:string}};
export default function FacebookLeadFormPicker({connectionId,environment,scope,value,onChange,disabled}:{
  connectionId:number;environment:string;scope:string;value:string;onChange:(id:string)=>void;disabled:boolean;
}) {
  const [page,setPage]=useState('');
  const [selectedPage,setSelectedPage]=useState('');
  const forms=useQuery({
    queryKey:['facebook-lead-forms',scope,environment,connectionId,selectedPage],
    enabled:!!selectedPage,
    retry:false,
    queryFn:async()=>{
      const result=await integrationApi.execute(environment,{connection_id:connectionId,action_id:'list_forms',
        input:{page_id:selectedPage},confirm_side_effect:false,request_id:crypto.randomUUID()});
      const data=result.data as Forms;
      if(!data||!Array.isArray(data.data)||data.data.some(f=>!f||typeof f.id!=='string')) throw new Error('Invalid form collection');
      return data;
    },
  });
  return <div className="space-y-2">
    <p>Select a Facebook form using an authorized Page token. After creating an automatic sync job, configure instant notifications below. Scheduled polling also recovers missed notifications.</p>
    <label>Facebook Page ID<Input value={page} onChange={e=>setPage(e.target.value)} disabled={disabled}/></label>
    <Button variant="outline" disabled={disabled||!page.trim()||forms.isFetching} onClick={()=>{
      if(page.trim()===selectedPage) void forms.refetch(); else setSelectedPage(page.trim());
    }}>Load Page forms</Button>
    {forms.isFetching&&<p role="status">Loading forms…</p>}
    {forms.isError&&<p role="alert">Could not load forms. {message(forms.error)} Verify the Page ID and lead access, or enter the form ID below.</p>}
    {forms.data&&<label>Available lead forms<NativeSelect aria-label="Facebook lead form" value={value} disabled={disabled} onChange={e=>onChange(e.target.value)}>
      <option value="">Choose a form</option>{forms.data.data?.map(f=><option key={f.id} value={f.id}>{f.name||f.id}{f.status?' · '+f.status:''}</option>)}
    </NativeSelect></label>}
    {forms.data?.data?.length===0&&<p>No forms were returned for this Page. Check access or enter a form ID below.</p>}
    {forms.data?.paging?.next&&<p>Showing the first 100 forms. For other forms, enter the form ID below.</p>}
    <label>Lead form ID<Input value={value} onChange={e=>onChange(e.target.value)} disabled={disabled}/></label>
  </div>;
}
