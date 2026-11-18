import type {AxiosInstance} from 'axios';
import type {POSFeatures} from './components/POSBasicCustomer';
import type {SRMRecord} from './types';
/** Fetch only the pages explicitly requested; search is executed on the server. */
export async function loadPOSCatalog(api:AxiosInstance,selected:boolean,search:string,pages:number,signal?:AbortSignal){
 const items:SRMRecord[]=[];let after:number|null=0,total=0,features:POSFeatures|undefined,hasMore=false;
 for(let page=1;page<=Math.max(1,pages);page++){
  if(selected){const {data}:{data:{items:SRMRecord[];next:number|null;features:POSFeatures}}=await api.get('/srm/pos/catalog',{params:{after,limit:200,search},signal,progress:false,recordCache:false});items.push(...data.items);features=data.features;after=data.next;hasMore=after!==null;total=items.length+(hasMore?1:0);}
  else{const {data}:{data:{items:SRMRecord[];total:number}}=await api.get('/srm/inventory/items',{params:{page,per_page:200,search},signal,progress:false});items.push(...data.items);total=data.total;hasMore=items.length<total&&data.items.length>0;}
  if(!hasMore)break;
 }
 return {items,total,features,hasMore};
}
