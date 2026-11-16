import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { useRecordScope } from '@/lib/record-scope';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

export default function EmployeeCategories({value, onChange, create = false, options, disabled = false}: {
  value: string[]; onChange: (value: string[]) => void; create?: boolean; options?: string[]; disabled?: boolean;
}) {
  const scope = useRecordScope();
  const [name, setName] = useState('');
  const query = useQuery({queryKey:['employee-work-categories', scope], enabled: options === undefined,
    queryFn: ({signal}) => api.get<{items:string[]}>('/employees/work-category-options', {signal}).then(response=>response.data)});
  const names = [...new Set([...(options || query.data?.items || []), ...value])].sort((a,b)=>a.localeCompare(b));
  return <fieldset className="min-w-0 space-y-2" disabled={disabled}>
    <legend className="text-sm font-medium">Employee categories</legend>
    <p className="text-xs text-muted-foreground">Select multiple work categories maintained in HRMS.</p>
    {query.isError && options === undefined && <p role="alert">Unable to load employee categories. <Button type="button" variant="outline" onClick={()=>void query.refetch()}>Retry</Button></p>}
    <div className="flex flex-wrap gap-3">{names.map(category=><label key={category} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={value.includes(category)} onChange={event=>onChange(event.target.checked?[...value,category]:value.filter(name=>name!==category))}/>{category}</label>)}</div>
    {create && <div className="flex gap-2"><Input aria-label="New employee category" maxLength={80} value={name} onChange={event=>setName(event.target.value)} placeholder="Category name"/><Button type="button" variant="outline" disabled={!name.trim() || value.length >= 20} onClick={()=>{const category=name.trim().replace(/\s+/g,' ');if(!value.some(item=>item.toLowerCase()===category.toLowerCase()))onChange([...value,category]);setName('');}}>Add category</Button></div>}
    {!create && !names.length && !query.isFetching && <p className="text-xs text-muted-foreground">Assign employee categories in HRMS to make them available here.</p>}
  </fieldset>;
}
