import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useRecordScope } from "@/lib/record-scope";
import { Button } from "@/components/ui/button";

export default function PurchaseOrderDetailPage() {
  const {id}=useParams(),scope=useRecordScope();
  const query=useQuery({queryKey:['srm','purchase-order',scope,id],queryFn:async()=>(await api.get(`/srm/procurement/purchase-orders/${id}`)).data});
  if(query.isPending)return <p role="status">Loading purchase order…</p>;
  if(query.isError)return <p role="alert">This purchase order is unavailable. <Button onClick={()=>query.refetch()}>Retry purchase order</Button></p>;
  const row=query.data;
  return <main className="space-y-4"><Link className="text-primary underline" to="/srm/inventory/purchase-orders">← Purchase orders</Link><h1 className="page-title">{row.po_number}</h1><p>{row.vendor_name||'Supplier not specified'} · {row.status}</p><div className="flex flex-wrap gap-6 text-sm"><p>Order date: {row.order_date}</p><p>Expected date: {row.expected_date||'Not set'}</p><p>Subtotal: {row.subtotal}</p><p>Tax: {row.tax_amount}</p><p>Total: {row.total_amount}</p></div><div className="overflow-x-auto rounded-lg border"><table className="w-full text-left text-sm"><thead><tr>{['Description','Quantity','Received','Unit price','Tax','Total'].map(title=><th key={title} className="p-3">{title}</th>)}</tr></thead><tbody>{row.lines.map((line:any)=><tr key={line.id} className="border-t">{[line.description,line.quantity,line.received_quantity,line.unit_price,line.tax_amount,line.line_total].map((value,index)=><td className="p-3" key={index}>{value}</td>)}</tr>)}</tbody></table></div>{row.notes&&<p className="whitespace-pre-wrap">{row.notes}</p>}</main>;
}
