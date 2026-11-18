import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { recordScope, useRecordScope } from "@/shared/records/Record360Workspace";
import { srmApi } from "@/apps/srm/api";
import { defaultText, defaultToday } from "@/lib/form-defaults";
import { dealError } from "@/apps/crm/deals/deal-utils";
import { toast } from "@/hooks/use-toast";
import CompactForm from "@/components/forms/CompactForm";
import { NativeSelect } from "@/components/ui/native-select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import { useFinanceWrite } from "./useFinanceWrite";
import type { FAMRecord } from "./types";
const rows=(data:unknown):FAMRecord[]=>Array.isArray(data)?data:(data as {items?:FAMRecord[]})?.items||[];
const amount=(value:string)=>/^(?:\d+\.?\d*|\.\d+)$/.test(value)&&Number.isFinite(Number(value));
export default function InventoryPriceListForm(){const scope=useRecordScope();return <PriceListForm key={scope} scope={scope}/>;}
function PriceListForm({scope}:{scope:string}){
 const qc=useQueryClient(),canWrite=useFinanceWrite(["srm_manage","srm_admin"],"create");
 const owner=useRef(recordScope(useAuthStore.getState().user)),active=useRef(true);
 useEffect(()=>{active.current=true;return()=>{active.current=false}},[]);
 const owns=()=>active.current&&owner.current===recordScope(useAuthStore.getState().user);
 const[draft,setDraft]=useState(()=>({code:"",name:"",channel:"retail",customer:"cash",currency:defaultText("currency","srm"),from:defaultToday("srm"),to:"",priority:"100",product:"",quantity:"1",price:"",percent:"0",discount:"0",inclusive:false}));
 const[submitted,setSubmitted]=useState(false),[lookupSubmitted,setLookupSubmitted]=useState(false),[error,setError]=useState("");
 const products=useQuery({queryKey:["srm","price-list-products",scope],queryFn:()=>srmApi.inventoryItems(),retry:false,staleTime:30000});
 const productRows=rows(products.data).filter(row=>row.active!==false);
 const fingerprint=JSON.stringify([draft.product,draft.channel,draft.customer,draft.from,draft.quantity]);
 const latestFingerprint=useRef(fingerprint);latestFingerprint.current=fingerprint;
 const[result,setResult]=useState<{fingerprint:string;rows:FAMRecord[]}>();
 const errors:Record<string,string>={};
 if(!productRows.some(row=>String(row.id)===draft.product))errors.product="Choose an available product.";
 if(!draft.name.trim())errors.name="Enter a price list name.";
 if(!draft.channel.trim())errors.channel="Enter a channel.";
 if(!draft.customer.trim())errors.customer="Enter a customer type.";
 if(!draft.currency.trim())errors.currency="Enter a currency.";
 if(!amount(draft.quantity)||Number(draft.quantity)<=0)errors.quantity="Enter a minimum quantity greater than zero.";
 if(!amount(draft.price))errors.price="Enter a nonnegative price.";
 if(!amount(draft.percent)||Number(draft.percent)>100)errors.percent="Discount percentage must be between zero and 100.";
 if(!amount(draft.discount)||Number(draft.discount)>Number(draft.price))errors.discount="Discount amount must be nonnegative and cannot exceed price.";
 if(!/^-?\d+$/.test(draft.priority)||!Number.isSafeInteger(Number(draft.priority)))errors.priority="Enter a whole-number priority.";
 if(draft.from&&draft.to&&draft.to<draft.from)errors.to="Effective-to date cannot precede effective-from date.";
 const save=useMutation({mutationFn:()=>{if(!owns())throw new Error("The inventory context changed. Reopen this form.");return srmApi.createPriceList({price_list_code:draft.code.trim()||undefined,price_list_name:draft.name.trim(),channel:draft.channel.trim(),customer_type:draft.customer.trim(),currency:draft.currency.trim().toUpperCase(),effective_from:draft.from||undefined,effective_to:draft.to||undefined,priority:Number(draft.priority),active:true,lines:[{product_id:Number(draft.product),min_quantity:Number(draft.quantity),price:Number(draft.price),discount_percent:Number(draft.percent),discount_amount:Number(draft.discount),tax_inclusive:draft.inclusive}]});},onSuccess:()=>{if(owns()){toast({title:"Price list saved"});void qc.invalidateQueries({queryKey:["srm"]});setResult(undefined);}},onError:reason=>{if(owns())setError(dealError(reason))}});
 const lookup=useMutation({mutationFn:(request:{fingerprint:string;payload:FAMRecord})=>srmApi.lookupPrices(request.payload),onSuccess:(data,request)=>{if(owns()&&latestFingerprint.current===request.fingerprint)setResult({fingerprint:request.fingerprint,rows:rows(data)})},onError:(reason,request)=>{if(owns()&&latestFingerprint.current===request.fingerprint)setError(dealError(reason))}});
 const change=(key:keyof typeof draft,value:string)=>setDraft(current=>({...current,[key]:value}));
 const limits:Partial<Record<keyof typeof draft,number>>={code:80,name:180,channel:80,customer:80,currency:10};
 const field=(key:Exclude<keyof typeof draft,"inclusive">,label:string,type="text",numeric=false)=><label className="grid gap-1 text-sm">{label}<Input aria-label={label} aria-invalid={(submitted||lookupSubmitted&&(key==="quantity"))&&!!errors[key]} maxLength={limits[key]} type={type} inputMode={numeric?"decimal":undefined} value={draft[key]} onChange={e=>change(key,e.target.value)}/>{(submitted||lookupSubmitted&&key==="quantity")&&errors[key]&&<span role="alert" className="text-destructive">{errors[key]}</span>}</label>;
 const busy=save.isPending||lookup.isPending;
 return <SmartCreateSection title="Create price list" size="standard"><div className="grid gap-4 lg:grid-cols-2"><Card><CardHeader><CardTitle className="text-base">Create price list</CardTitle></CardHeader><CardContent><CompactForm compactTabs={false} aria-label="Create price list" noValidate className="grid gap-3 md:grid-cols-2" onSubmit={e=>{e.preventDefault();setSubmitted(true);setError("");if(canWrite&&!busy&&!products.isError&&!Object.keys(errors).length)save.mutate();}}>
 <fieldset className="contents" disabled={save.isPending}>
 {field("code","Price list code (optional)")}{field("name","Price list name")}{field("channel","Channel")}{field("customer","Customer type")}{field("currency","Currency")}{field("from","Effective from","date")}{field("to","Effective to","date")}{field("priority","Priority","text",true)}
 <label className="grid gap-1 text-sm">Product<NativeSelect aria-label="Product" aria-invalid={(submitted||lookupSubmitted)&&!!errors.product} value={draft.product} onChange={e=>change("product",e.target.value)}><option value="">Choose product</option>{productRows.map(row=><option key={String(row.id)} value={String(row.id)}>{String(row.item_name)}{row.sku?` · ${row.sku}`:""}</option>)}</NativeSelect>{(submitted||lookupSubmitted)&&errors.product&&<span role="alert" className="text-destructive">{errors.product}</span>}</label>
 {field("quantity","Minimum quantity","text",true)}{field("price","Price","text",true)}{field("percent","Discount percent","text",true)}{field("discount","Discount amount","text",true)}
 <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.inclusive} onChange={e=>setDraft(current=>({...current,inclusive:e.target.checked}))}/>Tax inclusive price</label>
 </fieldset>
 {products.isError&&<p role="alert">Products could not load. <Button type="button" onClick={()=>void products.refetch()}>Retry products</Button></p>}
 {error&&<p role="alert" className="text-destructive md:col-span-2">{error}</p>}
 <div className="flex flex-wrap gap-2 md:col-span-2"><Button data-save-action type="submit" disabled={!canWrite||busy||products.isPending||products.isError}>Save price list</Button><Button type="button" variant="outline" disabled={busy||products.isPending||products.isError} onClick={()=>{setLookupSubmitted(true);setError("");setResult(undefined);if(!errors.product&&!errors.quantity)lookup.mutate({fingerprint,payload:{product_ids:[Number(draft.product)],channel:draft.channel.trim()||undefined,customer_type:draft.customer.trim()||undefined,price_date:draft.from||undefined,quantity:Number(draft.quantity)}});}}>Test lookup</Button></div>
 </CompactForm></CardContent></Card>
 <Card><CardHeader><CardTitle className="text-base">Price lookup</CardTitle></CardHeader><CardContent><p className="mb-3 text-sm text-muted-foreground">Looks up saved prices for the selected product and date.</p>{lookup.isPending&&<p role="status">Looking up prices…</p>}{result?.fingerprint===fingerprint&&<div className="space-y-3">{result.rows.map(row=><article key={String(row.product_id)} className="rounded border p-3"><h3>{String(row.item_name||row.sku||"Product")}</h3><p>{String(row.price_list_name||"")}</p><dl><dt>Base price</dt><dd>{String(row.base_price)} {String(row.currency||"")}</dd><dt>Net price</dt><dd>{String(row.net_price)} {String(row.currency||"")}</dd></dl></article>)}{!result.rows.length&&<p>No prices found.</p>}</div>}</CardContent></Card></div></SmartCreateSection>;
}
