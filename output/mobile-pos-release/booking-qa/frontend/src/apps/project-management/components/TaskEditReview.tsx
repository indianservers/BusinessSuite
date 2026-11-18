import {Button} from "@/components/ui/button";
import {RichTextContent} from "@/components/rich-text/LazyRichText";

const labels:Record<string,string>={description:"Description",status:"Status",priority:"Priority",assignee_user_ids:"Assignees",estimated_hours:"Estimated hours",start_date:"Start date",due_date:"Due date"};

/** Presentation only: callers own the permission checks, snapshots and mutations. */
export default function TaskEditReview({changes,latest,busy,canEdit,people,onReview,onApply,onDiscard}:{
 changes:Record<string,unknown>;latest?:Record<string,unknown>;busy:boolean;canEdit:boolean;
 people:{id:number;name:string}[];onReview:()=>void;onApply:()=>void;onDiscard:()=>void;
}){
 const display=(field:string,value:unknown)=>field==="assignee_user_ids"&&Array.isArray(value)
  ?value.map(id=>people.find(person=>person.id===id)?.name||`Person #${id}`).join(", ")||"Unassigned"
  :value==null||value===""?"Not set":String(value);
 return <section aria-label="Review task update" className="my-3 space-y-3 rounded-lg border border-amber-300 bg-background p-3 text-sm">
  <h3 className="font-semibold">Your task changes are retained</h3>
  <p>The update was not confirmed. Review the latest saved values before retrying or discarding your changes.</p>
  <Button type="button" variant="outline" disabled={busy} onClick={onReview}>Review latest task</Button>
  {latest&&<><div className="space-y-3">{Object.entries(changes).map(([field,value])=><div key={field} className="min-w-0 rounded border p-2">
   <h4 className="font-medium">{labels[field]||field.replace(/_/g," ")}</h4>
   <div className="mt-1 grid min-w-0 gap-2 sm:grid-cols-2">{[["Latest saved value",latest[field]],["Your attempted value",value]].map(([label,item])=><div key={String(label)} className="min-w-0 break-words"><p className="text-xs text-muted-foreground">{String(label)}</p>{field==="description"?<RichTextContent value={String(item||"")}/>:<p>{display(field,item)}</p>}</div>)}</div>
  </div>)}</div><div className="flex flex-wrap gap-2"><Button type="button" disabled={busy||!canEdit} onClick={onApply}>Apply reviewed changes</Button><Button type="button" variant="outline" disabled={busy} onClick={onDiscard}>Discard local changes and use latest</Button></div><p className="text-xs text-muted-foreground">A further server change will require another review.</p></>}
 </section>;
}
