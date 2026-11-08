import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import GridTable from "@/shared/data-grid/GridTable";
import { useFinanceWrite } from "./useFinanceWrite";

type Row = { box: string; amount: string; vat: string; adjustment: string };
type Result = { output_vat: string; recoverable_vat: string; net_vat_due: string; standard_due_date: string };
type Settings = { trn: string; emirate: string; output_vat_ledger_id: number; input_vat_ledger_id: number };
type VATRegister = {output_vat:string;recoverable_vat:string;net_vat:string;basis:string;items:{date:string;voucher_id:number;voucher_number:string;direction:string;vat_amount:string}[];comparison:null|{working_version:number;output_difference:string;recoverable_difference:string;net_difference:string}};
const boxes: Record<string,string> = { '1a':'Abu Dhabi','1b':'Dubai','1c':'Sharjah','1d':'Ajman','1e':'Umm Al Quwain','1f':'Ras Al Khaimah','1g':'Fujairah','2':'Tourist refunds','3':'Reverse charge outputs','4':'Zero-rated supplies','5':'Exempt supplies','6':'Goods imported','7':'Import adjustments','9':'Standard-rated expenses','10':'Recoverable reverse charge' };
const boxOrder = ['1a','1b','1c','1d','1e','1f','1g','2','3','4','5','6','7','9','10'];
function errorText(error: unknown) { const detail=(error as {response?:{data?:{detail?:unknown}}})?.response?.data?.detail; return typeof detail === 'string' ? detail : 'Check the entered figures, dates and permissions.'; }

