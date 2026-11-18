import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";

export function PersonalHighlights({ employeeId, identity }: { employeeId: number; identity: unknown[] }) {
  const certificates = useQuery({queryKey:["hrms-dashboard-personal",...identity,"certificates",employeeId],queryFn:({signal})=>api.get<{id:number}[]>("/documents/certificates",{params:{employee_id:employeeId},signal,progress:false}).then(r=>r.data),retry:false});
  const recognitions = useQuery({queryKey:["hrms-dashboard-personal",...identity,"recognitions",employeeId],queryFn:({signal})=>api.get<{id:number;title:string;badge?:string;points?:number}[]>("/engagement/recognitions",{params:{employee_id:employeeId},signal,progress:false}).then(r=>r.data),retry:false});
  return <section className="hrd-section"><h2>My documents & recognition</h2>
    {certificates.isError&&<p role="alert">{certificates.data?"Document count may be stale.":"Document count unavailable."}<Button variant="ghost" onClick={()=>void certificates.refetch()}>Retry documents</Button></p>}
    <p><Link to="/hrms/documents">My certificates</Link>: {certificates.data ? `${certificates.data.length}${certificates.data.length===500?"+":""}` : certificates.isPending?"Loading…":"Unavailable"}</p>
    {recognitions.isError&&<p role="alert">{recognitions.data?"Recognition feed may be stale.":"Recognition feed unavailable."}<Button variant="ghost" onClick={()=>void recognitions.refetch()}>Retry recognition</Button></p>}
    {recognitions.isPending&&<p role="status">Loading recognition…</p>}
    {recognitions.data&&<>{recognitions.data.slice(0,3).map(r=><p key={r.id}>{r.badge||r.title}{r.points?` · ${r.points} points`:""}</p>)}{!recognitions.data.length&&<p>No public recognition for you yet.</p>}<Link to="/hrms/engagement">Open recognition</Link></>}
  </section>;
}
