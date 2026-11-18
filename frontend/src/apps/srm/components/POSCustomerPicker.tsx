import { UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { useBusinessTerms } from "@/hooks/use-business-terms";
import { useRef, useState } from 'react';
import { Input } from '@/components/ui/input';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';

type Customer = {id:number; name:string; phone?:string;email?:string};
export default function POSCustomerPicker({customers,value,onChange,loading,error}: {customers:Customer[];value:number;onChange:(id:number)=>void;loading?:boolean;error?:boolean}) {
  const [search,setSearch] = useState(''), [open,setOpen] = useState(false);
  const { term } = useBusinessTerms();
  const trigger=useRef<HTMLButtonElement>(null);
  const matches = customers.filter(customer=>`${customer.name} ${customer.phone || ''} ${customer.id}`.toLowerCase().includes(search.trim().toLowerCase()));
  const visible = matches.slice(0,50);
  const selected = customers.find(customer=>customer.id === value);
  return <div className="pos-customer-identity min-w-0 flex-1">
    <span className="pos-customer-avatar">{selected?.id ? selected.name.split(' ').slice(0,2).map(part=>part[0]).join('') : <UserRound size={23}/>}</span>
    <div className="min-w-0 flex-1"><strong>{selected?.name || `Choose ${term('customer').toLowerCase()}`}</strong>{selected?.phone && <span className="block text-xs text-muted-foreground">{selected.phone}</span>}</div>
    <Button ref={trigger} variant="outline" aria-label="Change sale customer" onClick={()=>setOpen(true)}><UserRound size={16}/>Change</Button>
    <Dialog open={open} onOpenChange={setOpen}><DialogContent onCloseAutoFocus={event=>{event.preventDefault();trigger.current?.focus();}}><DialogTitle>Choose {term('customer').toLowerCase()}</DialogTitle><DialogDescription>Search shared records by name, phone or code.</DialogDescription><div className="space-y-3">
    <Input aria-label="Search customers" placeholder="Customer name, phone or code" value={search} onChange={event=>setSearch(event.target.value)}/>
    <Select value={String(value)} loading={loading} error={error} onValueChange={value=>{onChange(Number(value));setOpen(false);}}><SelectTrigger aria-label="Sale customer"><SelectValue/></SelectTrigger><SelectContent>
      {selected && !visible.some(customer=>customer.id===value) && <SelectItem value={String(value)}>{selected.name} (selected)</SelectItem>}
      {visible.map(customer=><SelectItem key={customer.id} value={String(customer.id)}><span className="grid gap-1 text-left"><strong>{customer.name}</strong><span className="grid grid-cols-2 gap-x-4 text-xs"><span>Mobile: {customer.phone||"Not recorded"}</span><span>ID: {customer.id}</span></span>{customer.email&&<small>{customer.email}</small>}</span></SelectItem>)}
    </SelectContent></Select>
    {!matches.length && <p role="status" className="text-xs">No customers match. Change the search or use Quick add.</p>}
    {matches.length > 50 && <p className="text-xs">Showing 50 matches. Refine your search.</p>}
  </div></DialogContent></Dialog>
  </div>;
}
