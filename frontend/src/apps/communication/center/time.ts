/** Convert an explicitly chosen wall time and IANA zone, including DST validation. */
export function zonedInstant(value:string,zone:string):string {
  if(!/^\d{4}-\d\d-\d\dT\d\d:\d\d$/.test(value))throw new Error('Choose a date and time');
  const [year,month,day,hour,minute]=value.split(/[-T:]/).map(Number);
  const desired=Date.UTC(year,month-1,day,hour,minute);let instant=desired;
  const format=new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
  const wall=(stamp:number)=>{const p=Object.fromEntries(format.formatToParts(new Date(stamp)).map(p=>[p.type,p.value]));return {stamp:Date.UTC(Number(p.year),Number(p.month)-1,Number(p.day),Number(p.hour),Number(p.minute)),value:`${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`};};
  for(let i=0;i<3;i++)instant+=desired-wall(instant).stamp;
  if(wall(instant).value!==value)throw new Error('This local time does not exist in the chosen timezone');
  return new Date(instant).toISOString();
}

/** Calendar date in the operator's timezone, matching the visible message date. */
export function localDateKey(value:string):string {
  const date=new Date(value);
  return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
}
