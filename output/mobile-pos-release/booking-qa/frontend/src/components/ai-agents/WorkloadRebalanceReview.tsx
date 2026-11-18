export type RebalanceReview = {
 project_id:number;source_sha256:string;limitations:string[];
 changes:{task_id:number;before_assignee_user_ids:number[];after_assignee_user_ids:number[];
 weeks:{week_start:string;moved_hours:number;source_before_hours:number;source_after_hours:number;
 target_before_hours:number;target_after_hours:number;target_snapshot_capacity_hours:number}[]}[];
};
type Step={tool:string;record_id?:unknown;payload:Record<string,unknown>};

export default function WorkloadRebalanceReview({review,steps}:{review?:RebalanceReview;steps?:Step[]}){
 if(!review)return null;
 const step=steps?.find(item=>item.tool==='pms.task_plan'&&item.record_id===review.project_id);
 const guard=step?.payload.workload_guard as {source_sha256?:string;start?:string;weeks?:number;scope?:string}|undefined;
 const plan=step?.payload.plan as {steps?:{tool:string;task_id:number;changes?:{assignee_user_ids?:number[]}}[]}|undefined;
 const sameIds=(a:number[],b:number[])=>a.length===b.length&&[...a].sort((x,y)=>x-y).every((id,index)=>id===[...b].sort((x,y)=>x-y)[index]);
 if(guard?.source_sha256!==review.source_sha256||plan?.steps?.length!==review.changes.length||
   !review.changes.every(change=>plan.steps?.some(item=>item.tool==='update_task'&&item.task_id===change.task_id&&
      Object.keys(item.changes||{}).length===1&&
      sameIds(item.changes?.assignee_user_ids||[],change.after_assignee_user_ids))))return null;
 return <section className="bot-result-card" aria-label="Workload rebalance review">
  <h3>Review workload rebalancing</h3>
  <p>Project #{review.project_id} · {guard.scope} workload · {guard.weeks} week(s) from {guard.start}</p>
  <p>These are proposed estimates. Approval is required; execution receipts confirm assignment changes.</p>
  {review.changes.map(change=><section key={change.task_id} aria-label={`Task ${change.task_id} workload changes`}>
   <h4>Task #{change.task_id}</h4>
   <p>Current assignees: {change.before_assignee_user_ids.map(id=>`#${id}`).join(', ')||'Unassigned'}</p>
   <p>Proposed assignees: {change.after_assignee_user_ids.map(id=>`#${id}`).join(', ')||'Unassigned'}</p>
   {change.weeks.map(week=><div key={week.week_start}>
    <strong>Week of {week.week_start} · move {week.moved_hours} estimated hours</strong>
    <p>Source load: {week.source_before_hours} → {week.source_after_hours} hours</p>
    <p>Recipient load: {week.target_before_hours} → {week.target_after_hours} hours; snapshot capacity {week.target_snapshot_capacity_hours} hours</p>
   </div>)}
  </section>)}
  {review.limitations.map(note=><p key={note} className="text-sm text-slate-500">{note}</p>)}
 </section>;
}
