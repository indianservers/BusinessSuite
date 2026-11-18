import init from '@sqlite.org/sqlite-wasm';
import wasmUrl from '@sqlite.org/sqlite-wasm/sqlite3.wasm?url';
import {MAX_AGE,MAX_BYTES,MAX_VIEWS} from './model';
import type {Entry} from './model';
const initialize=init as unknown as (options:Record<string,unknown>)=>ReturnType<typeof init>;
const ready=initialize({locateFile:()=>wasmUrl,print:()=>{},printErr:()=>{}}).then(async sqlite=>{
 const pool=await sqlite.installOpfsSAHPoolVfs({name:'suite-records',directory:'.suite-records-v1',initialCapacity:4,preserveOnInitFailure:true});
 const db=new pool.OpfsSAHPoolDb('/records.sqlite3');
 db.exec('CREATE TABLE IF NOT EXISTS snapshots (key TEXT PRIMARY KEY, scope TEXT NOT NULL, module TEXT NOT NULL, checked INTEGER NOT NULL, accessed INTEGER NOT NULL, bytes INTEGER NOT NULL, payload TEXT NOT NULL); CREATE INDEX IF NOT EXISTS snapshot_scope ON snapshots(scope);');
 return db;
});
let queue=Promise.resolve();
self.onmessage=event=>{queue=queue.then(async()=>{
 const {id,method,args}=event.data;
 try{
 const db=await ready;let value:unknown;
 if(method==='get'){
  const rows=db.selectObjects('SELECT payload FROM snapshots WHERE key=? AND checked>=?',[args[0],Date.now()-MAX_AGE]);
  value=rows.length?JSON.parse(String(rows[0].payload)):undefined;
 }else if(method==='save'){
  const entry=args[0] as Entry;
  db.exec({sql:'INSERT OR REPLACE INTO snapshots VALUES(?,?,?,?,?,?,?)',bind:[entry.key,entry.scope,entry.module,entry.checked,entry.accessed,entry.bytes,JSON.stringify(entry)]});
  db.exec({sql:'DELETE FROM snapshots WHERE checked < ?',bind:[Date.now()-MAX_AGE]});
  const rows=db.selectObjects('SELECT key,bytes FROM snapshots ORDER BY accessed DESC');let bytes=0;
  rows.forEach((row,index)=>{bytes+=Number(row.bytes);if(index>=MAX_VIEWS||bytes>MAX_BYTES)db.exec({sql:'DELETE FROM snapshots WHERE key=?',bind:[row.key]});});
 }else if(method==='clear'){
  db.exec({sql:'DELETE FROM snapshots WHERE scope=?'+(args[1]?' AND module=?':''),bind:args[1]?[args[0],args[1]]:[args[0]]});
 }else if(method==='usage'){
  const rows=db.selectObjects('SELECT COALESCE(SUM(bytes),0) AS bytes,COUNT(*) AS views FROM snapshots WHERE scope=?',[args[0]]);value=rows[0];
 }else if(method==='refresh'){
  const entry=args[0] as Entry;db.exec({sql:'UPDATE snapshots SET checked=?,accessed=?,payload=? WHERE key=?',bind:[entry.checked,entry.accessed,JSON.stringify(entry),entry.key]});
 }else if(method==='ping')value='sqlite-opfs';
 else throw Error('Unknown cache command');
 self.postMessage({id,value});
 }catch(error){self.postMessage({id,error:error instanceof Error?error.message:'Local database unavailable'});}
 });};
