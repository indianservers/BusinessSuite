import {useState} from 'react';
import {Link} from 'react-router-dom';
import {AlertTriangle, Bell, PackagePlus} from 'lucide-react';
import {Button} from '@/components/ui/button';

type Item = {id:number;name:string;sku:string;quantity:number;threshold:number};

export default function LowStockPanel({items,hasMore=false,updatedAt,loading=false,onRefresh}:{items:Item[];hasMore?:boolean;updatedAt?:number;loading?:boolean;onRefresh:()=>void}) {
 const [expanded,setExpanded]=useState(false);
 const low=items.filter(item=>item.threshold>0&&item.quantity<=item.threshold).sort((a,b)=>a.quantity-b.quantity);
 const unset=items.filter(item=>item.threshold<=0).length;
 return <section aria-label="Low stock alerts" className="rounded-lg border p-4 space-y-3">
  <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-2"><Bell size={18}/><h2 className="font-semibold">Low stock alerts</h2><span role="status" className={low.length?'text-destructive font-semibold':'text-muted-foreground'}>{low.length} {hasMore?'loaded ':''}items need attention</span></div><Button size="sm" variant="outline" onClick={onRefresh} disabled={loading}>{loading?'Checking…':'Check stock now'}</Button></div>
  <p className="text-sm text-muted-foreground">Alerts appear when stock reaches the reorder level (or minimum stock). Checks refresh every minute while this page is open.{updatedAt?` Last checked ${new Date(updatedAt).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}.`:''}</p>
  {low.length>0&&<><div className="flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={()=>setExpanded(value=>!value)}>{expanded?'Hide low stock':'Show low stock'}</Button><Button size="sm" asChild><Link to="/srm/inventory/stock-in"><PackagePlus size={15} className="mr-2"/>Receive stock</Link></Button></div>{expanded&&<ul className="max-h-72 overflow-y-auto divide-y">{low.map(item=><li key={item.id} className="flex flex-wrap items-center justify-between gap-2 py-3"><div><Link className="font-medium underline underline-offset-4" to={`/srm/inventory/items/${item.id}`}>{item.name}</Link><p className="text-xs text-muted-foreground">{item.sku} · Reorder at {item.threshold}</p></div><span className="flex items-center gap-1 text-sm text-destructive"><AlertTriangle size={14}/>{item.quantity<=0?'Out of stock':`${item.quantity} left`}</span></li>)}</ul>}</>}
  {unset>0&&<p className="text-sm">{unset} {hasMore?'loaded ':''}items have no alert threshold. <Link className="underline underline-offset-4" to="/srm/inventory/items">Set each product’s reorder level</Link> to enable alerts.</p>}
  {hasMore&&<p className="text-xs text-muted-foreground">Counts cover loaded items. Load more items below to check the rest.</p>}
 </section>;
}
