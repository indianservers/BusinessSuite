/** Development-only visual fixture; no real credentials or provider calls. */
import React from 'react';
import ReactDOM from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import SuiteOperatorPage from '../../src/pages/ai-agents/SuiteOperatorPage';
import { api } from '../../src/services/api';
import '../../src/index.css';

if (!import.meta.env.DEV) throw new Error('Development fixture only');
let artifacts:any[]=[];
const today=new Date().toISOString().slice(0,10);
function dateOffset(days:number){const d=new Date(`${today}T12:00:00Z`);d.setUTCDate(d.getUTCDate()+days);return d.toISOString().slice(0,10);}
const tasks=[
 {id:1,task_key:'VAT-01',title:'Review filing documents',status:'In Progress',priority:'High',due_date:dateOffset(-3),days_remaining:-3,bucket:'overdue',project_id:1},
 {id:2,task_key:'VAT-02',title:'Confirm client approval',status:'To Do',priority:'High',due_date:today,days_remaining:0,bucket:'today',project_id:1},
 {id:3,task_key:'VAT-03',title:'Submit quarterly return',status:'To Do',priority:'Medium',due_date:dateOffset(5),days_remaining:5,bucket:'upcoming',project_id:1},
 {id:4,task_key:'VAT-04',title:'Schedule next client review',status:'To Do',priority:'Low',due_date:null,days_remaining:null,bucket:'undated',project_id:1}
];
api.defaults.adapter=async config=>{
 const path=config.url||'';const body=config.data?JSON.parse(config.data):{};let data:any={};
 if(path.endsWith('/projects'))data=[{id:1,name:'Client compliance · QA data',workspace_id:null}];
 else if(path.endsWith('/workspaces'))data=[];
 else if(path.endsWith('/local-context'))data={tasks};
 else if(path.endsWith('/tools'))data={tools:[{name:'pms.tasks',module:'PMS',description:'Read authorized project tasks',approval_required:false,record_id_required:true}]};
 else if(path.endsWith('/providers'))data={items:[{provider:'gemini',model:'QA provider (mock)',enabled:true,data_sharing_allowed:true}]};
 else if(path.endsWith('/runs'))data={items:[]};
 else if(path.endsWith('/memories'))data={items:[]};
 else if(path.endsWith('/deadline-radar'))data={today,through:dateOffset(config.params.horizon_days),generated_at:new Date().toISOString(),source:'QA fixture tasks',project:{id:1,name:'Client compliance · QA data'},config:config.params,counts:{overdue:1,today:1,upcoming:1,undated:1,later:0,completed:0},items:tasks,coverage:{scanned:4,complete:true,limit:2000}};
 else if(path.includes('/workbench/items')){if(config.method==='post'){data={id:1,...body,revision:1};artifacts=[data];}else if(config.method==='put'){data={...body,id:1,revision:body.revision+1};artifacts=[data];}else data={items:artifacts};}
 else if(path.endsWith('/catalog'))data={items:[{id:'gmail',name:'Gmail',category:'Email',actions:[{name:'Search mail'}]},{id:'google_calendar',name:'Google Calendar',category:'Calendars',actions:[{name:'List events'}]}]};
 else if(path.endsWith('/connections'))data={items:[{id:1,connector_id:'gmail',name:'QA mailbox'}]};
 else if(path.endsWith('/commands'))data={id:1,command:body.text,status:'answered',plan_hash:'0'.repeat(64),plan:{summary:'QA operator: review the overdue filing documents first, confirm the client approval today, then prepare the return. No dates were changed.',steps:[]},receipts:[]};
 return {data,status:200,statusText:'OK',headers:{},config};
};
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><div style={{padding:24,maxWidth:1500,margin:'0 auto'}}><p style={{marginBottom:16}}>Development QA · all records and provider responses are sample data</p><MemoryRouter initialEntries={['/ai-agents/operator?module=PMS&project=1']}><SuiteOperatorPage/></MemoryRouter></div></React.StrictMode>);
