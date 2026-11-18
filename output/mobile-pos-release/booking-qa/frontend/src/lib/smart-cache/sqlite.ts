/** SQLite stays off the UI thread and is loaded only for approved cache data. */
let worker:Worker|undefined,disabled=false,next=0,ready=false;
export const sqliteReady=()=>ready&&!disabled;
const pending=new Map<number,{resolve:(value:any)=>void;reject:(error:Error)=>void;timer:ReturnType<typeof setTimeout>}>();
export async function sqliteCall<T>(method:string,...args:unknown[]):Promise<T>{
 if(disabled||!navigator.storage?.getDirectory)return Promise.reject(Error('SQLite unavailable'));
 if(!worker){
  worker=new Worker(new URL('./sqlite.worker.ts',import.meta.url),{type:'module'});
  worker.onmessage=({data})=>{const call=pending.get(data.id);if(!call)return;clearTimeout(call.timer);pending.delete(data.id);if(data.error)call.reject(Error(data.error));else{ready=true;call.resolve(data.value);}};
  worker.onerror=()=>disable();
 }
 const id=++next;
 return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{disable();},5000);pending.set(id,{resolve,reject,timer});worker!.postMessage({id,method,args});});
}
function disable(){disabled=true;worker?.terminate();worker=undefined;for(const call of pending.values()){clearTimeout(call.timer);call.reject(Error('SQLite unavailable'));}pending.clear();}
