import PipelineBoard from "./PipelineBoard";
import type { MoveGroup, MoveItem, MoveRequest } from "@/components/interaction/MoveBoard";

/** Compatibility adapter for existing task boards; domain callbacks stay unchanged. */
export default function PipelineMoveBoard({label,items,groups,onMove,disabled=false,reorder=true}:{label:string;items:MoveItem[];groups:MoveGroup[];onMove:(request:MoveRequest)=>Promise<void>;disabled?:boolean;reorder?:boolean}) {
  return <PipelineBoard label={label} disabled={disabled} reorder={reorder}
    stages={groups.map(group=>({id:group.id,name:group.label,disabled:group.disabled}))}
    records={items.map(item=>({id:String(item.id),title:item.label,stageId:item.group,disabled:item.disabled,content:item.content}))}
    onMove={async({record,stageId,beforeId})=>{
      const item=items.find(candidate=>String(candidate.id)===record.id);
      const before=items.find(candidate=>String(candidate.id)===beforeId);
      if(!item)throw new Error("This record is no longer available. Refresh the board.");
      await onMove({item,group:stageId,beforeId:before?.id});
    }}
  />;
}
