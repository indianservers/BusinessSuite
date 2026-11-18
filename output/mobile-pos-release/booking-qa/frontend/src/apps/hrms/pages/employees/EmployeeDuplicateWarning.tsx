import {useEffect,useState} from "react";
import {useQuery} from "@tanstack/react-query";
import {Link} from "react-router-dom";
import {api} from "@/services/api";
export default function EmployeeDuplicateWarning({values,excludeId,acknowledged,onAcknowledge}:{values:Record<string,unknown>;excludeId?:number;acknowledged:boolean;onAcknowledge:(value:boolean)=>void}) {
 const signature=JSON.stringify({...values,exclude_id:excludeId});
 const [criteria,setCriteria]=useState(signature);
 useEffect(()=>{onAcknowledge(false);const timer=setTimeout(()=>setCriteria(signature),400);return()=>clearTimeout(timer);},[signature]);
 const data=JSON.parse(criteria);
 const matches=useQuery({queryKey:["employee-duplicate-warning",criteria],queryFn:()=>api.post<{items:Array<{id:number;employee_code:string}>}>("/employees/duplicate-check",data,{readOnlyPreview:true,progress:false}).then(r=>r.data.items),enabled:!!(data.personal_email||data.work_email||data.phone_number||data.employee_id),retry:false,staleTime:30000,refetchOnWindowFocus:false});
 return matches.data?.length?<aside role="status" className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950"><strong>Possible duplicate employee details</strong><p>Review {matches.data.map((m,i)=><span key={m.id}>{i?", ":""}<Link className="underline" target="_blank" to={`/hrms/employees/${m.id}`}>{m.employee_code}</Link></span>)} before saving.</p><label className="mt-2 flex gap-2"><input type="checkbox" checked={acknowledged} onChange={e=>onAcknowledge(e.target.checked)}/>I reviewed these profiles and confirm that the shared contact details are intentional.</label></aside>:matches.isError?<p role="status" className="text-sm">Duplicate preview is unavailable. The server will still check when saving.</p>:null;
}
