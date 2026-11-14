import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { useRecordScope } from '@/shared/records/Record360Workspace';
import { NativeSelect } from '@/components/ui/native-select';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

type Person={id:number;name:string;email:string};
type Choices={users:Person[];roles:{id:number;name:string}[];selected_user:Person|null;has_more:boolean};
export default function ApprovalTargetPicker({kind,value,onChange,label,disabled=false}:{kind:'Role'|'User';value:string;onChange:(value:string)=>void;label:string;disabled?:boolean}){
  const scope=useRecordScope(),[search,setSearch]=useState(''),[page,setPage]=useState(1);
  const selectedUser=kind==='User'&&value?Number(value):undefined;
  const query=useQuery({queryKey:['workflow-approval-targets',scope,search,page,selectedUser],queryFn:()=>api.get<Choices>('/workflow-engine/approval-targets',{params:{search,page,selected_user:selectedUser}}).then(r=>r.data),retry:false});
  const users=[...(query.data?.users||[])];
  if(query.data?.selected_user&&!users.some(user=>user.id===query.data!.selected_user!.id))users.unshift(query.data.selected_user);
  const options=kind==='Role'?(query.data?.roles||[]).map(role=>({value:role.name,label:role.name})):users.map(user=>({value:String(user.id),label:`${user.name} · ${user.email}`}));
  return <div className="min-w-0 space-y-2">
    {kind==='User'&&<Input aria-label={`Find ${label}`} placeholder="Name or email" maxLength={100} disabled={disabled} value={search} onChange={e=>{setSearch(e.target.value);setPage(1);}}/>}
    <NativeSelect aria-label={label} value={value} disabled={disabled||query.isPending||query.isError} onChange={e=>onChange(e.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
      <option value="">{kind==='Role'?'Choose role':'Choose person'}</option>
      {value&&!options.some(option=>option.value===value)&&<option value={value}>Selection unavailable</option>}
      {options.map(option=><option key={option.value} value={option.value}>{option.label}</option>)}
    </NativeSelect>
    {query.isError&&<p role="alert">Choices could not load. <Button type="button" variant="outline" disabled={disabled} onClick={()=>void query.refetch()}>Retry {label}</Button></p>}
    {kind==='User'&&<div className="flex flex-wrap gap-2"><Button type="button" variant="outline" disabled={disabled||page===1||query.isFetching} onClick={()=>setPage(p=>p-1)}>Previous {label}</Button><Button type="button" variant="outline" disabled={disabled||!query.data?.has_more||query.isFetching} onClick={()=>setPage(p=>p+1)}>More {label}</Button></div>}
  </div>;
}
