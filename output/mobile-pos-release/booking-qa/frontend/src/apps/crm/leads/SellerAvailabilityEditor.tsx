import {Input} from '@/components/ui/input';
import {NativeSelect} from '@/components/ui/native-select';
import type {Settings,SellerAvailability} from './api';

const days=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
function time(value:number){return `${String(Math.floor(value/60)).padStart(2,'0')}:${String(value%60).padStart(2,'0')}`;}
export default function SellerAvailabilityEditor({assignment,owners,onChange}:{
  assignment:Settings['assignment'];owners:{id:number;name:string}[];onChange:(value:SellerAvailability[])=>void;
}){
  const selected=new Set([...assignment.ownerIds,...assignment.rules.map(r=>r.ownerId)]);
  const policies=assignment.availability||[];
  function update(ownerId:number,patch:Partial<SellerAvailability>){
    onChange(policies.map(p=>p.ownerId===ownerId?{...p,...patch}:p));
  }
  return <section className="lm-section"><h3>Working hours & capacity</h3>
    <p>Optional limits apply to automatic distribution and matching assignment rules. If no eligible seller is available, the lead remains unassigned for team review. Working hours use each seller’s time zone. Choose a start and end within the same local day.</p>
    {owners.filter(o=>selected.has(o.id)||policies.some(p=>p.ownerId===o.id)).map(owner=>{
      const policy=policies.find(p=>p.ownerId===owner.id);
      return <div key={owner.id} className="rounded border p-3 space-y-2">
        <label className="lm-check"><input type="checkbox" checked={!!policy} onChange={e=>onChange(e.target.checked?[...policies,{ownerId:owner.id,enabled:true,timezone:'Asia/Kolkata',days:[0,1,2,3,4],startMinute:540,endMinute:1080,maxActiveLeads:null}]:policies.filter(p=>p.ownerId!==owner.id))}/>{owner.name}: use working hours or capacity</label>
        {policy&&<><label className="lm-check"><input type="checkbox" checked={policy.enabled} onChange={e=>update(owner.id,{enabled:e.target.checked})}/> Available for automatic assignment</label>
          {!selected.has(owner.id)&&<p>Re-select this owner for distribution or a rule, or remove this availability policy.</p>}
          <label>Time zone<Input value={policy.timezone} onChange={e=>update(owner.id,{timezone:e.target.value})}/></label>
          <div className="flex flex-wrap gap-3" role="group" aria-label={`${owner.name} working days`}>{days.map((day,index)=><label key={day}><input type="checkbox" checked={policy.days.includes(index)} onChange={e=>update(owner.id,{days:e.target.checked?[...policy.days,index].sort():policy.days.filter(d=>d!==index)})}/>{day}</label>)}</div>
          <div className="grid gap-3 sm:grid-cols-2">{(['startMinute','endMinute'] as const).map(field=>{
            const options=Array.from({length:48},(_,i)=>(i+(field==='endMinute'?1:0))*30);
            if(!options.includes(policy[field]))options.push(policy[field]);options.sort((a,b)=>a-b);
            return <label key={field}>{field==='startMinute'?'Shift starts':'Shift ends'}<NativeSelect value={policy[field]} onChange={e=>update(owner.id,{[field]:Number(e.target.value)})}>{options.map(minute=><option key={minute} value={minute}>{time(minute)}</option>)}</NativeSelect></label>;
          })}</div>
          <label>Maximum active leads (blank for unlimited)<Input type="number" min={1} max={100000} value={policy.maxActiveLeads??''} onChange={e=>update(owner.id,{maxActiveLeads:e.target.value?Number(e.target.value):null})}/></label>
        </>}
      </div>;
    })}
  </section>;
}
