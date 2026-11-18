import { useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight, Eye, Star, Package, BriefcaseBusiness } from "lucide-react";
import LocalRecordGrid from "@/shared/data-grid/LocalRecordGrid";
import GroupLabel, { RecordStatusIcon } from "@/shared/data-grid/GroupLabel";
import type { GridColumn } from "@/shared/data-grid/types";
import { money, type CatalogItem } from "./api";
import { catalogItemKey } from "./useCatalogPreferences";

export function CatalogList({items,scope,favorites,toggleFavorite,open,actions,select,selected,canSelect,opened}:{items:CatalogItem[];scope:string;favorites:string[];toggleFavorite:(key:string)=>void;open:(item:CatalogItem)=>void;actions:(item:CatalogItem)=>ReactNode;select:(item:CatalogItem,checked:boolean)=>void;selected:CatalogItem[];canSelect:(item:CatalogItem)=>boolean;opened:Record<string,{count:number;last:number}>}){
  const columns:GridColumn<CatalogItem>[]=[
    {id:"favorite",title:"Favorite",width:65,sortable:false,groupable:false,render:item=><button type="button" className="sc-icon-action" title={favorites.includes(catalogItemKey(item))?"Remove favorite":"Add favorite"} aria-label={`${favorites.includes(catalogItemKey(item))?"Unfavorite":"Favorite"} ${item.name}`} aria-pressed={favorites.includes(catalogItemKey(item))} onClick={()=>toggleFavorite(catalogItemKey(item))}><Star size={15} fill={favorites.includes(catalogItemKey(item))?"currentColor":"none"}/></button>},
    {id:"name",title:"Item",width:290,render:item=><button type="button" className="sc-list-identity" onClick={()=>open(item)}>{item.kind==="product"?<Package size={18}/>:<BriefcaseBusiness size={18}/>}<span><strong>{item.name}</strong><small>{item.code}</small></span></button>},
    {id:"kind",title:"Type",width:90}, {id:"category",title:"Category",width:130,accessor:item=>item.category||"Uncategorized"},
    {id:"tags",title:"Tags",width:180,accessor:item=>(item.tags||[]).join(", "),render:item=><span className="sc-item-tags">{item.tags?.length?item.tags.map(tag=><span key={tag}>{tag}</span>):<small>Untagged</small>}</span>},
    {id:"price",title:"Price",type:"number",width:120,render:item=><strong>{money(item.price,item.currency)}<small className="sc-unit"> / {item.unit}</small></strong>},
    {id:"status",title:"Status",width:100,render:item=><span className="sc-list-status"><RecordStatusIcon label={item.status}/><span>{item.status}</span></span>},
    ...(Object.keys(opened).length?[{id:"opens",title:"Your opens",type:"number" as const,width:90,accessor:(item:CatalogItem)=>opened[catalogItemKey(item)]?.count||0}]:[]),
    {id:"actions",title:"Quick actions",width:235,sortable:false,groupable:false,render:item=><div className="sc-list-actions">{canSelect(item)&&<input type="checkbox" aria-label={`Select ${item.name}`} checked={selected.some(row=>catalogItemKey(row)===catalogItemKey(item))} onChange={event=>select(item,event.target.checked)}/>}<button type="button" className="sc-icon-action" title="Preview item" aria-label={`Preview ${item.name}`} onClick={()=>open(item)}><Eye size={15}/></button>{actions(item)}</div>},
  ];
  return <LocalRecordGrid<CatalogItem> gridId={`catalog-list:${scope}`} personalViews={false} selectionEnabled={false} detailsEnabled={false} rows={items} columns={columns} getRowId={catalogItemKey} hideSearch externalPagination onOpen={open} initialLayout={{density:"compact",rowHeight:44}}/>;
}

export function CatalogGroups({items,mode,renderItem}:{items:CatalogItem[];mode:"categories"|"tags";renderItem:(item:CatalogItem)=>ReactNode}){
  const [closed,setClosed]=useState<Set<string>>(new Set());
  const groups=new Map<string,CatalogItem[]>();
  for(const item of items){const labels=mode==="categories"?[item.category||"Uncategorized"]:item.tags?.length?item.tags:["Untagged"];for(const label of labels)groups.set(label,[...(groups.get(label)||[]),item]);}
  return <section className="sc-grouped-view" aria-label={mode==="tags"?"Items by tag":"Items by category"}><div className="sc-group-summary"><span>{groups.size} {mode==="tags"?"tags":"categories"} on this page · {items.length} unique items{mode==="tags"?" · An item can appear under multiple tags":""}</span><button type="button" onClick={()=>setClosed(new Set())}>Expand all</button><button type="button" onClick={()=>setClosed(new Set(groups.keys()))}>Collapse all</button></div>{[...groups].sort(([a],[b])=>a.localeCompare(b)).map(([label,rows])=><section key={label}><button type="button" className="sc-group-heading" aria-expanded={!closed.has(label)} aria-label={`${closed.has(label)?"Expand":"Collapse"} ${mode==="tags"?"tag":"category"} ${label}`} onClick={()=>setClosed(current=>{const next=new Set(current);next.has(label)?next.delete(label):next.add(label);return next;})}>{closed.has(label)?<ChevronRight size={14}/>:<ChevronDown size={14}/>}<GroupLabel label={label} field={mode==="tags"?"Tag":"Category"} count={rows.length}/></button>{!closed.has(label)&&<div className="sc-grid">{rows.map(renderItem)}</div>}</section>)}</section>;
}
