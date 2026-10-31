import PeopleAction from "../components/people/PeopleAction";
import AddPeopleMemberships from "../components/people/AddPeopleMemberships";
import { useMembershipOptions } from "../components/people/peopleMemberships";
import { useEffect, useState } from "react";
import { useAuthStore } from "@/store/authStore";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  Plus,
  Users,
  ClipboardList,
  Mail,
  Briefcase,
  ShieldCheck,
} from "lucide-react";
import {
  directoryGet,
  directoryTaskHref,
  type DirectoryPerson,
  type DirectoryReference,
} from "../components/people/peopleWorkspace";
import { DirectoryAvatar } from "../components/people/DirectoryPersonCard";
import {
  AddPeopleToTeam,
  DirectoryPagination,
} from "../components/people/DirectoryDialogs";
import { ManagePersonButton } from "../components/people/PersonIdentity";
import { openPerson } from "../components/people/peopleTypes";
import { workspaceError } from "./workspaceTypes";
import "./PeopleWorkspace.css";
type Profile = {
  person: DirectoryPerson;
  is_intern?: boolean;
  counts?: Record<string, number | null>;
  access_issues?: string[];
  current_projects?: { id: number; name: string; status: string; project_key: string; workspace_name?: string; role?: string; relationships?: string[] }[];
  can_manage: boolean;
  employment_status?: string;
  stats?: {
    total: number;
    completed: number;
    pending: number;
    overdue: number;
    submissions: Record<string, number>;
  };
  items?: any[];
  total?: number;
  pages?: number;
  restricted_reason?: string;
};
export default function PeopleDirectoryProfile() {
  const viewer = useAuthStore(state => state.user);
  const { personId } = useParams();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || "overview";
  const page = Number(params.get("page") || 1);
  const navigate = useNavigate();
  const [adding, setAdding] = useState(false);
  const [membershipMode, setMembershipMode] = useState<"workspace" | "project" | null>(null);
  const destinations = useMembershipOptions();
  const taskFilter = params.get("task_filter") || "all";
  const keyBase = ["people-workspace", "profile", viewer?.id, viewer?.access?.companyId, personId];
  const overview = useQuery({queryKey:[...keyBase,"overview",1,"all"], queryFn:()=>directoryGet<Profile>(`/people/${personId}`,{section:"overview",page:1,page_size:20}), staleTime:30000});
  const rawBack = params.get("returnTo");
  const back = rawBack?.startsWith("/pms/people?") ? rawBack : "/pms/people";
  const profile = useQuery({
    queryKey: [...keyBase, tab, page, tab === "tasks" ? taskFilter : "all"],
    queryFn: () =>
      directoryGet<Profile>(`/people/${personId}`, {
        section: tab,
        task_filter: tab === "tasks" ? taskFilter : "all",
        page,
        page_size: 20,
      }),
  });
  const reference = useQuery({
    queryKey: ["people-workspace", "reference"],
    queryFn: () => directoryGet<DirectoryReference>("/reference"),
    staleTime: 30000,
  });
  const data = profile.data || overview.data;
  const person = data?.person;
  const isIntern = data?.is_intern ?? person?.classification.toLowerCase() === "intern";
  useEffect(() => {
    if (person && !isIntern && tab === "batches") setParams(previous => {
      const next = new URLSearchParams(previous); next.delete("tab"); next.delete("page"); return next;
    }, { replace: true });
  }, [person, isIntern, tab, setParams]);
  return (
    <section className="people-workspace pd-profile">
      <nav className="pd-breadcrumb">
        <Link to={back}>
          <ArrowLeft size={14} />
          People directory
        </Link>
        <span>›</span>
        <strong>{person?.name || "Person profile"}</strong>
      </nav>
      {!person && profile.isLoading && (
        <div role="status" className="pd-profile-skeleton">
          Loading permitted profile information…
        </div>
      )}
      {profile.error && (
        <div role="alert" className="pd-error">
          {workspaceError(profile.error)}
          <button onClick={() => void profile.refetch()}>Retry</button>
        </div>
      )}
      {person && (
        <>
          <header className="pd-profile-header">
            <DirectoryAvatar person={person} size="large" />
            <div>
              <h1>{person.name}</h1>
              <p>
                {person.classification} · {person.email}
              </p>
              <div className="pd-tags">
                <span>{person.role}</span>
                {person.department && <span>{person.department}</span>}
                <span>{person.employee_code}</span>
              </div>
            </div>
            <span
              className={`pd-status ${person.status === "active" ? "active" : "inactive"}`}
            >
              <i />
              {person.status}
            </span>
          </header>
          <div className="pd-profile-actions">
            {data.can_manage ? (
              <button
                className="pd-button"
                onClick={() => openPerson({ userId: person.id })}
              >
                <ShieldCheck size={16} />
                Edit profile & access
              </button>
            ) : (
              <span className="pd-scope-note">
                Editing requires permission to manage this person.
              </span>
            )}
            <PeopleAction className="pd-button" reason={person.status !== "active" ? "Reactivate the account before adding team memberships." : !reference.data?.can_manage_people ? "Adding team members requires workspace administration access." : undefined} onClick={() => setAdding(true)}>
              <Users size={16} />
              Add to team
            </PeopleAction>
            <PeopleAction className="pd-button" reason={person.status !== "active" ? "Reactivate the account before adding memberships." : !destinations.data?.workspaces.length ? (destinations.isLoading ? "Loading workspaces…" : "No workspaces you can manage.") : undefined} onClick={()=>setMembershipMode("workspace")}>Add to workspace</PeopleAction>
            <PeopleAction className="pd-button" reason={person.status !== "active" ? "Reactivate the account before adding memberships." : !destinations.data?.projects.length ? (destinations.isLoading ? "Loading projects…" : "No projects you can manage.") : undefined} onClick={()=>setMembershipMode("project")}>Add to project</PeopleAction>
            <PeopleAction
              className="pd-primary"
              reason={person.status !== "active" ? "Reactivate the account before assigning work." : undefined}
              onClick={() => navigate(directoryTaskHref("people", [person.id]))}
            >
              <Plus size={15} />
              Assign task
            </PeopleAction>
            <a
              className="pd-button"
              href={`mailto:${encodeURIComponent(person.email)}`}
            >
              <Mail size={15} />
              Compose email
            </a>
          </div>
          {!!data.access_issues?.length && <section className="mb-4 rounded-lg border border-amber-400 p-4" aria-label="Access needs attention"><h2 className="font-semibold">Access needs attention</h2>{data.access_issues.map(issue=><p key={issue}>{issue}</p>)}{(viewer?.is_superuser || viewer?.access?.isAccessAdmin) ? <Link className="pd-button" to={`/admin/control/users/${person.id}`}>Review organization access</Link> : <p>Contact your organization access administrator to resolve this.</p>}</section>}
          <nav className="pd-profile-tabs" aria-label="Profile sections">
            {[
              "overview",
              "teams",
              "batches",
              "projects",
              "tasks",
              "activity",
            ].filter(value => value !== "batches" || isIntern).map((value) => (
              <button
                key={value}
                className={tab === value ? "active" : ""}
                aria-current={tab === value ? "page" : undefined}
                onClick={() =>
                  setParams((previous) => {
                    const next = new URLSearchParams(previous);
                    next.set("tab", value);
                    next.delete("page"); next.delete("task_filter");
                    return next;
                  })
                }
              >
                {value === "batches" ? "Intern batch" : value}{data.counts?.[value] != null ? ` (${data.counts[value]})` : ""}
              </button>
            ))}
          </nav>
          <div className="pd-profile-content" aria-busy={profile.isFetching}>
            {!profile.data && profile.isFetching && <p role="status">Loading {tab === "batches" ? "intern batch" : tab}…</p>}
            {profile.data && <>
            {tab === "overview" && (
              <>
                <div className="pd-overview-stats">
                  {[
                    ["Assigned tasks", data.stats?.total, "all"],
                    ["Pending", data.stats?.pending, "pending"],
                    ["Completed", data.stats?.completed, "completed"],
                    ["Overdue", data.stats?.overdue, "overdue"],
                  ].map(([label, value, filter]) => (
                    <button
                      key={label}
                      onClick={() =>
                        setParams((previous) => {
                          const next = new URLSearchParams(previous);
                          next.set("tab", "tasks"); next.set("task_filter", String(filter)); next.delete("page");
                          return next;
                        })
                      }
                    >
                      <strong>{value ?? 0}</strong>
                      <small>{label}</small>
                    </button>
                  ))}
                </div>
                <div className="pd-profile-columns">
                  <section>
                    <h2>Overview</h2>
                    <p>
                      Login access: <strong>{person.status}</strong>
                    </p>
                    {data.employment_status && (
                      <p>
                        Employment status:{" "}
                        <strong>{data.employment_status}</strong>
                      </p>
                    )}
                    {person.employee_code && (
                      <p>Employee / intern ID: {person.employee_code}</p>
                    )}
                    {person.department && (
                      <p>Department: {person.department}</p>
                    )}
                    <p>
                      Registered:{" "}
                      {new Date(person.registered_at).toLocaleDateString()}
                    </p>
                    <h3>Skills</h3>
                    <div className="pd-tags">
                      {person.skills.map((skill) => (
                        <span key={skill}>{skill}</span>
                      ))}
                    </div>
                    {!person.skills.length && (
                      <p className="pd-scope-note">
                        No publicly visible skills are recorded.
                      </p>
                    )}
                  </section>
                  <section>
                    <h2>Memberships</h2>
                    {person.teams.map((team) => (
                      <Link
                        className="pd-project-link"
                        key={team.id}
                        to={`/pms/people?team_id=${team.id}`}
                      >
                        {team.name}
                      </Link>
                    ))}
                    {isIntern && person.batches.map((batch) => (
                      <Link
                        className="pd-project-link"
                        key={batch.id}
                        to={`/pms/people?batch_id=${batch.id}`}
                      >
                        {batch.name}
                      </Link>
                    ))}
                    <h3 className="mt-4">Current projects</h3>
                    {data.current_projects?.map(project => <Link key={project.id} className="pd-project-link" to={`/pms/projects/${project.id}`}>
                      <Briefcase size={16} /><span><strong>{project.name}</strong><small className="block">{project.project_key} · {project.status}{project.workspace_name ? ` · ${project.workspace_name}` : ""} · {project.role}</small><small className="block">{project.relationships?.join(" · ")}</small></span>
                    </Link>)}
                    {!data.current_projects?.length && <p>No current projects assigned. <PeopleAction className="pd-button" reason={!destinations.data?.projects.length ? "No projects you can manage." : person.status !== "active" ? "Reactivate this account first." : undefined} onClick={()=>setMembershipMode("project")}>Add to project</PeopleAction></p>}
                    <p className="pd-scope-note">
                      Private HR documents and identity records are not part of
                      this directory profile.
                    </p>
                  </section>
                </div>
              </>
            )}
            {["teams", "batches"].includes(tab) && (
              <>
                {(tab !== "batches" || isIntern) && data.items?.map(group => <article key={group.id} className="mb-3 rounded-lg border p-4">
                  <Link className="pd-project-link" to={`/pms/people?${tab === "teams" ? "team_id" : "batch_id"}=${group.id}`}><Users size={16} /><strong>{group.name}</strong></Link>
                  {group.description && <p>{group.description}</p>}
                  {tab === "teams" ? <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                    <div><dt>Workspace</dt><dd>{group.workspace_name || "Not recorded"}</dd></div>
                    <div><dt>Team lead</dt><dd>{group.lead_name || "Not assigned"}</dd></div>
                    <div><dt>Members</dt><dd>{group.members}</dd></div>
                    <div><dt>Visibility</dt><dd>{group.visibility}</dd></div>
                  </dl> : <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                    {[["Batch code", group.code], ["Program", group.program], ["Status", group.status], ["Start date", group.start_date], ["End date", group.end_date], ["Department", group.department], ["Manager", group.manager_name], ["Mentor", group.mentor_name], ["Coordinator", group.coordinator_name]].filter(([,value]) => value).map(([label,value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
                    {group.project_name && <div><dt>Project</dt><dd><Link to={`/pms/projects/${group.project_id}`}>{group.project_name}</Link></dd></div>}
                  </dl>}
                </article>)}
                {!data.items?.length && (
                  <div><p>{tab === "teams" ? "No team memberships recorded." : "No active intern batch membership recorded."}</p>{tab === "teams" ? <PeopleAction className="pd-button" reason={!reference.data?.can_manage_people ? "Team changes require workspace administration access." : person.status !== "active" ? "Reactivate this account first." : undefined} onClick={()=>setAdding(true)}>Add to team</PeopleAction> : reference.data?.can_manage_batches && <Link className="pd-button" to="/hrms/interns/batches">Manage intern batches</Link>}</div>
                )}
              </>
            )}
            {tab === "projects" &&
              data.items?.map((project) => (
                <Link
                  className="pd-project-link"
                  key={project.id}
                  to={`/pms/projects/${project.id}`}
                >
                  <Briefcase size={16} />
                  <span><strong>{project.name}</strong><small className="block">{project.project_key} · {project.status} · {project.role}{project.workspace_name ? ` · ${project.workspace_name}` : ""}</small>
                    <small className="block">{project.relationships?.join(" · ")}</small>
                    {(project.start_date || project.due_date) && <small className="block">{project.start_date ? `Starts ${project.start_date}` : ""}{project.due_date ? ` · Due ${project.due_date}` : ""}</small>}</span>
                </Link>
              ))}
            {tab === "tasks" && <label className="mb-3 block">Task status <select aria-label="Filter profile tasks" value={taskFilter} onChange={event=>setParams(previous=>{const next=new URLSearchParams(previous);next.set("task_filter",event.target.value);next.delete("page");return next;})}><option value="all">All assigned tasks</option><option value="pending">Pending</option><option value="completed">Completed</option><option value="overdue">Overdue</option></select></label>}
            {tab === "tasks" &&
              data.items?.map((task) => (
                <Link
                  className="pd-task-row"
                  key={task.id}
                  to={`/pms/tasks/${task.id}`}
                >
                  <ClipboardList size={17} />
                  <span>
                    <strong>{task.title}</strong>
                    <small>
                      {task.task_key} · {task.status} ·{" "}
                      {task.due_date || "No due date"}
                    </small>
                  </span>
                </Link>
              ))}
            {tab === "activity" && (
              <>
                {data.restricted_reason && <p>{data.restricted_reason}</p>}
                {data.items?.map((item) => (
                  <div className="pd-history-row" key={item.id}>
                    <strong>{item.description || item.action}</strong>
                    <small>
                      {new Date(item.created_at).toLocaleString()} ·{" "}
                      {item.actor || "System"}
                    </small>
                  </div>
                ))}
              </>
            )}
            {["projects", "tasks", "activity"].includes(tab) && (
              <>
                {!data.items?.length && !data.restricted_reason && <p>{tab === "projects" ? "No projects assigned to this person yet." : tab === "tasks" ? `No ${taskFilter === "all" ? "assigned" : taskFilter} tasks recorded.` : "No membership activity recorded."}</p>}
                {!data.items?.length && tab === "projects" && <PeopleAction className="pd-button" reason={!destinations.data?.projects.length ? "No projects you can manage." : person.status !== "active" ? "Reactivate the account first." : undefined} onClick={()=>setMembershipMode("project")}>Add to project</PeopleAction>}
                {!data.items?.length && tab === "tasks" && <PeopleAction className="pd-button" reason={person.status !== "active" ? "Reactivate the account before assigning work." : undefined} onClick={()=>navigate(directoryTaskHref("people",[person.id]))}>Assign task</PeopleAction>}
                {!viewer?.is_superuser && <p className="pd-scope-note">
                  Only records in your authorized scope are shown.
                </p>}
                <DirectoryPagination
                  page={page}
                  pages={data.pages || 1}
                  onChange={(value) =>
                    setParams((previous) => {
                      const next = new URLSearchParams(previous);
                      next.set("page", String(value));
                      return next;
                    })
                  }
                />
              </>
            )}
            </>}
          </div>
          <AddPeopleMemberships mode={membershipMode} personIds={[person.id]} onClose={()=>setMembershipMode(null)} onAdded={()=>{}} />
          <AddPeopleToTeam
            open={adding}
            onClose={() => setAdding(false)}
            personIds={[person.id]}
            reference={reference.data}
          />
        </>
      )}
    </section>
  );
}
