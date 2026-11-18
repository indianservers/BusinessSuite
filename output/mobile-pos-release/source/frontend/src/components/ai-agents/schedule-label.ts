export function recurrenceLabel(spec:{frequency:string;interval?:number;interval_unit?:string}){
 return spec.frequency==='custom'?`Every ${spec.interval} ${spec.interval===1?spec.interval_unit?.replace(/s$/,''):spec.interval_unit}`:spec.frequency;
}
