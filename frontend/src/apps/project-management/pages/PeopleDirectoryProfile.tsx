import { useState } from "react";
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
  const { personId } = useParams();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || "overview";
  const page = Number(params.get("page") || 1);
  const navigate = useNavigate();
  const [adding, setAdding] = useState(false);
  const rawBack = params.get("returnTo");
  const back = rawBack?.startsWith("/pms/people?") ? rawBack : "/pms/people";
  const profile = useQuery({
    queryKey: ["people-workspace", "profile", personId, tab, page],
    queryFn: () =>
      directoryGet<Profile>(`/people/${personId}`, {
        section: tab,
        page,
        page_size: 20,
      }),
  });
  const reference = useQuery({
    queryKey: ["people-workspace", "reference"],
    queryFn: () => directoryGet<DirectoryReference>("/reference"),
    staleTime: 30000,
  });
  const data = profile.data;
  const person = data?.person;
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
      {profile.isLoading && (
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
            <button
              className="pd-button"
              disabled={
                person.status !== "active" || !reference.data?.can_manage_people
              }
              onClick={() => setAdding(true)}
            >
              <Users size={16} />
              Add to team
            </button>
            <button
              className="pd-primary"
              disabled={person.status !== "active"}
              onClick={() => navigate(directoryTaskHref("people", [person.id]))}
            >
              <Plus size={15} />
              Assign task
            </button>
            <a
              className="pd-button"
              href={`mailto:${encodeURIComponent(person.email)}`}
            >
              <Mail size={15} />
              Compose email
            </a>
          </div>
          <nav className="pd-profile-tabs">
            {[
              "overview",
              "teams",
              "batches",
              "projects",
              "tasks",
              "activity",
            ].map((value) => (
              <button
                key={value}
                className={tab === value ? "active" : ""}
                onClick={() =>
                  setParams((previous) => {
                    const next = new URLSearchParams(previous);
                    next.set("tab", value);
                    next.delete("page");
                    return next;
                  })
                }
              >
                {value === "batches" ? "Intern batch" : value}
              </button>
            ))}
          </nav>
          <div className="pd-profile-content">
            {tab === "overview" && (
              <>
                <div className="pd-overview-stats">
                  {[
                    ["Assigned tasks", data.stats?.total],
                    ["Pending", data.stats?.pending],
                    ["Completed", data.stats?.completed],
                    ["Overdue", data.stats?.overdue],
                  ].map(([label, value]) => (
                    <button
                      key={label}
                      onClick={() =>
                        setParams((previous) => {
                          const next = new URLSearchParams(previous);
                          next.set("tab", "tasks");
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
                    {person.batches.map((batch) => (
                      <Link
                        className="pd-project-link"
                        key={batch.id}
                        to={`/pms/people?batch_id=${batch.id}`}
                      >
                        {batch.name}
                      </Link>
                    ))}
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
                {data.items?.map((group) => (
                  <Link
                    className="pd-project-link"
                    key={group.id}
                    to={`/pms/people?${tab === "teams" ? "team_id" : "batch_id"}=${group.id}`}
                  >
                    <Users size={16} />
                    {group.name}
                  </Link>
                ))}
                {!data.items?.length && (
                  <p>No visible memberships in this view.</p>
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
                  {project.name}
                  <small>{project.status}</small>
                </Link>
              ))}
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
                <p className="pd-scope-note">
                  Only records in your authorized scope are shown.
                </p>
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
          </div>
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
