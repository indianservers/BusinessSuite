import { Button } from "@/components/ui/button";
import { useEffect, useRef, useState } from 'react';
import { Download, Paperclip } from 'lucide-react';
import { api } from '@/services/api';
import { whatsappBase, whatsappError } from './types';

export type Media = {id:string;kind:string;mimeType:string;filename:string;size?:number};
export type UploadedMedia = Media & {token:string};

/** Tokens stay on the server; blob URLs are scoped to the mounted message. */
export default function MessageMedia({id,media}:{id:number;media:Media}) {
  const [url,setUrl]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const request=useRef<AbortController>(),objectUrl=useRef('');
  useEffect(()=>{setUrl('');setBusy(false);setError('');return()=>{request.current?.abort();if(objectUrl.current)URL.revokeObjectURL(objectUrl.current);};},[id]);
  async function load(){
    if(busy)return;
    const controller=new AbortController();request.current=controller;setBusy(true);setError('');
    try{
      const response=await api.get<Blob>(`${whatsappBase}/messages/${id}/media`,{responseType:'blob',signal:controller.signal});
      if(controller.signal.aborted)return;
      if(objectUrl.current)URL.revokeObjectURL(objectUrl.current);
      objectUrl.current=URL.createObjectURL(response.data);setUrl(objectUrl.current);
    }catch(error){
      if(!controller.signal.aborted){
        const blob=(error as {response?:{data?:unknown}})?.response?.data;
        let message=whatsappError(error);
        if(blob instanceof Blob)try{const detail=JSON.parse(await blob.text()).detail;if(typeof detail==='string')message=detail;}catch{/* Keep the standard network error. */}
        if(!controller.signal.aborted)setError(message);
      }
    }
    finally{if(!controller.signal.aborted)setBusy(false);}
  }
  return <div className="wa-message-media">
    <span><Paperclip size={13}/>{media.filename||media.kind}{media.size?` · ${Math.ceil(media.size/1024)} KB`:''}</span>
    {!url&&<button type="button" disabled={busy} onClick={()=>void load()}>{busy?'Loading attachment…':error?'Retry attachment':'Load attachment'}</button>}
    {error&&<p role="alert">{error}</p>}
    {url&&<>
      {['image','sticker'].includes(media.kind)&&<a href={url} target="_blank" rel="noreferrer"><img src={url} alt={media.filename||'WhatsApp image'}/></a>}
      {media.kind==='audio'&&<audio controls preload="metadata" src={url}/>}
      {media.kind==='video'&&<video controls preload="metadata" src={url}/>}
      {media.mimeType==='application/pdf'&&<iframe title={`PDF preview: ${media.filename}`} src={url}/>}
      <Button asChild variant="outline"><a className="wa-media-download" href={url} download={media.filename||'attachment'}><Download size={13}/>Download {media.filename}</a></Button>
    </>}
  </div>;
}
