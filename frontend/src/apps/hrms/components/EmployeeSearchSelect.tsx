import { useBusinessTerms } from '@/hooks/use-business-terms';
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { useDeferredValue, useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Input } from "@/components/ui/input";
import { ChoiceStatus } from "@/components/ui/choice-status";

export default function EmployeeSearchSelect({ endpoint, value, onChange }: {
  endpoint: string; value: string; onChange: (value: string) => void;
}) {
  const { term } = useBusinessTerms();
  const id = useId();
  const [search, setSearch] = useState("");
  const deferred = useDeferredValue(search);
  const userId = useAuthStore(s => s.user?.id);
  const options = useQuery({ queryKey: ["hrms-employee-options", userId, endpoint, deferred], queryFn: () => api.get<Array<{ id: number; name: string; employee_code: string }>>(endpoint, { params: { search: deferred } }).then(r => r.data) });
  return <div className="space-y-2"><label htmlFor={`${id}-search`} className="text-sm font-medium">Search {term('employee').toLowerCase()}</label>
    <Input id={`${id}-search`} value={search} onChange={e => { setSearch(e.target.value); onChange(""); }} placeholder={`Name or ${term('employee').toLowerCase()} code`} />
    <label htmlFor={id} className="sr-only">{term('employee')}</label><NativeSelect recentKey={endpoint} loading={options.isFetching || deferred !== search} error={options.isError} id={id} className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={value} onChange={e => onChange(e.target.value)} disabled={options.isPending || options.isError}>
      <option value="">{options.isPending ? "Searching…" : `Select ${term('employee').toLowerCase()}`}</option>{options.data?.map(row => <option key={row.id} value={row.id}>{row.name} ({row.employee_code})</option>)}
    </NativeSelect>{options.isError && <p role="alert" className="text-sm text-destructive">{term('employee')} search could not load. <Button variant="outline" type="button" onClick={() => options.refetch()} className="underline">Retry</Button></p>}
    {options.data?.length === 50 && <p className="text-xs text-muted-foreground">Showing 50 matches. Refine your search to find anyone in the directory.</p>}
    <ChoiceStatus loading={options.isFetching || deferred !== search} empty={options.data?.length === 0} error={options.isError} emptyText={`No matching ${term('employee', true).toLowerCase()}.`} />
  </div>;
}
