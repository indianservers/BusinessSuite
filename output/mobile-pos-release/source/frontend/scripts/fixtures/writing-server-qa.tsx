/** Synthetic DEV-only UI; no credentials, real records or provider calls. */
import React from 'react';
import {createRoot} from 'react-dom/client';
import {MemoryRouter} from 'react-router-dom';
import WritingActions from '../../src/components/ai-agents/WritingActions';
import {useAuthStore} from '../../src/store/authStore';
import {api} from '../../src/services/api';
import '../../src/index.css';
if(!import.meta.env.DEV)throw new Error('Development fixture only');
useAuthStore.setState({user:{id:9001,email:'synthetic@example.test',role:'owner',is_superuser:true},isAuthenticated:true,isHydrated:true});
const requests:{url:string;body:any}[]=[];(window as any).__writingRequests=requests;
api.defaults.adapter=async config=>{
 const body=typeof config.data==='string'?JSON.parse(config.data):config.data;
 requests.push({url:config.url||'',body});
 let data:any;
 if(config.url?.endsWith('/suite/providers'))data={items:[{provider:'gemini',enabled:true,data_sharing_allowed:true,has_key:true},{provider:'openai',enabled:false,data_sharing_allowed:false,has_key:true}]};
 else if(config.url?.endsWith('/writing/draft'))data={text:body.provider==='gemini'?'Server Gemini draft R-742':'Local draft R-742',subject:'R-742',missing_details:[],engine:body.provider,method:'synthetic-server-fixture'};
 else throw new Error('Unexpected fixture request');
 return {data,status:200,statusText:'OK',headers:{},config};
};
function Fixture(){return <MemoryRouter initialEntries={['/crm/leads?workspace=7']}><main><label>Original notes<textarea defaultValue="Review R-742 Friday." aria-label="Original notes"/></label><WritingActions module="CRM" actions={[{id:'improve',label:'Improve writing'}]}/></main></MemoryRouter>;}
createRoot(document.getElementById('root')!).render(<Fixture/>);
