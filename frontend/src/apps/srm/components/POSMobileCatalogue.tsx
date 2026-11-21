import {posOfferingTabs} from "./pos-offering-types";
import { useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { LayoutGrid, Search, SlidersHorizontal, Star, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import { catalogIcon } from './catalog-icon';
import POSCatalogueQuantity from './POSCatalogueQuantity';
import './pos-mobile-catalogue.css';

type MobileProduct = {
  id:number; name:string; image?:string; sku:string; category:string; rate:number;
  stock:number; trackInventory:boolean; checkoutSupported?:boolean; unsupportedReason?:string;
  duration?:string; bookingRequired?:boolean;
};
type Props<T extends MobileProduct> = {
  products:T[]; counts:Record<string,number>;
  cart:{id:number;qty:number}[]; query:string; onQuery:(value:string)=>void;
  searchInputRef:RefObject<HTMLInputElement>; onScan:()=>void;
  category:string; categories:string[]; onCategory:(value:string)=>void;
  tab:string; onTab:(value:string)=>void; sort:string; onSort:(value:string)=>void;
  favorites:number[]; onFavorite:(id:number)=>void; onAdd:(product:T)=>void;
  onRemove:(id:number)=>void;
  isService:(product:T)=>boolean; formatMoney:(value:number)=>string;
  loading:boolean; error:boolean; onRetry:()=>void; canCreate:boolean; locked:boolean;
};

export default function POSMobileCatalogue<T extends MobileProduct>(props:Props<T>) {
  const {products,cart,query,category,tab,sort}=props;
  const [filtersOpen,setFiltersOpen]=useState(false);
  const gridRef=useRef<HTMLDivElement>(null);
  const quantities=useMemo(()=>{const values=new Map<number,number>();cart.forEach(line=>values.set(line.id,(values.get(line.id)||0)+line.qty));return values;},[cart]);
  useEffect(()=>{if(gridRef.current)gridRef.current.scrollTop=0;},[query,category,tab,sort]);
  const reset=()=>{props.onQuery('');props.onCategory('All');props.onTab('All');props.onSort('name');};
  const extraFilters=category!=='All'||!posOfferingTabs.some(value=>value===tab)||sort!=='name';
  return <div className="pos-mobile-catalogue">
    <div className="pos-mobile-search"><Search size={18}/><Input ref={props.searchInputRef} aria-label="Search or scan items" placeholder="Search or scan items" value={query} onChange={event=>props.onQuery(event.target.value)} onKeyDown={event=>{if(event.key==='Enter'){event.preventDefault();props.onScan();}}}/>{query&&<button type="button" aria-label="Clear product search" onClick={()=>props.onQuery('')}><X size={16}/></button>}<button type="button" className={extraFilters?'has-filters':''} aria-label="Product filters" onClick={()=>setFiltersOpen(true)}><SlidersHorizontal size={18}/>{extraFilters&&<span/>}</button></div>
    <nav className="pos-mobile-product-tabs" aria-label="Catalogue filters">
      {posOfferingTabs.map(value=><button key={value} type="button" aria-pressed={tab===value} onClick={()=>props.onTab(value)}>{value} <span>{props.counts[value]}</span></button>)}
    </nav>
    <div className="pos-mobile-catalogue-caption"><strong><LayoutGrid size={13}/>{category==='All'?'Products & services':category}</strong><span>{products.length} {products.length===1?'item':'items'}</span></div>
    <div ref={gridRef} className="pos-mobile-products-grid pos-catalog-results" role="region" aria-label="Catalogue items" tabIndex={0}>
      {props.loading?<div className="pos-mobile-catalogue-message" role="status">Loading products and services…</div>:props.error?<div className="pos-mobile-catalogue-message" role="alert"><strong>Products could not load</strong><Button variant="outline" onClick={props.onRetry}>Retry</Button></div>:!products.length?<div className="pos-mobile-catalogue-message" role="status"><Search size={26}/><strong>No matching items</strong><span>Try another search or clear your filters.</span><Button variant="outline" onClick={reset}>Clear search & filters</Button></div>:products.map(product=>{
        const service=props.isService(product),quantity=quantities.get(product.id)||0;
        const unavailable=product.checkoutSupported===false||product.trackInventory&&product.stock<=0;
        const Icon=catalogIcon(product.name,product.category,service);
        return <article key={product.id} className={`pos-mobile-product-card ${service?'is-service':''} ${quantity?'is-added':''}`}>
          <button type="button" className="pos-mobile-product-main" data-product-id={product.id} aria-label={`Add ${product.name}`} disabled={unavailable||props.locked} onClick={()=>props.onAdd(product)}>
            <span className="pos-mobile-product-art">{product.image?<img src={product.image} alt=""/>:<Icon size={32}/>}</span>
            <strong title={product.name}>{product.name}</strong><small>{service?product.bookingRequired?'Appointment required':product.duration||'Service':product.trackInventory?`${product.sku} · ${product.stock} in stock`:product.sku}</small>
          </button>
          <button type="button" className="pos-mobile-product-favorite" aria-label={`Favorite ${product.name}`} aria-pressed={props.favorites.includes(product.id)} onClick={()=>props.onFavorite(product.id)}><Star size={16} fill={props.favorites.includes(product.id)?'currentColor':'none'}/></button>
          <div className="pos-mobile-product-purchase">
            <strong>{props.formatMoney(product.rate)}</strong>
            <POSCatalogueQuantity product={product} quantity={quantity} locked={props.locked} onRemove={()=>props.onRemove(product.id)} onAdd={()=>props.onAdd(product)} />
          </div>
          {unavailable&&<span className="pos-mobile-product-unavailable" title={product.unsupportedReason}>{product.checkoutSupported===false?'Unavailable':'Out of stock'}</span>}
        </article>;
      })}
    </div>
    <Dialog.Root open={filtersOpen} onOpenChange={setFiltersOpen}><Dialog.Portal><Dialog.Overlay className="pos-booking-overlay"/><Dialog.Content className="pos-mobile-catalogue-dialog" aria-describedby={undefined}>
      <div className="pos-mobile-catalogue-dialog-heading"><Dialog.Title>Product filters</Dialog.Title><Dialog.Close aria-label="Close product filters"><X size={20}/></Dialog.Close></div>
      <label>Category<NativeSelect aria-label="Product category" value={category} onChange={event=>props.onCategory(event.target.value)}>{props.categories.map(value=><option key={value} value={value}>{value==='All'?'All categories':value}</option>)}</NativeSelect></label>
      <label>Show<NativeSelect aria-label="Product collection" value={tab} onChange={event=>props.onTab(event.target.value)}>{[...posOfferingTabs,'Favorites','Frequently Used','Recently Used'].map(value=><option key={value}>{value}</option>)}</NativeSelect></label>
      <label>Sort by<NativeSelect aria-label="Sort catalogue" value={sort} onChange={event=>props.onSort(event.target.value)}><option value="name">Name</option><option value="price">Price: low to high</option><option value="frequent">Most used</option></NativeSelect></label>
      <div className="pos-mobile-catalogue-links"><Link to="/srm/inventory/products">Manage catalogue</Link>{props.canCreate&&<><Link to="/srm/inventory/products?new=item&kind=product">Add product</Link><Link to="/srm/inventory/products?new=item&kind=service">Add service</Link></>}</div>
      <div className="pos-mobile-catalogue-dialog-actions"><Button variant="outline" onClick={reset}>Reset filters</Button><Button onClick={()=>setFiltersOpen(false)}>Show {products.length} items</Button></div>
    </Dialog.Content></Dialog.Portal></Dialog.Root>
  </div>;
}
