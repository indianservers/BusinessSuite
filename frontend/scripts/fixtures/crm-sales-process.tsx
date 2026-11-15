import {MemoryRouter} from "react-router-dom";
import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';
import {SalesProcessPanel,LeadMeetingOutcomes} from '../../src/apps/crm/leads/SalesProcessPanel';
import {api} from '../../src/services/api';
import '../../src/index.css';
import '../../src/apps/crm/leads/leads.css';
if(!import.meta.env.DEV || !['localhost','127.0.0.1'].includes(location.hostname))throw new Error('Local QA only');
let enabled=false;
let meetingStatus='Scheduled';
let allowed=false;
let evidence='';
const writes: {url:string;data:unknown}[]=[];
api.defaults.adapter=async config=>{
 const url=config.url||'';const method=config.method||'get';
 let data:unknown={};
 if(method!=='get')writes.push({url,data:JSON.parse(config.data||'{}')});
 if(url.endsWith('/meeting-metrics'))data={counts:{Scheduled:40,Confirmed:30,Attended:18,'No-show':12,Rescheduled:8},definition:'Disposable QA numbers. Current statuses, not a sequential funnel.'};
 if(url.endsWith('/sales-process'))data={enabled,ownerIds:[1],managerId:2,stages:[]};
 if(url.endsWith('/sales-process/setup')){enabled=true;data={enabled:true,pipelineId:99};}
 if(url.endsWith('/meetings'))data=[{id:1,title:'Product demo',status:meetingStatus,start_time:'2026-01-01T10:00:00Z',end_time:'2026-01-01T10:30:00Z'}];
 if(url.endsWith('/meetings/1')){meetingStatus=JSON.parse(config.data).status;data={saved:true};}
 if(url.endsWith('/nurture-consent')){
  if(method==='put'){const v=JSON.parse(config.data);allowed=v.allowed;evidence=v.evidence;}
  data={allowed,evidence};
 }
 return {data,status:200,statusText:'OK',headers:{},config};
};
function App(){const[revision,setRevision]=useState(0);const changed=()=>setRevision(v=>v+1);return <main style={{padding:16,maxWidth:1100,margin:'auto'}}><h1>Disposable sales workflow QA</h1><SalesProcessPanel bootstrap={{settings:{} as never,owners:[{id:1,name:'Salesperson'},{id:2,name:'Sales manager'}],canManage:true,canAdmin:true,userId:1}} search='' stage='' owner='' revision={revision} changed={changed}/><LeadMeetingOutcomes id={1} canManage changed={changed}/><button onClick={()=>{document.querySelector('output')!.textContent=JSON.stringify(writes);}}>Inspect fixture requests</button><output/></main>}
createRoot(document.getElementById('root')!).render(<MemoryRouter><App/></MemoryRouter>);

