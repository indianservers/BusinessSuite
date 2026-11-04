import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocation, useSearchParams } from "react-router-dom";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { NativeSelect } from "@/components/ui/native-select";
import PaymentRequests, { type PaymentSource } from "./PaymentRequests";

type SourceRow = {id:number;name?:string;title?:string;quote_number?:string;order_number?:string;invoice_number?:string};
export default function PaymentRequestsPage() {
  const location = useLocation(), [params, setParams] = useSearchParams();
  const user = useAuthStore(state => state.user);
  const allowed: PaymentSource[] = location.pathname.startsWith("/crm") ? ["crm_deal","crm_quotation"] : ["srm_invoice","srm_order"];
  const source = allowed.includes(params.get("source_type") as PaymentSource) ? params.get("source_type") as PaymentSource : allowed[0];
  const requestedId = Number(params.get("source_id"));
  const id = Number.isSafeInteger(requestedId) && requestedId > 0 ? requestedId : 0;
  const [search, setSearch] = useState("");
  const url = {crm_deal:"/crm/deals",crm_quotation:"/crm/quotations",srm_invoice:"/srm/business/collection-invoices",srm_order:"/srm/sales-orders"}[source];
  const records = useQuery({queryKey:["payment-sources",user?.id,user?.access?.companyId,sessionStorage.getItem("suite-branch"),source],queryFn:async()=>{
    const {data}=await api.get<SourceRow[]|{items:SourceRow[]}>(url,{params:{per_page:100}});return Array.isArray(data)?data:data.items;
  }});
  return <main className="space-y-5 p-5"><h1 className="text-2xl font-semibold">Payment requests</h1><p>Request an advance or an outstanding payment from a saved sales record.</p>
    <div className="grid gap-3 sm:grid-cols-2"><label>Payment source<NativeSelect className="mt-1 block h-10 w-full rounded-md border bg-background px-3" aria-label="Payment source type" value={source} onChange={e=>{setParams({source_type:e.target.value});setSearch("");}}>{allowed.map(value=><option key={value} value={value}>{({crm_deal:"CRM deal",crm_quotation:"CRM quotation",srm_invoice:"Issued invoice",srm_order:"Sales / POS order"})[value]}</option>)}</NativeSelect></label>
      <label>Find record<input className="block w-full rounded-md border bg-background p-2" value={search} onChange={e=>setSearch(e.target.value)} aria-label="Search payment source" placeholder="Name or reference"/></label></div>
    <label className="block">Record<NativeSelect className="mt-1 block h-10 w-full rounded-md border bg-background px-3" aria-label="Payment source record" loading={records.isFetching} error={records.isError} value={id||""} onChange={e=>setParams({source_type:source,source_id:e.target.value})}><option value="">Choose a saved record</option>{id>0&&!records.data?.some(row=>row.id===id)&&<option value={id}>Record #{id}</option>}{records.data?.filter(row=>JSON.stringify(row).toLowerCase().includes(search.toLowerCase())).map(row=><option key={row.id} value={row.id}>{row.invoice_number||row.order_number||row.quote_number||row.name||row.title||`Record #${row.id}`}</option>)}</NativeSelect></label>
    {records.data&&!records.data.length&&<p>No saved records of this type are available in the current branch.</p>}
    {records.isError&&<p role="alert">Records could not load or are outside your permissions. <button onClick={()=>void records.refetch()}>Retry</button></p>}
    {id>0&&<PaymentRequests source={source} sourceId={id}/>}
  </main>;
}
