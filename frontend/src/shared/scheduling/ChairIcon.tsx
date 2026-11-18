import type { SVGProps } from 'react';

/** Upright service chair used by the resource and booking surfaces. */
export default function ChairIcon({size=24,...props}:SVGProps<SVGSVGElement>&{size?:number}) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
    <rect x="7" y="2.5" width="10" height="12" rx="2.5"/>
    <path d="M5 13v4h14v-4M5 14.5h14M7 17l-2 5m12-5 2 5M8 20h8"/>
  </svg>;
}
