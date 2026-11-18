import { useEffect, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useMobile } from '@/components/mobile/useMobile';
/** Keep the native controls and their handlers visible above every record page. */
export default function SRMMobileToolbar({children}:{children:ReactNode}){
  const mobile=useMobile(),[target,setTarget]=useState<HTMLElement|null>(null);
  useEffect(()=>{setTarget(mobile?document.querySelector<HTMLElement>('.srm-mobile-booking-toolbar'):null);},[mobile]);
  return mobile&&target?createPortal(children,target):<>{children}</>;
}
