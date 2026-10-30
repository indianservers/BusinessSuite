import ProfileListCard, { ProfileAction } from "@/components/ProfileListCard";
import FullDetailsExport from "../../components/FullDetailsExport";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  CalendarDays,
  Cake,
  Copy,
  Download,
  Eye,
  Filter,
  Grid2X2,
  List,
  Mail,
  Phone,
  Search,
  Users,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { employeeApi } from "@/services/api";
import { assetUrl, getInitials } from "@/lib/utils";
import { usePageTitle } from "@/hooks/use-page-title";
import { useToast } from "@/hooks/use-toast";
import { useAuthStore } from "@/store/authStore";

interface DirectoryEmployee {
  id: number;
  employee_id: string;
  full_name: string;
  email: string | null;
  phone_number: string | null;
  phone_number_country_code?: string | null;
  office_extension: string | null;
  department: string | null;
  designation: string | null;
  branch: string | null;
  reporting_manager: string | null;
  work_location: string | null;
  desk_code: string | null;
  timezone: string | null;
  skills_tags: string | null;
  profile_completeness: number | null;
  profile_photo_url: string | null;
  is_direct_report: boolean;
  contact_masked: boolean;
}

interface DirectoryEvent {
  id: number;
  employee_id: string;
  full_name: string;
  event_date: string;
  profile_photo_url: string | null;
}

interface ProfileCard extends DirectoryEmployee {
  skills: string[];
}

const sortOptions = [
  ["name", "Name"],
  ["department", "Department"],
  ["joining_date", "Joining date"],
  ["location", "Location"],
  ["designation", "Designation"],
];

function isPrivileged(role?: string | null, isSuperuser = false) {
  const key = (role || "").toLowerCase().replace(/\s+/g, "_");
  return isSuperuser || ["admin", "super_admin", "hr", "hr_admin", "hr_manager"].includes(key);
}

