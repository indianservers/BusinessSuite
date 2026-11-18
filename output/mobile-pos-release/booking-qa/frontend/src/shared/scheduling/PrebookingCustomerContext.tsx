import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { useRecordScope } from '@/lib/record-scope';
import { useEffect, useState } from 'react';
import AppointmentVisitPanel from '@/apps/srm/industry/AppointmentVisitPanel';
import { Button } from '@/components/ui/button';

type Visit={id:number;status:string;data:{starts_at:string;service_name?:string}};
export default function PrebookingCustomerContext({customerId,serviceId,startsAt,onRepeat,timezone='UTC',onUseProvider}:{timezone?:string;onUseProvider?:(id:number)=>void;customerId:number;serviceId?:number;startsAt?:string;onRepeat:(id:number)=>void}) {
  const [inspecting,setInspecting]=useState<number>();
  const [inspectionVersion,setInspectionVersion]=useState(0);
  useEffect(()=>setInspecting(undefined),[customerId,serviceId]);
  const scope=useRecordScope();
  const query=useQuery({queryKey:['prebooking-customer-context',scope,customerId,serviceId,startsAt],enabled:customerId>0,retry:false,
    queryFn:({signal})=>api.get<{recent:Visit[];upcoming:Visit[];possible_duplicates:Visit[];preferred_provider:{name:string;employee_id:number}|null}>(`/srm/industry/appointments/customer-context/${customerId}`,{signal,recordCache:false,params:{service_id:serviceId||undefined,starts_at:startsAt||undefined}}).then(r=>r.data)});
  const detail=useQuery({queryKey:['prebooking-duplicate-detail',scope,inspecting],enabled:!!inspecting,retry:false,queryFn:()=>api.get(`/srm/industry/appointments/${inspecting}`,{recordCache:false}).then(r=>r.data)});
  if(!customerId)return null;
  return <section className="prebooking-customer-context" aria-label="Customer booking context">
    {!!query.data?.possible_duplicates?.length && <p role="alert">Possible duplicate: this customer already has {query.data.possible_duplicates.length} active booking(s) for this service{startsAt?' within 2 hours of this time':''}. Review before confirming; repeat bookings are allowed.</p>}
    {!!query.data?.possible_duplicates?.length && <div>{query.data.possible_duplicates.map(v=><Button type="button" variant="outline" key={v.id} onClick={()=>{setInspectionVersion(n=>n+1);setInspecting(v.id);}}>Inspect booking #{v.id}</Button>)}{inspecting && (detail.isPending?<p role="status">Loading booking…</p>:detail.isError?<p role="alert">Booking could not load. <button type="button" onClick={()=>void detail.refetch()}>Retry booking</button></p>:<AppointmentVisitPanel key={`${inspecting}:${inspectionVersion}`} row={detail.data} timezone={timezone} onClosed={()=>setInspecting(undefined)} defaultOpen canViewBilling={false} canCollect={false} canInvoice={false} canApprove={false} onChanged={()=>void query.refetch()}/>)}</div>}
    <details><summary>Customer visits and preferences</summary>{query.isPending?<p role="status">Loading permitted visits…</p>:query.isError?<p role="alert">Customer history could not load. <Button type="button" variant="outline" onClick={()=>void query.refetch()}>Retry customer visits</Button></p>:<>
      {query.data?.preferred_provider && <p>Suggested provider from recent visits: {query.data.preferred_provider.name} {onUseProvider && <Button type="button" variant="outline" onClick={()=>onUseProvider(query.data!.preferred_provider!.employee_id)}>Use suggested provider</Button>}</p>}
      <strong>Upcoming visits</strong>{query.data?.upcoming?.length?query.data.upcoming.map(v=><p key={v.id}>#{v.id} · {v.data.service_name} · {new Date(v.data.starts_at).toLocaleString(undefined,{timeZone:timezone})} ({timezone})</p>):<p>No upcoming visits in this branch.</p>}
      <strong>Recent visits</strong>{query.data?.recent?.length?query.data.recent.map(v=><div key={v.id}>#{v.id} · {v.data.service_name} · {new Date(v.data.starts_at).toLocaleDateString(undefined,{timeZone:timezone})} ({timezone}) <Button type="button" variant="ghost" onClick={()=>onRepeat(v.id)}>Repeat appointment #{v.id}</Button></div>):<p>No recent visits in this branch.</p>}
    </>}</details>
  </section>;
}
