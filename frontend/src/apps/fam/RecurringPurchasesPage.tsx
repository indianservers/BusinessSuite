import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import { useState } from 'react';
import { useMutation,useQuery,useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import { useFinanceWrite } from './useFinanceWrite';

type Source={id:number;bill_number?:string;claim_number?:string;grand_total:string;status:string};
type Profile={id:number;version:number;name:string;kind:'bill'|'expense';status:string;start_date:string;rule:string;interval:number;next_index:number;currency:string;last_error?:string;history:{date:string;record_id:number;number:string}[]};
function detail(error:unknown){const value=(error as {response?:{data?:{detail?:unknown}}})?.response?.data?.detail;return typeof value==='string'?value:'Check the source document, dates and your permissions.';}
export default function RecurringPurchasesPage(){
  const cache=useQueryClient();
  const canBill=useFinanceWrite(['fam_admin','fam_purchase_manage']);
  const canExpense=useFinanceWrite(['fam_admin','fam_expense_manage']);
  const [form,setForm]=useState({kind:'bill',source_id:'',name:'',start_date:'',rule:'monthly',interval:1,occurrences:12,never_expires:false,end_date:'',payment_terms_days:30});
  const sources=useQuery({queryKey:['fam','recurring-sources',form.kind],queryFn:async()=>(await api.get<{items:Source[]}>(`/fam/${form.kind==='bill'?'purchase-bills':'expenses'}`)).data.items});
  const profiles=useQuery({queryKey:['fam','recurring-purchases'],queryFn:async()=>(await api.get<Profile[]>('/fam/recurring-purchases')).data,refetchInterval:60000});
  const create=useMutation({mutationFn:()=>api.post('/fam/recurring-purchases',{...form,source_id:Number(form.source_id),end_date:form.never_expires?null:form.end_date||null}),onSuccess:()=>cache.invalidateQueries({queryKey:['fam','recurring-purchases']})});
  const change=useMutation({mutationFn:({row,status}:{row:Profile;status:string})=>api.put(`/fam/recurring-purchases/${row.id}/status`,{status,expected_version:row.version}),onSuccess:()=>cache.invalidateQueries({queryKey:['fam','recurring-purchases']})});
  const allowed=form.kind==='bill'?canBill:canExpense;
  return <section className="space-y-5"><h1 className="text-2xl font-semibold">Recurring bills and expenses</h1>
    <p>Create recurring drafts from an existing native bill or expense. The source lines and tax amounts are copied into the schedule. Drafts retain the normal review and posting process.</p>
    <div className="flex gap-3"><Button asChild variant="outline"><Link to="/fam/purchase-bills/new">New source bill</Link></Button><Button asChild variant="outline"><Link to="/fam/expenses/new">New source expense</Link></Button></div>
    <SmartCreateSection title="Create recurring schedule" size="standard"><form className="grid gap-3 rounded border p-4 md:grid-cols-3" onSubmit={e=>{e.preventDefault();if(allowed)create.mutate();}}>
      <label>Document type<NativeSelect className="block h-10 w-full rounded border bg-background px-3" value={form.kind} onChange={e=>setForm({...form,kind:e.target.value,source_id:''})}><option value="bill">Vendor bill</option><option value="expense">Expense</option></NativeSelect></label>
      <label>Source document<NativeSelect className="block h-10 w-full rounded border bg-background px-3" required value={form.source_id} onChange={e=>setForm({...form,source_id:e.target.value})}><option value="">Choose an existing document</option>{sources.data?.filter(s=>s.status!=='cancelled').map(s=><option key={s.id} value={s.id}>{s.bill_number||s.claim_number} · {s.grand_total}</option>)}</NativeSelect></label>
      <label>Schedule name<Input required maxLength={150} value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label>
      <label>First date<Input required type="date" value={form.start_date} onChange={e=>setForm({...form,start_date:e.target.value})}/></label>
      <label>Repeat<NativeSelect className="block h-10 w-full rounded border bg-background px-3" value={form.rule} onChange={e=>setForm({...form,rule:e.target.value})}>{['daily','weekly','monthly','quarterly','yearly'].map(rule=><option key={rule} value={rule}>{rule}</option>)}</NativeSelect></label>
      <label>Repeat interval<Input type="number" required min={1} max={120} value={form.interval} onChange={e=>setForm({...form,interval:Number(e.target.value)})}/></label>
      <label>Occurrences<Input type="number" required min={1} max={120} disabled={form.never_expires} value={form.occurrences} onChange={e=>setForm({...form,occurrences:Number(e.target.value)})}/></label>
      <label>End date<Input type="date" min={form.start_date} disabled={form.never_expires} value={form.end_date} onChange={e=>setForm({...form,end_date:e.target.value})}/></label>
      {form.kind==='bill'&&<label>Payment terms days<Input type="number" required min={0} max={365} value={form.payment_terms_days} onChange={e=>setForm({...form,payment_terms_days:Number(e.target.value)})}/></label>}
      <label className="flex items-center gap-2"><input type="checkbox" checked={form.never_expires} onChange={e=>setForm({...form,never_expires:e.target.checked})}/>Never expires</label>
      <Button disabled={!allowed||create.isPending||!form.source_id}>Create recurring schedule</Button>
    </form></SmartCreateSection>
    {sources.isError&&<p role="alert">{detail(sources.error)}</p>}{create.isError&&<p role="alert">{detail(create.error)}</p>}{create.isSuccess&&<p role="status">Recurring purchase schedule saved. Due drafts are generated by the scheduler.</p>}
    <Button variant="outline" onClick={()=>profiles.refetch()}>Refresh schedules</Button>
    {profiles.isLoading&&<p>Loading schedules...</p>}{profiles.isError&&<p role="alert">{detail(profiles.error)}</p>}{change.isError&&<p role="alert">{detail(change.error)}</p>}
    {profiles.data?.map(row=><article className="space-y-2 rounded border p-4" key={row.id}><h2 className="font-semibold">{row.name}</h2><p>{row.kind} · {row.status} · every {row.interval} {row.rule} · first {row.start_date} · {row.next_index} drafts generated · {row.currency}</p>
      {row.last_error&&<p role="alert">{row.last_error}</p>}
      <div className="flex gap-2">{row.status!=='completed'&&<><Button variant="outline" disabled={change.isPending||!(row.kind==='bill'?canBill:canExpense)} onClick={()=>change.mutate({row,status:row.status==='active'?'paused':'active'})}>{row.status==='active'?'Pause':'Resume'} {row.name}</Button><Button variant="outline" disabled={change.isPending||!(row.kind==='bill'?canBill:canExpense)} onClick={()=>change.mutate({row,status:'completed'})}>Complete {row.name}</Button></>}</div>
      <ul>{row.history.map(h=><li key={h.number}>{h.date}: <Link className="text-primary underline" to={row.kind==='bill'?`/fam/purchase-bills/${h.record_id}`:'/fam/expenses'}>{h.number}</Link></li>)}</ul>
    </article>)}{profiles.data?.length===0&&<p>No recurring purchase schedules yet.</p>}
  </section>;
}
