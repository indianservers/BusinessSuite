import DirectoryDestinations, { type DestinationRequest } from "../components/people/DirectoryDestinations";
import { useAuthStore } from "@/store/authStore";
import PeopleAction from "../components/people/PeopleAction";
import DirectoryTable, { PageSelection } from "../components/people/DirectoryTable";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as Dropdown from "@radix-ui/react-dropdown-menu";
import {
  Users,
  Circle,
  Clock3,
  GraduationCap,
  Plus,
  Search,
  Filter,
  ChevronDown,
  ChevronRight,
  LayoutGrid,
  List,
  Download,
  MoreVertical,
  X,
  Save,
  RefreshCw,
} from "lucide-react";
import { api } from "@/services/api";
import { usePageRefresh } from "@/lib/page-refresh";
import DirectoryPersonCard from "../components/people/DirectoryPersonCard";
import DirectoryGroupsPanel from "../components/people/DirectoryGroupsPanel";
import {
  PeopleDialog,
  TeamEditor,
  AddPeopleToTeam,
  DirectoryPagination,
} from "../components/people/DirectoryDialogs";
import DirectoryImport from "../components/people/DirectoryImport";
import AddPeopleMemberships from "../components/people/AddPeopleMemberships";
import { useMembershipOptions } from "../components/people/peopleMemberships";
import {
  directoryRoot,
  directoryGet,
  directoryTaskHref,
  type DirectoryPerson,
  type DirectoryPage,
  type DirectoryReference,
  type GroupPage,
} from "../components/people/peopleWorkspace";
import { workspaceError } from "./workspaceTypes";
import "./PeopleWorkspace.css";
function GroupFilter({
  kind,
  value,
  onChange,
}: {
  kind: "teams" | "batches";
  value: string;
  onChange: (value: string) => void;
}) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const groups = useQuery({
    queryKey: ["people-workspace", "filter", kind, search, page],
    queryFn: () =>
      directoryGet<GroupPage>("/groups", {
        kind,
        q: search,
        page,
        page_size: 20,
      }),
  });
  return (
    <label>
      {kind === "teams" ? "Team" : "Intern batch"}
      <input
        aria-label={`Search filter ${kind}`}
        value={search}
        placeholder={`Search ${kind}�`}
        onChange={(e) => {
          setSearch(e.target.value);
          setPage(1);
        }}
      />
      <select
        aria-label={`Filter ${kind}`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">All accessible {kind}</option>
        {value && !groups.data?.items.some((g) => String(g.id) === value) && (
          <option value={value}>
            Selected {kind === "teams" ? "team" : "batch"} #{value}
          </option>
        )}
        {groups.data?.items.map((g) => (
          <option key={g.id} value={g.id}>
            {g.name}
          </option>
        ))}
      </select>
      {groups.isError && (
        <span role="alert">
          Could not load groups.{" "}
          <button onClick={() => groups.refetch()}>Retry</button>
        </span>
      )}
      {(groups.data?.pages || 0) > 1 && (
        <DirectoryPagination
          page={page}
          pages={groups.data!.pages}
          onChange={setPage}
        />
      )}
    </label>
  );
}
export default function PeopleManagementDirectory() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [search, setSearch] = useState(params.get("q") || "");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const [selectionPeople, setSelectionPeople] = useState<Record<number, DirectoryPerson>>({});
  const [selectionPages, setSelectionPages] = useState<Record<number, number>>({});
  const [destinationRequest, setDestinationRequest] = useState<DestinationRequest>();
  const [dragging, setDragging] = useState(false);
  const [previewPerson, setPreviewPerson] = useState<DirectoryPerson>();
  const [notice, setNotice] = useState("");
  const [exportOpen, setExportOpen] = useState(false);
  const [reviewSelection, setReviewSelection] = useState(false);
  const user = useAuthStore(state => state.user);
  const [adding, setAdding] = useState(false);
  const [membershipMode, setMembershipMode] = useState<"workspace" | "project" | null>(null);
  const membershipOptions = useMembershipOptions();
  const canAddWorkspace = !!membershipOptions.data?.workspaces.length;
  const canAddProject = !!membershipOptions.data?.projects.length;
  const [teamEditor, setTeamEditor] = useState<{
    id?: number;
    workspace?: number;
  } | null>(null);
  const [importing, setImporting] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);
  const [viewName, setViewName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [mobileTab, setMobileTab] = useState<
    "people" | "destinations" | "teams" | "batches" | "organizations"
  >("people");
  const listRef = useRef<HTMLElement>(null);
  const page = Number(params.get("page") || 1);
  const query = Object.fromEntries(params);
  const dataQuery = Object.fromEntries(
    Object.entries(query).filter(([key]) =>
      [
        "q",
        "status",
        "role",
        "workspace_id",
        "team_id",
        "batch_id",
        "department_id",
        "skill",
        "kind",
        "membership",
        "registered_from",
        "registered_to",
        "sort",
        "page",
      ].includes(key),
    ),
  );
  const layout = params.get("layout") || "cards";
  const backTo = "/pms/people?" + params.toString();
  const storageKey = "people-directory-scroll:" + params.toString();
  const paramsRef = useRef(params);
  paramsRef.current = params;
  const change = (key: string, value: string) => {
    const next = new URLSearchParams(paramsRef.current);
    value ? next.set(key, value) : next.delete(key);
    if (!["page", "layout", "density", "panel", "columns"].includes(key)) next.delete("page");
    paramsRef.current = next;
    setParams(next);
    if (!["page", "layout", "sort", "density", "panel", "columns"].includes(key)) setSelected([]);
  };
  useEffect(() => {
    const timer = setTimeout(() => {
      if (search !== (params.get("q") || "")) change("q", search);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => setSearch(params.get("q") || ""), [params.get("q")]);
  useEffect(() => { const role = params.get("role") || ""; if (role !== "superuser" && ["superadmin", "superuser"].includes(role.toLowerCase().replace(/[ _]/g, ""))) change("role", "superuser"); }, [params.get("role")]);
  const people = useQuery({
    queryKey: ["people-workspace", "directory", JSON.stringify(dataQuery)],
    queryFn: () =>
      directoryGet<DirectoryPage>("/people", { ...query, page, page_size: 24 }),
  });
  const selectionFilter = JSON.stringify(Object.entries(dataQuery).filter(([key]) => !["page", "sort"].includes(key)));
  useEffect(() => { setSelected([]); setSelectionPeople({}); setSelectionPages({}); }, [selectionFilter, user?.id, user?.access?.companyId]);
  useEffect(() => { if (people.data) setSelectionPeople(current => ({...current, ...Object.fromEntries(people.data.items.map(person => [person.id, person]))})); }, [people.data]);
  const selectPerson = (person: DirectoryPerson) => {
    setSelected(ids => ids.includes(person.id) ? ids.filter(id => id !== person.id) : ids.length < 100 ? [...ids,person.id] : ids);
    setSelectionPages(current => ({...current,[person.id]:page}));
    if (selected.length >= 100 && !selected.includes(person.id)) setError("Select at most 100 people per bulk operation.");
  };
  const togglePage = () => {
    const active = (people.data?.items || []).filter(person => person.status === "active").map(person => person.id);
    const all = active.length > 0 && active.every(id => selected.includes(id));
    const next = all ? selected.filter(id => !active.includes(id)) : [...new Set([...selected,...active])];
    if (next.length > 100) { setError("Select at most 100 people per bulk operation. Review or clear the existing selection first."); return; }
    setSelected(next); setSelectionPages(current => ({...current, ...Object.fromEntries(active.map(id => [id,page]))}));
  };
  const reference = useQuery({
    queryKey: ["people-workspace", "reference"],
    queryFn: () => directoryGet<DirectoryReference>("/reference"),
    staleTime: 30000,
  });
  const views = useQuery({
    queryKey: ["people-workspace", "views"],
    queryFn: () =>
      directoryGet<
        { id: number; name: string; filters: Record<string, string> }[]
      >("/views"),
  });
  usePageRefresh(() =>
    qc.invalidateQueries({ queryKey: ["people-workspace"] }),
  );
  useEffect(() => {
    if (people.data) {
      const offset = Number(sessionStorage.getItem(storageKey) || 0);
      requestAnimationFrame(() => listRef.current?.scrollTo({ top: offset }));
    }
  }, [people.data]);
  const currentRef = useRef(storageKey);
  currentRef.current = storageKey;
  useEffect(
    () => () => {
      if (listRef.current)
        sessionStorage.setItem(
          currentRef.current,
          String(listRef.current.scrollTop),
        );
    },
    [],
  );
  const ref = reference.data;
  const stats = ref?.stats;
  const countFilters = [...params.keys()].filter(
    (key) => !["page", "layout", "sort", "density", "panel", "columns"].includes(key),
  ).length;
  const metrics = [
    {
      label: "Registered users",
      value: stats?.total,
      icon: Users,
      color: "blue",
      key: "",
    },
    {
      label: "Login enabled",
      value: stats?.active,
      icon: Circle,
      color: "green",
      key: "active",
    },
    {
      label: "Login disabled",
      value: stats?.inactive,
      icon: Clock3,
      color: "orange",
      key: "inactive",
    },
    {
      label: "Teams",
      value: stats?.teams,
      icon: Users,
      color: "purple",
      key: "teams",
    },
    {
      label: "Interns Batches",
      value: stats?.batches,
      icon: GraduationCap,
      color: "red",
      key: "batches",
    },
  ];
  const canTeam = !!ref?.can_manage_people;
  const exportPeople = async (scope: "filtered" | "page" | "selected" = "filtered") => {
    setBusy(true);
    setError("");
    try {
      const { data } = await api.get<Blob>(directoryRoot + "/export", {
        params: scope === "filtered" ? query : { selected_ids: (scope === "selected" ? selected : (people.data?.items || []).map(p => p.id)).join(",") },
        responseType: "blob",
      });
      const url = URL.createObjectURL(data);
      const a = document.createElement("a");
      a.href = url;
      a.download = "people-directory.csv";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError(workspaceError(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className={`people-workspace pd-mobile-${mobileTab} ${dragging ? "pd-dragging" : ""} pd-density-${params.get("density") || "comfortable"} ${params.get("panel") === "hidden" ? "pd-panel-hidden" : ""}`}>
      <div className="pd-mobile-tabs">
        {["people", "destinations", "teams", "batches", "organizations"].map((value) => (
          <button
            key={value}
            className={mobileTab === value ? "active" : ""}
            onClick={() => {setMobileTab(value as typeof mobileTab);if(value === "destinations")change("panel","");}}
          >
            {value === "batches" ? "Interns Batches" : value}
          </button>
        ))}
      </div>
      <div className="pd-layout">
        <section
          ref={listRef}
          className="pd-center"
          onScroll={(e) =>
            sessionStorage.setItem(
              storageKey,
              String(e.currentTarget.scrollTop),
            )
          }
        >
          <nav className="pd-breadcrumb" aria-label="People breadcrumbs">
            <Link to="/dashboard">All applications</Link>
            <ChevronRight />
            <Link to="/pms">KaryaFlow PMS</Link>
            <ChevronRight />
            <strong>People directory</strong>
          </nav>
          <header className="pd-heading">
            <div>
              <h1>People directory</h1>
              <p>
                Explore registered users, teams and intern batches across all
                workspaces.
              </p>
            </div>
            <div className="pd-heading-actions">
              <div className="pd-split-button">
                <button
                  className="pd-primary"
                  disabled={!ref?.can_create_user && !canTeam}
                  title={
                    !ref?.can_create_user && !canTeam
                      ? "Creating or inviting people requires an authorized administrator"
                      : "Add a registered person or invitation"
                  }
                  onClick={() =>
                    navigate(
                      ref?.can_create_user
                        ? "/users?create=1"
                        : "/pms/members#invitations",
                    )
                  }
                >
                  <Plus size={16} />
                  Add Person
                </button>
                <Dropdown.Root>
                  <Dropdown.Trigger aria-label="Add person options">
                    <ChevronDown size={14} />
                  </Dropdown.Trigger>
                  <Dropdown.Portal>
                    <Dropdown.Content className="pd-dropdown">
                      <Dropdown.Item asChild>
                        <Link to="/pms/members">
                          Add existing person to workspace / project
                        </Link>
                      </Dropdown.Item>
                      <Dropdown.Item asChild>
                        <Link to="/pms/members#invitations">
                          Invite by email
                        </Link>
                      </Dropdown.Item>
                    </Dropdown.Content>
                  </Dropdown.Portal>
                </Dropdown.Root>
              </div>
              <button
                className="pd-button"
                disabled={!canTeam}
                onClick={() => setImporting(true)}
              >
                Import
              </button>
              <button
                className="pd-button pd-export"
                disabled={!ref?.can_export || busy}
                title={
                  !ref?.can_export
                    ? "Scoped export permission is required"
                    : "Export the current filtered records"
                }
                onClick={() => setExportOpen(true)}
              >
                <Download size={15} />
                Export
              </button>
              <Dropdown.Root>
                <Dropdown.Trigger
                  className="pd-button"
                  aria-label="More directory actions"
                >
                  <MoreVertical size={17} />
                </Dropdown.Trigger>
                <Dropdown.Portal>
                  <Dropdown.Content className="pd-dropdown">
                    <Dropdown.Item
                      onSelect={() =>
                        void qc.invalidateQueries({
                          queryKey: ["people-workspace"],
                        })
                      }
                    >
                      <RefreshCw size={15} />
                      Refresh directory
                    </Dropdown.Item>
                    <Dropdown.Item
                      disabled={!ref?.can_export || busy}
                      onSelect={() => void exportPeople()}
                    >
                      <Download size={15} />
                      Export filtered people
                    </Dropdown.Item>
                    <Dropdown.Item
                      onSelect={() => {
                        setParams(new URLSearchParams());
                        setSelected([]);
                      }}
                    >
                      Clear all filters
                    </Dropdown.Item>
                    <Dropdown.Item asChild>
                      <Link to="/pms/members#invitations">
                        Invitations & resend
                      </Link>
                    </Dropdown.Item>
                  </Dropdown.Content>
                </Dropdown.Portal>
              </Dropdown.Root>
            </div>
          </header>
          <div className="pd-metrics">
            {metrics.map((metric) => (
              <button
                key={metric.label}
                title={metric.key===""?"Unique registered accounts visible in the current organization; pending invitations excluded. Employee records and membership rows are separate measures.":metric.key==="active"||metric.key==="inactive"?"Global login switch for registered accounts; employment and workspace access are separate.":"Visible records in your current organization and permission scope."}
                className={`pd-metric ${metric.color}`}
                onClick={() => {
                  if (metric.key === "teams" || metric.key === "batches") {
                    setMobileTab(metric.key);
                    return;
                  }
                  change("status", metric.key);
                }}
              >
                <span>
                  <metric.icon size={23} />
                </span>
                <div>
                  <strong>{metric.value ?? "—"}</strong>
                  <small>{metric.label}</small>
                </div>
              </button>
            ))}
          </div>
          {(error || people.error || reference.error) && (
            <div role="alert" className="pd-error pd-alert">
              {error || workspaceError(people.error || reference.error)}
              <button
                onClick={() => {
                  setError("");
                  void qc.invalidateQueries({ queryKey: ["people-workspace"] });
                }}
              >
                Retry
              </button>
            </div>
          )}
          <div className="pd-search-row">
            <label className="pd-search">
              <Search size={17} />
              <input
                aria-label="Search people directory"
                placeholder="Search by name, email, role, skills, batch, team, workspace…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </label>
            <button
              className="pd-button pd-filter"
              aria-expanded={filtersOpen}
              onClick={() => setFiltersOpen((v) => !v)}
            >
              <Filter size={15} />
              Filters{countFilters > 0 && <i>{countFilters}</i>}
            </button>
            <select
              aria-label="Saved people views"
              value=""
              onChange={(e) => {
                if (e.target.value === "save") setSaveOpen(true);
                else {
                  const view = views.data?.find(
                    (v) => v.id === Number(e.target.value),
                  );
                  if (view) setParams(new URLSearchParams(view.filters));
                }
              }}
            >
              <option value="">Saved views</option>
              {views.data?.map((view) => (
                <option key={view.id} value={view.id}>
                  {view.name}
                </option>
              ))}
              <option value="save">+ Save current view</option>
            </select>
            <div className="pd-view-toggle">
              <button
                aria-label="Card view"
                aria-pressed={layout === "cards"}
                className={layout === "cards" ? "active" : ""}
                onClick={() => change("layout", "cards")}
              >
                <LayoutGrid size={17} />
              </button>
              <button
                aria-label="Table view"
                aria-pressed={layout === "list"}
                className={layout === "list" ? "active" : ""}
                onClick={() => change("layout", "list")}
              >
                <List size={17} />
              </button>
            </div>
          </div>
          <div className="pd-command-bar"><label>Density <select aria-label="Card density" value={params.get("density") || "comfortable"} onChange={e=>change("density",e.target.value)}>{["comfortable","compact","detailed"].map(v=><option key={v}>{v}</option>)}</select></label><button className="pd-button" onClick={()=>change("panel",params.get("panel") === "hidden" ? "" : "hidden")}>{params.get("panel") === "hidden" ? "Show destinations" : "Hide destinations"}</button><button className="pd-button" onClick={async()=>{try{await navigator.clipboard.writeText(window.location.href);setNotice("Directory link copied with filters and layout.");}catch{setNotice("Copy this page URL from the address bar.");}}}>Copy filtered link</button><span role="status">{notice}</span></div>
          <div className="pd-quick-filters">
            {[
              ["all", "All people"],
              ["team_members", "Team members"],
              ["interns", "Interns"],
              ["employees", "Employees"],
              ["needs_attention", "Needs attention"],
              ["batched", "By batch"],
            ].map(([key, label]) => (
              <button
                key={key}
                className={
                  (params.get("kind") || "all") === key ? "active" : ""
                }
                onClick={() => change("kind", key === "all" ? "" : key)}
              >
                {key !== "all" && <Users size={12} />} {label}
              </button>
            ))}
            <button className={params.get("membership") === "unassigned" ? "active" : ""} onClick={()=>change("membership",params.get("membership") === "unassigned" ? "" : "unassigned")}>Unassigned</button>
            <button onClick={() => setFiltersOpen(true)}>
              <Users size={12} />
              By team
            </button>
            <select
              aria-label="Filter role"
              value={params.get("role") || ""}
              onChange={(e) => change("role", e.target.value)}
            >
              <option value="">Roles</option>
              <option value="superuser">Super Admin</option>
              {ref?.roles.map((role) => (
                <option key={role}>{role}</option>
              ))}
            </select>
            <select
              aria-label="Filter status"
              value={params.get("status") || ""}
              onChange={(e) => change("status", e.target.value)}
            >
              <option value="">Status</option>
              {["active", "inactive", "suspended", "terminated"].map(
                (status) => (
                  <option key={status} value={status}>
                    {status[0].toUpperCase() + status.slice(1)}
                  </option>
                ),
              )}
            </select>
            <button onClick={() => setFiltersOpen((v) => !v)}>
              More filters
              <Filter size={11} />
            </button>
          </div>
          {filtersOpen && (
            <div className="pd-filter-panel">
              <GroupFilter
                kind="teams"
                value={params.get("team_id") || ""}
                onChange={(v) => change("team_id", v)}
              />
              <GroupFilter
                kind="batches"
                value={params.get("batch_id") || ""}
                onChange={(v) => change("batch_id", v)}
              />
              <label>
                Workspace
                <select
                  aria-label="Filter workspace"
                  value={params.get("workspace_id") || ""}
                  onChange={(e) => change("workspace_id", e.target.value)}
                >
                  <option value="">All accessible workspaces</option>
                  {ref?.workspaces.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Department
                <select
                  aria-label="Filter department"
                  value={params.get("department_id") || ""}
                  onChange={(e) => change("department_id", e.target.value)}
                >
                  <option value="">All visible departments</option>
                  {ref?.departments.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Skills
                <input
                  aria-label="Filter skill"
                  value={params.get("skill") || ""}
                  onChange={(e) => change("skill", e.target.value)}
                  placeholder="Skill name"
                />
              </label>
              <label>
                Registered from
                <input
                  aria-label="Registered from"
                  type="date"
                  value={params.get("registered_from") || ""}
                  onChange={(e) => change("registered_from", e.target.value)}
                />
              </label>
              <label>
                Registered to
                <input
                  aria-label="Registered to"
                  type="date"
                  value={params.get("registered_to") || ""}
                  onChange={(e) => change("registered_to", e.target.value)}
                />
              </label>
              <label>
                Membership
                <select
                  aria-label="Filter membership"
                  value={params.get("membership") || ""}
                  onChange={(e) => change("membership", e.target.value)}
                >
                  <option value="">All registered people</option>
                  <option value="member">
                    Members of accessible workspaces
                  </option>
                  <option value="unassigned">
                    No membership in accessible workspaces
                  </option>
                </select>
              </label>
              <label>
                Sort
                <select
                  aria-label="Sort people"
                  value={params.get("sort") || "name"}
                  onChange={(e) => change("sort", e.target.value)}
                >
                  {[
                    ["name", "Name"],
                    ["name_desc", "Name (Z–A)"],
                    ["email", "Email"],
                    ["email_desc", "Email (Z–A)"],
                    ["newest", "Newest registered"],
                    ["oldest", "Oldest registered"],
                    ["status", "Active first"],
                    ["status_desc", "Inactive first"],
                  ].map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <button
                className="pd-button"
                onClick={() => {
                  setParams(new URLSearchParams());
                  setSearch("");
                }}
              >
                Clear filters
              </button>
              <p>
                Pending invitations remain separate from registered identities.{" "}
                <Link to="/pms/members#invitations">Manage invitations</Link>
              </p>
            </div>
          )}
          {countFilters > 0 && (
            <div className="pd-active-filters">
              {[...params.entries()]
                .filter(([key]) => !["page", "layout", "sort", "density", "panel", "columns"].includes(key))
                .map(([key, value]) => (
                  <button key={key} onClick={() => change(key, "")}>
                    {key.replace(/_/g, " ")}: {value}
                    <X size={11} />
                  </button>
                ))}
            </div>
          )}
          {!!selected.length && (
            <div className="pd-bulk-actions">
              <strong>{selected.length} selected across {new Set(selected.map(id => selectionPages[id] || page)).size} {new Set(selected.map(id => selectionPages[id] || page)).size === 1 ? "page" : "pages"} · limit 100</strong>
              <button onClick={() => setReviewSelection(true)}>Review selection</button>
              {membershipOptions.isError && <span role="alert">Could not load membership destinations. <button onClick={() => membershipOptions.refetch()}>Retry</button></span>}
              <PeopleAction reason={!canAddWorkspace ? (membershipOptions.isLoading ? "Loading workspaces…" : "No workspaces you can manage. Ask a workspace owner for access.") : undefined} onClick={() => setMembershipMode("workspace")}>
                Add to workspace
              </PeopleAction>
              <PeopleAction reason={!canAddProject ? (membershipOptions.isLoading ? "Loading projects…" : "No projects you can manage. Ask a project owner for access.") : undefined} onClick={() => setMembershipMode("project")}>
                Add to project
              </PeopleAction>
              <PeopleAction reason={!canTeam ? "Adding team members requires workspace administration access." : undefined} onClick={() => setAdding(true)}>
                <Users size={15} />
                Add to team
              </PeopleAction>
              <button
                onClick={() => navigate(directoryTaskHref("people", selected))}
              >
                Assign task
              </button>
              <button onClick={()=>{change("panel","");setMobileTab("destinations");setDestinationRequest({kind:"projects",action:"add",sequence:Date.now()});}}>Bulk destinations / transfer / remove / roles</button>
              <button disabled={!ref?.can_export || busy} onClick={()=>void exportPeople("selected")}>Export selected</button>
              <button onClick={() => setSelected([])}>Clear selection</button>
            </div>
          )}
          <div className="mb-3 flex flex-wrap items-center gap-4 text-sm"><PageSelection people={people.data?.items || []} selected={selected} onToggle={togglePage} /><span>Select up to 100 active people across pages. Changing filters clears the selection.</span></div>
          {people.isLoading ? (
            <div
              className="pd-card-grid"
              role="status"
              aria-label="Loading directory"
            >
              {Array.from({ length: 12 }, (_, i) => (
                <div className="pd-card-skeleton" key={i} />
              ))}
            </div>
          ) : layout === "list" ? <DirectoryTable columnsValue={params.get("columns") ?? undefined} onColumnsChange={value=>change("columns",value)} people={people.data?.items || []} selected={selected} onSelect={selectPerson} onTogglePage={togglePage} backTo={backTo} sort={params.get("sort") || "name"} onSort={value => change("sort",value)} /> : (
            <div className="pd-card-grid">
              {people.data?.items.map((person) => (
                <DirectoryPersonCard
                  key={person.id}
                  person={person}
                  onPreview={()=>setPreviewPerson(person)}
                  onDestinations={()=>{setSelected([person.id]);change("panel","");setMobileTab("destinations");setDestinationRequest({kind:"projects",action:"add",sequence:Date.now()});}}
                  onDragMembers={event=>{const ids=selected.includes(person.id)?selected:[person.id];event.dataTransfer.setData("application/x-pms-members",JSON.stringify(ids));event.dataTransfer.effectAllowed="copyMove";setSelected(ids);setDragging(true);}}
                  onDragEnd={()=>setDragging(false)}
                  selected={selected.includes(person.id)}
                  canTeam={canTeam}
                  canAddWorkspace={canAddWorkspace}
                  canAddProject={canAddProject}
                  onWorkspace={() => { setSelected([person.id]); setMembershipMode("workspace"); }}
                  onProject={() => { setSelected([person.id]); setMembershipMode("project"); }}
                  profileHref={`/pms/people/${person.id}?returnTo=${encodeURIComponent(backTo)}`}
                  onSelect={() => selectPerson(person)}
                  onTeam={() => {
                    setSelected([person.id]);
                    setAdding(true);
                  }}
                  onAssign={() =>
                    navigate(directoryTaskHref("people", [person.id]))
                  }
                />
              ))}
            </div>
          )}
          {people.data && !people.data.items.length && (
            <div className="pd-empty">
              <Users />
              <h2>No people match these filters</h2>
              <p>Try another name, workspace, team, batch, or status.</p>
              <button
                className="pd-button"
                onClick={() => setParams(new URLSearchParams())}
              >
                Clear filters
              </button>
            </div>
          )}
          <footer className="pd-results-footer">
            <span>
              {people.data?.total ?? 0} matching registered people
              {people.isFetching && !people.isLoading ? " · Updating…" : ""}
            </span>
            <DirectoryPagination
              page={page}
              pages={people.data?.pages || 1}
              onChange={(value) => change("page", String(value))}
            />
          </footer>
        </section>
        <div className="pd-destination-column"><DirectoryDestinations onClose={()=>{setMobileTab("people");change("panel","hidden");}} selected={selected} dragging={dragging} request={destinationRequest} onChanged={()=>{void qc.invalidateQueries({queryKey:["people-workspace"]});}} /><details className="pd-group-administration" open={!["people","destinations"].includes(mobileTab) || undefined}><summary>Team and batch administration</summary>
        <DirectoryGroupsPanel
          reference={ref}
          onNewTeam={() => setTeamEditor({})}
          onEditTeam={(id, workspace) => setTeamEditor({ id, workspace })}
          forcedTab={mobileTab === "people" || mobileTab === "destinations" ? undefined : mobileTab}
          onTabChange={setMobileTab}
        /></details></div>
      </div>
      <PeopleDialog open={exportOpen} onClose={()=>setExportOpen(false)} title="Export people" description="Choose exactly which registered people to export."><div className="pd-dialog-actions">{(["filtered","page","selected"] as const).map(scope=><button className="pd-button" key={scope} disabled={busy || !ref?.can_export || (scope === "selected" && !selected.length)} onClick={()=>void exportPeople(scope)}>{scope === "filtered" ? "All filtered results" : scope === "page" ? "Current page" : `${selected.length} selected people`}</button>)}</div></PeopleDialog>
      <PeopleDialog className="pd-preview-drawer" open={!!previewPerson} onClose={()=>setPreviewPerson(undefined)} title={previewPerson?.name || "Member preview"} description="Quick member preview. Close to return to your current selection and filters.">{previewPerson && <div className="pd-member-preview"><p>{previewPerson.email}</p><p>{previewPerson.classification} / {previewPerson.status}</p><h3>Current projects</h3><p>{previewPerson.projects?.map(p=>p.name).join(", ") || "No current projects"}</p><h3>Teams</h3><p>{previewPerson.teams.map(p=>p.name).join(", ") || "No teams"}</p>{previewPerson.classification.toLowerCase() === "intern" && <><h3>Intern batches</h3><p>{previewPerson.batches.map(p=>p.name).join(", ") || "No batch"}</p></>}<h3>Skills</h3><p>{previewPerson.skills.join(", ") || "No skills listed"}</p><div className="pd-dialog-actions"><Link className="pd-button" to={`/pms/people/${previewPerson.id}?returnTo=${encodeURIComponent(backTo)}`}>Open full profile</Link><Link className="pd-button" to={`/pms/people/${previewPerson.id}?tab=activity&returnTo=${encodeURIComponent(backTo)}`}>Assignment history</Link><button className="pd-primary" onClick={()=>{setSelected([previewPerson.id]);setPreviewPerson(undefined);change("panel","");setMobileTab("destinations");setDestinationRequest({kind:"projects",action:"add",sequence:Date.now()});}}>Assign to destination</button></div></div>}</PeopleDialog>
      <PeopleDialog open={reviewSelection} onClose={() => setReviewSelection(false)} title="Review selected people" description={`${selected.length} selected people. Remove anyone before applying a bulk action.`}>
        <ul className="max-h-80 overflow-auto">{selected.map(id => <li className="flex items-center justify-between border-b py-2" key={id}><span>{selectionPeople[id]?.name || `Person #${id}`}<small className="block">{selectionPeople[id]?.email}</small></span><button className="pd-button" onClick={() => setSelected(ids => ids.filter(value => value !== id))}>Remove</button></li>)}</ul>
        <button className="pd-button" onClick={() => setReviewSelection(false)}>Done</button>
      </PeopleDialog>
      <TeamEditor
        open={!!teamEditor}
        onClose={() => setTeamEditor(null)}
        reference={ref}
        initialWorkspace={
          teamEditor?.workspace ||
          Number(params.get("workspace_id")) ||
          undefined
        }
        teamId={teamEditor?.id}
      />
      <AddPeopleToTeam
        open={adding}
        onClose={() => setAdding(false)}
        personIds={selected}
        reference={ref}
      />
      <AddPeopleMemberships mode={membershipMode} personIds={selected}
        onClose={() => setMembershipMode(null)} onAdded={() => setSelected([])} />
      <DirectoryImport
        open={importing}
        onClose={() => setImporting(false)}
        reference={ref}
      />
      <PeopleDialog
        open={saveOpen}
        onClose={() => setSaveOpen(false)}
        title="Save people view"
        description="Store this directory's filters and layout against your own account."
      >
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await api.post(directoryRoot + "/views", {
                name: viewName,
                filters: query,
              });
              await views.refetch();
              setSaveOpen(false);
              setViewName("");
            } catch (e) {
              setError(workspaceError(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            View name
            <input
              aria-label="People view name"
              required
              maxLength={120}
              value={viewName}
              onChange={(e) => setViewName(e.target.value)}
            />
          </label>
          {error && (
            <p role="alert" className="pd-error">
              {error}
            </p>
          )}
          <div className="pd-dialog-actions">
            <button className="pd-primary" disabled={busy}>
              <Save size={15} />
              Save view
            </button>
          </div>
        </form>
        <h3>My saved views</h3>
        {views.data?.map((view) => (
          <div className="pd-saved-view" key={view.id}>
            {view.name}
            <button
              onClick={async () => {
                try {
                  await api.delete(`${directoryRoot}/views/${view.id}`);
                  await views.refetch();
                } catch (e) {
                  setError(workspaceError(e));
                }
              }}
            >
              Delete view
            </button>
          </div>
        ))}
      </PeopleDialog>
    </div>
  );
}
