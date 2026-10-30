import {useHRSession} from "../../workbench/useHRSession";
import {HRQuickAdd} from "../../workbench/shared";
import ProfileListCard, { ProfileAction } from "@/components/ProfileListCard";
import { useAuthStore as useAccountAdminStore } from "@/store/authStore";
import FullDetailsExport from "../../components/FullDetailsExport";
import { lazy, Suspense, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  createColumnHelper,
} from "@tanstack/react-table";
import {
  Plus, Search, Download, RefreshCw,
  Eye, Edit, UserX, Camera, Users
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, companyApi, employeeApi } from "@/services/api";
import { assetUrl, formatDate, statusColor, getInitials } from "@/lib/utils";
import { usePageTitle } from "@/hooks/use-page-title";
import { loadManagerOptions } from "./employeeJobOptions";
import { toast } from "@/hooks/use-toast";

interface Employee {
  id: number;
  employee_id: string;
  first_name: string;
  last_name: string;
  personal_email: string | null;
  phone_number: string | null;
  phone_number_country_code?: string | null;
  designation_id: number | null;
  department_id: number | null;
  employment_type: string;
  status: string;
  date_of_joining: string;
  profile_photo_url: string | null;
  skills_tags?: string | null;
  branch_id?: number | null;
}
const EmployeeDetailPage = lazy(() => import("./EmployeeDetailPage"));

const columnHelper = createColumnHelper<Employee>();

