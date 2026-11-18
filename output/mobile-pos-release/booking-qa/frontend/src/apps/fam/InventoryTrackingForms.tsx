import { useEffect, useRef, useState } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { srmApi } from "@/apps/srm/api";
import { useAuthStore } from "@/store/authStore";
import { recordScope, useRecordScope } from "@/shared/records/Record360Workspace";
import { useDebounced } from "@/shared/master-data/CompanySelect";
import SmartRecordPicker from "@/shared/records/SmartRecordPicker";
import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import CompactForm from "@/components/forms/CompactForm";
import { RichTextField } from "@/components/rich-text/LazyRichText";
import { NativeSelect } from "@/components/ui/native-select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { defaultToday } from "@/lib/form-defaults";
import { dealError } from "@/apps/crm/deals/deal-utils";
import { toast } from "@/hooks/use-toast";
import { useFinanceWrite } from "./useFinanceWrite";
import type { FAMRecord } from "./types";

const rows = (data: unknown): FAMRecord[] => Array.isArray(data) ? data : (data as {items?:FAMRecord[]})?.items || [];
const amount = (value: string) => /^(?:\d+\.?\d*|\.\d+)$/.test(value) && Number.isFinite(Number(value));
export default function InventoryTrackingForms() {
  const scope = useRecordScope();
  return <div className="grid gap-4 lg:grid-cols-2">{(["batch", "serial"] as const).map(kind => <TrackingForm key={`${scope}:${kind}`} scope={scope} kind={kind}/>)}</div>;
}
function TrackingForm({scope, kind}:{scope:string;kind:"batch"|"serial"}) {
  const batch = kind === "batch", qc = useQueryClient();
  const canWrite = useFinanceWrite(["srm_manage", "srm_admin"], "create");
  const owner = useRef(recordScope(useAuthStore.getState().user)), active = useRef(true);
  useEffect(()=>{active.current=true;return()=>{active.current=false}},[]);
  const owns = () => active.current && owner.current === recordScope(useAuthStore.getState().user);
  const initial = () => ({product:"",warehouse:"",code:"",received:defaultToday("srm"),manufacture:"",expiry:"",quantity:"",available:"",cost:"0",status:"available",notes:"",reference:""});
  const [draft,setDraft] = useState(initial),[submitted,setSubmitted]=useState(false),[error,setError]=useState("");
  const [selectedBatch,setSelectedBatch]=useState<FAMRecord>(),[search,setSearch]=useState("");
  const term=useDebounced(search);
  const products=useQuery({queryKey:["srm","tracking-products",scope],queryFn:()=>srmApi.inventoryItems(),staleTime:30000,retry:false});
  const warehouses=useQuery({queryKey:["srm","tracking-warehouses",scope],queryFn:srmApi.inventoryWarehouses,staleTime:30000,retry:false});
  const productRows=rows(products.data).filter(row=>row.active!==false),warehouseRows=rows(warehouses.data).filter(row=>row.active!==false);
  const batches=useInfiniteQuery({queryKey:["srm","tracking-batch-options",scope,draft.product,term],initialPageParam:1,enabled:!batch&&!!draft.product,retry:false,
    queryFn:({pageParam,signal})=>api.get<{items:FAMRecord[];has_more:boolean}>("/srm/inventory/batches",{signal,params:{product_id:Number(draft.product),search:term,page:pageParam,per_page:30}}).then(r=>r.data),
    getNextPageParam:(last,_all,page)=>last.has_more?page+1:undefined});
  const batchRows=batches.data?.pages.flatMap(page=>page.items)||[];
  const option=(row:FAMRecord)=>({id:String(row.id),label:String(row.batch_number),description:String((row.warehouse as FAMRecord | undefined)?.warehouse_name||warehouseRows.find(w=>w.id===row.warehouse_id)?.warehouse_name||""),record:row});
  const errors:Record<string,string>={};
  if(!productRows.some(row=>String(row.id)===draft.product))errors.product="Choose an available product.";
  if(draft.warehouse&&!warehouseRows.some(row=>String(row.id)===draft.warehouse))errors.warehouse="Choose an available warehouse.";
  if(!draft.code.trim())errors.code=`Enter a ${kind} number.`;
  if(!draft.status.trim())errors.status="Enter a status.";
  if(batch){
    if(!amount(draft.quantity))errors.quantity="Enter a nonnegative quantity.";
    if(draft.available&&(!amount(draft.available)||Number(draft.available)>Number(draft.quantity)))errors.available="Available quantity must be between zero and batch quantity.";
    if(!amount(draft.cost))errors.cost="Enter a nonnegative unit cost.";
    if(draft.manufacture&&draft.expiry&&draft.expiry<draft.manufacture)errors.expiry="Expiry cannot precede manufacture date.";
  }
  const save=useMutation({mutationFn:()=>{
    if(!owns())throw new Error("The inventory context changed. Reopen this form.");
    const common={product_id:Number(draft.product),warehouse_id:draft.warehouse?Number(draft.warehouse):undefined,status:draft.status.trim(),received_date:draft.received||undefined};
    return batch?srmApi.createInventoryBatch({...common,batch_number:draft.code.trim(),manufacture_date:draft.manufacture||undefined,expiry_date:draft.expiry||undefined,quantity:Number(draft.quantity),available_quantity:draft.available?Number(draft.available):undefined,unit_cost:Number(draft.cost),notes:draft.notes||undefined}):srmApi.createSerialNumber({...common,serial_number:draft.code.trim(),batch_id:selectedBatch?.id,reference_number:draft.reference||undefined});
  },onSuccess:()=>{if(!owns())return;toast({title:batch?"Batch saved":"Serial number saved"});setDraft(initial());setSelectedBatch(undefined);setSearch("");setSubmitted(false);setError("");void qc.invalidateQueries({queryKey:["srm"]});},onError:reason=>{if(owns())setError(dealError(reason))}});
  const change=(key:keyof typeof draft,value:string)=>setDraft(current=>({...current,[key]:value}));
  const field=(key:keyof typeof draft,label:string,type="text",required=false,numeric=false)=><label className="grid gap-1 text-sm">{label}<Input aria-label={label} aria-invalid={submitted&&!!errors[key]} required={required} type={type} inputMode={numeric?"decimal":undefined} value={draft[key]} maxLength={key==="code"?(batch?120:160):undefined} onChange={e=>change(key,e.target.value)}/>{submitted&&errors[key]&&<span role="alert" className="text-destructive">{errors[key]}</span>}</label>;
  const title=batch?"Create batch / expiry lot":"Register serial number";
  return <SmartCreateSection title={title} size="compact"><Card><CardHeader><CardTitle className="text-base">{title}</CardTitle></CardHeader><CardContent><CompactForm compactTabs={false} aria-label={title} className="grid gap-3 md:grid-cols-2" noValidate onSubmit={e=>{e.preventDefault();setSubmitted(true);setError("");if(canWrite&&!save.isPending&&!products.isError&&!warehouses.isError&&!Object.keys(errors).length)save.mutate();}}>
    <fieldset disabled={!canWrite||save.isPending} className="contents">
      <label className="grid gap-1 text-sm">Product<NativeSelect aria-label="Product" aria-invalid={submitted&&!!errors.product} value={draft.product} onChange={e=>{change("product",e.target.value);setSelectedBatch(undefined);setSearch("");}}><option value="">Choose product</option>{productRows.map(row=><option key={String(row.id)} value={String(row.id)}>{String(row.item_name)}{row.sku?` · ${row.sku}`:""}</option>)}</NativeSelect>{submitted&&errors.product&&<span role="alert" className="text-destructive">{errors.product}</span>}</label>
      <label className="grid gap-1 text-sm">Warehouse (optional)<NativeSelect aria-label="Warehouse" value={draft.warehouse} onChange={e=>change("warehouse",e.target.value)}><option value="">Use {batch?"product":"batch or product"} default</option>{warehouseRows.map(row=><option key={String(row.id)} value={String(row.id)}>{String(row.warehouse_name)}</option>)}</NativeSelect>{submitted&&errors.warehouse&&<span role="alert">{errors.warehouse}</span>}</label>
      {field("code",batch?"Batch number":"Serial number","text",true)}
      {field("received","Received date","date")}
      {batch?<>{field("manufacture","Manufacture date","date")}{field("expiry","Expiry date","date")}{field("quantity","Quantity","text",true,true)}{field("available","Available quantity (optional)","text",false,true)}{field("cost","Unit cost","text",true,true)}<label className="grid gap-1 text-sm">Notes<RichTextField value={draft.notes} onChange={e=>change("notes",e.target.value)}/></label></>:<><div className="grid gap-1 text-sm">Batch (optional){draft.product?<SmartRecordPicker name="batch" value={selectedBatch?String(selectedBatch.id):""} selected={selectedBatch?option(selectedBatch):undefined} search={search} onSearch={setSearch} items={batchRows.map(option)} onSelect={setSelectedBatch} onClear={()=>setSelectedBatch(undefined)} loading={batches.isFetching} error={batches.isError?"Batches could not load.":undefined} retry={()=>void batches.refetch()} hasMore={batches.hasNextPage} loadMore={()=>void batches.fetchNextPage()}/>:<p>Choose a product to find its batches.</p>}</div>{field("reference","Reference number")}</>}
      {field("status","Status","text",true)}
    </fieldset>
    {products.isError&&<p role="alert">Products could not load. <Button type="button" onClick={()=>void products.refetch()}>Retry products</Button></p>}
    {warehouses.isError&&<p role="alert">Warehouses could not load. <Button type="button" onClick={()=>void warehouses.refetch()}>Retry warehouses</Button></p>}
    {error&&<p role="alert" className="text-destructive">{error}</p>}
    <Button data-save-action type="submit" disabled={!canWrite||save.isPending||products.isPending||warehouses.isPending||products.isError||warehouses.isError}>{save.isPending?"Saving…":batch?"Save batch":"Save serial"}</Button>
  </CompactForm></CardContent></Card></SmartCreateSection>;
}
