import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
export default function PayrollDepartmentSelect({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const query = useQuery({ queryKey: ["payroll-department-options"], queryFn: () => api.get<{ id: number; name: string }[]>("/payroll/department-options").then(r => r.data) });
  return <label className="text-sm">Department<select className="mt-1 h-10 w-full rounded border bg-background px-2" value={value} onChange={e => onChange(e.target.value)}><option value="">All departments</option>{query.data?.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select>{query.isError && <span role="alert">Department options could not load.</span>}</label>;
}
