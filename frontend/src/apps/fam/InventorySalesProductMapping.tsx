import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRecordScope } from "@/shared/records/Record360Workspace";
import { useRecordScopeOwner } from "@/hooks/use-record-scope-owner";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { dealError } from "@/apps/crm/deals/deal-utils";
import { useFinanceWrite } from "./useFinanceWrite";
type Choice={id:number;label:string};
type Saved=Choice&{product_id:number|null;available:boolean};
export default function InventorySalesProductMapping({itemId}:{itemId:string}) {
  const scope=useRecordScope(),key=`${scope}:${itemId}`,current=useRef(key);current.current=key;
  return <Editor key={key} itemId={itemId} scope={scope} current={()=>current.current===key}/>;
}
function Editor({itemId,scope,current}:{itemId:string;scope:string;current:()=>boolean}) {
  const owner=useRecordScopeOwner(),owns=()=>current()&&owner(),qc=useQueryClient();
  const canMap=useFinanceWrite(['fam_admin','fam_inventory_manage'],'create');
  const canRemove=useFinanceWrite(['fam_admin','fam_inventory_manage'],'delete');
  const [search,setSearch]=useState(''),[page,setPage]=useState(1),[selected,setSelected]=useState('');
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const savedKey=['fam','inventory-sales-products',scope,itemId];
  const path=`/fam/inventory/items/${itemId}`;
  const saved=useQuery({queryKey:savedKey,queryFn:()=>api.get(path+'/sales-products').then(r=>r.data as {items:Saved[]}),retry:false});
  const options=useQuery({queryKey:['fam','inventory-sales-product-options',scope,search,page],queryFn:()=>api.get('/fam/inventory/sales-products',{params:{search,page}}).then(r=>r.data as {items:Choice[];has_more:boolean}),enabled:canMap,retry:false});
  async function change(link?:Saved) {
    if(busy||!owns()||(link?!canRemove:!canMap))return;
    const choice=options.data?.items?.find(row=>String(row.id)===selected);
    if(!link&&!choice)return;
    setBusy(true);setError('');setNotice('');
    try {
      const result=link?await api.delete(path+'/sales-products/'+link.id):await api.post(path+'/link',{stock_item_id:Number(itemId),target_module:'srm',target_record_type:'product',target_record_id:selected});
      if(!owns())return;
      qc.setQueryData<{items:Saved[]}>(savedKey,old=>({items:link?(old?.items||[]).filter(row=>row.id!==link.id):[...(old?.items||[]).filter(row=>row.id!==result.data.id),{id:result.data.id,product_id:choice!.id,label:choice!.label,available:true}]}));
      if(!link)setSelected('');
      setNotice(link?'Sales product link removed.':'Sales product linked.');
      void qc.invalidateQueries({queryKey:['fam']});
    } catch(failure) {if(owns())setError(dealError(failure));}
    finally {if(owns())setBusy(false);}
  }
  return <Card><CardHeader><CardTitle className="text-base">Sales products for revenue attribution</CardTitle></CardHeader><CardContent className="space-y-3">
    <p className="text-sm">Link the Sales catalog products represented by this Finance stock item. Each Sales product can belong to one stock item. Invoice descriptions are never used to guess links.</p>
    {saved.isPending&&<p role="status">Loading linked Sales products...</p>}
    {saved.isError&&<p role="alert">Linked products could not load. <Button disabled={busy} onClick={()=>void saved.refetch()}>Retry linked products</Button></p>}
    <fieldset disabled={busy} className="space-y-3">
      {saved.data?.items?.map(link=><div key={link.id} className="flex flex-wrap items-center gap-2"><span>{link.label}{!link.available?' - unavailable for new links':''}</span>{canRemove&&<Button variant="outline" onClick={()=>void change(link)}>Remove {link.label}</Button>}</div>)}
      {saved.isSuccess&&!saved.data?.items?.length&&<p>No Sales products linked.</p>}
      {canMap&&<><label className="grid gap-1 text-sm">Search Sales products<input aria-label="Search Sales products" maxLength={160} value={search} onChange={e=>{setSearch(e.target.value);setPage(1);setSelected('');}}/></label>
      {options.isPending&&<p role="status">Loading Sales product choices...</p>}
      {options.isError&&<p role="alert">Sales products could not load. <Button onClick={()=>void options.refetch()}>Retry Sales products</Button></p>}
      <label className="grid gap-1 text-sm">Sales product<NativeSelect aria-label="Sales product" value={selected} disabled={!options.isSuccess} onChange={e=>setSelected(e.target.value)}><option value="">Choose Sales product</option>{options.data?.items?.map(row=><option key={row.id} value={row.id}>{row.label}</option>)}</NativeSelect></label>
      <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={page===1} onClick={()=>{setPage(p=>p-1);setSelected('');}}>Previous products</Button><Button variant="outline" disabled={!options.data?.has_more} onClick={()=>{setPage(p=>p+1);setSelected('');}}>More products</Button><Button disabled={!selected||!options.isSuccess||!saved.isSuccess} onClick={()=>void change()}>Link Sales product</Button></div></>}
    </fieldset>
    {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
  </CardContent></Card>;
}
