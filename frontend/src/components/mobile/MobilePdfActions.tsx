import { useEffect, useState } from "react";
import { Share2, FileText } from "lucide-react";
import { api } from "@/services/api";
import { MobileSheet } from "./MobilePrimitives";
import { useMobile } from "./useMobile";
export default function MobilePdfActions({ url, filename }: { url:string;filename:string }) {
 const mobile=useMobile();const [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[file,setFile]=useState<File>(),[objectUrl,setObjectUrl]=useState('');
 useEffect(()=>()=>{if(objectUrl)URL.revokeObjectURL(objectUrl);},[objectUrl]);
 if(!mobile)return null;
 const load=async()=>{setOpen(true);setBusy(true);setError('');try{const r=await api.get<Blob>(url,{responseType:'blob'});const f=new File([r.data],filename,{type:'application/pdf'});setFile(f);setObjectUrl(URL.createObjectURL(f));}catch{setError('PDF unavailable. Check your connection and retry.');}finally{setBusy(false);}};
 return <><button className="mobile-filter-trigger" type="button" onClick={()=>void load()}><FileText size={18}/>Preview & share PDF</button><MobileSheet open={open} onClose={()=>setOpen(false)} title="Invoice PDF">{busy&&<p role="status">Preparing PDF…</p>}{error&&<p role="alert">{error}<button onClick={()=>void load()}>Retry</button></p>}{objectUrl&&<><iframe className="rounded-lg border w-full h-[38dvh]" title="Invoice PDF preview" src={objectUrl}/><a href={objectUrl} target="_blank" rel="noreferrer" className="mobile-filter-trigger">Open PDF viewer</a><a className="mobile-filter-trigger" href={objectUrl} download={filename}>Download PDF</a>{file&&navigator.canShare?.({files:[file]})&&<button type="button" className="mobile-primary-action" onClick={()=>{void navigator.share({files:[file],title:filename}).catch(e=>{if(e.name!=='AbortError')setError('Sharing unavailable. Use Download PDF instead.');});}}><Share2 size={18}/>Share PDF</button>}</>}</MobileSheet></>;
}
