import {useEffect,useRef,useState} from 'react';
import {api} from '@/services/api';

/** Authenticated, version-bound bytes; no public image URL or browser storage. */
export function ProtectedImage({path,params,title,label,onStatus}:{path:string;params:Record<string,unknown>;title:string;label:string;onStatus?:(status:'loading'|'ready'|'error')=>void}){
 const paramsKey=JSON.stringify(params),status=useRef(onStatus);status.current=onStatus;
 const [url,setUrl]=useState(''),[error,setError]=useState('');
 useEffect(()=>{
  let live=true,objectUrl='';const abort=new AbortController();setUrl('');setError('');status.current?.('loading');
  const dispose=()=>{live=false;abort.abort();if(objectUrl)URL.revokeObjectURL(objectUrl);objectUrl=''};
  const clear=()=>{dispose();setUrl('');setError('Access context changed. Reopen this artifact.');status.current?.('error')};
  window.addEventListener('suite:organization-changed',clear);window.addEventListener('suite:branch-changed',clear);
  api.get(path,{params:JSON.parse(paramsKey),responseType:'blob',signal:abort.signal})
   .then(response=>{if(!live)return;if(response.data.type!=='image/png')throw Error('Unexpected image format');objectUrl=URL.createObjectURL(response.data);setUrl(objectUrl)})
   .catch(()=>{if(live){setError('Image unavailable in your current access scope.');status.current?.('error')}});
  return()=>{dispose();window.removeEventListener('suite:organization-changed',clear);window.removeEventListener('suite:branch-changed',clear)};
 },[path,paramsKey]);
 return <figure aria-label={label}>{error&&<p role="alert">{error}</p>}{url?<img src={url} alt={title} onLoad={()=>status.current?.('ready')} onError={()=>{setError('Image could not be displayed.');status.current?.('error')}} style={{maxWidth:'100%',maxHeight:560,objectFit:'contain'}}/>:!error&&<p>Loading private image…</p>}</figure>;
}

export default function ArtifactImage({id,revision,title}:{id:number;revision:number;title:string}){
 return <ProtectedImage path={`/ai-operator/suite/artifacts/${id}/image`} params={{revision}} title={title} label={`Image artifact ${id} version ${revision}`}/>;
}
