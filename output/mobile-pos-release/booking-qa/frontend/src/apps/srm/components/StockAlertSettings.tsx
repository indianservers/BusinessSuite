import {useState} from 'react';
import {useMutation,useQueryClient} from '@tanstack/react-query';
import {srmApi} from '../api';
import {useFinanceWrite} from '@/apps/fam/useFinanceWrite';
import {useRecordScope,recordScope} from '@/lib/record-scope';
import {useAuthStore} from '@/store/authStore';
import {Input} from '@/components/ui/input';
import {Button} from '@/components/ui/button';
import {catalogError} from '@/shared/catalog/api';

export default function StockAlertSettings({id,reorder,minimum}:{id:string;reorder:number;minimum:number}) {
 const scope=useRecordScope(),qc=useQueryClient(),canEdit=useFinanceWrite(['srm_manage','srm_admin'],'edit');
 const [level,setLevel]=useState(String(reorder)),[min,setMin]=useState(String(minimum)),[message,setMessage]=useState('');
 const [owner]=useState(()=>recordScope(useAuthStore.getState().user));
 const save=useMutation({mutationFn:async()=>{
  if(owner!==recordScope(useAuthStore.getState().user))throw Error('Inventory context changed. Reopen this item.');
  if(![level,min].every(value=>/^\d+(?:\.\d{1,3})?$/.test(value)&&Number.isFinite(Number(value))))throw Error('Enter nonnegative stock levels with up to three decimal places.');
  return srmApi.updateInventoryItem(id,{reorder_level:Number(level),min_stock:Number(min)});
 },onSuccess:()=>{if(owner!==recordScope(useAuthStore.getState().user))return;setMessage('Stock alert levels saved. Reports will use these levels.');void qc.invalidateQueries({queryKey:['srm']});},onError:error=>setMessage(error instanceof Error&&!('response' in error)?error.message:catalogError(error))});
 return <form key={scope} aria-label="Stock alert settings" className="rounded-lg border p-4 space-y-3" onSubmit={event=>{event.preventDefault();setMessage('');if(canEdit&&!save.isPending)save.mutate();}}>
  <h2 className="font-semibold">Stock alert settings</h2><p className="text-sm text-muted-foreground">Alert when on-hand stock reaches this level. If reorder level is zero, minimum stock is used. Set both to zero to turn off this item’s low-stock alert.</p>
  <fieldset disabled={!canEdit||save.isPending} className="flex flex-wrap items-end gap-3"><label className="grid gap-1 text-sm">Reorder level<Input aria-label="Stock alert reorder level" inputMode="decimal" value={level} onChange={event=>setLevel(event.target.value)}/></label><label className="grid gap-1 text-sm">Minimum stock<Input aria-label="Stock alert minimum stock" inputMode="decimal" value={min} onChange={event=>setMin(event.target.value)}/></label><Button type="submit">{save.isPending?'Saving…':'Save stock alerts'}</Button></fieldset>
  {message&&<p role={save.isError?'alert':'status'} className="text-sm">{message}</p>}
 </form>;
}
