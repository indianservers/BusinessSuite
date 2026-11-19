import {CanceledError, type AxiosAdapter, type InternalAxiosRequestConfig} from 'axios';

type Context = {route:string;scope:string}|null;
const optional = new Set(['/notifications/summary','/access/setup','/access/enterprise/branding']);
const barrier = (route:string,url:string) => route.startsWith('/srm/pos') || route==='/srm/appointments'
  ? url==='/srm/industry/capabilities'
  : route==='/srm/service-scheduling' ? url==='/employees/planned-services' : url==='/branches/context';

/** Briefly prioritize destination reads over optional shell metadata. No response
 * or authority is cached. A user action/error/timeout always releases the lane. */
export function startupReadPriority(transport:AxiosAdapter, context:()=>Context, maxWait=2500, yieldMs=100):AxiosAdapter {
  let done='';
  let phase:{key:string;scope:string;wait:Promise<void>;release:()=>void}|undefined;
  const keyOf=(value:NonNullable<Context>)=>JSON.stringify([value.route,value.scope]);
  const finish=(key:string)=>{if(phase?.key===key){phase.release();phase=undefined;}done=key;};
  const start=(value:NonNullable<Context>)=>{
    const key=keyOf(value);
    if(phase?.key===key)return phase;
    phase?.release();
    let release!:()=>void;
    const wait=new Promise<void>(resolve=>{release=resolve;});
    const timer=setTimeout(()=>finish(key),maxWait);
    phase={key,scope:value.scope,wait,release:()=>{clearTimeout(timer);release();}};
    return phase;
  };
  const waitFor=(config:InternalAxiosRequestConfig, wait:Promise<void>)=>new Promise<void>((resolve,reject)=>{
    let ended=false;
    const settle=(error?:unknown)=>{if(ended)return;ended=true;config.signal?.removeEventListener?.('abort',cancel);error?reject(error):resolve();};
    const cancel=()=>settle(new CanceledError('canceled',config));
    config.signal?.addEventListener?.('abort',cancel);
    if(config.signal?.aborted)cancel();
    wait.then(()=>settle(),settle);
  });
  return async config=>{
    const current=context(),url=(config.url||'').split('?')[0];
    if(!current){phase?.release();phase=undefined;return transport(config);}
    const key=keyOf(current);
    if((config.method||'get').toLowerCase()!=='get') {finish(key);return transport(config);}
    if(optional.has(url)&&done!==key){
      const pending=start(current);
      await waitFor(config,pending.wait);
      if(context()?.scope!==current.scope)throw new CanceledError('Startup context changed',config);
      return transport(config);
    }
    try {
      const response=await transport(config);
      if(barrier(current.route,url)) {
        if(response.status>=400)finish(key);
        else setTimeout(()=>finish(key),yieldMs);
      }
      return response;
    } catch(error) {
      if(barrier(current.route,url))finish(key);
      throw error;
    }
  };
}
