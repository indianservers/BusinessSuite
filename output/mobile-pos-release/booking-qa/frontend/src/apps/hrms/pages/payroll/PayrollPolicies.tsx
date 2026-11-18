import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, payrollApi } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from '@/hooks/use-toast';

type Rules = {
  charge_weekly_off:boolean;charge_holidays:boolean;sandwich_enabled:boolean;
  missing_attendance:'block'|'payable'|'lop';leave_conflict:'block'|'paid_wins'|'unpaid_wins';
  lop_divisor:string;proration_divisor:string;proration_basis:string;use_component_flags:boolean;
  components:Record<string,{prorate:boolean;lop:boolean}>;
};
type Version={id:number;effective_from:string;reason:string;rules:Rules};
const nextMonth=()=>{const date=new Date();return `${date.getFullYear()+(date.getMonth()===11?1:0)}-${String((date.getMonth()+1)%12+1).padStart(2,'0')}-01`;};
const divisors=[['working_days','Actual working days'],['calendar_days','Actual calendar days'],['fixed_26','Fixed 26 days'],['fixed_30','Fixed 30 days']];

export default function PayrollPolicies({canManage}:{canManage:boolean}){
  const qc=useQueryClient();
  const [group,setGroup]=useState('');const [rules,setRules]=useState<Rules|null>(null);
  const [effective,setEffective]=useState(nextMonth);const [reason,setReason]=useState('');const [code,setCode]=useState('');
  const groups=useQuery({queryKey:['payroll-pay-groups'],queryFn:()=>payrollApi.payGroups().then(r=>r.data as {id:number;name:string}[])});
  const policies=useQuery({queryKey:['payroll-policies',group],enabled:!!group,queryFn:()=>api.get(`/payroll/setup/pay-groups/${group}/policies`).then(r=>r.data as {defaults:Rules;versions:Version[]})});
  useEffect(()=>{if(policies.data)setRules(structuredClone(policies.data.versions[0]?.rules||policies.data.defaults));},[policies.data]);
  const update=<K extends keyof Rules>(key:K,value:Rules[K])=>setRules(previous=>previous?{...previous,[key]:value}:previous);
  const publish=useMutation({mutationFn:()=>api.post(`/payroll/setup/pay-groups/${group}/policies`,{effective_from:effective,reason,rules}),onSuccess:()=>{void qc.invalidateQueries({queryKey:['payroll-policies',group]});toast({title:'Payroll policy version published'});},onError:(error:any)=>toast({title:'Policy could not be published',description:typeof error.response?.data?.detail==='string'?error.response.data.detail:'Check the effective month and configuration.',variant:'destructive'})});
  return <div className="space-y-4">
    <Card><CardHeader><CardTitle>Payroll Policies</CardTitle></CardHeader><CardContent className="space-y-3">
      <p className="text-sm text-muted-foreground">Publish policies per pay group from a new effective month. Versions and calculated-run snapshots are retained. Groups without a published policy keep their existing calculations.</p>
      <label className="block space-y-1">Policy pay group<NativeSelect aria-label="Policy pay group" value={group} onChange={event=>{setGroup(event.target.value);setRules(null);}} className="h-10 w-full rounded border p-2"><option value="">Select pay group</option>{groups.data?.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</NativeSelect></label>
      {policies.isError&&<p role="alert">Could not load policy versions. <Button onClick={()=>void policies.refetch()}>Retry policies</Button></p>}
      {!group&&<p className="text-sm">Create a pay group in Setup Wizard if needed, then select it here.</p>}
    </CardContent></Card>
    {group&&rules&&<>
      <Card><CardHeader><CardTitle>Attendance and leave</CardTitle></CardHeader><CardContent className="grid gap-4 sm:grid-cols-2">
        <label className="flex items-center gap-2"><input type="checkbox" checked={rules.charge_weekly_off} disabled={!canManage} onChange={e=>update('charge_weekly_off',e.target.checked)}/>Charge approved unpaid leave on weekly offs</label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={rules.charge_holidays} disabled={!canManage} onChange={e=>update('charge_holidays',e.target.checked)}/>Charge approved unpaid leave on holidays</label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={rules.sandwich_enabled} disabled={!canManage} onChange={e=>update('sandwich_enabled',e.target.checked)}/>Enable sandwich leave</label>
        <p className="text-sm text-muted-foreground">Sandwich leave charges intervening nonworking days only when the scheduled working days on both sides have approved full-day unpaid leave. Half-days do not trigger it.</p>
        <label>Missing attendance<NativeSelect aria-label="Missing attendance policy" value={rules.missing_attendance} disabled={!canManage} onChange={e=>update('missing_attendance',e.target.value as Rules['missing_attendance'])} className="h-10 w-full rounded border p-2"><option value="block">Block payroll approval</option><option value="payable">Payable, flag for review</option><option value="lop">Treat missing time as LOP</option></NativeSelect></label>
        <label>Conflicting leave<NativeSelect aria-label="Conflicting leave policy" value={rules.leave_conflict} disabled={!canManage} onChange={e=>update('leave_conflict',e.target.value as Rules['leave_conflict'])} className="h-10 w-full rounded border p-2"><option value="block">Block until HR resolves</option><option value="paid_wins">Paid leave / attendance takes precedence</option><option value="unpaid_wins">Approved unpaid leave takes precedence</option></NativeSelect></label>
        <p className="text-sm text-muted-foreground sm:col-span-2">Force Approve cannot bypass policy blockers. Resolve attendance or conflicting requests and regenerate. An approved manual attendance input requires an audited resolution note to resolve missing attendance.</p>
      </CardContent></Card>
      <Card><CardHeader><CardTitle>Salary divisors</CardTitle></CardHeader><CardContent className="grid gap-4 sm:grid-cols-3">
        <label>LOP divisor<NativeSelect aria-label="LOP divisor" value={rules.lop_divisor} disabled={!canManage} onChange={e=>update('lop_divisor',e.target.value)} className="h-10 w-full rounded border p-2">{divisors.map(([value,label])=><option key={value} value={value}>{label}</option>)}</NativeSelect></label>
        <label>Joining and exit divisor<NativeSelect aria-label="Joining and exit divisor" value={rules.proration_divisor} disabled={!canManage} onChange={e=>update('proration_divisor',e.target.value)} className="h-10 w-full rounded border p-2">{divisors.map(([value,label])=><option key={value} value={value}>{label}</option>)}</NativeSelect></label>
        <label>Proration day basis<NativeSelect aria-label="Proration day basis" value={rules.proration_basis} disabled={!canManage} onChange={e=>update('proration_basis',e.target.value)} className="h-10 w-full rounded border p-2"><option value="calendar_days">Employed calendar days</option><option value="working_days">Employed working days</option></NativeSelect></label>
        <p className="text-sm text-muted-foreground sm:col-span-3">Full-month employment always receives the full monthly amount before LOP. Partial employment is capped at 100%. Fixed/calendar LOP uses the full monthly rate; working-day LOP spreads prorated earnings over the employed working days.</p>
      </CardContent></Card>
      <Card><CardHeader><CardTitle>Component treatment</CardTitle></CardHeader><CardContent className="space-y-4">
        <label className="flex items-center gap-2"><input type="checkbox" checked={rules.use_component_flags} disabled={!canManage} onChange={e=>update('use_component_flags',e.target.checked)}/>Use assigned salary-component proration and LOP settings</label>
        <p className="text-sm text-muted-foreground">Unconfigured assigned earnings block approval. The mappings below apply to built-in earnings and extras, or to component codes when component settings are disabled. Reimbursements and incentives are excluded by default.</p>
        {Object.entries(rules.components).map(([name,value])=><div key={name} className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b pb-3"><strong className="w-full text-sm sm:w-40">{name.replace(/_/g,' ')}</strong><label className="flex items-center gap-2"><input type="checkbox" aria-label={`${name} prorate`} checked={value.prorate} disabled={!canManage} onChange={e=>update('components',{...rules.components,[name]:{...value,prorate:e.target.checked}})}/>Prorate joining / exit</label><label className="flex items-center gap-2"><input type="checkbox" aria-label={`${name} LOP`} checked={value.lop} disabled={!canManage} onChange={e=>update('components',{...rules.components,[name]:{...value,lop:e.target.checked}})}/>Reduce for LOP</label></div>)}
        {canManage&&<div className="flex flex-wrap gap-2"><Input aria-label="Additional component code" placeholder="Additional component code" value={code} onChange={e=>setCode(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g,''))} className="max-w-xs"/><Button disabled={!code||!!rules.components[code]} onClick={()=>{update('components',{...rules.components,[code]:{prorate:true,lop:true}});setCode('');}}>Add component mapping</Button></div>}
      </CardContent></Card>
      <Card><CardHeader><CardTitle>Publish a policy version</CardTitle></CardHeader><CardContent className="space-y-4">
        <label className="block">Effective from<Input aria-label="Policy effective from" type="date" value={effective} disabled={!canManage} onChange={e=>setEffective(e.target.value)} className="max-w-xs"/></label>
        <label className="block">Change reason<Input aria-label="Policy change reason" value={reason} disabled={!canManage} onChange={e=>setReason(e.target.value)} placeholder="Why this policy is being introduced or changed" maxLength={1000}/></label>
        <Button disabled={!canManage||publish.isPending||reason.trim().length<3||!effective} onClick={()=>publish.mutate()}>{publish.isPending?'Publishing policy…':'Publish payroll policy'}</Button>
        <p className="text-sm text-muted-foreground">Use the first day of a month later than any existing payroll for this group. Existing versions cannot be edited or backdated over generated payroll.</p>
      </CardContent></Card>
      {!!policies.data?.versions.length&&<Card><CardHeader><CardTitle>Policy version history</CardTitle></CardHeader><CardContent><ul className="space-y-3">{policies.data.versions.map(version=><li key={version.id} className="border-b pb-3"><strong>Version {version.id} · {version.effective_from}</strong><p className="text-sm">{version.reason}</p></li>)}</ul></CardContent></Card>}
    </>}
  </div>;
}