function useDebouncedValue(value: string, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export default function EmployeesPage() {
  usePageTitle("Employees");
  const canManageAccounts = useAccountAdminStore(state => state.user?.is_superuser === true);
  const [employeePopup, setEmployeePopup] = useState<{ employee: Employee; editing: boolean } | null>(null);
  const qc = useQueryClient();
  const [quickAdd,setQuickAdd]=useState(false);
  const [search, setSearch] = useHRSession("employee-list-search","");
  const debouncedSearch = useDebouncedValue(search);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useHRSession("employee-list-status","");
  const [filters, setFilters] = useHRSession<Record<string,string>>("employee-list-filters",{});
  const [sortBy, setSortBy] = useState("name");
  const [sortOrder, setSortOrder] = useState("asc");
  const [perPage, setPerPage] = useState(20);
  const [layout, setLayout] = useState<"cards" | "table">("cards");
  const { data: filterOptions, isError: optionsError, refetch: reloadOptions } = useQuery({
    queryKey: ["employee-filter-options"],
    queryFn: async () => {
      const [facets, branches, departments, designations, managers] = await Promise.all([
        api.get("/employees/filter-options"), companyApi.listBranches(), companyApi.listDepartments(),
        companyApi.listDesignations(), loadManagerOptions(),
      ]);
      const result: Record<string, Array<{ value: string; label: string }>> = {};
      for (const [key, values] of Object.entries(facets.data)) {
        result[key] = (values as Array<string | number>).map((value) => ({ value: String(value), label: String(value) }));
      }
      for (const [key, values] of [["branch_id", branches.data], ["department_id", departments.data], ["designation_id", designations.data], ["reporting_manager_id", managers]] as const) {
        result[key] = values.map((row: { id: number; name: string }) => ({ value: String(row.id), label: row.name }));
      }
      result.account_status = [{ value: "active", label: "Active login" }, { value: "inactive", label: "Inactive login" }, { value: "unlinked", label: "No login account" }];
      return result;
    },
  });
  const filterFields = [
    ["city", "City"], ["passout_year", "Passout year"], ["designation_id", "Designation"],
    ["department_id", "Department"], ["branch_id", "Branch"], ["employment_type", "Employment type"],
    ["state", "State"], ["college", "College"], ["degree", "Qualification"], ["specialization", "Specialization"],
    ["reporting_manager_id", "Reporting manager"], ["gender", "Gender"], ["work_location", "Work location"],
    ["worker_type", "Worker type"], ["account_status", "Login account"],
  ];
  const changeFilter = (key: string, value: string) => { setFilters((current) => ({ ...current, [key]: value })); setPage(1); };
  const queryFilters = { ...Object.fromEntries(Object.entries(filters).filter(([, value]) => value)), search: debouncedSearch || undefined, status: statusFilter || undefined, sort_by: sortBy, sort_order: sortOrder };
  const activeCount = Object.values(filters).filter(Boolean).length + Number(!!statusFilter);


  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["employees", queryFilters, page, perPage],
    queryFn: () =>
      employeeApi
        .list({ ...queryFilters, page, per_page: perPage })
        .then((r) => r.data),
  });

  const photoMutation = useMutation({
    mutationFn: ({ employeeId, file }: { employeeId: number; file: File }) => {
      const form = new FormData();
      form.append("file", file);
      return employeeApi.uploadPhoto(employeeId, form);
    },
    onSuccess: () => {
      toast({ title: "Photo updated" });
      qc.invalidateQueries({ queryKey: ["employees"] });
    },
    onError: () => toast({ title: "Could not upload photo", variant: "destructive" }),
  });

  const importMutation = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return employeeApi.importCsv(form);
    },
    onSuccess: (response) => {
      const { created, failed } = response.data;
      toast({ title: "Import completed", description: `${created} created, ${failed} failed` });
      qc.invalidateQueries({ queryKey: ["employees"] });
    },
    onError: (error: unknown) => {
      const msg = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Could not import employees";
      toast({ title: "Import failed", description: msg, variant: "destructive" });
    },
  });

  async function exportEmployees() {
    const response = await employeeApi.exportCsv(queryFilters);
    const url = URL.createObjectURL(response.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = "employees_export.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  const columns = [
    columnHelper.display({
      id: "avatar",
      cell: (info) => {
        const emp = info.row.original;
        const initials = getInitials(`${emp.first_name} ${emp.last_name}`);
        return (
          <div className="flex items-center gap-3">
            {emp.profile_photo_url ? (
              <img
                src={assetUrl(emp.profile_photo_url)}
                alt={initials}
                className="h-9 w-9 rounded-full object-cover"
              />
            ) : (
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 text-primary text-sm font-semibold">
                {initials}
              </div>
            )}
            <div>
              <p className="font-medium text-sm">
                {emp.first_name} {emp.last_name}
              </p>
              <p className="text-xs text-muted-foreground">{emp.employee_id}</p>
            </div>
          </div>
        );
      },
    }),
    columnHelper.accessor("personal_email", {
      header: "Email",
      cell: (info) => (
        <span className="text-sm text-muted-foreground">{info.getValue() || "-"}</span>
      ),
    }),
    columnHelper.accessor("phone_number", {
      header: "Phone",
      cell: (info) => (
        <span className="text-sm">{info.getValue() ? `${info.row.original.phone_number_country_code || ""} ${info.getValue()}` : "-"}</span>
      ),
    }),
    columnHelper.accessor("employment_type", {
      header: "Type",
      cell: (info) => (
        <Badge variant="outline" className="text-xs">
          {info.getValue()}
        </Badge>
      ),
    }),
    columnHelper.accessor("date_of_joining", {
      header: "Joined",
      cell: (info) => (
        <span className="text-sm">{formatDate(info.getValue())}</span>
      ),
    }),
    columnHelper.accessor("status", {
      header: "Status",
      cell: (info) => (
        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${statusColor(info.getValue())}`}>
          {info.getValue()}
        </span>
      ),
    }),
    columnHelper.display({
      id: "actions",
      header: "Actions",
      cell: (info) => (
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" className="h-8 w-8" title="Preview employee" aria-label={`Preview ${info.row.original.first_name} ${info.row.original.last_name}`} onClick={(event) => { event.stopPropagation(); setEmployeePopup({ employee: info.row.original, editing: false }); }}>
            <Eye className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8" title="Edit employee" aria-label={`Edit ${info.row.original.first_name} ${info.row.original.last_name}`} onClick={(event) => { event.stopPropagation(); setEmployeePopup({ employee: info.row.original, editing: true }); }}>
            <Edit className="h-3.5 w-3.5" />
          </Button>
          <label className="inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-md hover:bg-muted" onClick={(event) => event.stopPropagation()}>
            <Camera className="h-3.5 w-3.5" />
            <input
              type="file"
              accept="image/png,image/jpeg"
              className="hidden"
              onChange={(event) => {
                event.stopPropagation();
                const file = event.target.files?.[0];
                if (file) photoMutation.mutate({ employeeId: info.row.original.id, file });
                event.currentTarget.value = "";
              }}
            />
          </label>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-destructive"
            title="Manage employee access and exit"
            aria-label="Manage employee access and exit"
            onClick={(event) => {
              event.stopPropagation();
              setEmployeePopup({employee:info.row.original,editing:false});
            }}
          >
            <UserX className="h-3.5 w-3.5" />
          </Button>
        </div>
      ),
    }),
  ];

  const table = useReactTable({
    data: data?.items || [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    pageCount: data?.pages ?? 0,
  });
  const colSpan = columns.length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="page-title">Employees</h1>
          <p className="page-description">
            {data?.total ?? 0} {activeCount || search ? "matching" : "total"} employees
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant={layout === "cards" ? "default" : "outline"} size="sm" aria-pressed={layout === "cards"} onClick={() => setLayout("cards")}>Profile cards</Button>
          <Button variant={layout === "table" ? "default" : "outline"} size="sm" aria-pressed={layout === "table"} onClick={() => setLayout("table")}>Table</Button>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <label className="inline-flex h-9 cursor-pointer items-center justify-center gap-2 rounded-md border border-input bg-background px-3 text-sm font-medium hover:bg-accent hover:text-accent-foreground">
            Import CSV
            <input
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) importMutation.mutate(file);
                event.currentTarget.value = "";
              }}
            />
          </label>
          <Button variant="outline" size="sm" onClick={exportEmployees}>
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
          <FullDetailsExport endpoint="/employees/export/full" params={queryFilters} filename="employees_full_details.xlsx" />
          {canManageAccounts && <Link to="/hrms/users"><Button variant="outline">Users & Roles</Button></Link>}
          <Button size="sm" onClick={()=>setQuickAdd(true)}><Plus className="h-4 w-4 mr-2"/>Quick Add Employee</Button><Link className="p-2 text-sm underline" to="/hrms/employees/new">Full employee form</Link>
        </div>
      </div>

      {/* Filters */}
      <Card className="p-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search by name, ID, email..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="pl-9"
            />
          </div>
          <Select value={statusFilter || "__all__"} onValueChange={(value) => { setStatusFilter(value === "__all__" ? "" : value); setPage(1); }}>
            <SelectTrigger className="w-full sm:w-48">
              <SelectValue placeholder="All Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All Status</SelectItem>
              {(filterOptions?.status?.length ? filterOptions.status : ["Active", "Probation", "On Leave", "Resigned", "Terminated", "Suspended", "Absconding"].map((value) => ({ value, label: value }))).map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <details open className="mt-4 border-t pt-3">
          <summary className="cursor-pointer text-sm font-medium">Filters {activeCount > 0 ? `(${activeCount} active)` : "— city, education, job and account"}</summary>
          {optionsError && <p role="alert" className="mt-2 text-sm text-destructive">Could not load filter choices. <button className="underline" onClick={() => void reloadOptions()}>Retry</button></p>}
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            {filterFields.map(([key, label]) => (
              <label key={key} className="space-y-1 text-xs font-medium">
                <span>{label}</span>
                <select aria-label={label} value={filters[key] || ""} onChange={(event) => changeFilter(key, event.target.value)} className="flex h-10 w-full min-w-0 rounded-md border border-input bg-background px-2 text-sm font-normal">
                  <option value="">All {label.toLowerCase()}</option>
                  {(filterOptions?.[key] || []).map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </label>
            ))}
            {[["joined_from", "Joined from"], ["joined_to", "Joined to"]].map(([key, label]) => (
              <label key={key} className="space-y-1 text-xs font-medium"><span>{label}</span><Input aria-label={label} type="date" value={filters[key] || ""} onChange={(event) => changeFilter(key, event.target.value)} /></label>
            ))}
          </div>
        </details>
        <div className="mt-4 flex flex-wrap items-end gap-3 border-t pt-3">
          <label className="space-y-1 text-xs font-medium"><span>Sort by</span><select aria-label="Sort by" value={sortBy} onChange={(event) => { setSortBy(event.target.value); setPage(1); }} className="block h-10 rounded-md border bg-background px-3 text-sm">
            {[["name", "Name"], ["employee_id", "Employee ID"], ["date_of_joining", "Joining date"], ["city", "City"], ["passout_year", "Passout year"], ["status", "Status"], ["employment_type", "Employment type"]].map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select></label>
          <label className="space-y-1 text-xs font-medium"><span>Order</span><select aria-label="Sort order" value={sortOrder} onChange={(event) => { setSortOrder(event.target.value); setPage(1); }} className="block h-10 rounded-md border bg-background px-3 text-sm"><option value="asc">Ascending</option><option value="desc">Descending</option></select></label>
          <label className="space-y-1 text-xs font-medium"><span>Rows per page</span><select aria-label="Rows per page" value={perPage} onChange={(event) => { setPerPage(Number(event.target.value)); setPage(1); }} className="block h-10 rounded-md border bg-background px-3 text-sm">{[20, 50, 100].map((size) => <option key={size} value={size}>{size}</option>)}</select></label>
          <Button variant="ghost" onClick={() => { setFilters({}); setStatusFilter(""); setSearch(""); setSortBy("name"); setSortOrder("asc"); setPage(1); }}>Clear filters</Button>
          <span className="pb-2 text-sm text-muted-foreground" aria-live="polite">{data?.total ?? 0} matching employees</span>
        </div>
      </Card>
      {isError && <div role="alert" className="rounded-md border border-destructive p-3 text-sm text-destructive">{(error as { response?: { data?: { detail?: string } } })?.response?.data?.detail && typeof (error as any).response.data.detail === "string" ? (error as any).response.data.detail : "Could not load employees. Check filters and try again."} <button className="underline" onClick={() => void refetch()}>Retry</button></div>}

      {/* Table */}
      <Card className={layout === "cards" ? "overflow-hidden border-0 bg-transparent shadow-none" : "overflow-hidden"}>
        {layout === "cards" && <div className="grid gap-2.5 md:grid-cols-2 xl:grid-cols-3">
          {isLoading ? Array.from({length:6},(_,i) => <div key={i} className="h-28 rounded-lg border bg-card p-4"><div className="h-10 w-10 rounded-full skeleton" /><div className="mt-2 h-3 w-2/3 skeleton" /></div>) : (data?.items || []).map((employee: Employee) => {
            const name = `${employee.first_name} ${employee.last_name}`;
            const designation = filterOptions?.designation_id?.find(option => option.value === String(employee.designation_id))?.label;
            const department = filterOptions?.department_id?.find(option => option.value === String(employee.department_id))?.label;
            const branch = filterOptions?.branch_id?.find(option => option.value === String(employee.branch_id))?.label;
            return <ProfileListCard key={employee.id} name={name} photoUrl={employee.profile_photo_url} location={branch}
              subtitle={<><strong>{designation || employee.employment_type}</strong>{department && ` · ${department}`}</>}
              status={{label:employee.status,tone:employee.status.toLowerCase() === "active" ? "positive" : "muted"}}
              tags={[employee.employee_id,...(employee.skills_tags || "").split(",").map(tag => tag.trim()).filter(Boolean).slice(0,2)]}
              onOpen={() => setEmployeePopup({employee,editing:false})}
              actions={<><ProfileAction onClick={() => setEmployeePopup({employee,editing:false})}>View profile</ProfileAction><ProfileAction onClick={() => setEmployeePopup({employee,editing:true})}>Edit</ProfileAction>{employee.personal_email && <ProfileAction href={`mailto:${employee.personal_email}`}>Email</ProfileAction>}</>} />;
          })}
          {!isLoading && !data?.items?.length && <div className="col-span-full rounded-lg border bg-card p-10 text-center text-muted-foreground">No profiles match these filters.</div>}
        </div>}
        {layout === "table" && <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <th
                      key={header.id}
                      className="px-4 py-3 text-left font-medium text-muted-foreground text-xs uppercase tracking-wide"
                    >
                      {flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {isLoading ? (
                Array.from({ length: 10 }).map((_, i) => (
                  <tr key={i} className="border-b">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="h-9 w-9 skeleton rounded-full" />
                        <div className="space-y-1">
                          <div className="h-4 w-32 skeleton rounded" />
                          <div className="h-3 w-20 skeleton rounded" />
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3"><div className="h-4 w-40 skeleton rounded" /></td>
                    <td className="px-4 py-3"><div className="h-4 w-28 skeleton rounded" /></td>
                    <td className="px-4 py-3"><div className="h-6 w-20 skeleton rounded-full" /></td>
                    <td className="px-4 py-3"><div className="h-4 w-24 skeleton rounded" /></td>
                    <td className="px-4 py-3"><div className="h-6 w-24 skeleton rounded-full" /></td>
                    <td className="px-4 py-3"><div className="ml-auto h-8 w-28 skeleton rounded" /></td>
                  </tr>
                ))
              ) : table.getRowModel().rows.length === 0 ? (
                <tr>
                  <td colSpan={colSpan} className="px-4 py-12 text-center text-muted-foreground">
                    <Users className="h-10 w-10 mx-auto mb-2 opacity-30" />
                    <p>{activeCount || search ? "No employees match these filters" : "No employees found"}</p>
                    {activeCount || search ? (
                      <Button variant="link" size="sm" onClick={() => { setFilters({}); setStatusFilter(""); setSearch(""); setPage(1); }}>Clear filters</Button>
                    ) : <Link to="/hrms/employees/new"><Button variant="link" size="sm">Add your first employee</Button></Link>}
                  </td>
                </tr>
              ) : (
                table.getRowModel().rows.map((row) => (
                  <tr
                    key={row.id}
                    className="cursor-pointer border-b transition-colors hover:bg-muted/30"
                    onClick={() => setEmployeePopup({ employee: row.original, editing: false })}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="px-4 py-3">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>}

        {/* Pagination */}
        {data && data.pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t">
            <p className="text-xs text-muted-foreground">
              Showing {(page - 1) * perPage + 1}&ndash;{Math.min(page * perPage, data.total)} of {data.total}
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Previous
              </Button>
              <span className="text-sm">
                Page {page} of {data.pages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
                disabled={page === data.pages}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>

      {quickAdd&&<HRQuickAdd close={()=>setQuickAdd(false)} saved={async id=>{setQuickAdd(false);void qc.invalidateQueries({queryKey:["employees"]});const r=await employeeApi.get(id);setEmployeePopup({employee:r.data,editing:false});}}/>}
      <Dialog open={!!employeePopup} onOpenChange={(open) => { if (!open) setEmployeePopup(null); }}>
        <DialogContent className="flex max-h-[94dvh] w-[calc(100%-1rem)] max-w-7xl flex-col overflow-hidden p-0 sm:w-[calc(100%-3rem)]">
          <div className="border-b px-5 py-4 pr-12">
            <DialogTitle className="text-lg font-semibold">{employeePopup?.editing ? "Edit employee" : "Employee preview"}: {employeePopup?.employee.first_name} {employeePopup?.employee.last_name}</DialogTitle>
          </div>
          <div className="min-h-0 overflow-y-auto overscroll-contain px-4 pb-5 sm:px-6">
      {employeePopup && <Suspense fallback={<p role="status" className="p-6 text-muted-foreground">Loading employee details…</p>}>
              <EmployeeDetailPage key={`${employeePopup.employee.id}-${employeePopup.editing}`} employeeId={employeePopup.employee.id} initialEditing={employeePopup.editing} onClose={() => setEmployeePopup(null)} />
            </Suspense>}
          </div>
        </DialogContent>
      </Dialog>


    </div>
  );
}
