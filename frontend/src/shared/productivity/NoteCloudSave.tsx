import { useEffect, useRef, useState } from "react";
import { Cloud, FolderOpen, RefreshCw } from "lucide-react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";

type Account = {id:number;provider:"google_drive"|"onedrive";account:string};
type Folder = {id:string;name:string};
type Props = {source:"project_management"|"crm";title:string;content:string;disabled?:boolean;prepare?:()=>Promise<{id:number;version:number}|null>};
const labels = {google_drive:"Google Drive",onedrive:"OneDrive"};
const errorMessage=(error:unknown)=>{const e=error as {response?:{data?:{detail?:unknown}};message?:string};const detail=e.response?.data?.detail;return typeof detail==="string"?detail:e.message||"Could not save a cloud copy. Please retry.";};

export default function NoteCloudSave({source,title,content,disabled,prepare}:Props) {
  const [open,setOpen]=useState(false),[accounts,setAccounts]=useState<Account[]>([]),[provider,setProvider]=useState<keyof typeof labels>("google_drive");
  const [account,setAccount]=useState(0),[trail,setTrail]=useState<Folder[]>([{id:"root",name:"My files"}]),[folders,setFolders]=useState<Folder[]>([]);
  const [cursor,setCursor]=useState<string|null>(null),[format,setFormat]=useState("html"),[loading,setLoading]=useState(false),[saving,setSaving]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
  const [retry,setRetry]=useState(0);
  const [connecting,setConnecting]=useState<string|null>(null);
  const preferredAccount=useRef(0),connectionCleanup=useRef<(()=>void)|null>(null);
  useEffect(()=>()=>connectionCleanup.current?.(),[]);
  useEffect(()=>{
    if(!open)return;
    let active=true;setLoading(true);setError("");
    api.get<{accounts:Account[]}>("/files-storage/notes/options",{params:{source},recordCache:false}).then(({data})=>{
      if(!active)return;setAccounts(data.accounts);const selected=data.accounts.find(a=>a.id===preferredAccount.current)||data.accounts.find(a=>a.provider===provider);preferredAccount.current=0;setAccount(selected?.id||0);
    }).catch(e=>{if(active)setError(errorMessage(e));}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[open,source,retry]);
  const parent=trail[trail.length-1]?.id||"root";
  useEffect(()=>{
    if(!open||!account){setFolders([]);setCursor(null);return;}
    let active=true;setLoading(true);setError("");setFolders([]);setCursor(null);
    api.get<{items:Folder[];cursor:string|null}>(`/files-storage/notes/accounts/${account}/folders`,{params:{source,parent},recordCache:false}).then(({data})=>{if(active){setFolders(data.items);setCursor(data.cursor);}})
      .catch(e=>{if(active)setError(errorMessage(e));}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[open,account,parent,source,retry]);
  function selectAccount(id:number){setAccount(id);setTrail([{id:"root",name:"My files"}]);setNotice("");setError("");}
  async function connect(kind:keyof typeof labels){
    setError("");setNotice("");
    const popup=window.open("about:blank",`notes-storage-${crypto.randomUUID()}`,"width=600,height=720");
    if(!popup){setError("Allow the connection popup, then try again. Your note stays open here.");return;}
    setConnecting(kind);
    try{
      const {data}=await api.post<{authorize_url:string;request_id:string;callback_origin:string}>("/files-storage/notes/connect",{source,provider:kind});
      if(popup.closed)throw new Error("Connection canceled. Your note is still open.");
      let pending=true;
      const cleanup=()=>{pending=false;window.removeEventListener("message",receive);window.clearInterval(poll);window.clearTimeout(timeout);connectionCleanup.current=null;};
      const receive=(event:MessageEvent)=>{
        if(event.source!==popup||event.origin!==data.callback_origin||event.data?.type!=="suite-note-storage"||event.data?.request_id!==data.request_id)return;
        cleanup();popup.close();setConnecting(null);
        if(event.data.status==="connected"&&Number.isInteger(event.data.connection_id)){
          preferredAccount.current=event.data.connection_id;setProvider(kind);setTrail([{id:"root",name:"My files"}]);setError("");setNotice(`${labels[kind]} connected. Choose a folder to save your note copy.`);setRetry(v=>v+1);
        }else setError("Connection was canceled or denied. Your note is unchanged. You can try connecting again.");
      };
      const poll=window.setInterval(()=>{if(popup.closed)window.setTimeout(()=>{if(pending){cleanup();setConnecting(null);setError("Connection canceled. Your note is still open.");}},300);},500);
      const timeout=window.setTimeout(()=>{if(pending){cleanup();popup.close();setConnecting(null);setError("Connection timed out. Your note is unchanged. Please try again.");}},10*60*1000);
      connectionCleanup.current=()=>{cleanup();popup.close();};
      window.addEventListener("message",receive);
      popup.location.assign(data.authorize_url);
    }catch(e){connectionCleanup.current?.();popup.close();setConnecting(null);setError(errorMessage(e));}
  }
  async function save(){
    setSaving(true);setError("");setNotice("");
    try {
      const note=prepare?await prepare():undefined;
      if(prepare&&!note)throw new Error("Save the note in the app before copying it to cloud storage.");
      const {data}=await api.post<{saved:boolean;filename:string}>("/files-storage/notes/save",{source,connection_id:account,folder_id:parent,format,
        ...(note?{note_id:note.id,note_version:note.version}:{title:title||"Untitled note",content})});
      setNotice(`Saved ${data.filename} to ${labels[provider]}. Future edits stay in the app until you save another copy.`);
    }catch(e){setError(errorMessage(e));}finally{setSaving(false);}
  }
  return <><button type="button" disabled={disabled} onClick={()=>{setError("");setNotice("");setOpen(true);}}><Cloud size={14}/>Save to cloud</button>
    <Dialog open={open} onOpenChange={value=>{if(!saving&&!connecting)setOpen(value);}}><DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
      <DialogTitle>Save a note copy</DialogTitle><DialogDescription>Choose your connected Google Drive or OneDrive account. This copies note text and formatting; attachments stay in the app. People with access to the destination folder can read the copy.</DialogDescription>
      <div className="grid gap-2 sm:grid-cols-2">{(Object.keys(labels) as (keyof typeof labels)[]).map(kind=><Button type="button" key={kind} variant="outline" disabled={saving||loading||!!connecting} onClick={()=>void connect(kind)}>{connecting===kind?"Connecting…":`Connect ${labels[kind]}`}</Button>)}</div>
      {connecting&&<p role="status" className="text-sm">Complete {labels[connecting as keyof typeof labels]} authorization in the popup. Your note stays open here.</p>}
      <label className="grid gap-2 text-sm">Storage provider<NativeSelect aria-label="Note storage provider" disabled={saving||loading||!!connecting} value={provider} onChange={e=>{const next=e.target.value as keyof typeof labels;setProvider(next);selectAccount(accounts.find(a=>a.provider===next)?.id||0);}}>{Object.entries(labels).map(([id,label])=><option key={id} value={id}>{label}</option>)}</NativeSelect></label>
      <label className="grid gap-2 text-sm">Connected account<NativeSelect aria-label="Note storage account" disabled={saving||loading} value={account} onChange={e=>selectAccount(Number(e.target.value))}><option value="">Choose your account</option>{accounts.filter(a=>a.provider===provider).map(a=><option key={a.id} value={a.id}>{a.account}</option>)}</NativeSelect></label>
      {!loading&&!accounts.some(a=>a.provider===provider)&&<p className="text-sm">No {labels[provider]} account connected by you. Use Connect {labels[provider]} above to authorize your own account without leaving Notes.</p>}
      {!!account&&<div className="space-y-2"><div className="flex items-center gap-2 text-sm"><FolderOpen size={16}/><span>{trail.map(f=>f.name).join(" / ")}</span>{trail.length>1&&<Button type="button" size="sm" variant="outline" disabled={saving||loading} onClick={()=>setTrail(t=>t.slice(0,-1))}>Back</Button>}</div>
        <div className="max-h-44 overflow-y-auto rounded-md border p-2">{loading?<p role="status">Loading folders…</p>:folders.length?folders.map(folder=><button type="button" disabled={saving} className="flex w-full items-center gap-2 rounded px-2 py-2 text-left text-sm hover:bg-muted" key={folder.id} onClick={()=>setTrail(t=>[...t,folder])}><FolderOpen size={14}/>{folder.name}</button>):<p className="text-sm text-muted-foreground">No subfolders. You can save in this folder.</p>}
        {cursor&&<Button type="button" variant="outline" disabled={saving||loading} onClick={async()=>{setLoading(true);try{const {data}=await api.get<{items:Folder[];cursor:string|null}>(`/files-storage/notes/accounts/${account}/folders`,{params:{source,parent,cursor},recordCache:false});setFolders(old=>[...old,...data.items]);setCursor(data.cursor);}catch(e){setError(errorMessage(e));}finally{setLoading(false);}}}>More folders</Button>}</div></div>}
      <label className="grid gap-2 text-sm">File format<NativeSelect aria-label="Cloud note format" value={format} disabled={saving} onChange={e=>setFormat(e.target.value)}><option value="html">HTML — keep formatting</option><option value="txt">Text — plain text</option></NativeSelect></label>
      {error&&<p role="alert" className="text-sm text-destructive">{error}</p>}{notice&&<p role="status" className="text-sm text-emerald-700">{notice}</p>}
      <div className="flex flex-wrap justify-end gap-2"><Button type="button" variant="outline" disabled={saving||loading||!!connecting} onClick={()=>setRetry(v=>v+1)}><RefreshCw size={14}/>Refresh accounts</Button><Button type="button" disabled={saving||loading||!!connecting||!account||!!error} onClick={()=>void save()}>{saving?"Saving copy…":`Save copy to ${labels[provider]}`}</Button></div>
    </DialogContent></Dialog>
  </>;
}
