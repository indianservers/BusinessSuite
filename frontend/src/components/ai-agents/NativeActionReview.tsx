type Changes=Record<string,{record_id:number;record_name?:string;project_id?:number;changes:{field:string;before:unknown;after:unknown}[]}>;

export default function NativeActionReview({label,title,entity,changes}:{label:string;title:string;entity:string;changes?:Changes}){
 if(!Object.keys(changes||{}).length)return null;
 return <section className="bot-result-card" aria-label={label}><h3>{title}</h3><p>Current values were checked when this draft was prepared. Proposed values require separate approval; execution receipts confirm completion.</p>{Object.entries(changes||{}).map(([step,target])=><section key={step} aria-label={`${entity} ${target.record_id} proposed changes`}><h4 className="break-words">Step {step} · {entity} #{target.record_id}{target.record_name?` · ${target.record_name}`:''}</h4>{target.project_id&&<p>Project #{target.project_id}</p>}{target.changes.map(change=><div key={change.field} className="break-words whitespace-pre-wrap"><strong>{change.field.replace(/_/g,' ')}</strong><p>Current: {change.before==null?'Not set':String(change.before)}</p><p>Proposed: {change.after==null?'Not set':String(change.after)}</p></div>)}</section>)}</section>;
}
