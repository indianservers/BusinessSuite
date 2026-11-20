import {displayDate,defaultText} from '@/lib/form-defaults';
import type {PlanConfiguration} from './api';
export type PlanBenefit={id:number;key:string;label:string;type:string;remaining:number|string|null;allowance:number|string|null};
export type PlanRecord={id:number;offering_id:number;number:string;name:string;tier:string;kind:string;status:string;display_status:string;status_description:string;start_date:string;end_date:string|null;server_date:string;revision:number;configuration:PlanConfiguration;beneficiaries:number[];benefit_summary:PlanBenefit[]};
export function planDate(value:string|null){return value?displayDate(value):'Lifetime';}
export function planTime(value:string,zone:string){try{return new Intl.DateTimeFormat(defaultText('number_format')||'en-IN',{dateStyle:'medium',timeStyle:'short',timeZone:zone}).format(new Date(/(?:Z|[+-]\d\d:\d\d)$/.test(value)?value:value+'Z'));}catch{return value;}}
export function stateLabel(value:string){return ({awaiting_first_use:'Awaiting first use',pending_approval:'Pending approval',scheduled:'Scheduled',active:'Active',paused:'Paused',suspended:'Suspended',expired:'Expired',cancelled:'Cancelled'} as Record<string,string>)[value]||value;}
export function BenefitBalance({benefit}:{benefit:PlanBenefit}){
 const remaining=benefit.remaining===null?null:Number(benefit.remaining),total=benefit.allowance===null?null:Number(benefit.allowance);
 const units=({sessions:'sessions',credits:'credits',seats:'seats',discount_percent:'redemptions',discount_fixed:'redemptions',special_price:'redemptions'} as Record<string,string>)[benefit.type]||'uses';
 return <div className="cp-balance"><div className="cp-balance-heading"><span>{benefit.label}</span><strong>{remaining===null?'Unlimited':`${remaining} of ${total??'recorded allowance'} ${units} remaining`}</strong></div>{remaining!==null&&total!==null&&total>0?<progress aria-label={`${benefit.label} remaining`} max={total} value={Math.min(total,Math.max(0,remaining))}/>:<span className="cp-balance-note">{remaining===null?'No usage limit':'No allowance available'}</span>}</div>;
}
export function PlanSummary({plan,balances=true,compact=false}:{plan:PlanRecord;balances?:boolean;compact?:boolean}){
 const renewal=plan.configuration.renewal?.mode==='automatic'?'Automatic preference saved; execution unavailable':'Manual';
 if(compact)return <div className="cp-row-summary"><span className="cp-state" data-state={plan.display_status}>{stateLabel(plan.display_status)}</span><span title={plan.end_date||'Lifetime'}>{plan.end_date?`Until ${planDate(plan.end_date)}`:'Lifetime access'}</span></div>;
 return <><div className="cp-summary-grid"><div><span>Status</span><strong className="cp-state" data-state={plan.display_status}>{stateLabel(plan.display_status)}</strong></div><div><span>Access period</span><strong><time title={plan.start_date}>{planDate(plan.start_date)}</time> – <time title={plan.end_date||'Lifetime'}>{planDate(plan.end_date)}</time></strong><small>{plan.end_date?'Expiry date excluded':'No expiry'}</small></div><div><span>Renewal</span><strong>Renewal: {renewal}</strong></div><div><span>Billing timezone</span><strong>{plan.configuration.billing?.timezone||'UTC'}</strong></div></div><p className="cp-state-description">{plan.status_description}</p>{balances&&plan.benefit_summary.map(b=><BenefitBalance key={b.id} benefit={b}/>)}</>;
}
