import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {api} from '@/services/api';
import {useRecordScope} from '@/lib/record-scope';
import {catalogError,useDebounced,type CatalogSource,type PlanConfiguration} from './api';

export type Validity={start_date:string;end_date:string|null;last_access_date:string|null;estimated:boolean;billing_timezone:string};
export function PlanDates({value,activation}:{value:Validity;activation:PlanConfiguration['activation']}){
 return <section className="sc-section cp-validity" aria-label="Plan validity preview"><h3>{value.estimated?'Example validity if first used on this date':'Validity preview'}</h3><div className="sc-preview-line"><span>{value.estimated?'Example first use':'Access starts'}</span><strong>{value.start_date}</strong></div><div className="sc-preview-line"><span>Last day with access</span><strong>{value.last_access_date||'No expiry'}</strong></div>{value.end_date&&<p className="sc-muted">Access ends at the start of {value.end_date}; that date is not included.</p>}<p className="sc-muted">Validity follows the plan service’s date-only calendar. Billing timezone: {value.billing_timezone||'Not set'}.</p>{activation==='first_use'&&<p className="sc-muted">Actual validity is calculated when first use is recorded. Assignment alone does not activate access.</p>}{activation==='approval'&&<p className="sc-muted">Approval is required for access. The validity period starts on the displayed date, even while approval is pending.</p>}</section>;
}

export function PlanTerms({plan}:{plan:PlanConfiguration}){
 const duration=plan.duration,billing=plan.billing;
 const validity=duration.unit==='lifetime'?'Lifetime access':duration.unit==='custom'?`Valid ${duration.start||'…'} to ${duration.end||'…'} (expiry excluded)`:`Valid for ${duration.count} ${duration.unit}${duration.count===1?'':'s'}`;
 const interval=billing?`${billing.interval_count} ${billing.interval_unit}${billing.interval_count===1?'':'s'}`:'';
 return <p className="sc-muted" aria-label="Validity and billing summary">{validity}. {billing?.recurring?`Billing preference: every ${interval}, ${billing.mode}. Invoices and collection are manual.`:`One-time ${billing?.mode||'prepaid'} payment terms.`}</p>;
}

export function AutomationNotice(){return <p role="note" className="sc-muted">Automatic billing, automatic renewal execution and reminder delivery are not connected. Saved preferences do not schedule invoices, collect payments or send reminders.</p>;}

export function DraftValidityPreview({source,plan}:{source:CatalogSource;plan:PlanConfiguration}){
 const scope=useRecordScope(),[start,setStart]=useState('');
 const payload=JSON.stringify({duration:plan.duration,activation:plan.activation,start_date:start||undefined,billing_timezone:plan.billing?.timezone??'UTC'}),debounced=useDebounced(payload);
 const durationValid=plan.duration.unit==='custom'?!!plan.duration.start&&!!plan.duration.end&&plan.duration.end>plan.duration.start:plan.duration.unit==='lifetime'||Number.isInteger(plan.duration.count)&&plan.duration.count>=1&&plan.duration.count<=12000;
 const ready=durationValid&&(plan.activation!=='selected_date'||!!start),settled=payload===debounced;
 const query=useQuery<Validity>({queryKey:['draft-plan-validity',scope,source,debounced],enabled:ready&&settled,retry:false,queryFn:({signal})=>api.post('/customer-plans/validity-preview',JSON.parse(debounced),{params:{source},signal,progress:false,readOnlyPreview:true}).then(r=>r.data),staleTime:30000});
 return <><label>Preview activation date<input aria-label="Preview activation date" type="date" value={start} onChange={event=>setStart(event.target.value)}/></label><p className="sc-muted">This date is an example for the plan definition; it does not assign or activate a customer plan.</p>{!ready&&<p className="sc-muted">{!durationValid?'Enter a valid duration to preview the dates.':'Choose a preview activation date.'}</p>}{ready&&(!settled||query.isFetching)&&<p role="status">Updating validity preview…</p>}{ready&&settled&&query.error&&<p className="sc-error" role="alert">{catalogError(query.error)} <button type="button" onClick={()=>void query.refetch()}>Retry preview</button></p>}{ready&&settled&&query.data&&!query.isFetching&&<PlanDates value={query.data} activation={plan.activation}/>}</>;
}
