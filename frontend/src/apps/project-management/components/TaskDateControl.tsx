import {Input} from "@/components/ui/input";

export default function TaskDateControl({label,value,disabled,onSave}:{label:string;value?:string|null;disabled:boolean;onSave:(value:string|null)=>unknown}){
 return <div className="min-w-0 space-y-1">
  <Input aria-label={label} type="date" disabled={disabled} value={value||""} onChange={event=>{void onSave(event.target.value||null);}}/>
  {value&&<button type="button" aria-label={`Clear ${label.replace(/^Task /,"").toLowerCase()}`} disabled={disabled} className="min-h-6 text-xs underline disabled:opacity-50" onClick={()=>{void onSave(null);}}>Clear date</button>}
 </div>;
}