export default function UAETaxPage() {
  const client=useQueryClient();
  const canConfigure=useFinanceWrite(["fam_settings_manage","fam_admin"]);
  const canPrepare=useFinanceWrite(["fam_gst_return_prepare","fam_gst_manage","fam_admin"]);
  const [settings,setSettings]=useState<Settings>({trn:'',emirate:'1b',output_vat_ledger_id:0,input_vat_ledger_id:0});
  const config=useQuery({queryKey:['fam','uae-tax-settings'],queryFn:async()=>(await api.get<{settings:Settings|null;ledgers:{id:number;name:string;nature:string}[]}>('/fam/uae-tax/settings')).data,refetchOnWindowFocus:false});
  useEffect(()=>{if(config.data?.settings)setSettings(config.data.settings);},[config.data]);
  const saveSettings=useMutation({mutationFn:()=>api.put('/fam/uae-tax/settings',settings),onSuccess:()=>client.invalidateQueries({queryKey:['fam','uae-tax-settings']})});
  const [workingVersion,setWorkingVersion]=useState(0);
  const [start,setStart]=useState('');const [end,setEnd]=useState('');const [note,setNote]=useState('');
  const [rows,setRows]=useState<Row[]>(boxOrder.map(box=>({box,amount:'0',vat:'0',adjustment:'0'})));
  const register=useMutation({mutationFn:async()=>(await api.get<VATRegister>('/fam/uae-tax/register',{params:{period_start:start,period_end:end}})).data});
  const working=useMutation({mutationFn:async(save:boolean)=>(await api.post<Result|{result:Result;version:number}>(`/fam/uae-tax/vat201/${save?'workings':'preview'}`,{period_start:start,period_end:end,rows,reconciliation_note:note,expected_version:workingVersion})).data,onSuccess:data=>{if('result' in data){setWorkingVersion(data.version);register.reset();}client.invalidateQueries({queryKey:['fam','uae-vat-workings']});}});
  const saved=useQuery({queryKey:['fam','uae-vat-workings'],queryFn:async()=>(await api.get<{id:number;version:number;data:{input:{period_start:string;period_end:string;rows:Row[];reconciliation_note:string};result:Result}}[]>('/fam/uae-tax/vat201/workings')).data});
  const result=working.data && ('result' in working.data ? working.data.result : working.data);
  const [income,setIncome]=useState('');const [regime,setRegime]=useState('standard');
  const corporate=useMutation({mutationFn:async()=>(await api.post<{estimated_tax:string}>('/fam/uae-tax/corporate-tax/preview',{adjusted_taxable_income:income,regime})).data});
  const [vatAmount,setVatAmount]=useState('');const [inclusive,setInclusive]=useState(false);
  const calculator=useMutation({mutationFn:async()=>(await api.post<{net:string;vat:string;gross:string}>('/fam/uae-tax/calculate-vat',{amount:vatAmount,inclusive,treatment:'standard'})).data});
  function submit(event:FormEvent, action:()=>void){event.preventDefault();action();}
  return <section className="space-y-5"><h1 className="text-2xl font-semibold">UAE tax working papers</h1>
    <p>India GST and TDS remain available separately. These UAE working papers do not submit returns or make payments.</p>
    <Card><CardHeader><CardTitle>VAT registration and ledger mapping</CardTitle></CardHeader><CardContent>
      <p className="mb-3 text-sm">Use existing tax accounts from the chart of accounts. UAE invoice posting uses the output VAT mapping when the company financial country is AE.</p>
      <form className="grid gap-3 md:grid-cols-4" onSubmit={e=>submit(e,()=>saveSettings.mutate())}>
        <label>VAT TRN<Input required pattern="[0-9]{15}" maxLength={15} value={settings.trn} onChange={e=>setSettings({...settings,trn:e.target.value})}/></label>
        <label>Emirate<NativeSelect className="block h-10 w-full rounded-md border bg-background px-3" value={settings.emirate} onChange={e=>setSettings({...settings,emirate:e.target.value})}>{Object.entries(boxes).filter(([k])=>/^1[a-g]$/.test(k)).map(([k,v])=><option key={k} value={k}>{v}</option>)}</NativeSelect></label>
        {(['output','input'] as const).map(kind=><label key={kind}>{kind==='output'?'Output VAT liability account':'Input VAT asset account'}<NativeSelect className="block h-10 w-full rounded-md border bg-background px-3" required value={settings[`${kind}_vat_ledger_id`]||''} onChange={e=>setSettings({...settings,[`${kind}_vat_ledger_id`]:Number(e.target.value)})}><option value="">Select existing tax account</option>{config.data?.ledgers.filter(l=>l.nature===(kind==='output'?'liability':'asset')).map(l=><option key={l.id} value={l.id}>{l.name}</option>)}</NativeSelect></label>)}
        <Button disabled={!canConfigure||saveSettings.isPending}>Save UAE settings</Button>
      </form>{saveSettings.isSuccess&&<p role="status">UAE settings saved.</p>}{saveSettings.isError&&<p role="alert">{errorText(saveSettings.error)}</p>}{config.isError&&<p role="alert">UAE settings could not be loaded.</p>}
    </CardContent></Card>
    <Card><CardHeader><CardTitle>VAT201 draft working</CardTitle></CardHeader><CardContent className="space-y-3">
      <p className="text-sm">Enter reconciled AED figures. Boxes 9 and 10 contain recoverable VAT, not all VAT incurred. Tourist refunds are negative. Verify the assigned tax period and actual FTA due date, including holidays.</p>
      <div className="grid gap-3 md:grid-cols-2"><label>Period start<Input type="date" value={start} onChange={e=>{setStart(e.target.value);setWorkingVersion(0);working.reset();register.reset();}}/></label><label>Period end<Input type="date" min={start} value={end} onChange={e=>{setEnd(e.target.value);setWorkingVersion(0);working.reset();register.reset();}}/></label></div>
      <div className="overflow-x-auto"><GridTable gridId="fam-uae-vat201" className="w-full text-sm"><thead><tr><th>Box</th><th>Category</th><th>Amount AED</th><th>VAT / recoverable VAT AED</th><th>VAT adjustment AED</th></tr></thead><tbody>{rows.map((row,index)=><tr key={row.box}><td>{row.box}</td><td>{boxes[row.box]}</td>{(['amount','vat','adjustment'] as const).map(field=><td key={field}><Input aria-label={`Box ${row.box} ${field}`} type="number" step="0.01" value={row[field]} onChange={e=>{setRows(rows.map((r,i)=>i===index?{...r,[field]:e.target.value}:r));working.reset();}}/></td>)}</tr>)}</tbody></GridTable></div>
      <label>Reconciliation note<textarea className="block w-full rounded border p-2" maxLength={4000} value={note} onChange={e=>{setNote(e.target.value);working.reset();}}/></label>
      <div className="flex gap-2"><Button disabled={working.isPending||!start||!end} onClick={()=>working.mutate(false)}>Preview VAT201</Button><Button variant="outline" disabled={!canPrepare||working.isPending||!start||!end} onClick={()=>working.mutate(true)}>Save draft working</Button></div>
      {result&&<p role="status">Output VAT AED {result.output_vat} · Recoverable VAT AED {result.recoverable_vat} · Net due AED {result.net_vat_due}. Standard date before holiday adjustments: {result.standard_due_date}. Not submitted.</p>}{working.isError&&<p role="alert">{errorText(working.error)}</p>}
      <Button variant="outline" disabled={!start||!end||register.isPending} onClick={()=>register.mutate()}>Reconcile VAT accounts</Button>
      {register.isError&&<p role="alert">{errorText(register.error)}</p>}
      {register.data&&<section className="space-y-2 rounded border p-3"><h3 className="font-semibold">Posted VAT account register</h3><p>{register.data.basis}</p><p>Output VAT AED {register.data.output_vat} · Recoverable VAT AED {register.data.recoverable_vat} · Net VAT AED {register.data.net_vat}</p>
        {register.data.comparison&&<p role="status">Difference from saved working version {register.data.comparison.working_version}: output AED {register.data.comparison.output_difference}, recoverable AED {register.data.comparison.recoverable_difference}, net AED {register.data.comparison.net_difference}.</p>}
        <div className="overflow-x-auto"><GridTable gridId="fam-uae-vat-account-register" className="w-full text-sm"><thead><tr><th>Date</th><th>Voucher</th><th>Direction</th><th>VAT AED</th></tr></thead><tbody>{register.data.items.map((row,index)=><tr key={`${row.voucher_id}-${index}`}><td>{row.date}</td><td><a className="text-primary underline" href={`/fam/vouchers/${row.voucher_id}`}>{row.voucher_number}</a></td><td>{row.direction}</td><td>{row.vat_amount}</td></tr>)}</tbody></GridTable></div></section>}
      {saved.data?.map(record=><Button key={record.id} variant="outline" onClick={()=>{const input=record.data.input;register.reset();setWorkingVersion(record.version);setStart(input.period_start);setEnd(input.period_end);setRows(boxOrder.map(box=>input.rows.find(r=>r.box===box)||{box,amount:'0',vat:'0',adjustment:'0'}));setNote(input.reconciliation_note);working.reset();}}>Load {record.data.input.period_start} – {record.data.input.period_end} · version {record.version}</Button>)}
    </CardContent></Card>
    <Card><CardHeader><CardTitle>VAT calculator</CardTitle></CardHeader><CardContent><form className="flex flex-wrap items-end gap-3" onSubmit={e=>submit(e,()=>calculator.mutate())}><label>Amount AED<Input required type="number" min="0" step="0.01" value={vatAmount} onChange={e=>{setVatAmount(e.target.value);calculator.reset();}}/></label><label><input type="checkbox" checked={inclusive} onChange={e=>{setInclusive(e.target.checked);calculator.reset();}}/> VAT included</label><Button disabled={calculator.isPending}>Calculate 5% VAT</Button></form>{calculator.data&&<p role="status">Net AED {calculator.data.net} · VAT AED {calculator.data.vat} · Gross AED {calculator.data.gross}</p>}{calculator.isError&&<p role="alert">{errorText(calculator.error)}</p>}</CardContent></Card>
    <Card><CardHeader><CardTitle>Corporate tax estimate</CardTitle></CardHeader><CardContent><p className="mb-3 text-sm">Use adjusted taxable income after the applicable tax adjustments. The ordinary 0%/9% calculation does not assess free-zone treatment, relief eligibility, exemptions or domestic minimum top-up tax.</p><form className="flex flex-wrap items-end gap-3" onSubmit={e=>submit(e,()=>corporate.mutate())}><label>Adjusted taxable income AED<Input required type="number" step="0.01" value={income} onChange={e=>{setIncome(e.target.value);corporate.reset();}}/></label><label>Regime<NativeSelect className="block h-10 w-full rounded-md border bg-background px-3" value={regime} onChange={e=>{setRegime(e.target.value);corporate.reset();}}>{[['standard','Ordinary taxable person'],['qualifying_free_zone','Qualifying free-zone person'],['small_business_relief','Small business relief'],['exempt','Exempt person'],['dmtt','Domestic minimum top-up tax']].map(([k,v])=><option key={k} value={k}>{v}</option>)}</NativeSelect></label><Button disabled={corporate.isPending}>Preview corporate tax</Button></form>{corporate.data&&<p role="status">Draft estimate AED {corporate.data.estimated_tax}. Not submitted.</p>}{corporate.isError&&<p role="alert">{errorText(corporate.error)}</p>}</CardContent></Card>
  </section>;
}
