import type {ReactNode} from "react";
import "./task-property-strip.css";

/** Shared placement only; callers retain their permissions and mutation handlers. */
export default function TaskPropertyStrip({status,assignees,priority,estimate,start,due,className=""}:{status:ReactNode;assignees:ReactNode;priority:ReactNode;estimate:ReactNode;start:ReactNode;due:ReactNode;className?:string}) {
  const fields = [["Status",status],["Assignees",assignees],["Priority",priority],["Estimated hours",estimate],["Start date",start],["Due date",due]] as const;
  return <div role="group" aria-label="Task properties" className={`pms-task-properties grid min-w-0 gap-3 border-y py-3 ${className}`} style={{gridTemplateColumns:"repeat(auto-fit,minmax(min(100%,9rem),1fr))"}}>{fields.map(([label,control])=><div key={label} className="min-w-0 space-y-1 text-sm"><span className="block text-xs font-medium text-muted-foreground">{label}</span>{control}</div>)}</div>;
}
