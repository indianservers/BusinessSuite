import {useEffect,useState,type ReactNode} from "react";
import * as Dialog from "@radix-ui/react-dialog";
import {Expand,X} from "lucide-react";
import {useMobile} from "./useMobile";
import "./mobile-chart-zoom.css";
/** Read-only chart view: uses existing data/config and performs no data requests. */
export function MobileChartZoom({title,children,expandedContent,minWidth=640}:{title:string;children:ReactNode;expandedContent?:ReactNode;minWidth?:number}) {
 const phone=useMobile(480),[open,setOpen]=useState(false);
 useEffect(()=>{if(!phone)setOpen(false)},[phone]);
 if(!phone)return <>{children}</>;
 return <div className="suite-mobile-chart"><div className="suite-mobile-chart-preview">{children}</div>
  <Dialog.Root open={open} onOpenChange={setOpen}>
   <Dialog.Trigger asChild><button type="button" className="suite-mobile-chart-expand" aria-label={`Expand ${title}`}><Expand size={16}/>Expand chart</button></Dialog.Trigger>
   <Dialog.Portal><Dialog.Overlay className="suite-mobile-chart-overlay"/>
    <Dialog.Content className="suite-mobile-chart-dialog"><header><div><Dialog.Title>{title}</Dialog.Title><Dialog.Description>Scroll horizontally for the full chart. Arrow keys also scroll the chart area.</Dialog.Description></div><Dialog.Close asChild><button type="button" aria-label="Close expanded chart"><X size={20}/></button></Dialog.Close></header>
     <div className="suite-mobile-chart-scroll" role="region" aria-label={`${title} expanded chart`} tabIndex={0}><div className="suite-mobile-chart-plot" style={{minWidth}}>{expandedContent ?? children}</div></div>
    </Dialog.Content>
   </Dialog.Portal>
  </Dialog.Root>
 </div>;
}
