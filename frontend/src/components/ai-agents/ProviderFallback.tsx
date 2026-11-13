type Provider={provider:string;model:string;enabled:boolean;data_sharing_allowed:boolean};
export function FallbackChoice({primary,value,providers,disabled,onChange}:{primary:string;value:string;providers:Provider[];disabled:boolean;onChange:(value:string)=>void}){
 if(primary==='local')return null;
 const choices=providers.filter(p=>p.enabled&&p.data_sharing_allowed&&p.provider!==primary);
 return <label className="mt-2 block text-sm">Planning fallback <select aria-label="Planning fallback" className="ml-2 rounded border bg-background p-2" value={value} disabled={disabled} onChange={e=>onChange(e.target.value)}><option value="">None</option>{value&&!choices.some(p=>p.provider===value)&&<option value={value}>{value} · unavailable</option>}{choices.map(p=><option key={p.provider} value={p.provider}>{p.provider} · {p.model}</option>)}</select><span className="mt-1 block text-xs text-muted-foreground">If planning times out or the provider is temporarily unavailable, allow this request’s authorized context to be sent to this provider. Actions still need review.</span></label>;
}

export function FallbackAttempts({value}:{value?:{fallback_used:boolean;attempts:{provider:string;model:string;status:string;error_code?:string}[]}}){
 if(!value?.attempts?.length)return null;
 return <div className="rounded border p-3 text-sm" aria-label="Provider attempts"><p>{value.fallback_used?'Planning used the selected fallback.':'Planning provider attempts'}</p><ol className="mt-1 list-inside list-decimal">{value.attempts.map((a,i)=><li key={i}>{a.provider} / {a.model}: {a.status}{a.error_code?` · ${a.error_code}`:''}</li>)}</ol></div>;
}
