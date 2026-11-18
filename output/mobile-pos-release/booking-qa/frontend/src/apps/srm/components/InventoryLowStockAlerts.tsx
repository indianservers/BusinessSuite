import {useQuery} from '@tanstack/react-query';
import {srmApi} from '../api';
import {useRecordScope} from '@/lib/record-scope';
import {Button} from '@/components/ui/button';
import LowStockPanel from './LowStockPanel';

/** Mounted only in the verified native fallback, never inside a selected pack. */
export default function InventoryLowStockAlerts() {
 const scope=useRecordScope();
 const query=useQuery({queryKey:['srm','inventory-summary',scope],queryFn:srmApi.inventoryStockSummary,retry:false,refetchInterval:60000});
 if(query.isPending)return <p role="status">Checking low stock…</p>;
 if(query.isError)return <div role="alert" className="rounded-lg border p-4">Stock alerts could not be checked. <Button variant="outline" size="sm" onClick={()=>void query.refetch()}>Retry stock alerts</Button></div>;
 const rows=(query.data?.items??[]) as {id:number;item_name:string;sku:string;current_quantity:number;reorder_threshold:number}[];
 return <LowStockPanel items={rows.map(row=>({id:row.id,name:row.item_name,sku:row.sku,quantity:Number(row.current_quantity),threshold:Number(row.reorder_threshold)}))} updatedAt={query.dataUpdatedAt} loading={query.isFetching} onRefresh={()=>void query.refetch()}/>;
}
