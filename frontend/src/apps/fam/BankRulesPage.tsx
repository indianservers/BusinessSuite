import {SmartCreateSection} from "@/shared/creation/SmartCreateSection";
import {useMobile} from "@/components/mobile/useMobile";
import {MobileDisclosure} from "@/components/mobile/MobilePrimitives";
import "./fam-mobile-workflows.css";
import {useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {Link} from 'react-router-dom';
import {api} from '@/services/api';
import {Input} from '@/components/ui/input';
import {Button} from '@/components/ui/button';
import {NativeSelect} from '@/components/ui/native-select';
import {useFinanceWrite} from './useFinanceWrite';
type Form={name:string;bank_account_id:string;direction:string;field:string;operator:string;text:string;counter_ledger_id:string;minimum:string;maximum:string;priority:number;active:boolean};
type Rule=Omit<Form,'bank_account_id'|'counter_ledger_id'|'minimum'|'maximum'> & {id:number;version:number;bank_account_id:number;counter_ledger_id:number;minimum:string|null;maximum:string|null};
type Suggestion={line_id:number;line_hash:string;date:string;description:string;amount:string;rule_id:number;rule_version:number;rule_name:string;counter_ledger_id:number};
const blank:Form={name:'',bank_account_id:'',direction:'withdrawal',field:'description',operator:'contains',text:'',counter_ledger_id:'',minimum:'',maximum:'',priority:100,active:true};
function message(error:unknown){const d=(error as {response?:{data?:{detail?:unknown}}})?.response?.data?.detail;return typeof d==='string'?d:'Check the rule, accounts and permissions.';}
export default function BankRulesPage(){
  const phone=useMobile(480);
  const cache=useQueryClient();const canManage=useFinanceWrite(['fam_admin','fam_banking_manage']);
  const canPost=useFinanceWrite(['fam_admin','fam_vouchers_post']);const canReconcile=useFinanceWrite(['fam_admin','fam_bank_reconcile']);
  const [form,setForm]=useState<Form>(blank);const [editing,setEditing]=useState<Rule|null>(null);const [statement,setStatement]=useState('');
  const rules=useQuery({queryKey:['fam','bank-rules'],queryFn:async()=>(await api.get<Rule[]>('/fam/bank-rules')).data});
  const banks=useQuery({queryKey:['fam','bankAccounts'],queryFn:async()=>(await api.get<{items:{id:number;bank_name:string;account_number_masked:string}[]}>('/fam/bank-accounts')).data.items});
  const ledgers=useQuery({queryKey:['fam','bank-rule-options'],queryFn:async()=>(await api.get<{ledgers:{id:number;ledger_name:string;nature:string;ledger_type:string;active:boolean}[]}>('/fam/bank-rules/options')).data.ledgers});
  const statements=useQuery({queryKey:['fam','bankStatements'],queryFn:async()=>(await api.get<{items:{id:number;bank_account_id:number;imported_file_name:string}[]}>('/fam/bank-statements')).data.items});
  const preview=useQuery({queryKey:['fam','bank-rule-preview',statement],enabled:!!statement,queryFn:async()=>(await api.get<{suggestions:Suggestion[]}>(`/fam/bank-rules/statements/${statement}/preview`)).data.suggestions});
  const save=useMutation({mutationFn:()=>{const body={...form,bank_account_id:Number(form.bank_account_id),counter_ledger_id:Number(form.counter_ledger_id),minimum:form.minimum||null,maximum:form.maximum||null,expected_version:editing?.version||0};return editing?api.put(`/fam/bank-rules/${editing.id}`,body):api.post('/fam/bank-rules',body);},onSuccess:()=>{setEditing(null);setForm(blank);cache.invalidateQueries({queryKey:['fam','bank-rules']});cache.invalidateQueries({queryKey:['fam','bank-rule-preview']});}});
  const apply=useMutation({mutationFn:(row:Suggestion)=>api.post<{voucher_id:number}>(`/fam/bank-rules/lines/${row.line_id}/apply`,{rule_id:row.rule_id,expected_version:row.rule_version,line_hash:row.line_hash}),onSuccess:()=>{cache.invalidateQueries({queryKey:['fam','bank-rule-preview']});cache.invalidateQueries({queryKey:['fam','bankStatements']});}});
  const ruleActions=<><Button disabled={!canManage||save.isPending}>{editing?'Save rule changes':'Create rule'}</Button>{editing&&<Button type="button" variant="outline" onClick={()=>{setEditing(null);setForm(blank);}}>Cancel editing</Button>}</>;
  const accountName=(id:number)=>ledgers.data?.find(l=>l.id===id)?.ledger_name||String(id);
  return <section className="space-y-5 fam-mobile-bank-rules"><h1 className="text-2xl font-semibold">Bank transaction rules</h1><p>Preview and categorize simple expense withdrawals or income deposits. Applying a reviewed suggestion posts a native voucher and confirms its reconciliation match. Use the existing tax and customer/vendor workflows for tax splits and settlements.</p>
    <SmartCreateSection title={editing ? "Edit bank rule" : "Create bank rule"} autoOpen={!!editing} onClose={() => setEditing(null)}><form className="grid gap-3 rounded border p-4 md:grid-cols-3 fam-bank-rule-form" onSubmit={e=>{e.preventDefault();if(canManage)save.mutate();}}>
      <label>Rule name<Input required maxLength={150} value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label>
      <label>Bank account<NativeSelect className="block h-10 w-full rounded border bg-background px-3" required value={form.bank_account_id} onChange={e=>setForm({...form,bank_account_id:e.target.value})}><option value="">Select bank</option>{banks.data?.map(b=><option value={b.id} key={b.id}>{b.bank_name} · {b.account_number_masked}</option>)}</NativeSelect></label>
      <label>Direction<NativeSelect className="block h-10 w-full rounded border bg-background px-3" value={form.direction} onChange={e=>setForm({...form,direction:e.target.value,counter_ledger_id:''})}><option value="withdrawal">Withdrawal</option><option value="deposit">Deposit</option></NativeSelect></label>
      <label>Match field<NativeSelect className="block h-10 w-full rounded border bg-background px-3" value={form.field} onChange={e=>setForm({...form,field:e.target.value})}><option value="description">Description</option><option value="reference_number">Reference</option></NativeSelect></label>
      <label>Condition<NativeSelect className="block h-10 w-full rounded border bg-background px-3" value={form.operator} onChange={e=>setForm({...form,operator:e.target.value})}><option value="contains">Contains</option><option value="equals">Equals</option><option value="starts_with">Starts with</option></NativeSelect></label>
      <label>Matching text<Input required maxLength={200} value={form.text} onChange={e=>setForm({...form,text:e.target.value})}/></label>
      <label>Counter account<NativeSelect className="block h-10 w-full rounded border bg-background px-3" required value={form.counter_ledger_id} onChange={e=>setForm({...form,counter_ledger_id:e.target.value})}><option value="">Choose account</option>{ledgers.data?.filter(l=>l.active&&l.nature===(form.direction==='withdrawal'?'expense':'income')&&!['tax','bank','cash','customer','vendor'].includes(l.ledger_type)).map(l=><option value={l.id} key={l.id}>{l.ledger_name}</option>)}</NativeSelect></label>
      <MobileDisclosure maxWidth={480} title={`Amount limits & priority: ${form.minimum || "No min"} / ${form.maximum || "No max"}, priority ${form.priority}`}>
      <label>Minimum amount<Input type="number" min={0} step="0.01" value={form.minimum} onChange={e=>setForm({...form,minimum:e.target.value})}/></label>
      <label>Maximum amount<Input type="number" min={form.minimum||0} step="0.01" value={form.maximum} onChange={e=>setForm({...form,maximum:e.target.value})}/></label>
      <label>Priority (lower first)<Input type="number" min={1} max={999} value={form.priority} onChange={e=>setForm({...form,priority:Number(e.target.value)})}/></label>
      </MobileDisclosure>
      <label className="flex items-center gap-2"><input type="checkbox" checked={form.active} onChange={e=>setForm({...form,active:e.target.checked})}/>Active</label>
      {phone?<div className="fam-bank-rule-actions" role="group" aria-label="Bank rule actions">{ruleActions}</div>:ruleActions}
    </form>{save.isError&&<p role="alert">{message(save.error)}</p>}{save.isSuccess&&<p role="status">Bank rule saved.</p>}</SmartCreateSection>
    {rules.data?.map(r=><article className="flex flex-wrap items-center justify-between gap-3 rounded border p-3" key={r.id}><div><h2 className="font-semibold">{r.name}</h2><p>{r.active?'Active':'Inactive'} · priority {r.priority} · {r.field} {r.operator} “{r.text}” → {accountName(r.counter_ledger_id)}</p></div><Button variant="outline" disabled={!canManage} onClick={()=>{setEditing(r);setForm({...r,bank_account_id:String(r.bank_account_id),counter_ledger_id:String(r.counter_ledger_id),minimum:r.minimum||'',maximum:r.maximum||''});}}>Edit {r.name}</Button></article>)}
    <h2 className="text-lg font-semibold">Review statement suggestions</h2><label>Bank statement<NativeSelect className="block h-10 rounded border bg-background px-3" value={statement} onChange={e=>setStatement(e.target.value)}><option value="">Select imported statement</option>{statements.data?.map(s=><option key={s.id} value={s.id}>{s.imported_file_name}</option>)}</NativeSelect></label><Button variant="outline" disabled={!statement||preview.isFetching} onClick={()=>preview.refetch()}>Refresh suggestions</Button>
    {[rules.error,banks.error,ledgers.error,statements.error,preview.error,apply.error].filter(Boolean).map((error,index)=><p role="alert" key={index}>{message(error)}</p>)}
    {preview.data?.map(row=><article className="space-y-2 rounded border p-3" key={row.line_id}><p>{row.date} · {row.description} · {row.amount}</p><p>{row.rule_name} → {accountName(row.counter_ledger_id)}</p><Button disabled={!canManage||!canPost||!canReconcile||apply.isPending} onClick={()=>apply.mutate(row)}>Apply rule and post</Button></article>)}
    {preview.data?.length===0&&<p>No unmatched statement lines qualify for the active rules.</p>}{apply.data&&<p role="status">Categorized and reconciled. <Button asChild variant="outline"><Link className="text-primary underline" to={`/fam/vouchers/${apply.data.data.voucher_id}`}>Open voucher</Link></Button></p>}
  </section>;
}
