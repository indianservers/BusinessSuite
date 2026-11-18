/** Development-only model governance fixture. No actual training or activation. */
import React from 'react';
import ReactDOM from 'react-dom/client';
import NlpTraining from '../../src/platform/NlpTraining';
import {platformApi} from '../../src/services/platform-api';
import '../../src/index.css';
import '../../src/platform/platform.css';
if(!import.meta.env.DEV)throw Error('Development fixture only');
const gate={passed:false,checks:[{name:'Canonical actions and safety',passed:false,actual:'25/26',required:'all native tests'}],limitations:'Synthetic tests, not production accuracy.'};
let active=218,previous:number|null=null;
let jobs=[{id:218,name:'Active baseline',status:'succeeded',epochs:400,release:{...gate,passed:true,checks:[{...gate.checks[0],passed:true,actual:'26/26'}]}},{id:220,name:'New candidate',status:'succeeded',epochs:400,release:gate}];
const requests:string[]=[];(window as any).__releaseRequests=requests;
platformApi.defaults.adapter=async config=>{
 const path=config.url||'';requests.push(path);let data:any={};
 if(path.endsWith('/evaluate')){jobs=jobs.map(j=>j.id===220?{...j,release:{...j.release,passed:true,checks:j.release.checks.map(c=>({...c,passed:true,actual:'28/28'}))}}:j);data={id:220}}
 else if(path.endsWith('/activate')){previous=active;active=220;data={active_job_id:active}}
 else if(path.endsWith('/rollback')){const old=active;active=previous!;previous=old;data={active_job_id:active}}
 else data={jobs,datasets:[],active_job_id:active,previous_job_id:previous,release_policy:'action-model-release-v1',learning_policy:'Only privacy-approved examples are trained.',storage:'C:\\Indian Servers\\ERPTrainedModel'};
 return {data,status:200,statusText:'OK',headers:{},config};
};
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><main style={{maxWidth:1100,margin:'24px auto',padding:20}}><NlpTraining/></main></React.StrictMode>);
