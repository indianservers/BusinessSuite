import { useState, lazy, Suspense } from "react";

import { createRoot } from "react-dom/client";

import { MemoryRouter } from "react-router-dom";

import PipelineBoard, { PipelineViewSwitch, PipelineSearch, type PipelineRecord } from "@/shared/pipeline/PipelineBoard";

import PipelineStageEditor, { type PipelineConfiguration } from "@/shared/pipeline/PipelineStageEditor";

import SalesPipeline from "@/apps/srm/components/SalesPipeline";

import "@/index.css";



const Integration=lazy(()=>import("./pipeline-integration-qa"));

const initial:PipelineConfiguration={name:"Sales pipeline",stages:[{id:"1",name:"Qualified",probability:20,color:"#7f4b9e",outcome:"open"},{id:"2",name:"Demo Scheduled",probability:40,outcome:"open"},{id:"3",name:"Demo Completed",probability:60,outcome:"open"},{id:"4",name:"Proposal Made",probability:80,outcome:"open"},{id:"5",name:"Negotiations",probability:90,outcome:"open"},{id:"6",name:"Contract Signed",probability:100,outcome:"won"}],remap:{}};

const titles=["Oracle","Mindbend Deal","Robinson LT","Mac LTD deal","Cora Whitney deal","Wayne deal","Rayteon deal","NoNews deal","Interpublic","Network Deal","Schmidt deal","WellCare Plans Deal"];

function Fixture(){

  const params=new URLSearchParams(location.search);const readOnly=params.has("readonly");

  const [records,setRecords]=useState<PipelineRecord[]>(titles.map((title,i)=>({id:String(i+1),stageId:String(Math.floor(i/3)+1),title,subtitle:["Oracle, Amar Kerr","Mindbend LLP, Jose Miller","Robinson LT, Ashlynn Smith"][i%3],value:`$${(5500+i*900).toLocaleString()}`,priority:i===0?"Medium":undefined,description:i===0?"Confirm the customer’s priorities and agree on the next steps with the delivery team.":undefined,tags:i===0?["Priority account","Follow-up"]:undefined,progress:i===0?{completed:2,total:5,label:"Checklist"}:undefined,attachmentCount:i===0?1:undefined,owner:["AK","JM","AS"][i%3],activity:i%3===0?"missing":i%3===1?"overdue":"scheduled",labelColor:i%2?"#9963aa":undefined})));

  const [configuration,setConfiguration]=useState(params.has("draftIds")?{...initial,stages:initial.stages.map((stage,index)=>({...stage,id:`new:${index}`}))}:initial),[revision,setRevision]=useState(0),[search,setSearch]=useState(""),[view,setView]=useState<"board"|"list">("board");

  const [opened,setOpened]=useState(""),[saved,setSaved]=useState(""),[action,setAction]=useState("");

  if(params.has("integration"))return <Suspense fallback={<p>Loading integration…</p>}><Integration/></Suspense>;

  if(params.has("sales"))return <MemoryRouter><main className="p-5"><SalesPipeline kind="salesOrders" canManage records={[{id:1,order_number:"SO-001",status:"draft",total_amount:12500,currency:"INR"},{id:2,order_number:"SO-002",status:"approved",total_amount:45000,currency:"INR"}]} loading={false} onAction={async(name)=>setAction(name)}/><output aria-label="Sales action">{action}</output></main></MemoryRouter>;

  return <main style={{padding:24,background:"#fff",minHeight:"100vh"}}><h1 className="text-lg font-semibold mb-3">Deals</h1>

    {params.has("editor")?<PipelineStageEditor key={revision} {...configuration} sales onSave={async draft=>{setSaved(draft.name);setConfiguration(draft);setRevision(v=>v+1);}}/>:<PipelineBoard label="QA pipeline" renderDetails={params.has("drawer")?record=><div><p>Record detail: {record.title}</p><p>Notes, activities and related work stay beside the board.</p></div>:undefined} onAdd={stageId=>setRecords(rows=>[...rows,{id:"new-record",title:"New record",stageId}])} stages={configuration.stages} records={records.filter(r=>r.title.toLowerCase().includes(search.toLowerCase()))} disabled={readOnly}

      toolbar={<><PipelineViewSwitch view={view} onChange={setView}/><button className="pipeline-primary" onClick={()=>setOpened("New deal")}>+ Deal</button><PipelineSearch value={search} onChange={setSearch}/><div className="pipeline-toolbar-end">Sales pipeline · Filter · Sort by next activity</div></>}

      onOpen={r=>setOpened(r.title)}

      onMove={async({record,stageId,beforeId})=>{if(params.has("fail"))throw new Error("Stage entry requirements are not met");setRecords(rows=>{const remaining=rows.filter(r=>r.id!==record.id);const moved={...record,stageId};const before=remaining.findIndex(r=>r.id===beforeId);remaining.splice(before<0?remaining.length:before,0,moved);return remaining;});}}

      actions={[{id:"won",label:"Won",tone:"success",onAction:r=>setOpened(`Won review: ${r.title}`)},{id:"lost",label:"Lost",tone:"danger",onAction:r=>setOpened(`Lost review: ${r.title}`)}]}

    />}

    <output aria-label="Opened record">{opened}</output><output aria-label="Saved pipeline">{saved}</output>

  </main>;

}

createRoot(document.getElementById("root")!).render(<Fixture/>);

