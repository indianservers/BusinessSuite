import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import { useRecordScope } from '@/lib/record-scope';
import { useRecordScopeOwner } from '@/hooks/use-record-scope-owner';
import { financialIntentKey, readFinancialIntent, saveFinancialIntent, clearFinancialIntent } from '@/lib/financial-intent';
import { dealError } from '@/apps/crm/deals/deal-utils';

type Options = { checkout_id:number; revision:number; invoice_number:string; currency:string; ready:boolean; unavailable_reason:string|null;
  lines:{id:number;description:string;remaining_quantity:string;issued_total:string}[] };
type Command = {checkout_id:number;expected_checkout_revision:number;request_key:string;lines:{checkout_line_id:number;quantity:string;restock:boolean}[];
  refund:{method:'cash'|'card';session_id:number;reference:string};reason:string};
type Result = {id:number;return_number:string;currency:string;refund_amount:string;accounting:{credit_note:{number:string};refund:{number:string}}};
type Attempt = {payload:Command};
const pending = new Map<string,Attempt>();
const positive=(value:unknown):value is number=>Number.isSafeInteger(value)&&Number(value)>0;
const valid=(value:Attempt|null|undefined,id:number):value is Attempt=>!!value&&value.payload?.checkout_id===id&&positive(value.payload.expected_checkout_revision)
  &&typeof value.payload.request_key==='string'&&/^[0-9a-f-]{36}$/i.test(value.payload.request_key)&&Array.isArray(value.payload.lines)&&value.payload.lines.length>0
  &&value.payload.lines.every(line=>positive(line.checkout_line_id)&&typeof line.quantity==='string'&&Number.isFinite(Number(line.quantity))&&Number(line.quantity)>0)
  &&['cash','card'].includes(value.payload.refund?.method)&&positive(value.payload.refund?.session_id)&&typeof value.payload.reason==='string';

export default function RetailReturnPanel(props:{checkoutId:number;sessionId:number|null;onChanged:()=>void}) {
  const scope=useRecordScope();
  return <Form key={`${scope}:${props.checkoutId}`} {...props} scope={scope}/>;
}

