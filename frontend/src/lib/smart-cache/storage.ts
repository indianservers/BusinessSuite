import type {Entry} from './model';
import * as fallback from './indexeddb-storage';
import {sqliteCall,sqliteReady} from './sqlite';
// Mirror approved data in the existing store so unsupported browsers and other tabs
// retain the same normalized projections and cross-tab invalidation behavior.
export async function getCachedRecords(key:string):Promise<Entry|undefined>{
 const local=await fallback.getCachedRecords(key);
 if(!local)return; // IndexedDB is the invalidation fence across tabs.
 if(!sqliteReady()){void sqliteCall("save",local).catch(()=>{});return local;} // Never delay the first cached render for WASM startup.
 try{const sql=await sqliteCall<Entry|undefined>('get',key);if(sql&&sql.checked===local.checked&&sql.serverScope===local.serverScope)return sql;}catch{/* IndexedDB fallback */}
 return local;
}
export async function saveCachedRecords(entry:Entry){
 if(!entry.persistent)return;
 await fallback.saveCachedRecords(entry);
 void sqliteCall('save',entry).catch(()=>{});
}
export async function refreshSnapshot(entry:Entry){await fallback.refreshSnapshot(entry);if(entry.persistent)void sqliteCall('refresh',entry).catch(()=>{});}
export async function invalidateCache(scope:string,module?:string){await fallback.invalidateCache(scope,module);try{await sqliteCall('clear',scope,module);}catch{/* fallback already invalidated */}}
export const clearUserCache=(scope:string)=>invalidateCache(scope);
export const storageUsage=fallback.storageUsage;
