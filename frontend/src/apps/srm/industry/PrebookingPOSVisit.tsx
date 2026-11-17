import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '@/services/api';
import { useRecordScope } from '@/lib/record-scope';
import { Button } from '@/components/ui/button';
import { dealError } from '@/apps/crm/deals/deal-utils';
import AppointmentVisitPanel from './AppointmentVisitPanel';

/** Open the existing reservation's native billing; never add it to a new POS cart. */
export default function PrebookingPOSVisit({ id }: { id: number }) {
  const scope = useRecordScope();
  const visit = useQuery({queryKey:['pos-prebooking',scope,id],retry:false,queryFn:({signal})=>api.get<{id:number;title:string;status:string;revision:number;customer_id?:number;data:Record<string,string|number|number[]>}>(`/srm/industry/appointments/${id}`,{signal,recordCache:false}).then(r=>r.data)});
  const caps = useQuery({queryKey:['pos-prebooking-permissions',scope],retry:false,queryFn:({signal})=>api.get<{billing:boolean;collect:boolean;invoice:boolean;approve_invoice:boolean}>('/srm/industry/capabilities',{signal,recordCache:false}).then(r=>r.data)});
  return <main className="prebooking-pos-visit"><header><h1>Prebooking at POS</h1><Button asChild variant="outline"><Link to="/srm/pos/terminal">Open POS cart</Link></Button></header>
    <p>This is the existing reservation. Payments and invoices remain linked to this booking.</p>
    {(visit.isPending || caps.isPending) && <p role="status">Loading prebooking and permissions…</p>}
    {(visit.isError || caps.isError) && <p role="alert">{dealError(visit.error || caps.error)} <Button onClick={()=>{void visit.refetch();void caps.refetch();}}>Retry prebooking</Button></p>}
    {visit.data && caps.data && <section><h2>{visit.data.title} · #{visit.data.id}</h2><p>{String(visit.data.data.customer_name || 'Selected customer')} · {String(visit.data.data.service_name || 'Service')}</p><AppointmentVisitPanel key={`${scope}:${id}`} row={visit.data} defaultOpen triggerLabel="View booking and billing" canViewBilling={caps.data.billing} canCollect={caps.data.collect} canInvoice={caps.data.invoice} canApprove={caps.data.approve_invoice} onChanged={()=>void visit.refetch()}/></section>}
  </main>;
}
