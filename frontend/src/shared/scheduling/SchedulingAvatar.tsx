import { useState } from 'react';

/** Images come from the record; initials remain the fallback for live records without a photo. */
export default function SchedulingAvatar({ name, src, className = 'appointment-avatar' }: { name: string; src?: string; className?: string }) {
  const [failed,setFailed] = useState<string>();
  return <span className={`${className} scheduling-avatar`} aria-hidden="true">
    {name.split(' ').slice(0,2).map(word=>word[0]).join('').toUpperCase() || '?'}
    {src && failed!==src && <img src={src} alt="" onError={()=>setFailed(src)}/>}
  </span>;
}
