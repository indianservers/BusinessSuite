import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Users,
  GraduationCap,
  Search,
  Plus,
  ChevronRight,
  Building2,
  Check,
  Clock3,
  ClipboardList,
} from "lucide-react";
import { api } from "@/services/api";
import {
  directoryGet,
  directoryRoot,
  directoryTaskHref,
  type DirectoryReference,
  type GroupPage,
  type DirectoryPerson,
  type DirectoryPage,
} from "./peopleWorkspace";
import { DirectoryAvatar } from "./DirectoryPersonCard";
import { PeopleDialog, DirectoryPagination } from "./DirectoryDialogs";
import { workspaceError } from "../../pages/workspaceTypes";
type Detail = {
  group: {
    id: number;
    name: string;
    description: string;
    lead_user_id?: number;
    workspace_id?: number;
    project_id?: number;
    can_manage: boolean;
    responsible_people?: { role: string; id: number; name: string }[];
    status?: string;
    start_date?: string;
    end_date?: string;
    manager_user_id?: number;
    mentor_user_id?: number;
  };
  members: number;
  stats: {
    total: number;
    completed: number;
    pending: number;
    overdue: number;
    submissions: Record<string, number>;
    average_review_score?: number | null;
    with_reviewer?: number;
    without_reviewer?: number;
  };
  workload_scope: string;
  projects?: { id: number; name: string }[];
  items?: any[];
  total?: number;
  page?: number;
  pages?: number;
};
export default function DirectoryGroupsPanel({
  reference,
  onNewTeam,
  onEditTeam,
  forcedTab,
  onTabChange,
}: {
  reference?: DirectoryReference;
  onNewTeam: () => void;
  onEditTeam: (id: number, workspace: number) => void;
  forcedTab?: "teams" | "batches" | "organizations";
  onTabChange?: (value: "teams" | "batches" | "organizations") => void;
}) {
  const [tab, setTab] = useState<"teams" | "batches" | "organizations">(
    "teams",
  );
  const [teamQ, setTeamQ] = useState("");
  const [batchQ, setBatchQ] = useState("");
  const [teamPage, setTeamPage] = useState(1);
  const [batchPage, setBatchPage] = useState(1);
  const [opened, setOpened] = useState<{
    kind: "teams" | "batches";
    id: number;
  }>();
  const active = forcedTab || tab;
  const navigate = useNavigate();
  const teams = useQuery({
    queryKey: ["people-workspace", "groups", "teams", teamQ, teamPage],
    queryFn: () =>
      directoryGet<GroupPage>("/groups", {
        kind: "teams",
        q: teamQ,
        page: teamPage,
        page_size: 8,
      }),
  });
  const batches = useQuery({
    queryKey: ["people-workspace", "groups", "batches", batchQ, batchPage],
    queryFn: () =>
      directoryGet<GroupPage>("/groups", {
        kind: "batches",
        q: batchQ,
        page: batchPage,
        page_size: 6,
      }),
  });
  return (
    <aside className="pd-right-panel">
      <div className="pd-panel-tabs">
        {[
          ["teams", "Teams"],
          ["batches", "Interns Batches"],
          ["organizations", "Organizations"],
        ].map(([value, label]) => (
          <button
            key={value}
            className={active === value ? "active" : ""}
            onClick={() => {
              setTab(value as typeof tab);
              onTabChange?.(value as typeof tab);
            }}
          >
            {label}
          </button>
        ))}
      </div>
      {active === "teams" && (
        <section>
          <header>
            <h2>
              Teams <span>({teams.data?.total ?? "…"})</span>
            </h2>
            <button
              className="pd-button"
              disabled={!reference?.workspaces.some((w) => w.can_manage)}
              onClick={onNewTeam}
            >
              <Plus size={14} />
              New team
            </button>
          </header>
          <label className="pd-panel-search">
            <Search size={15} />
            <input
              aria-label="Search teams"
              placeholder="Search teams…"
              value={teamQ}
              onChange={(e) => {
                setTeamQ(e.target.value);
                setTeamPage(1);
              }}
            />
          </label>
          {teams.isLoading && (
            <div className="pd-panel-skeleton" role="status">
              Loading teams…
            </div>
          )}
          {teams.error && (
            <p role="alert" className="pd-error">
              {workspaceError(teams.error)}
              <button onClick={() => void teams.refetch()}>Retry</button>
            </p>
          )}
          {teams.data?.items.map((team, index) => (
            <button
              className="pd-team-row"
              key={team.id}
              onClick={() => setOpened({ kind: "teams", id: team.id })}
            >
              <span className={`pd-group-icon color-${index % 5}`}>
                <Users size={18} />
              </span>
              <span>
                <strong>{team.name}</strong>
                <small>{team.members} members</small>
              </span>
              <span className="pd-avatar-stack">
                {team.avatars?.slice(0, 2).map((person) => (
                  <DirectoryAvatar
                    key={person.id}
                    person={person}
                    size="small"
                  />
                ))}
                {team.members > 2 && <i>+{team.members - 2}</i>}
              </span>
              <ChevronRight size={14} />
            </button>
          ))}
          {teams.data && !teams.data.total && (
            <p className="pd-empty-small">
              No accessible teams match this search.
            </p>
          )}
          <DirectoryPagination
            page={teamPage}
            pages={teams.data?.pages || 1}
            onChange={setTeamPage}
          />
        </section>
      )}
      {(active === "teams" || active === "batches") && (
        <section className={active === "teams" ? "pd-secondary-batches" : ""}>
          <header>
            <h2>
              Interns Batches <span>({batches.data?.total ?? "…"})</span>
            </h2>
            <button
              className="pd-button"
              disabled={!reference?.can_manage_batches}
              onClick={() => navigate("/hrms/interns/batches?create=batch")}
            >
              <Plus size={14} />
              New batch
            </button>
          </header>
          <label className="pd-panel-search">
            <Search size={15} />
            <input
              aria-label="Search intern batches"
              placeholder="Search batches…"
              value={batchQ}
              onChange={(e) => {
                setBatchQ(e.target.value);
                setBatchPage(1);
              }}
            />
          </label>
          {batches.isLoading && <p role="status">Loading batches…</p>}
          {batches.error && (
            <p className="pd-error" role="alert">
              {workspaceError(batches.error)}
              <button onClick={() => void batches.refetch()}>Retry</button>
            </p>
          )}
          {batches.data?.items.map((batch, index) => (
            <button
              className="pd-batch-row"
              key={batch.id}
              onClick={() => setOpened({ kind: "batches", id: batch.id })}
            >
              <span className={`pd-group-icon color-${index % 5}`}>
                <GraduationCap size={18} />
              </span>
              <span>
                <strong>{batch.name}</strong>
                <small>
                  {batch.members} visible interns · {batch.start_date}
                </small>
              </span>
              <em className={`pd-batch-status ${batch.status?.toLowerCase()}`}>
                {batch.status}
              </em>
              <ChevronRight size={14} />
            </button>
          ))}
          {batches.data && !batches.data.total && (
            <p className="pd-empty-small">
              {reference?.can_manage_batches
                ? "No batches in your management scope."
                : "InternHub management permission is required to view or modify batches."}
            </p>
          )}
          <DirectoryPagination
            page={batchPage}
            pages={batches.data?.pages || 1}
            onChange={setBatchPage}
          />
        </section>
      )}
      {active === "organizations" && (
        <section>
          <header>
            <h2>Organizations</h2>
          </header>
          {reference?.organizations.map((org) => (
            <div className="pd-organization" key={org.id}>
              <Building2 />
              <h3>{org.name}</h3>
              <p>Current authorized organization</p>
              {reference.workspaces.map((w) => (
                <Link key={w.id} to={`/pms/workspaces?workspace=${w.id}`}>
                  {w.name}
                  <ChevronRight size={13} />
                </Link>
              ))}
            </div>
          ))}
        </section>
      )}
      <GroupDetails
        opened={opened}
        onClose={() => setOpened(undefined)}
        onEdit={onEditTeam}
      />
    </aside>
  );
}
function GroupDetails({
  opened,
  onClose,
  onEdit,
}: {
  opened?: { kind: "teams" | "batches"; id: number };
  onClose: () => void;
  onEdit: (id: number, workspace: number) => void;
}) {
  const [tab, setTab] = useState("overview");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["people-workspace", "group-detail", opened, tab, q, page],
    enabled: !!opened,
    queryFn: () =>
      directoryGet<Detail>(`/groups/${opened!.kind}/${opened!.id}`, {
        section: tab,
        q,
        page,
        page_size: 20,
      }),
  });
  const detail = query.data;
  return (
    <PeopleDialog
      open={!!opened}
      onClose={() => {
        onClose();
        setTab("overview");
        setSelected([]);
        setPage(1);
      }}
      title={detail?.group.name || "Group details"}
      description="Live members, permitted project workload, submissions, and review status."
    >
      <div className="pd-detail-tabs">
        {["overview", "members", "tasks"].map((value) => (
          <button
            key={value}
            className={tab === value ? "active" : ""}
            onClick={() => {
              setTab(value);
              setPage(1);
            }}
          >
            {value}
          </button>
        ))}
      </div>
      {(query.error || error) && (
        <p role="alert" className="pd-error">
          {error || workspaceError(query.error)}
        </p>
      )}
      {query.isLoading && <p role="status">Loading group details…</p>}
      {detail && (
        <>
          <div className="pd-detail-actions">
            <button
              className="pd-primary"
              onClick={() => {
                if (opened)
                  navigate(directoryTaskHref(opened.kind, [opened.id]));
              }}
            >
              Assign task
            </button>
            {detail.group.can_manage && opened?.kind === "teams" && (
              <button
                className="pd-button"
                onClick={() => {
                  onEdit(opened.id, detail.group.workspace_id!);
                  onClose();
                }}
              >
                Edit team & members
              </button>
            )}
            {opened?.kind === "batches" && (
              <Link
                className="pd-button"
                to={`/hrms/interns/list?batch_id=${opened.id}`}
              >
                Open InternHub management
              </Link>
            )}
          </div>
          {tab === "overview" && (
            <>
              <p className="pd-group-description">
                {detail.group.description || "No description has been added."}
              </p>
              {detail.group.start_date && (
                <p>
                  {detail.group.start_date} — {detail.group.end_date} ·{" "}
                  {detail.group.status}
                </p>
              )}
              {detail.group.responsible_people?.map((person) => (
                <p key={person.role}>
                  {person.role}:{" "}
                  <Link to={`/pms/people/${person.id}`}>{person.name}</Link>
                </p>
              ))}
              <label>
                Completion:{" "}
                {detail.stats.total
                  ? Math.round(
                      (detail.stats.completed / detail.stats.total) * 100,
                    )
                  : 0}
                %
                <progress
                  aria-label="Group completion"
                  value={detail.stats.completed}
                  max={detail.stats.total || 1}
                  style={{
                    display: "block",
                    width: "100%",
                    accentColor: "#7625ff",
                  }}
                />
              </label>
              <div className="pd-overview-stats">
                {[
                  ["Members", detail.members],
                  ["Tasks", detail.stats.total],
                  ["Completed", detail.stats.completed],
                  ["Pending", detail.stats.pending],
                  ["Overdue", detail.stats.overdue],
                ].map(([label, value]) => (
                  <div key={label}>
                    <strong>{value}</strong>
                    <small>{label}</small>
                  </div>
                ))}
              </div>
              <p className="pd-scope-note">{detail.workload_scope}</p>
              <h3>Active projects</h3>
              {detail.projects?.map((project) => (
                <Link
                  className="pd-project-link"
                  key={project.id}
                  to={`/pms/projects/${project.id}`}
                >
                  {project.name}
                  <ChevronRight size={14} />
                </Link>
              ))}
              {!detail.projects?.length && (
                <p className="pd-empty-small">
                  No project workload in your accessible scope.
                </p>
              )}
              <h3>Submissions & review</h3>
              {Object.entries(detail.stats.submissions).map(
                ([status, count]) => (
                  <span className="pd-stat-chip" key={status}>
                    {status}: {count}
                  </span>
                ),
              )}
              {!Object.keys(detail.stats.submissions).length && (
                <p className="pd-empty-small">
                  No submitted work in this scope.
                </p>
              )}
              <p>
                With reviewer: {detail.stats.with_reviewer || 0} · No reviewer:{" "}
                {detail.stats.without_reviewer || 0}
              </p>
              {detail.stats.average_review_score != null && (
                <p>
                  Average review score:{" "}
                  {detail.stats.average_review_score.toFixed(1)}
                </p>
              )}
            </>
          )}
          {tab === "members" && (
            <>
              <input
                aria-label="Search group members"
                placeholder="Name, email, or employee ID…"
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  setPage(1);
                }}
              />
              <div className="pd-selection-summary">
                {selected.length} selected
                <button
                  onClick={() =>
                    setSelected(
                      (detail.items || [])
                        .filter((p) => p.status === "active")
                        .map((p) => p.id),
                    )
                  }
                >
                  Select this page
                </button>
              </div>
              {detail.items?.map((person) => (
                <div className="pd-member-row" key={person.id}>
                  <input
                    type="checkbox"
                    aria-label={`Select member ${person.email}`}
                    disabled={person.status !== "active"}
                    checked={selected.includes(person.id)}
                    onChange={(e) =>
                      setSelected((ids) =>
                        e.target.checked
                          ? [...ids, person.id]
                          : ids.filter((id) => id !== person.id),
                      )
                    }
                  />
                  <DirectoryAvatar person={person} size="small" />
                  <Link to={`/pms/people/${person.id}`}>
                    <strong>{person.name}</strong>
                    <small>{person.email}</small>
                  </Link>
                  <span className="pd-status">{person.status}</span>
                </div>
              ))}
              {!!selected.length && (
                <div className="pd-detail-actions">
                  <button
                    className="pd-primary"
                    onClick={() =>
                      navigate(directoryTaskHref("people", selected))
                    }
                  >
                    Assign selected people
                  </button>
                  {opened?.kind === "teams" && detail.group.can_manage && (
                    <button
                      className="pd-button"
                      disabled={busy}
                      onClick={async () => {
                        if (
                          !window.confirm(
                            `Remove ${selected.length} selected people from this team? Workspace and project access stays unchanged.`,
                          )
                        )
                          return;
                        setBusy(true);
                        try {
                          await api.post(
                            `${directoryRoot}/teams/${opened.id}/members`,
                            {
                              user_ids: selected,
                              action: "remove",
                              reason: "Remove selected team members",
                            },
                          );
                          setSelected([]);
                          await qc.invalidateQueries({
                            queryKey: ["people-workspace"],
                          });
                        } catch (e) {
                          setError(workspaceError(e));
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      Remove from team
                    </button>
                  )}
                </div>
              )}
            </>
          )}
          {tab === "tasks" &&
            detail.items?.map((task) => (
              <Link
                className="pd-task-row"
                key={task.id}
                to={`/pms/tasks/${task.id}`}
              >
                <ClipboardList size={16} />
                <span>
                  <strong>{task.title}</strong>
                  <small>
                    {task.task_key} · {task.status} ·{" "}
                    {task.due_date || "No due date"}
                  </small>
                </span>
                <ChevronRight size={14} />
              </Link>
            ))}
          {tab !== "overview" && (
            <DirectoryPagination
              page={page}
              pages={detail.pages || 1}
              onChange={setPage}
            />
          )}
        </>
      )}
    </PeopleDialog>
  );
}
