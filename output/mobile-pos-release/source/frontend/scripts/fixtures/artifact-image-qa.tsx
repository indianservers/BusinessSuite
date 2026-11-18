/** Development-only private image preview fixture. No generation or saved keys. */
import React from 'react';
import ReactDOM from 'react-dom/client';
import {MemoryRouter} from 'react-router-dom';
import {ArtifactView} from '../../src/components/ai-agents/BotArtifacts';
import {api} from '../../src/services/api';
import {ArtifactSharePublisher,SharedView} from '../../src/components/ai-agents/ArtifactSharing';
import '../../src/index.css';
if(!import.meta.env.DEV)throw Error('Development fixture only');
const requests:any[]=[];(window as any).__imageRequests=requests;
const bytes=Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAQAAAADCAYAAAC09K7GAAAAFUlEQVR4nGNkYPj/nwEJMCFzsAoAAF9tAgT9rRKIAAAAAElFTkSuQmCC'),c=>c.charCodeAt(0));
const sharedBody={title:'Synthetic shared image',kind:'image',content:'Synthetic caption',columns:[],rows:[]};
api.defaults.adapter=async config=>{
 const path=config.url||'';requests.push({path,params:config.params,responseType:config.responseType,body:config.data?JSON.parse(config.data):undefined});let data:any={};
 if(path.endsWith('/artifact-templates/preview'))data={id:701,definition:JSON.parse(config.data),variables:['customer'],module:'CRM',preview_hash:'synthetic-template-review'};
 else if(path.includes('/artifact-templates/reviews/'))data={template:{id:702}};
 else if(path.includes('/artifact-shares/source/'))data={items:[],can_publish:true};
 else if(path.endsWith('/library/targets'))data={members:[{id:7,label:'Synthetic reviewer'}],teams:[]};
 else if(path.endsWith('/artifact-shares/preview'))data={id:601,pending:{preview_hash:'synthetic-review',proposed_revision:1,audience:{kind:'members',member_ids:[7],team_ids:[]},image_positions:['0'],definition:{root:{module:'CRM',source_revision:2,body:sharedBody},sources:[],workspace_id:null}}};
 else if(path.endsWith('/preview-image')){await new Promise(resolve=>setTimeout(resolve,500));data=new Blob([bytes],{type:'image/png'})}
 else if(path.endsWith('/publish'))data={};
 else if(path.endsWith('/artifact-shares/601/content'))data={item:{...sharedBody,module:'CRM',revision:2,provenance:{note:'Synthetic reviewed snapshot'}}};
 else if(path.endsWith('/versions'))data={items:[{revision:2},{revision:1}]};
 else if(path.endsWith('/image'))data=new Blob([bytes],{type:'image/png'});
 else if(path.endsWith('/download'))data=new Blob([bytes],{type:'image/png'});
 else data={id:501,title:'Synthetic private image',module:'CRM',kind:'image',revision:Number(config.params?.revision)||2,current_revision:2,content:'Synthetic preview fixture',columns:[],rows:[],provenance:{note:'Simulated image, no generation performed.',citations:[]}};
 return {data,status:200,statusText:'OK',headers:{},config};
};
ReactDOM.createRoot(document.getElementById('root')!).render(<MemoryRouter><main style={{maxWidth:720,padding:20}}>{location.search.includes('sharing')?<><ArtifactSharePublisher artifact={{id:501,revision:2,title:'Synthetic private image'}}/><SharedView share={{id:601,revision:1}} refresh={0}/></>:<ArtifactView id={501} onEdit={()=>{}}/>}</main></MemoryRouter>);
