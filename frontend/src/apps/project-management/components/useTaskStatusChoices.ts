import {useState} from "react";
import {api} from "@/services/api";
import {useRefreshableEffect} from "@/lib/page-refresh";
import {workspaceError} from "../pages/workspaceTypes";

export type TaskStatusChoices={can_request:boolean;transitions:{target:string;approval_required:boolean}[];requests:{target:string;current:boolean;status:string}[]};
export const taskStatusNeedsReview=(data:TaskStatusChoices|undefined,target:string)=>!!data?.transitions.find(item=>item.target===target)?.approval_required&&!data.requests.some(request=>request.target===target&&request.current&&request.status==="Approved");

/** Existing workflow projection, loaded only while the calling editor/menu is active. */
export function useTaskStatusChoices({taskId,value,version,refreshKey,enabled=true}:{taskId:number;value:string;version?:string|null;refreshKey?:number;enabled?:boolean}){
 const [data,setData]=useState<TaskStatusChoices>(),[loading,setLoading]=useState(enabled),[error,setError]=useState(""),[retry,setRetry]=useState(0);
 useRefreshableEffect(()=>{
  let active=true;setError("");setData(undefined);setLoading(enabled);
  if(!enabled)return;
  void api.get<TaskStatusChoices>(`/project-management/tasks/${taskId}/transition-approvals`).then(response=>{if(active)setData(response.data);}).catch(e=>{if(active)setError(workspaceError(e));}).finally(()=>{if(active)setLoading(false);});
  return()=>{active=false;};
 },[taskId,value,version,retry,refreshKey,enabled]);
 return {data,loading,error,retry:()=>setRetry(current=>current+1)};
}
