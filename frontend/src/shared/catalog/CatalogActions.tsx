import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { Archive, ArrowUpRight, Clipboard, Copy, MoreHorizontal, Pencil, Tags } from "lucide-react";
import type { CatalogItem } from "./api";
export default function CatalogActions({item,canEdit,canCreate=canEdit,busy,edit,tags,copyCode,duplicate,reuse,archive}:{item:CatalogItem;canEdit:boolean;canCreate?:boolean;busy:boolean;edit:()=>void;tags:()=>void;copyCode:()=>void;duplicate:()=>void;reuse:()=>void;archive:()=>void}){
  return <div className="sc-quick-actions" aria-label={`Actions for ${item.name}`}>
    {canEdit&&<><button type="button" className="sc-icon-action" title="Edit item" aria-label={`Edit ${item.name}`} onClick={edit}><Pencil size={15}/></button><button type="button" className="sc-icon-action" title="Manage tags" aria-label={`Manage tags for ${item.name}`} onClick={tags}><Tags size={15}/></button></>}
    <button type="button" className="sc-icon-action" title="Copy item code" aria-label={`Copy code for ${item.name}`} onClick={copyCode}><Clipboard size={15}/></button>
    {(canEdit||canCreate)&&<Dropdown.Root modal={false}><Dropdown.Trigger className="sc-icon-action" aria-label={`More actions for ${item.name}`} title="More actions"><MoreHorizontal size={16}/></Dropdown.Trigger><Dropdown.Portal><Dropdown.Content className="sc-action-menu" align="end" sideOffset={6} collisionPadding={12}><Dropdown.Label>{item.name}</Dropdown.Label><Dropdown.Item disabled={busy||!canCreate} onSelect={duplicate}><Copy size={15}/>Duplicate item</Dropdown.Item><Dropdown.Item disabled={busy||!canEdit} onSelect={()=>requestAnimationFrame(reuse)}><ArrowUpRight size={15}/>Reuse in other branches</Dropdown.Item>{canEdit&&item.status==="Active"&&<><Dropdown.Separator/><Dropdown.Item disabled={busy} onSelect={()=>requestAnimationFrame(archive)}><Archive size={15}/>Archive item</Dropdown.Item></>}</Dropdown.Content></Dropdown.Portal></Dropdown.Root>}
  </div>;
}
