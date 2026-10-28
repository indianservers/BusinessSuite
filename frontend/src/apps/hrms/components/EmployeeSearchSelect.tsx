import { useDeferredValue, useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Input } from "@/components/ui/input";

export default function EmployeeSearchSelect({ endpoint, value, onChange }: {
  endpoint: string; value: string; onChange: (value: string) => void;
}) {
  const id = useId();
  const [search, setSearch] = useState("");
  const deferred = useDeferredValue(search);
  const userId = useAuthStore(s => s.user?.id);
  const options = useQuery({ queryKey: ["hrms-employee-options", userId, endpoint, deferred], queryFn: () => api.get<Array<{ id: number; name: string; employee_code: string }>>(endpoint, { params: { search: deferred } }).then(r => r.data) });
  return <div className="space-y-2"><label htmlFor={`${id}-search`} className="text-sm font-medium">Search employee</label>
    <Input id={`${id}-search`} value={search} onChange={e => { setSearch(e.target.value); onChange(""); }} placeholder="Name or employee code" />
    <label htmlFor={id} className="sr-only">Employee</label><select id={id} className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={value} onChange={e => onChange(e.target.value)} disabled={options.isPending || options.isError}>
      <option value="">{options.isPending ? "Searching…" : "Select employee"}</option>{options.data?.map(row => <option key={row.id} value={row.id}>{row.name} ({row.employee_code})</option>)}
    </select>{options.isError && <p role="alert" className="text-sm text-destructive">Employee search could not load. <button type="button" onClick={() => options.refetch()} className="underline">Retry</button></p>}
    {options.data?.length === 50 && <p className="text-xs text-muted-foreground">Showing 50 matches. Refine your search to find anyone in the directory.</p>}
    {options.data?.length === 0 && <p className="text-xs text-muted-foreground">No matching employees.</p>}
  </div>;
}
