import {useState,type ReactNode} from 'react';
export default function CatalogOptions({title,children,onOpen,lazy=false}:{title:string;children:ReactNode;onOpen?:()=>void;lazy?:boolean}){
 const [mounted,setMounted]=useState(!lazy);
 return <details className="catalog-options" onToggle={e=>{if(e.currentTarget.open){setMounted(true);onOpen?.();}}}><summary>{title}</summary>{mounted?children:null}</details>;
}
