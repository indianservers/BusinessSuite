import {useState,type ReactNode} from 'react';
export default function CatalogOptions({title,children,onOpen,lazy=false,initialOpen=false}:{title:string;children:ReactNode;onOpen?:()=>void;lazy?:boolean;initialOpen?:boolean}){
 const [mounted,setMounted]=useState(!lazy);
 const [open,setOpen]=useState(initialOpen);
 return <details className="catalog-options" open={open} onToggle={e=>{setOpen(e.currentTarget.open);if(e.currentTarget.open){setMounted(true);onOpen?.();}}}><summary>{title}</summary>{mounted?children:null}</details>;
}
