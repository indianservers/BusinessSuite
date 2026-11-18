/** Development-only synthetic platform training metrics; no real auth or jobs. */
import React from 'react';
import ReactDOM from 'react-dom/client';
import NlpTraining from '../../src/platform/NlpTraining';
import {platformApi} from '../../src/services/platform-api';
import '../../src/index.css';
if(!import.meta.env.DEV)throw new Error('Development fixture only');
const requests:string[]=[];(window as any).__platformNlpRequests=requests;
platformApi.defaults.adapter=async config=>{
 requests.push(config.url||'');
 const data={storage:'C:\\Indian Servers\\ERPTrainedModel',active_job_id:243,datasets:[],jobs:[{id:244,name:'Synthetic dialogue candidate',status:'succeeded',stage:'release_blocked',epochs:220,metrics:{dialogue:{initial:{mode:'fine_tune',job_id:243},training_accuracy:.9983,heldout_accuracy:.9589,workplace_training_turns:450,workplace_dialogue_version:'workplace-followups-v1'},workplace_followups:{passed:81,total:90,version:'workplace-followup-probes-v1'}},release:{passed:false,checks:[],limitations:'Synthetic fixture; no release is activated.'}}]};
 return {data,status:200,statusText:'OK',headers:{},config};
};
ReactDOM.createRoot(document.getElementById('root')!).render(<NlpTraining/>);