function useDebouncedValue(value: string, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export default function EmployeeDirectoryPage() {
  usePageTitle("Employee Directory");
  const { toast } = useToast();
  const { user } = useAuthStore();
  const canManage = isPrivileged(user?.role, user?.is_superuser);
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const [page, setPage] = useState(1);
  const [viewMode, setViewMode] = useState(localStorage.getItem("directory-view") || "grid");
  const [departmentId, setDepartmentId] = useState("");
  const [designationId, setDesignationId] = useState("");
  const [branchId, setBranchId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [skills, setSkills] = useState("");
  const [teamOnly, setTeamOnly] = useState(false);
  const [sortBy, setSortBy] = useState("name");
  const [sortOrder, setSortOrder] = useState("asc");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [reportEmployee, setReportEmployee] = useState<DirectoryEmployee | null>(null);
  const [reportField, setReportField] = useState("contact");
  const [reportMessage, setReportMessage] = useState("");

  useEffect(() => localStorage.setItem("directory-view", viewMode), [viewMode]);

  const params = useMemo(
    () => ({
      search: debouncedSearch || undefined,
      department_id: departmentId || undefined,
      designation_id: designationId || undefined,
      branch_id: branchId || undefined,
      location_id: locationId || undefined,
      skills: skills || undefined,
      team_only: teamOnly || undefined,
      sort_by: sortBy,
      sort_order: sortOrder,
      page,
      per_page: 24,
    }),
    [debouncedSearch, departmentId, designationId, branchId, locationId, skills, teamOnly, sortBy, sortOrder, page]
  );

  const { data, isLoading } = useQuery({
    queryKey: ["employee-directory", params],
    queryFn: () => employeeApi.directory(params).then((response) => response.data),
  });

  const { data: filters } = useQuery({
    queryKey: ["employee-directory-filters"],
    queryFn: () => employeeApi.directoryFilters().then((response) => response.data),
  });

  const { data: recentJoiners } = useQuery({
    queryKey: ["employee-recent-joiners"],
    queryFn: () => employeeApi.recentJoiners({ days: 45, limit: 6 }).then((response) => response.data),
  });

  const { data: birthdays } = useQuery({
    queryKey: ["employee-birthdays"],
    queryFn: () => employeeApi.birthdays({ days: 30 }).then((response) => response.data),
  });

  const { data: anniversaries } = useQuery({
    queryKey: ["employee-anniversaries"],
    queryFn: () => employeeApi.workAnniversaries({ days: 30 }).then((response) => response.data),
  });

  const { data: suggestions } = useQuery({
    queryKey: ["employee-org-search", debouncedSearch],
    queryFn: () => employeeApi.orgSearch({ q: debouncedSearch, limit: 5 }).then((response) => response.data),
    enabled: debouncedSearch.length >= 2,
  });

  const { data: profileCard } = useQuery({
    queryKey: ["employee-profile-card", selectedId],
    queryFn: () => employeeApi.profileCard(selectedId!).then((response) => response.data as ProfileCard),
    enabled: !!selectedId,
  });

  const reportMutation = useMutation({
    mutationFn: () =>
      employeeApi.reportDirectoryCorrection({
        employee_id: reportEmployee?.id,
        field_name: reportField,
        message: reportMessage,
      }),
    onSuccess: () => {
      toast({ title: "Report submitted" });
      setReportEmployee(null);
      setReportMessage("");
    },
    onError: () => toast({ title: "Could not submit report", variant: "destructive" }),
  });

  const items = (data?.items || []) as DirectoryEmployee[];

  function resetFilters() {
    setDepartmentId("");
    setDesignationId("");
    setBranchId("");
    setLocationId("");
    setSkills("");
    setTeamOnly(false);
    setPage(1);
  }

  async function exportDirectory() {
    const response = await employeeApi.directoryExport(params);
    const url = URL.createObjectURL(response.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = "employee_directory.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  function copyText(value: string | null) {
    if (!value || value === "Hidden by privacy setting") return;
    navigator.clipboard.writeText(value);
    toast({ title: "Copied" });
  }

  const filterPanel = (
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-4">
        <Input value={departmentId} onChange={(e) => { setDepartmentId(e.target.value); setPage(1); }} placeholder="Department ID" />
        <Input value={designationId} onChange={(e) => { setDesignationId(e.target.value); setPage(1); }} placeholder="Designation ID" />
        <Input value={branchId} onChange={(e) => { setBranchId(e.target.value); setPage(1); }} placeholder="Branch ID" />
        <Input value={locationId} onChange={(e) => { setLocationId(e.target.value); setPage(1); }} placeholder="Location ID" />
      </div>
      <div className="grid gap-3 md:grid-cols-4">
        <Input value={skills} onChange={(e) => { setSkills(e.target.value); setPage(1); }} placeholder="Skill tag" />
        <select className="h-10 rounded-md border bg-background px-3 text-sm" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
          {sortOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <select className="h-10 rounded-md border bg-background px-3 text-sm" value={sortOrder} onChange={(e) => setSortOrder(e.target.value)}>
          <option value="asc">Ascending</option>
          <option value="desc">Descending</option>
        </select>
        <label className="flex h-10 items-center gap-2 rounded-md border px-3 text-sm">
          <input type="checkbox" checked={teamOnly} onChange={(e) => { setTeamOnly(e.target.checked); setPage(1); }} />
          My team only
        </label>
      </div>
      <div className="flex flex-wrap gap-2">
        {(filters?.departments || []).slice(0, 8).map((item: { id: number; count: number }) => (
          <Button key={item.id} variant={departmentId === String(item.id) ? "default" : "outline"} size="sm" onClick={() => setDepartmentId(String(item.id))}>
            Dept {item.id} <Badge variant="secondary" className="ml-2">{item.count}</Badge>
          </Button>
        ))}
        {(filters?.skills || []).slice(0, 8).map((item: { name: string; count: number }) => (
          <Button key={item.name} variant={skills === item.name ? "default" : "outline"} size="sm" onClick={() => setSkills(item.name)}>
            {item.name} <Badge variant="secondary" className="ml-2">{item.count}</Badge>
          </Button>
        ))}
        <Button variant="ghost" size="sm" onClick={resetFilters}>Clear filters</Button>
      </div>
    </div>
  );

  const renderEmployee = (employee: DirectoryEmployee) => (
    <ProfileListCard key={employee.id} name={employee.full_name} photoUrl={employee.profile_photo_url}
      location={employee.branch || employee.work_location} onOpen={() => setSelectedId(employee.id)}
      subtitle={<><strong>{employee.designation || employee.employee_id}</strong>{employee.department && ` · ${employee.department}`}</>}
      tags={[...(employee.is_direct_report ? ["Direct report"] : []), ...(employee.contact_masked ? ["Privacy protected"] : []),
        ...(employee.skills_tags || "").split(",").map(tag => tag.trim()).filter(Boolean).slice(0,3)]}
      actions={<>
        <ProfileAction onClick={() => setSelectedId(employee.id)}>View profile</ProfileAction>
        {employee.email && employee.email !== "Hidden by privacy setting" && <ProfileAction href={`mailto:${employee.email}`}>Email</ProfileAction>}
        {employee.phone_number && employee.phone_number !== "Hidden by privacy setting" && <ProfileAction href={`tel:${employee.phone_number_country_code || ""}${employee.phone_number}`}>Call</ProfileAction>}
        <ProfileAction onClick={() => setReportEmployee(employee)}>Report</ProfileAction>
        {canManage && <ProfileAction href={`/hrms/employees/${employee.id}`}>Full profile</ProfileAction>}
      </>}
    />
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="page-title">Employee Directory</h1>
          <p className="page-description">{data?.total ?? 0} people available</p>
        </div>
        <div className="flex flex-col gap-2 md:flex-row">
          <div className="relative w-full md:w-80">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder="Search name, ID, email, or skill" className="pl-9" />
            {!!suggestions?.length && (
              <div className="absolute z-20 mt-1 w-full rounded-md border bg-background shadow">
                {suggestions.map((item: { id: number; label: string; subtitle: string }) => (
                  <button key={item.id} className="block w-full px-3 py-2 text-left text-sm hover:bg-muted" onClick={() => setSelectedId(item.id)}>
                    {item.label}<span className="block text-xs text-muted-foreground">{item.subtitle}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <Button variant="outline" onClick={() => setFiltersOpen(true)} className="md:hidden"><Filter className="mr-2 h-4 w-4" />Filters</Button>
          <Button variant="outline" onClick={() => setViewMode(viewMode === "grid" ? "list" : "grid")}>
            {viewMode === "grid" ? <List className="mr-2 h-4 w-4" /> : <Grid2X2 className="mr-2 h-4 w-4" />}
            {viewMode === "grid" ? "List" : "Grid"}
          </Button>
          {canManage && <Button variant="outline" onClick={exportDirectory}><Download className="mr-2 h-4 w-4" />Export</Button>}
          <FullDetailsExport endpoint="/employees/directory/export/full" params={params} filename="employees_full_details.xlsx" />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Recent Joiners</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            {(recentJoiners || []).slice(0, 3).map((item: DirectoryEmployee) => <button key={item.id} className="block text-left hover:text-primary" onClick={() => setSelectedId(item.id)}>{item.full_name}</button>)}
            {!recentJoiners?.length && <p className="text-muted-foreground">No recent joiners.</p>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm"><Cake className="mr-2 inline h-4 w-4" />Birthdays</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            {(birthdays || []).slice(0, 3).map((item: DirectoryEvent) => <p key={item.id}>{item.full_name} <span className="text-muted-foreground">{item.event_date}</span></p>)}
            {!birthdays?.length && <p className="text-muted-foreground">No upcoming birthdays.</p>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm"><CalendarDays className="mr-2 inline h-4 w-4" />Anniversaries</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            {(anniversaries || []).slice(0, 3).map((item: DirectoryEvent) => <p key={item.id}>{item.full_name} <span className="text-muted-foreground">{item.event_date}</span></p>)}
            {!anniversaries?.length && <p className="text-muted-foreground">No upcoming anniversaries.</p>}
          </CardContent>
        </Card>
      </div>

      <Card className="hidden md:block"><CardContent className="p-4">{filterPanel}</CardContent></Card>

      {filtersOpen && (
        <div className="fixed inset-0 z-40 bg-background/80 p-4 md:hidden">
          <Card className="h-full overflow-auto">
            <CardHeader className="flex flex-row items-center justify-between"><CardTitle>Filters</CardTitle><Button variant="ghost" size="icon" onClick={() => setFiltersOpen(false)}><X className="h-4 w-4" /></Button></CardHeader>
            <CardContent>{filterPanel}</CardContent>
          </Card>
        </div>
      )}

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => <Card key={index}><CardContent className="p-4"><div className="h-24 rounded skeleton" /></CardContent></Card>)}
        </div>
      ) : items.length === 0 ? (
        <Card><CardContent className="p-10 text-center text-muted-foreground"><Users className="mx-auto mb-3 h-10 w-10 opacity-30" />No employees found.</CardContent></Card>
      ) : (
        <div className={viewMode === "grid" ? "grid gap-4 md:grid-cols-2 xl:grid-cols-3" : "space-y-3"}>{items.map(renderEmployee)}</div>
      )}

      <div className="flex items-center justify-end gap-2">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</Button>
        <span className="text-sm text-muted-foreground">Page {data?.page ?? page} of {data?.pages ?? 1}</span>
        <Button variant="outline" size="sm" disabled={!data || page >= data.pages} onClick={() => setPage((value) => value + 1)}>Next</Button>
      </div>

      {profileCard && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4">
          <Card className="w-full max-w-lg">
            <CardHeader className="flex flex-row items-center justify-between"><CardTitle>{profileCard.full_name}</CardTitle><Button variant="ghost" size="icon" onClick={() => setSelectedId(null)}><X className="h-4 w-4" /></Button></CardHeader>
            <CardContent className="space-y-3 text-sm">
              <p className="text-muted-foreground">{profileCard.designation || "No designation"}{profileCard.department ? `, ${profileCard.department}` : ""}</p>
              <p>Employee ID: {profileCard.employee_id}</p>
              {profileCard.reporting_manager && <p>Manager: {profileCard.reporting_manager}</p>}
              {profileCard.desk_code && <p>Desk: {profileCard.desk_code}</p>}
              {profileCard.email && <p>Email: {profileCard.email} <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => copyText(profileCard.email)}><Copy className="h-3 w-3" /></Button></p>}
              {profileCard.phone_number && <p>Phone: {profileCard.phone_number_country_code || ""} {profileCard.phone_number} <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => copyText(profileCard.phone_number)}><Copy className="h-3 w-3" /></Button></p>}
              {!!profileCard.skills?.length && <div className="flex flex-wrap gap-2">{profileCard.skills.map((skill) => <Badge key={skill} variant="outline">{skill}</Badge>)}</div>}
            </CardContent>
          </Card>
        </div>
      )}

      {reportEmployee && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4">
          <Card className="w-full max-w-md">
            <CardHeader className="flex flex-row items-center justify-between"><CardTitle>Report Wrong Info</CardTitle><Button variant="ghost" size="icon" onClick={() => setReportEmployee(null)}><X className="h-4 w-4" /></Button></CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-muted-foreground">{reportEmployee.full_name}</p>
              <Input value={reportField} onChange={(e) => setReportField(e.target.value)} placeholder="Field name" />
              <Input value={reportMessage} onChange={(e) => setReportMessage(e.target.value)} placeholder="What needs correction?" />
              <Button disabled={!reportMessage || reportMutation.isPending} onClick={() => reportMutation.mutate()}>Submit report</Button>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