function Form({checkoutId,sessionId,onChanged,scope}:{checkoutId:number;sessionId:number|null;onChanged:()=>void;scope:string}) {
  const owns=useRecordScopeOwner(),key=financialIntentKey('refund',checkoutId);
  const [recovery]=useState(()=>readFinancialIntent<Attempt>(key));
  const initial=pending.get(key)||(valid(recovery.payload,checkoutId)?recovery.payload:null);
  const attempt=useRef<Attempt|null>(initial),uncertain=useRef(!!initial||recovery.pending);
  const [locked,setLocked]=useState(!!initial||recovery.pending),[open,setOpen]=useState(!!initial||recovery.pending);
  const [lineId,setLineId]=useState(''),[quantity,setQuantity]=useState('1'),[method,setMethod]=useState<'cash'|'card'>('cash');
  const [reason,setReason]=useState(''),[reference,setReference]=useState(''),[restock,setRestock]=useState(true);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[result,setResult]=useState<Result|null>(null);
  const options=useQuery({queryKey:['retail-return-sale',scope,checkoutId],enabled:open,
    queryFn:({signal})=>api.get<Options>(`/srm/retail/returns/sales/${checkoutId}`,{signal,recordCache:false}).then(response=>response.data),retry:false,refetchOnWindowFocus:false});
  const complete=(value:Result)=>{
    if(!owns())return;
    pending.delete(key);clearFinancialIntent(key);attempt.current=null;uncertain.current=false;setLocked(false);
    setResult(value);setError('');onChanged();void options.refetch();
  };
  const send=async(saved:Attempt)=>{
    if(!owns()||busy)return;
    const wasUncertain=uncertain.current;
    setBusy(true);setError('');
    try {
      if(!pending.has(key)&&pending.size>=50)throw new Error('Resolve an earlier refund before starting another.');
      saveFinancialIntent(key,saved);pending.set(key,saved);attempt.current=saved;setLocked(true);
      const response=await api.post<Result>('/srm/retail/returns',saved.payload);
      complete(response.data);
    } catch(caught) {
      if(!owns())return;
      setError(dealError(caught));
      const definite=isAxiosError(caught)&&[400,403,404,409,422].includes(caught.response?.status||0);
      if(definite&&!wasUncertain) {
        pending.delete(key);clearFinancialIntent(key);attempt.current=null;setLocked(false);
      } else {uncertain.current=true;setLocked(true);}
    } finally {if(owns())setBusy(false);}
  };
  const recover=async()=>{
    const saved=attempt.current;
    if(!saved||!owns()||busy)return;
    setBusy(true);setError('');
    try {
      const response=await api.get<{state:string;result:Result|null}>(`/srm/retail/returns/requests/${saved.payload.request_key}`,{recordCache:false});
      if(response.data.state==='committed'&&response.data.result)complete(response.data.result);
      else setError('The saved refund has not completed. Retry the same saved request.');
    } catch(caught) {
      if(owns())setError(isAxiosError(caught)&&caught.response?.status===404?'No completed refund is visible yet. Retry the same saved request; its identity is preserved.':dealError(caught));
    } finally {if(owns())setBusy(false);}
  };
  const line=options.data?.lines.find(item=>String(item.id)===lineId);
  return <details className="mt-3 rounded-lg border bg-card p-3 text-left text-foreground" open={open} onToggle={event=>setOpen(event.currentTarget.open)}>
    <summary className="cursor-pointer text-sm font-medium">Return physical items and refund</summary>
    <div className="mt-3 space-y-3 text-sm">
      {result&&<div className="space-y-3">
        <div role="status" className="space-y-2">
          <p className="font-semibold">Refund completed: {result.refund_amount} {result.currency}</p>
          <dl className="space-y-1">
            <div><dt className="font-medium">Return</dt><dd className="break-all">{result.return_number}</dd></div>
            <div><dt className="font-medium">Credit note</dt><dd className="break-all">{result.accounting.credit_note.number}</dd></div>
            <div><dt className="font-medium">Refund</dt><dd className="break-all">{result.accounting.refund.number}</dd></div>
          </dl>
        </div>
        <Button variant="outline" onClick={()=>{setResult(null);setLineId('');setQuantity('1');setReason('');setReference('');}}>Return another item</Button>
      </div>}
      {locked&&<div className="space-y-2"><p role="status">A saved refund must be resolved before creating another.</p>{attempt.current?<div className="flex flex-wrap gap-2"><Button type="button" variant="outline" disabled={busy} onClick={()=>void recover()}>Check saved refund</Button><Button type="button" disabled={busy} onClick={()=>attempt.current&&void send(attempt.current)}>Retry saved refund</Button></div>:<p role="alert">Refund recovery data cannot be read. Keep this sale locked and ask an authorized administrator to review its returns.</p>}</div>}
      {options.isPending&&<p role="status">Loading original sale…</p>}
      {options.isError&&<p role="alert">{dealError(options.error)} <Button variant="outline" onClick={()=>void options.refetch()}>Reload</Button></p>}
      {options.data&&!options.data.ready&&<p role="status">{options.data.unavailable_reason}</p>}
      {!result&&!locked&&options.data&&<form className="space-y-3" onSubmit={event=>{
        event.preventDefault();if(busy||!owns()||!options.data?.ready||!line||!positive(sessionId))return;
        if(!/^\d+(?:\.\d{1,2})?$/.test(quantity)||Number(quantity)<=0||Number(quantity)>Number(line.remaining_quantity)){setError('Enter a quantity within the original sale’s remaining quantity, with at most two decimal places.');return;}
        if(!reason.trim()){setError('Enter a return reason.');return;}
        void send({payload:{checkout_id:checkoutId,expected_checkout_revision:options.data.revision,request_key:crypto.randomUUID(),
          lines:[{checkout_line_id:line.id,quantity,restock}],refund:{method,session_id:sessionId,reference:method==='card'?reference:''},reason:reason.trim()}});
      }}><fieldset className="space-y-3" disabled={busy||!options.data.ready||!sessionId}>
        <label className="grid gap-1">Original sale item<NativeSelect aria-label="Retail return item" value={lineId} onChange={event=>{setLineId(event.target.value);setQuantity('1');}}><option value="">Select a physical item</option>{options.data.lines.map(item=><option key={item.id} value={item.id}>{item.description} · {item.remaining_quantity} returnable</option>)}</NativeSelect></label>
        {line&&<p>Original issued total: {line.issued_total} {options.data.currency}. The refund uses the original invoice price and tax.</p>}
        <label className="grid gap-1">Return quantity<Input aria-label="Retail return quantity" inputMode="decimal" value={quantity} onChange={event=>setQuantity(event.target.value)}/></label>
        <label className="grid gap-1">Refund method<NativeSelect aria-label="Retail refund method" value={method} onChange={event=>setMethod(event.target.value as 'cash'|'card')}><option value="cash">Cash</option><option value="card">Card</option></NativeSelect></label>
        {method==='card'&&<label className="grid gap-1">Completed card refund reference<Input aria-label="Retail refund reference" required maxLength={200} value={reference} onChange={event=>setReference(event.target.value)}/></label>}
        <label className="flex items-center gap-2"><input type="checkbox" checked={restock} onChange={event=>setRestock(event.target.checked)}/>Return sellable stock to its original warehouse</label>
        <label className="grid gap-1">Return reason<Input aria-label="Retail return reason" required maxLength={2000} value={reason} onChange={event=>setReason(event.target.value)}/></label>
        <Button type="submit" disabled={!line||busy}>Return items and refund</Button>
      </fieldset>{!sessionId&&<p role="status">Open an authorized POS register before refunding.</p>}</form>}
      {error&&<p role="alert">{error}</p>}
    </div>
  </details>;
}
