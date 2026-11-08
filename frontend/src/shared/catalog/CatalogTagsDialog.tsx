import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { catalogApi, catalogChanged, catalogError, type CatalogItem, type CatalogSource } from "./api";
import { parseCatalogTags } from "./catalog-tags";

export default function CatalogTagsDialog({item,source,close,saved}:{item:CatalogItem;source:CatalogSource;close:()=>void;saved:(item:CatalogItem)=>void}){
  const [record,setRecord]=useState<CatalogItem>(),[text,setText]=useState(""),[busy,setBusy]=useState(false),[error,setError]=useState("");
  useEffect(()=>{let active=true;catalogApi.get(source,item.kind,item.id).then(({data})=>{if(active){setRecord(data);setText((data.tags||[]).join(", "));}}).catch(e=>{if(active)setError(catalogError(e));});return()=>{active=false;};},[source,item.kind,item.id]);
  return <Dialog open onOpenChange={open=>{if(!open&&!busy)close();}}><DialogContent><DialogTitle>Tags for {item.name}</DialogTitle><p className="text-sm text-muted-foreground">Shared across the catalog. Separate tags with commas; use up to 20.</p><form className="space-y-3" onSubmit={async event=>{event.preventDefault();if(!record||busy)return;setBusy(true);setError("");try{const tags=parseCatalogTags(text);const response=await catalogApi.save(source,{...record,tags});catalogChanged();saved(response.data);}catch(e){setError(e instanceof Error&&e.message.startsWith("Use up to")?e.message:catalogError(e));}finally{setBusy(false);}}}><Input aria-label="Item tags" value={text} maxLength={1000} disabled={!record||busy} onChange={event=>setText(event.target.value)} placeholder="e.g. recurring, priority, consulting"/>{!record&&!error&&<p role="status">Loading current item…</p>}{error&&<p role="alert" className="text-sm text-destructive">{error}</p>}<div className="flex justify-end gap-2"><Button type="button" variant="outline" disabled={busy} onClick={close}>Cancel</Button><Button type="submit" disabled={!record||busy}>{busy?"Saving…":"Save tags"}</Button></div></form></DialogContent></Dialog>;
}
