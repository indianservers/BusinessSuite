import React from 'react';
import ReactDOM from 'react-dom/client';
import {MemoryRouter,Routes,Route} from 'react-router-dom';
import {api} from '../../src/services/api';
import NlpDatasetsPage from '../../src/pages/ai-agents/NlpDatasetsPage';
import NlpTrainingPage from '../../src/pages/ai-agents/NlpTrainingPage';
import '../../src/index.css';
if(!import.meta.env.DEV)throw new Error('Development fixture only');
let datasets:any[]=[],jobs:any[]=[],jobReads=0;const intents={CRM:['leads.list','deals.list'],PMS:['tasks.list'],Sales:['invoices.list'],HRMS:['directory']};
let query:any={id:42,user_id:7,module:'CRM',provider:'local',input_mode:'text',query_text:'CRM: show my leads',predicted_intent:'leads.list',outcome:'answered',review_status:'pending',revision:1};
(window as any).__nlpQaRequests=[];
api.defaults.adapter=async config=>{
 const path=config.url || '',body=(typeof config.data==='string'?JSON.parse(config.data):config.data) || {};let data:any={};
 (window as any).__nlpQaRequests.push({path,method:config.method,keys:body instanceof FormData?Array.from(body.keys()):Object.keys(body)});
 if(path.endsWith('/workspaces'))data=[];
 else if(path.endsWith('/training/template'))data=new Blob(['QA workbook']);
 else if(path.endsWith('/training/datasets')){
  if(config.method==='post'){const name=body instanceof FormData?body.get('name'):'QA commands';datasets=[{id:1,name:name||'QA commands',status:'pending',revision:1,counts:{total:1,splits:{train:1},base_duplicates:0},preview:[{module:'CRM',text:'CRM: fetch prospect roster',intent:'leads.list',split:'train'}]}];data=datasets[0];}
  else data={items:datasets,intents};
 }
 else if(path.endsWith('/training/datasets/1')){if(config.method==='put'){datasets[0]={...datasets[0],status:body.approved?'approved':'rejected',revision:2};data=datasets[0];}else{datasets=[];data={deleted:true};}}
 else if(path.endsWith('/nlp-queries'))data={items:query.review_status===(config.params?.review_status||query.review_status)?[query]:[],intents,can_review:true,has_more:false};
 else if(path.endsWith('/nlp-queries/42')){query={...query,...body,review_status:body.decision,reviewed_intent:body.intent,revision:query.revision+1};data=query;}
 else if(path.endsWith('/training/jobs')){
  if(config.method==='post'){jobs=[{id:9,status:'queued',epochs:body.epochs,counts:{examples:1}}];jobReads=0;data=jobs[0];}
  else{jobReads++;if(jobs.length&&jobReads>=2)jobs=[{...jobs[0],status:'succeeded',metrics:{modules:{CRM:{training_commands:121,training_accuracy:1,internal_validation_accuracy:.65}},uploaded_evaluation:{test:{passed:3,total:4}}}}];data={items:jobs,active_model:{description:'TensorFlow-trained neural intent models + typed rules',tensorflow_version:'2.20.0'}};}
 }
 else if(path.endsWith('/training/jobs/9/activate'))data={activated:true,job_id:9};
 return {data,status:200,statusText:'OK',headers:{},config};
};
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><MemoryRouter initialEntries={['/ai-agents/nlp-datasets']}><Routes><Route path="/ai-agents/nlp-datasets" element={<NlpDatasetsPage/>}/><Route path="/ai-agents/nlp-training" element={<NlpTrainingPage/>}/></Routes></MemoryRouter></React.StrictMode>);
