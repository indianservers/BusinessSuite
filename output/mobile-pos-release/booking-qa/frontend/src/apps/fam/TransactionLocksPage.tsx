import {MobileDisclosure} from "@/components/mobile/MobilePrimitives";
import "./fam-mobile-workflows.css";
import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useFinanceWrite } from "./useFinanceWrite";

type Lock = { module: string; locked_through: string | null; reason: string; version: number };
const labels: Record<string,string> = {all:'All accounting modules',sales:'Sales',purchases:'Purchases',banking:'Banking',accountant:'Accountant'};
export default function TransactionLocksPage(){
  const client=useQueryClient();
  const canConfigure=useFinanceWrite(['fam_settings_manage','fam_admin']);
  const query=useQuery({queryKey:['fam','transaction-locks'],queryFn:async()=>(await api.get<Lock[]>('/fam/transaction-locks')).data,refetchOnWindowFocus:false});
  return <section className="space-y-5 fam-mobile-transaction-locks"><h1 className="text-2xl font-semibold">Accounting transaction locks</h1><p>Prevent changes to accounting vouchers on or before a selected date. These controls apply in addition to financial-year and accounting-period locks. Sales covers sales and credit notes; purchases covers purchases and debit notes; banking covers receipts, payments and contra; accountant covers journals, opening and adjustments.</p><Button variant="outline" onClick={()=>query.refetch()}>Refresh locks</Button>{query.isPending&&<p role="status">Loading transaction locks…</p>}{query.isError&&<p role="alert">Transaction locks could not be loaded.</p>}{query.data?.map(row=><LockRow key={`${row.module}-${row.version}`} row={row} canConfigure={canConfigure} onSaved={()=>client.invalidateQueries({queryKey:['fam','transaction-locks']})}/>)}</section>;
}
function LockRow({row,canConfigure,onSaved}:{row:Lock;canConfigure:boolean;onSaved:()=>unknown}){
  const [through,setThrough]=useState(row.locked_through||'');
  const [reason,setReason]=useState('');
  const save=useMutation({mutationFn:()=>api.put(`/fam/transaction-locks/${row.module}`,{locked_through:through||null,reason,expected_version:row.version}),onSuccess:()=>onSaved()});
  function submit(event:FormEvent){event.preventDefault();save.mutate();}
  const detail=(save.error as {response?:{data?:{detail?:unknown}}})?.response?.data?.detail;
  return <Card className="fam-transaction-lock"><CardHeader className="fam-lock-header"><CardTitle>{labels[row.module]}</CardTitle></CardHeader><CardContent className="fam-lock-body"><p className="mb-3 text-sm">{row.locked_through?`Locked through ${row.locked_through}`:'No module/date lock'}{row.reason?` · ${row.reason}`:''}</p><MobileDisclosure maxWidth={480} title={`Change ${labels[row.module]} lock${canConfigure?"":" (read-only)"}`}><form className="grid gap-3 md:grid-cols-3" onSubmit={submit}><label>Lock through<Input aria-label={`${labels[row.module]} lock through`} type="date" value={through} onChange={e=>setThrough(e.target.value)}/></label><label>Reason for change<Input required aria-label={`${labels[row.module]} reason`} maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/></label><Button className="self-end" disabled={!canConfigure||save.isPending}>{through?'Save lock':'Save unlock'}</Button></form><p className="mt-2 text-sm text-muted-foreground">Clear the date to remove this module/date lock. Existing financial-year and accounting-period locks remain effective.</p>{save.isError&&<p role="alert">{typeof detail==='string'?detail:'Could not save this lock. Your entries are kept for retry.'}</p>}</MobileDisclosure></CardContent></Card>;
}
