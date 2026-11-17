import { useEffect, useRef, useState, type MutableRefObject } from 'react';
import { useQuery } from '@tanstack/react-query';
import { catalogApi, catalogError, money, type CatalogItem } from '@/shared/catalog/api';
import { useRecordScope } from '@/lib/record-scope';
import { api } from '@/services/api';
import type { Options } from '@/apps/srm/industry/POSServiceScheduling';
import SmartRecordPicker from '@/shared/records/SmartRecordPicker';
import { NativeSelect } from '@/components/ui/native-select';
import { useBusinessTerms } from '@/hooks/use-business-terms';

export default function PrebookingServicePicker({ value, onChange, onSelected, onQuoteReady, validateRef }: { value: string; onChange: (value: string) => void; onSelected: (service?: CatalogItem) => void; onQuoteReady?:(ready:boolean)=>void; validateRef?:MutableRefObject<(()=>Promise<CatalogItem|undefined>)|null> }) {
  const scope = useRecordScope(), { term } = useBusinessTerms();
  const [search, setSearch] = useState(''), [category, setCategory] = useState(''), [page, setPage] = useState(1), [chosen, setChosen] = useState<CatalogItem>();
  const list = useQuery({ queryKey: ['prebooking-catalog', scope, search, category, page], retry: false,
    queryFn: () => catalogApi.list('srm', { kind: 'service', status: 'Active', search, category, page, per_page: 50, include_facets: true }).then(r => r.data) });
  const facets = useQuery({ queryKey: ['prebooking-service-categories', scope], retry: false,
    queryFn: () => catalogApi.list('srm', { kind: 'service', status: 'Active', per_page: 1, include_facets: true }).then(r => r.data.facets?.categories || []) });
  const options = useQuery({ queryKey: ['prebooking-options', scope, Number(value)], enabled: !!value, retry: false,
    queryFn: ({ signal }) => api.get<Options>('/srm/service-checkout/options', { signal, recordCache: false, params: { service_id: value } }).then(r => r.data) });
  const initialQuote=useRef<string>();
  const callbacks=useRef({onSelected,onQuoteReady});callbacks.current={onSelected,onQuoteReady};
  const [acceptedQuote,setAcceptedQuote]=useState('');
  const detail=useQuery({queryKey:['prebooking-service-detail',scope,value],enabled:!!value,retry:false,refetchInterval:60000,
    queryFn:async()=>{const record=(await catalogApi.get('srm','service',Number(value))).data;if(record.id!==Number(value)||record.kind!=='service')throw new Error('Service details are unavailable');return record;}});
  const selected=detail.data || (String(chosen?.id)===value?chosen:undefined);
  const quoteKey=selected?`${selected.id}:${selected.price}:${selected.currency}:${selected.tax}`:'';
  useEffect(()=>{if(detail.isSuccess && quoteKey && !initialQuote.current)initialQuote.current=quoteKey;},[detail.isSuccess,quoteKey]);
  const needsReview=!!initialQuote.current && quoteKey!==initialQuote.current && quoteKey!==acceptedQuote;
  useEffect(()=>{callbacks.current.onSelected(selected);callbacks.current.onQuoteReady?.(!!value && detail.isSuccess && !detail.isFetching && !needsReview);},[selected,value,detail.isSuccess,detail.isFetching,needsReview]);
  useEffect(()=>{if(!validateRef)return;validateRef.current=async()=>{const response=await detail.refetch();const fresh=response.data;if(!response.isSuccess||!fresh)return;const key=`${fresh.id}:${fresh.price}:${fresh.currency}:${fresh.tax}`;if(initialQuote.current && key!==initialQuote.current && key!==acceptedQuote && !window.confirm(`The estimated service price changed to ${money(fresh.price,fresh.currency)} before tax. Accept this updated estimate?`))return;initialQuote.current=key;setAcceptedQuote(key);callbacks.current.onSelected(fresh);callbacks.current.onQuoteReady?.(true);return fresh;};return()=>{validateRef.current=null;};},[validateRef,detail.refetch,acceptedQuote]);
  const price = selected && Number.isFinite(selected.price) && selected.currency ? money(selected.price, selected.currency) : 'Price unavailable';
  return <div className="prebooking-service-picker">
    <div className="prebooking-service-row"><label>{term('service')}<SmartRecordPicker name={term('service')} value={value} search={search} onSearch={s => { setSearch(s); setPage(1); }}
      items={(list.data?.items || []).filter(r => r.kind === 'service').map(r => ({ id: String(r.id), label: r.name, description: [r.category, Number.isFinite(r.price) && r.currency ? money(r.price, r.currency) : undefined].filter(Boolean).join(' · '), record: r }))}
      selected={selected ? { id: String(selected.id), label: selected.name, record: selected } : undefined}
      onSelect={r => { initialQuote.current=`${r.id}:${r.price}:${r.currency}:${r.tax}`;setAcceptedQuote(''); setChosen(r); onSelected(r); onChange(String(r.id)); }} onClear={() => { setChosen(undefined); onSelected(undefined); onChange(''); }}
      loading={list.isFetching} error={list.isError ? catalogError(list.error) : undefined} retry={() => void list.refetch()} hasMore={!!list.data && page < list.data.pages} loadMore={() => setPage(p => p + 1)}/></label>
      <label>Service category<NativeSelect aria-label="Service category" value={category} disabled={facets.isPending} onChange={e => { setCategory(e.target.value); setPage(1); setSearch(''); if(selected && e.target.value && selected.category !== e.target.value){if(!window.confirm('Changing category clears the selected service. Your schedule will be retained and rechecked for the next service.')){setCategory(category);return;}initialQuote.current=undefined;setChosen(undefined);onSelected(undefined);onChange('');} }}><option value="">All categories</option>{facets.data?.map(name => <option key={name}>{name}</option>)}</NativeSelect></label></div>
    {facets.isError && <p role="alert">Service categories could not load. <button type="button" onClick={() => void facets.refetch()}>Retry categories</button></p>}
    {selected && <p className="prebooking-service-summary" aria-label="Selected service summary"><strong>{selected.name}</strong> · {options.data?.policy ? `${options.data.policy.default_duration_minutes} min` : options.isError ? 'Duration unavailable' : 'Loading duration…'} · {price} <small>Estimated price before tax. Final pricing is confirmed in POS.</small></p>}
    {needsReview && <p role="alert">The service quote changed. <button type="button" onClick={()=>{initialQuote.current=quoteKey;setAcceptedQuote(quoteKey);}}>Accept updated estimate</button></p>}
    {value && detail.isError && <p role="alert">Latest service details could not be verified. <button type="button" onClick={()=>void detail.refetch()}>Retry service details</button></p>}
    {value && <small>Quote checked {detail.dataUpdatedAt?new Date(detail.dataUpdatedAt).toLocaleTimeString():'not yet'} · <button type="button" disabled={detail.isFetching} onClick={()=>void detail.refetch()}>Refresh service quote</button></small>}
  </div>;
}
