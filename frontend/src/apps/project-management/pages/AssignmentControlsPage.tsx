import { useMobileDraftGuard } from "@/components/mobile/useMobileDraftGuard";
import { useMobileContext } from "@/components/mobile/useMobileContext";
import { syncScope } from "@/shared/record-sync/store";
import { workspaceError } from "./workspaceTypes";
import { useMobile } from "@/components/mobile/useMobile";
import { MobileActionBar } from "@/components/mobile/MobileActionBar";
import "./assignment-controls-mobile.css";
import { NativeSelect } from "@/components/ui/native-select";
import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
type Row=Record<string,any>;
export default function AssignmentControlsPage(){
 const scope=useMobileContext(),phone=useMobile(480);
 if(phone&&scope!==syncScope())return <p role="status">Updating assignment context…</p>;
 return <AssignmentControlsContent key={scope}/>;
}
function AssignmentControlsContent(){
 const phone=useMobile(480),inFlight=useRef(false);
 const mounted=useRef(true),ownerScope=useRef(syncScope());
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 const currentOwner=()=>!phone||mounted.current&&ownerScope.current===syncScope();
 const owns=(owned:boolean,scope:string)=>!owned||mounted.current&&scope===syncScope();
 const queryScope=phone?[ownerScope.current]:[];
 async function read(path:string,params?:Record<string,unknown>){if(!currentOwner())throw new Error('Assignment context changed.');return (await api.get<Row>(path,params?{params}:undefined)).data;}
 const [busy,setBusy]=useState(false),[failure,setFailure]=useState(false);
 const [project,setProject]=useState('');const [task,setTask]=useState('');const [person,setPerson]=useState('');const [action,setAction]=useState('deadline');const [deadline,setDeadline]=useState('');const [target,setTarget]=useState('');const [reason,setReason]=useState('');const [message,setMessage]=useState('');
 const draftKey=JSON.stringify([project,task,person,action,deadline,target,reason]);
 const [savedDraft,setSavedDraft]=useState(draftKey);
 useMobileDraftGuard({enabled:phone,dirty:draftKey!==savedDraft,draftKey,pending:()=>inFlight.current,onDiscard:()=>setSavedDraft(draftKey),message:'Discard unsubmitted assignment changes before leaving?'});
 const optionsSource=useQuery<Row>({queryKey:['assignment-control-options',...queryScope],queryFn:()=>read('/interns-hub/management/options')});
 const tasksSource=useQuery<Row>({queryKey:['assignment-control-tasks',project,...queryScope],queryFn:()=>read(`/interns-hub/management/projects/${project}/tasks`),enabled:!!project});
 const peopleSource=useQuery<Row>({queryKey:['assignment-control-people',...queryScope],queryFn:()=>read('/interns-hub/management/interns',{include_employees:true})});
 const options=optionsSource.data,tasks=tasksSource.data,people=peopleSource.data;
 const sourceBlocked=phone&&(!currentOwner()||[optionsSource,tasksSource,peopleSource].some(source=>!source.isSuccess||source.isFetching||source.isPaused)||!(options?.projects||[]).some((p:Row)=>p.can_assign&&String(p.id)===project)||!(tasks?.items||[]).some((t:Row)=>String(t.id)===task)||!(people?.items||[]).some((p:Row)=>p.user_id&&String(p.user_id)===person));
 function sourceFeedback(source:typeof optionsSource,label:string,empty:string,enabled=true){
  if(!phone||!enabled)return null;
  if(source.isPaused)return <p className="assignment-control-source" role="status">{label} will load when the connection is available.</p>;
  if(source.isError)return <div role="alert" className="assignment-control-source text-destructive"><p>Could not load {label}. {workspaceError(source.error)}</p><Button variant="outline" disabled={busy||source.isFetching} onClick={()=>{if(!currentOwner()||inFlight.current||source.isFetching)return;void source.refetch({cancelRefetch:false});}}>Retry {label}</Button></div>;
  if(source.isPending||source.isFetching)return <p className="assignment-control-source" role="status">{source.data?'Refreshing':'Loading'} {label}…</p>;
  if(source.isSuccess&&empty)return <p className="assignment-control-source" role="status">{empty}</p>;
  return null;
 }
 const applyButton=<Button data-primary={phone||undefined} disabled={phone&&(busy||sourceBlocked)||!task||!person||!reason.trim()} onClick={async()=>{const owned=phone,scope=syncScope();if(!currentOwner())return;if(phone&&(inFlight.current||sourceBlocked))return;if(phone){inFlight.current=true;setBusy(true);setFailure(false);setMessage('');}try{await api.post(`/project-management/work/tasks/${task}/assignees/${person}/control`,{action,due_date:deadline||null,new_user_id:Number(target)||null,reason});if(owns(owned,scope)){setSavedDraft(draftKey);setMessage('Individual assignment updated; history preserved.');}}catch(e:any){if(owns(owned,scope)){if(owned)setFailure(true);setMessage(e.response?.data?.detail||'Could not update assignment')}}finally{if(owned&&owns(owned,scope)){inFlight.current=false;setBusy(false);}}}}>{phone&&busy?'Applying…':'Apply Individual Change'}</Button>;
 return <section aria-busy={phone?busy:undefined} data-control-action={phone?action:undefined} className="pms-assignment-controls mx-auto grid max-w-2xl gap-4 rounded-xl border bg-card p-6"><h1 className="text-xl font-bold">Individual Assignment Controls</h1><p>Deadline changes affect one participant. Cancellation and reassignment retain the earlier work and audit trail.</p><label>Project<NativeSelect loading={phone&&(optionsSource.isPending||optionsSource.isFetching)} error={phone&&optionsSource.isError} disabled={phone&&(busy||!optionsSource.isSuccess||optionsSource.isFetching)} aria-label="Control project" className="w-full rounded border p-2" value={project} onChange={e=>{setProject(e.target.value);setTask('')}}><option value="">Choose project</option>{options?.projects.filter((p:Row)=>p.can_assign).map((p:Row)=><option key={p.id} value={p.id}>{p.name}</option>)}</NativeSelect></label>{sourceFeedback(optionsSource,"projects",(options?.projects||[]).some((p:Row)=>p.can_assign)?"":"No assignable projects available.")}<label>Task<NativeSelect loading={phone&&!!project&&(tasksSource.isPending||tasksSource.isFetching)} error={phone&&tasksSource.isError} disabled={phone&&(busy||!project||!tasksSource.isSuccess||tasksSource.isFetching)} aria-label="Control task" className="w-full rounded border p-2" value={task} onChange={e=>setTask(e.target.value)}><option value="">Choose task</option>{tasks?.items.map((t:Row)=><option key={t.id} value={t.id}>{t.title}</option>)}</NativeSelect></label>{sourceFeedback(tasksSource,"tasks",tasks?.items.length?"":"No tasks available in this project.",!!project)}<label>Participant<NativeSelect loading={phone&&(peopleSource.isPending||peopleSource.isFetching)} error={phone&&peopleSource.isError} disabled={phone&&(busy||!peopleSource.isSuccess||peopleSource.isFetching)} aria-label="Control participant" className="w-full rounded border p-2" value={person} onChange={e=>setPerson(e.target.value)}><option value="">Choose participant</option>{people?.items.filter((p:Row)=>p.user_id).map((p:Row)=><option key={p.id} value={p.user_id}>{p.name}</option>)}</NativeSelect></label>{sourceFeedback(peopleSource,"participants",(people?.items||[]).some((p:Row)=>p.user_id)?"":"No linked participants available.")}<label>Action<NativeSelect disabled={phone&&busy} className="w-full rounded border p-2" aria-label="Control action" value={action} onChange={e=>setAction(e.target.value)}>{['deadline','cancel','restore','reassign'].map(a=><option key={a}>{a}</option>)}</NativeSelect></label>{action==='deadline'&&<label>Individual deadline<Input disabled={phone&&busy} aria-label="Individual deadline" type="date" value={deadline} onChange={e=>setDeadline(e.target.value)}/></label>}{action==='reassign'&&<label>New participant<NativeSelect loading={phone&&(peopleSource.isPending||peopleSource.isFetching)} error={phone&&peopleSource.isError} disabled={phone&&(busy||!peopleSource.isSuccess||peopleSource.isFetching)} aria-label="New participant" className="w-full rounded border p-2" value={target} onChange={e=>setTarget(e.target.value)}><option value="">Choose participant</option>{people?.items.map((p:Row)=><option key={p.id} value={p.user_id}>{p.name}</option>)}</NativeSelect></label>}<label>Reason<Input disabled={phone&&busy} aria-label="Control reason" value={reason} onChange={e=>setReason(e.target.value)}/></label>{phone?<MobileActionBar label="Individual assignment actions">{applyButton}</MobileActionBar>:applyButton}{message&&<p role={phone&&failure?"alert":"status"} className={phone&&failure?"text-destructive":undefined}>{message}</p>}</section>
}
