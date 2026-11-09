import { Children, cloneElement, isValidElement, type ReactNode, type ReactElement } from "react";
import { useLocation } from "react-router-dom";
import { resourcePath } from "@/lib/record-changes";
import { gridCellText, gridHeaderText } from "@/shared/data-grid/cell-content";
import { useRecordSync, type SyncItem } from "./store";
import { SyncRing } from "./RecordSyncItems";
const nodes=(children:ReactNode)=>Children.toArray(children).filter(isValidElement) as ReactElement<Record<string,any>>[];
const fieldKey=(value:string)=>value.toLowerCase().replace(/[^a-z0-9]/g,"");
function field(patch:Record<string,unknown>,label:string){const wanted=fieldKey(label),aliases:Record<string,string[]>={name:["name","fullname","title"],employee:["fullname","employeename","name"],task:["title","taskname","name"],project:["name","title"],company:["companyname","name"],customer:["customername","name"],email:["email","emailaddress"],phone:["phone","phonenumber","mobile"],priority:["priority"],status:["status","stage"]};return Object.entries(patch).find(([key])=>(aliases[wanted]||[wanted]).includes(fieldKey(key)));}
function applies(item:SyncItem,hint:string,gridId:string){if(hint===item.resource||hint.startsWith(item.resource+"/"))return true;const collection=item.resource.split("/").pop()||"";const module=item.resource.split("/")[1];const moduleMatch=hint.split("/")[1]===module||module!=="fam"&&hint.startsWith("/employees")&&module==="employees";return moduleMatch&&gridId.toLowerCase().includes(collection);}
/** Project local mutations into legacy React table cells while retaining their handlers. */
export function useSyncedTable(children:ReactNode,gridId:string){
 const entries=useRecordSync(),location=useLocation(),hint=resourcePath(new URLSearchParams(location.search).get("operation")||location.pathname);
 const updates=entries.filter(item=>["pending","saved"].includes(item.phase)&&item.operation!=="create"&&applies(item,hint,gridId));
 if(!updates.length)return children;
 const sections=nodes(children),head=nodes(sections.find(section=>section.type==="thead")?.props.children)[0];const labels=nodes(head?.props.children).map(cell=>gridHeaderText(cell.props.children));
 return Children.map(children,section=>{if(!isValidElement<Record<string,any>>(section)||section.type!=="tbody")return section;return cloneElement(section,{},Children.map(section.props.children,(row,index)=>{
  if(!isValidElement<Record<string,any>>(row)||row.type!=="tr")return row;
  const key=String(row.key??index).replace(/^\.\$/,"");const update=[...updates].reverse().find(item=>item.ids.map(String).includes(key));if(!update)return row;if(update.operation==="delete")return null;
  let marked=false;return cloneElement(row,{"data-syncing":"true"},Children.map(row.props.children,(cell,column)=>{if(!isValidElement<Record<string,any>>(cell))return cell;const label=labels[column]||"",changed=field(update.patch,label);const original=changed?String(changed[1]??""):cell.props.children;const identity=!marked&&!/^(select|actions?|favorites?)$/i.test(label)&&!!gridCellText(cell.props.children).trim();if(identity)marked=true;return cloneElement(cell,{},<>{identity&&update.phase==="pending"&&<span className="record-sync-row-marker"><SyncRing item={update}/></span>}{original}</>);}));
 }));});
}
