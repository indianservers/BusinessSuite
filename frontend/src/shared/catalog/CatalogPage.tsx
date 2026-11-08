import {reconcileRecordList,recordSavedEvent,type RecordSaved} from "@/lib/record-changes";
import {useAuthStore} from "@/store/authStore";
import { useCreateIntent } from "@/hooks/use-create-intent";
import GroupedRecords from "@/shared/data-grid/GroupedRecords";
import { standardRecordGroups } from "@/shared/data-grid/record-group-fields";
import { NativeSelect } from "@/components/ui/native-select";
import { ImportWizard, DataExportButton } from "@/shared/data-transfer";
import { catalogImportFields } from "@/shared/data-transfer/fields";
import { useCallback, useEffect, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { ArrowDownUp, ArrowUpRight, Boxes, BriefcaseBusiness, Clock3, FolderTree, LayoutGrid, List, Package, Pencil, Plus, RefreshCw, Search, Star, Tags, X } from "lucide-react";
import { Link, useLocation, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { api } from "@/services/api";
import { catalogApi, catalogChanged, catalogError, money, useCatalogRefresh, useDebounced, type CatalogItem, type CatalogKind, type CatalogSource } from "./api";
import CatalogEditor from "./CatalogEditor";
import CatalogBranchReuse from "./CatalogBranchReuse";
import CatalogActions from "./CatalogActions";
import CatalogTagsDialog from "./CatalogTagsDialog";
import { CatalogGroups, CatalogList } from "./CatalogViews";
import useCatalogPreferences, { catalogItemKey, type CatalogView } from "./useCatalogPreferences";
import "./catalog.css";
import "./catalog-views.css";

const views = [{id:"cards",label:"Cards",Icon:LayoutGrid},{id:"list",label:"List",Icon:List},{id:"categories",label:"Categories",Icon:FolderTree},{id:"tags",label:"Tags",Icon:Tags},{id:"frequent",label:"Frequent",Icon:Clock3},{id:"favorites",label:"Favorites",Icon:Star}] as const;
type CatalogData={items:CatalogItem[];total:number;pages:number;permissions:Partial<Record<CatalogKind,boolean>>;facets?:{categories:string[];tags:string[]}};
const emptyData=():CatalogData=>({items:[],total:0,pages:0,permissions:{}});
export default function CatalogPage({ source }: { source: CatalogSource }) {
  const location=useLocation(),params=useParams(),personal=useCatalogPreferences();
  const actor=useAuthStore(s=>s.user),grant=actor?.access?.grants[source];
  const permits=(action:string)=>!!actor?.is_superuser||!actor?.access?.managed||!!grant?.enabled&&grant.actions.includes(action);
  const [search,setSearch]=useState(""),query=useDebounced(search);
  const [kind,setKind]=useState<""|CatalogKind>(location.pathname.includes("services")&&!location.pathname.includes("products-services")?"service":"");
  const [status,setStatus]=useState("Active"),[category,setCategory]=useState(""),[tag,setTag]=useState(""),[sort,setSort]=useState("name"),[direction,setDirection]=useState("asc");
  const [page,setPage]=useState(1),[revision,setRevision]=useState(0),[perPage,setPerPage]=useState(24);
  const [data,setData]=useState<CatalogData>(emptyData),[dataKey,setDataKey]=useState("");
  const [loading,setLoading]=useState(true),[error,setError]=useState(""),[message,setMessage]=useState("");
  const [editor,setEditor]=useState<CatalogItem|"new"|null>(new URLSearchParams(location.search).has("new")||location.pathname.endsWith("/create")?"new":null),[preview,setPreview]=useState<CatalogItem|null>(null),[tagItem,setTagItem]=useState<CatalogItem|null>(null);
  const [selected,setSelected]=useState<CatalogItem[]>([]),[reuseItems,setReuseItems]=useState<CatalogItem[]|null>(null),[archiveItem,setArchiveItem]=useState<CatalogItem|null>(null),[busy,setBusy]=useState(false);
  const mutating=useRef(false);
  const frequentKeys=Object.entries(personal.opened).sort((a,b)=>b[1].count-a[1].count||b[1].last-a[1].last).map(([key])=>key);
  const itemKeys=personal.view==="favorites"?personal.favorites.join(","):personal.view==="frequent"?frequentKeys.join(","):undefined;
  const projectionKey=JSON.stringify([source,personal.scope,query,kind,status,category,tag,sort,direction,page,perPage,itemKeys,personal.view==="frequent"]);
  const requestKey=JSON.stringify([projectionKey,revision]);
  const ready=dataKey===projectionKey,items=ready?data.items:[],isLoading=!ready;

  useEffect(()=>{setKind(location.pathname.includes("services")&&!location.pathname.includes("products-services")?"service":"");setPage(1);},[location.pathname]);
  const refresh=useCallback(()=>setRevision(value=>value+1),[]);
  useCatalogRefresh(refresh);
  useEffect(()=>{
    const changed=(event:Event)=>{
      const change=(event as CustomEvent<RecordSaved>).detail;
      if(!change.resource?.startsWith("/catalog/items"))return;
      const item=change.record as unknown as CatalogItem;
      setData(current=>{
        const next=reconcileRecordList(current,change) as CatalogData;
        if(change.operation==="delete"||!item.id||!["product","service"].includes(item.kind)||current.items.some(row=>catalogItemKey(row)===catalogItemKey(item)))return next;
        if(page!==1||itemKeys||query&&!item.name.toLowerCase().includes(query.toLowerCase())||kind&&kind!==item.kind||status&&item.status!==status||category&&item.category!==category||tag&&!item.tags?.includes(tag)||!current.permissions[item.kind])return next;
        return {...next,items:[item,...next.items].slice(0,perPage),total:next.total+1};
      });
      if(change.operation==="delete")setPreview(current=>current&&change.ids?.map(String).includes(String(current.id))&&(!change.kind||change.kind===current.kind)?null:current);
      refresh();
    };
    window.addEventListener(recordSavedEvent,changed);return()=>window.removeEventListener(recordSavedEvent,changed);
  },[page,perPage,itemKeys,query,kind,status,category,tag,refresh]);

  useEffect(()=>{
    let active=true;setLoading(true);setError("");setSelected([]);
    catalogApi.list(source,{search:query,kind:kind||undefined,status,category,tag,sort,direction,page,per_page:perPage,item_keys:itemKeys,key_order:personal.view==="frequent",include_facets:true}).then(({data:result})=>{
      if(!active)return;setData(result);setDataKey(projectionKey);if(page>Math.max(1,result.pages))setPage(Math.max(1,result.pages));
    }).catch(e=>{if(active){if(!ready)setData(emptyData());setDataKey(projectionKey);setError(catalogError(e));}}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};
  },[requestKey]);
  useEffect(()=>{let active=true;if(params.id)catalogApi.get(source,location.pathname.includes("services")?"service":"product",Number(params.id)).then(({data})=>{if(active)setPreview(data);}).catch(e=>{if(active)setError(catalogError(e));});return()=>{active=false;};},[params.id,source,location.pathname]);
  // A row may be opened while a save-triggered list refresh is still in flight.
  // Load the current record so the preview cannot retain stale tags or prices.
  useEffect(()=>{if(!preview)return;let active=true;catalogApi.get(source,preview.kind,preview.id).then(({data})=>{if(active)setPreview(data);}).catch(e=>{if(active)setError(catalogError(e));});return()=>{active=false;};},[source,preview?.kind,preview?.id]);
  const canCreate=ready&&permits("create")&&Object.values(data.permissions).some(Boolean);
  const canEdit=(item:CatalogItem)=>ready&&permits("edit")&&data.permissions[item.kind]===true;
  useCreateIntent(()=>setEditor("new"));
  const open=(item:CatalogItem)=>{personal.recordOpen(catalogItemKey(item));setPreview(item);};
  const select=(item:CatalogItem,checked:boolean)=>setSelected(current=>checked?[...current.filter(row=>catalogItemKey(row)!==catalogItemKey(item)),item]:current.filter(row=>catalogItemKey(row)!==catalogItemKey(item)));
  async function mutate(item:CatalogItem,operation:"archive"|"duplicate"){
    if(mutating.current)return;mutating.current=true;setBusy(true);setError("");try{await api.post(`/catalog/items/${item.kind}/${item.id}/${operation}`,{},{params:{source}});setArchiveItem(null);catalogChanged();refresh();setMessage(operation==="archive"?"Item archived. Existing associations are preserved.":"Item duplicated with a new code.");}catch(e){setError(catalogError(e));}finally{mutating.current=false;setBusy(false);}
  }
  const copyCode=(item:CatalogItem)=>{void navigator.clipboard.writeText(item.code).then(()=>setMessage(`Code copied: ${item.code}`)).catch(()=>setError("Could not copy the code. Check browser clipboard access."));};
  const actions=(item:CatalogItem)=><CatalogActions item={item} canEdit={canEdit(item)} canCreate={canCreate} busy={busy} edit={()=>setEditor(item)} tags={()=>setTagItem(item)} copyCode={()=>copyCode(item)} duplicate={()=>void mutate(item,"duplicate")} reuse={()=>setReuseItems([item])} archive={()=>setArchiveItem(item)}/>;
  const renderCard=(item:CatalogItem)=><article className="sc-card" key={catalogItemKey(item)}>
    <div className="sc-card-media"><button type="button" className="sc-card-cover" aria-label={`Preview ${item.name}`} onClick={()=>open(item)}>{item.images[0]?<img src={item.images[0]} alt="" referrerPolicy="no-referrer"/>:<div className={`sc-card-art ${item.kind}`}>{item.kind==="product"?<Package size={38} strokeWidth={1.3}/>:<BriefcaseBusiness size={38} strokeWidth={1.3}/>}</div>}<span className="sc-kind">{item.kind}</span><span className={`sc-status ${item.status.toLowerCase()}`}><i/>{item.status}</span></button><button type="button" className="sc-card-star sc-icon-action" aria-label={`${personal.favorites.includes(catalogItemKey(item))?"Unfavorite":"Favorite"} ${item.name}`} aria-pressed={personal.favorites.includes(catalogItemKey(item))} title="Toggle favorite" onClick={()=>personal.toggleFavorite(catalogItemKey(item))}><Star size={16} fill={personal.favorites.includes(catalogItemKey(item))?"currentColor":"none"}/></button></div>
    <div className="sc-card-body"><div className="sc-card-meta">{canEdit(item)&&<input type="checkbox" aria-label={`Select ${item.name}`} checked={selected.some(row=>catalogItemKey(row)===catalogItemKey(item))} onChange={event=>select(item,event.target.checked)}/>}<span>{item.code}</span><small>{item.category||"Uncategorized"}</small></div><button type="button" className="sc-card-title" onClick={()=>open(item)}><span>{item.name}</span><ArrowUpRight size={15}/></button><p className="sc-card-description">{item.description||"No description added."}</p><div className="sc-item-tags">{item.tags?.map(value=><button type="button" key={value} title={`Filter tag: ${value}`} onClick={()=>{setTag(value);setPage(1);}}>{value}</button>)}</div><div className="sc-card-price"><strong>{money(item.price,item.currency)}</strong><span>/ {item.unit}</span>{!!item.pricing_options.length&&<small>+{item.pricing_options.length} prices</small>}</div><footer><span>{item.workspace_id?`Workspace #${item.workspace_id}`:"Organization catalog"}</span>{actions(item)}</footer>{source==="crm"&&<Link className="sc-related-link" to={`/crm/product-customers?kind=${item.kind}&item_id=${item.id}&product_name=${encodeURIComponent(item.name)}`}>Related customers & pipeline<ArrowUpRight size={12}/></Link>}</div>
  </article>;
  const categories=data.facets?.categories||[...new Set(items.map(item=>item.category).filter(Boolean))];
  const tags=data.facets?.tags||[...new Set(items.flatMap(item=>item.tags||[]))];
  const writable=items.filter(canEdit);
  const changeView=(view:CatalogView)=>{personal.setView(view);setPage(1);setSelected([]);};
  return <main className="sc-page">
    <header className="sc-hero"><div><h1>Products & services<span><Boxes size={23}/></span></h1><p>Your shared products, services and pricing.</p></div><div className="sc-hero-actions"><Button variant="outline" size="icon" aria-label="Refresh catalog" title="Refresh catalog" disabled={isLoading} onClick={refresh}><RefreshCw size={16}/></Button><DataExportButton filename="products-services" description="All accessible products and services, including archived items." load={async()=>(await api.get("/catalog/export",{params:{source,format:"json"},responseType:"blob"})).data}/><ImportWizard disabled={!canCreate} title="Import products & services" fields={catalogImportFields.map(field=>field.key==="kind"?{...field,default:kind||"product"}:field)} maxRows={500} maxBytes={2*1024*1024} onImport={async({file})=>{const form=new FormData();form.append("file",file);const response=await api.post("/catalog/import",form,{params:{source}});catalogChanged();refresh();return response.data;}}/>{canCreate&&<Button onClick={()=>setEditor("new")}><Plus size={16}/>New item</Button>}</div></header>
    {source==="crm"&&<nav className="sc-growth-links" aria-label="CRM customer growth"><Link to="/crm/product-customers">Customers & pipeline</Link><Link to="/crm/customer-follow-ups">Follow-ups</Link><Link to="/crm/greetings">Greetings</Link></nav>}
    <div className="sc-catalog-bar"><div className="sc-tabs" role="group" aria-label="Catalog type">{[["","All items"],["product","Products"],["service","Services"]].map(([key,label])=><button type="button" key={key} aria-pressed={kind===key} onClick={()=>{setKind(key as typeof kind);setPage(1);}}>{label}</button>)}</div><span className="sc-muted">{ready?data.total:"..."} matching items</span></div>
    <section className="sc-workspace" aria-label="Catalog workspace">
      <nav className="sc-view-tabs" role="tablist" aria-label="Catalog views">{views.map(({id,label,Icon})=><button key={id} type="button" role="tab" tabIndex={personal.view===id?0:-1} onKeyDown={event=>{if(!["ArrowLeft","ArrowRight","Home","End"].includes(event.key))return;event.preventDefault();const index=views.findIndex(view=>view.id===id);const next=event.key==="Home"?0:event.key==="End"?views.length-1:(index+(event.key==="ArrowRight"?1:-1)+views.length)%views.length;changeView(views[next].id);document.getElementById(`catalog-view-${views[next].id}`)?.focus();}} id={`catalog-view-${id}`} aria-selected={personal.view===id} aria-controls="catalog-view-panel" onClick={()=>changeView(id)}><Icon size={15}/>{label}</button>)}</nav>
      <div className="sc-filters"><label className="sc-search"><Search size={16}/><input placeholder="Search name, code or description..." aria-label="Search catalog" value={search} onChange={event=>{setSearch(event.target.value);setPage(1);}}/></label><NativeSelect aria-label="Filter category" value={category} onChange={event=>{setCategory(event.target.value);setPage(1);}}><option value="">All categories</option>{[...new Set([...categories,...(category?[category]:[])])].map(value=><option key={value}>{value}</option>)}</NativeSelect><NativeSelect aria-label="Filter tag" value={tag} onChange={event=>{setTag(event.target.value);setPage(1);}}><option value="">All tags</option>{[...new Set([...tags,...(tag?[tag]:[])])].map(value=><option key={value}>{value}</option>)}</NativeSelect><NativeSelect aria-label="Filter status" value={status} onChange={event=>{setStatus(event.target.value);setPage(1);}}><option>Active</option><option>Archived</option><option value="all">All statuses</option></NativeSelect><NativeSelect aria-label="Sort catalog" value={sort} disabled={personal.view==="frequent"} onChange={event=>{setSort(event.target.value);setPage(1);}}><option value="name">Name</option><option value="price">Price</option><option value="category">Category</option><option value="code">Code</option></NativeSelect><button type="button" aria-label="Reverse sort order" title="Reverse sort order" disabled={personal.view==="frequent"} onClick={()=>{setDirection(value=>value==="asc"?"desc":"asc");setPage(1);}}><ArrowDownUp size={15}/></button>{(query||category||tag||status!=="Active")&&<button type="button" onClick={()=>{setSearch("");setCategory("");setTag("");setStatus("Active");setPage(1);}}>Clear filters</button>}</div>
      <div className="sc-view-context"><span>{personal.view==="frequent"?"Most opened by you - personal to this account and company in this browser":personal.view==="favorites"?"Your favorites - personal to this account and company in this browser":personal.view==="categories"||personal.view==="tags"?"Groups show this page; category and tag filters search all matching items":"Shared catalog - personal view preferences saved in this browser"}</span>{canCreate&&writable.length>0&&<label><input type="checkbox" aria-label="Select all offerings on this page" checked={writable.every(item=>selected.some(row=>catalogItemKey(row)===catalogItemKey(item)))} onChange={event=>setSelected(event.target.checked?writable:[])}/>Select page</label>}</div>
      {selected.length>0&&<div className="sc-selection-bar"><span>{selected.length} selected</span><Button variant="outline" onClick={()=>setReuseItems(selected)}><ArrowUpRight size={14}/>Reuse in other branches</Button><button type="button" onClick={()=>setSelected([])}>Clear selection</button></div>}
      {error&&<p className="sc-error" role="alert">{error}<button type="button" onClick={refresh}>Retry</button></p>}{message&&<p className="sc-success" role="status">{message}<button type="button" aria-label="Dismiss catalog notice" onClick={()=>setMessage("")}><X size={13}/></button></p>}
      <div role="tabpanel" id="catalog-view-panel" aria-labelledby={`catalog-view-${personal.view}`} aria-busy={isLoading}>
        {isLoading?<p className="sc-loading" role="status">Loading catalog...</p>:items.length>0?personal.view==="cards"?<GroupedRecords personalViews={false} scope="shared/catalog/CatalogPage:cards-1" items={items} fields={standardRecordGroups(items)} gridClassName="sc-grid" renderItem={renderCard}/>:personal.view==="categories"||personal.view==="tags"?<CatalogGroups key={personal.view} items={items} mode={personal.view} renderItem={renderCard}/>:<CatalogList items={items} scope={personal.scope} favorites={personal.favorites} toggleFavorite={personal.toggleFavorite} open={open} actions={actions} selected={selected} select={select} canSelect={canEdit} opened={personal.opened}/>:!error&&<div className="sc-empty"><Boxes size={32}/><h2>{personal.view==="favorites"?"No matching favorites":personal.view==="frequent"?"Your frequent items will appear here":query||category||tag?"No matching offerings":"Your catalog is ready for its first item"}</h2><p>{personal.view==="favorites"?"Star an item in Cards or List to keep it here. Your current filters still apply.":personal.view==="frequent"?"Preview items from Cards or List. This view ranks the items you open most often.":"Try another filter or add a product or service."}</p>{personal.view==="favorites"||personal.view==="frequent"?<Button variant="outline" onClick={()=>changeView("list")}><List size={15}/>Browse all items</Button>:canCreate&&<Button onClick={()=>setEditor("new")}><Plus size={15}/>New item</Button>}</div>}
      </div>
      <footer className="sc-pagination"><label>Rows<NativeSelect aria-label="Catalog rows per page" value={perPage} onChange={event=>{setPerPage(Number(event.target.value));setPage(1);}}>{[12,24,48,100].map(count=><option key={count}>{count}</option>)}</NativeSelect></label><span>{ready&&data.total?`${(page-1)*perPage+1}-${Math.min(page*perPage,data.total)} of ${data.total}`:"0 items"}</span><Button variant="outline" disabled={isLoading||page<=1} onClick={()=>setPage(value=>value-1)}>Previous</Button><span>Page {page} of {Math.max(1,ready?data.pages:1)}</span><Button variant="outline" disabled={isLoading||!ready||page>=data.pages} onClick={()=>setPage(value=>value+1)}>Next</Button></footer>
    </section>
    {tagItem&&<CatalogTagsDialog item={tagItem} source={source} close={()=>setTagItem(null)} saved={row=>{setTagItem(null);if(preview&&catalogItemKey(preview)===catalogItemKey(row))setPreview(row);refresh();setMessage("Tags saved across the shared catalog.");}}/>}
    {reuseItems && <CatalogBranchReuse items={reuseItems} source={source} close={() => setReuseItems(null)} saved={message => { setReuseItems(null); setSelected([]); setMessage(message); refresh(); }}/>}
    {editor && (editor==="new"?canCreate:canEdit(editor)) && <CatalogEditor source={source} initial={editor === "new" ? undefined : editor} defaultKind={kind || (data.permissions.product ? "product" : "service")} close={() => setEditor(null)} saved={row => { setEditor(null); if(preview&&catalogItemKey(preview)===catalogItemKey(row))setPreview(row); refresh(); }}/>}<Dialog.Root open={!!preview} onOpenChange={open => { if (!open) setPreview(null); }}><Dialog.Portal><Dialog.Overlay className="sc-overlay"/><Dialog.Content className="sc-preview">{preview && <><Dialog.Close className="sc-preview-close" aria-label="Close preview"><X size={20}/></Dialog.Close><span className="sc-eyebrow">{preview.kind} / {preview.code}</span><Dialog.Title>{preview.name}</Dialog.Title><Dialog.Description>{preview.description || "No description added."}</Dialog.Description><div className="sc-item-tags">{preview.tags?.map(tag=><span key={tag}>{tag}</span>)}</div><div className="sc-preview-price">{money(preview.price, preview.currency)}<small>per {preview.unit} · {preview.tax}% tax</small></div>{preview.images.map((url, index) => <img className="sc-preview-image" key={index} src={url} alt={`${preview.name} ${index + 1}`} referrerPolicy="no-referrer"/>)}{preview.pricing_options.map(price => <div className="sc-preview-line" key={price.id}><span>{price.name}</span><strong>{money(Number(price.amount), price.currency)}<small>{price.interval === "once" ? "One-time" : `Every ${price.interval}`}</small></strong></div>)}{Object.entries(preview.custom_fields).map(([name, value]) => <div className="sc-preview-line" key={name}><span>{name}</span><strong>{String(value ?? "—")}</strong></div>)}{canEdit(preview) && <Button onClick={() => { setEditor(preview); setPreview(null); }}><Pencil size={15}/>Edit item</Button>}</>}</Dialog.Content></Dialog.Portal></Dialog.Root>
    <Dialog.Root open={!!archiveItem} onOpenChange={open => { if (!open && !busy) setArchiveItem(null); }}><Dialog.Portal><Dialog.Overlay className="sc-overlay"/><Dialog.Content className="sc-preview"><Dialog.Title>Archive {archiveItem?.name}?</Dialog.Title><Dialog.Description>Existing links and quotations stay intact. This item will no longer appear in active selectors.</Dialog.Description>{error && <p role="alert">{error}</p>}<div className="sc-form-footer"><Button variant="outline" disabled={busy} onClick={() => setArchiveItem(null)}>Cancel</Button><Button disabled={busy} onClick={() => archiveItem && void mutate(archiveItem, "archive")}>{busy ? "Archiving…" : "Archive item"}</Button></div></Dialog.Content></Dialog.Portal></Dialog.Root>
  </main>;
}
