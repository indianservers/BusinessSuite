import "../pages/MyWorkPage.css";
import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import {
  Search,
  X,
  Users,
  GraduationCap,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { api } from "@/services/api";
import { workspaceError } from "../pages/workspaceTypes";

export type AssignmentPerson = {
  id: number;
  name: string;
  email?: string;
  role?: string;
  availability?: string;
  photo_url?: string | null;
};
export type AssignmentGroup = {
  id: number;
  name: string;
  kind?: string;
  member_ids?: number[];
  member_count?: number;
  excluded_count?: number;
  code?: string;
  start_date?: string;
  end_date?: string;
  status?: string;
};
type TaskRef = { id: number; project_id: number; title: string };
type Detail = {
  version: string;
  can_edit: boolean;
  task: { assignee_user_ids: number[] };
  protected_ids: number[];
  group_targets: AssignmentGroup[];
};
const root = "/project-management";
export function AssignmentAvatar({ person }: { person: AssignmentPerson }) {
  const [failed, setFailed] = useState(false);
  return person.photo_url && !failed ? (
    <img
      className="mw-avatar"
      src={person.photo_url}
      alt={person.name}
      onError={() => setFailed(true)}
    />
  ) : (
    <span className="mw-avatar" title={person.name}>
      {person.name
        .split(/\s+/)
        .slice(0, 2)
        .map((n) => n[0])
        .join("")
        .toUpperCase()}
    </span>
  );
}

export function PeopleSelector({
  projectId,
  value,
  onChange,
  protectedIds = [],
  groupKind,
  groupId,
}: {
  groupKind?: string;
  groupId?: number;
  projectId: number;
  value: number[];
  onChange: (ids: number[]) => void;
  protectedIds?: number[];
}) {
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{
    items: AssignmentPerson[];
    roles: string[];
    pages: number;
    total: number;
  }>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      setLoading(true);
      api
        .get(`${root}/task-studio/people`, {
          params: {
            project_id: projectId,
            group_kind: groupKind,
            group_id: groupId,
            q,
            role,
            page,
          },
        })
        .then((r) => {
          if (active) {
            setData(r.data);
            setError("");
          }
        })
        .catch((e) => {
          if (active) setError(workspaceError(e));
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }, 250);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [projectId, q, page, groupKind, groupId, role]);
  return (
    <>
      <label className="mw-search">
        <Search size={16} />
        <input
          aria-label="Search people"
          placeholder="Search name or email…"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
        />
      </label>
      <select
        className="mw-person-role"
        aria-label="Filter people by role"
        value={role}
        onChange={(e) => {
          setRole(e.target.value);
          setPage(1);
        }}
      >
        <option value="">All roles</option>
        {data?.roles?.map((r) => (
          <option key={r} value={r}>
            {r === "superuser" ? "Super Admin" : r}
          </option>
        ))}
      </select>
      {error && <p role="alert">{error}</p>}
      {loading && (
        <p role="status" className="mw-muted">
          Loading people…
        </p>
      )}
      <div className="mw-picker-list">
        {data?.items.map((p) => (
          <label className="mw-person" key={p.id}>
            <input
              type="checkbox"
              checked={value.includes(p.id)}
              disabled={protectedIds.includes(p.id)}
              onChange={(e) =>
                onChange(
                  e.target.checked
                    ? [...new Set([...value, p.id])]
                    : value.filter((id) => id !== p.id),
                )
              }
            />
            <AssignmentAvatar person={p} />
            <span>
              <strong>{p.name}</strong>
              <small>
                {p.role || p.email}
                {protectedIds.includes(p.id) ? " · Batch managed" : ""}
              </small>
            </span>
            {p.availability && (
              <small
                className="mw-availability"
                data-availability={p.availability}
              >
                {p.availability}
              </small>
            )}
          </label>
        ))}
        {data && !data.items.length && (
          <p className="mw-empty">No eligible people match your search.</p>
        )}
      </div>
      {!!data && data.pages > 1 && (
        <div className="mw-pager">
          <button
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            aria-label="Previous people"
          >
            <ChevronLeft size={16} />
          </button>
          <span>
            {page} / {data.pages} · {data.total} people
          </span>
          <button
            disabled={page >= data.pages}
            onClick={() => setPage((p) => p + 1)}
            aria-label="Next people"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      )}
    </>
  );
}

export function GroupSelector({
  groups,
  value,
  onChange,
  people,
  onPeopleChange,
  label,
  projectId,
  groupKind,
}: {
  projectId: number;
  groupKind: string;
  groups: AssignmentGroup[];
  value: number[];
  onChange: (ids: number[]) => void;
  people: number[];
  onPeopleChange: (ids: number[]) => void;
  label: string;
}) {
  const [q, setQ] = useState("");
  return (
    <>
      <label className="mw-search">
        <Search size={16} />
        <input
          aria-label={`Search ${label}`}
          placeholder={`Search ${label.toLowerCase()}…`}
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </label>
      <p className="mw-muted">
        Assign group responsibility, or explicitly select members. Membership
        changes do not add individual assignees.
      </p>
      <div className="mw-picker-list">
        {groups
          .filter((g) => g.name.toLowerCase().includes(q.toLowerCase()))
          .map((g) => (
            <div className="mw-group" key={g.id}>
              <label className="mw-person">
                <input
                  type="checkbox"
                  checked={value.includes(g.id)}
                  onChange={(e) =>
                    onChange(
                      e.target.checked
                        ? [...value, g.id]
                        : value.filter((id) => id !== g.id),
                    )
                  }
                />
                <Users size={20} />
                <span>
                  <strong>{g.name}</strong>
                  <small>
                    {g.member_count ?? g.member_ids?.length ?? 0} eligible
                    members
                    {g.excluded_count ? ` · ${g.excluded_count} excluded` : ""}
                  </small>
                  {g.code && (
                    <small>
                      {g.code} · {g.status} · {g.start_date} – {g.end_date}
                    </small>
                  )}
                </span>
              </label>
              <details>
                <summary>Select individual members</summary>
                <PeopleSelector
                  projectId={projectId}
                  groupKind={groupKind}
                  groupId={g.id}
                  value={people}
                  onChange={onPeopleChange}
                />
              </details>
            </div>
          ))}
        {!groups.length && (
          <p className="mw-empty">
            No accessible {label.toLowerCase()} in this project.
          </p>
        )}
      </div>
    </>
  );
}

export default function TaskAssignmentPanel({
  tasks,
  onClose,
  onSaved,
}: {
  tasks: TaskRef[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const task = tasks[0];
  const [tab, setTab] = useState("People");
  const [details, setDetails] = useState<Detail[]>([]);
  const [options, setOptions] = useState<{
    teams: AssignmentGroup[];
    batches: AssignmentGroup[];
    people: AssignmentPerson[];
    batch_reason: string;
  }>();
  const [people, setPeople] = useState<number[]>([]);
  const [teams, setTeams] = useState<number[]>([]);
  const [batches, setBatches] = useState<number[]>([]);
  const [note, setNote] = useState("");
  const [notify, setNotify] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [outcome, setOutcome] = useState("");
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    let active = true;
    Promise.all([
      Promise.all(
        tasks.map((t) =>
          api
            .get<Detail>(`${root}/my-work/tasks/${t.id}/assignment`)
            .then((r) => r.data),
        ),
      ),
      api.get(`${root}/task-studio/options`, {
        params: { project_id: task.project_id, compact: true },
      }),
    ])
      .then(([ds, opts]) => {
        if (!active) return;
        setDetails(ds);
        setOptions(opts.data);
        setPeople(ds.length === 1 ? ds[0].task.assignee_user_ids : []);
        setTeams(
          ds.length === 1
            ? ds[0].group_targets
                .filter((g) => g.kind === "teams")
                .map((g) => g.id)
            : [],
        );
        setBatches(
          ds.length === 1
            ? ds[0].group_targets
                .filter((g) => g.kind === "batches")
                .map((g) => g.id)
            : [],
        );
        setLoaded(true);
      })
      .catch((e) => {
        if (active) setError(workspaceError(e));
      });
    return () => {
      active = false;
    };
  }, [tasks]);
  const protectedIds = [...new Set(details.flatMap((d) => d.protected_ids))];
  async function save() {
    setBusy(true);
    setError("");
    const failures: string[] = [];
    let succeeded = 0;
    for (let i = 0; i < tasks.length; i++) {
      try {
        await api.put(`${root}/my-work/tasks/${tasks[i].id}/assignment`, {
          people: [...new Set([...people, ...details[i].protected_ids])],
          teams,
          batches,
          note,
          notify,
          version: details[i].version,
        });
        succeeded++;
      } catch (e) {
        failures.push(`${tasks[i].title}: ${workspaceError(e)}`);
      }
    }
    setBusy(false);
    onSaved();
    if (failures.length) {
      setOutcome(
        `${succeeded} saved, ${failures.length} failed. Reopen the panel before retrying.`,
      );
      setError(failures.join("\n"));
      setLoaded(false);
    } else onClose();
  }
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open && !busy) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="mw-overlay" />
        <Dialog.Content
          className="mw-assignment"
          aria-describedby="mw-assignment-description"
        >
          <header>
            <Dialog.Title>Assign Task</Dialog.Title>
            <Dialog.Close disabled={busy} aria-label="Close assignment">
              <X size={20} />
            </Dialog.Close>
          </header>
          <Dialog.Description id="mw-assignment-description">
            {tasks.length === 1
              ? task.title
              : `Replace assignments on ${tasks.length} selected tasks. Options are for the first project; each task is checked separately when saving.`}
          </Dialog.Description>
          <div className="mw-assignment-body">
            <div
              className="mw-tabs"
              role="tablist"
              aria-label="Assignment types"
            >
              {["People", "Teams", "Intern Batches"].map((t) => (
                <button
                  key={t}
                  role="tab"
                  aria-selected={tab === t}
                  onClick={() => setTab(t)}
                >
                  {t === "Intern Batches" && <GraduationCap size={14} />}
                  {t}
                </button>
              ))}
            </div>
            {!options && !error && (
              <p role="status">Loading assignment options…</p>
            )}
            {error && (
              <p role="alert" className="mw-error">
                {error}
              </p>
            )}
            {outcome && <p role="status">{outcome}</p>}
            {options && (
              <fieldset disabled={busy || !loaded}>
                {tab === "People" ? (
                  <PeopleSelector
                    projectId={task.project_id}
                    value={people}
                    onChange={setPeople}
                    protectedIds={protectedIds}
                  />
                ) : (
                  <GroupSelector
                    key={tab}
                    projectId={task.project_id}
                    groupKind={tab === "Teams" ? "teams" : "batches"}
                    label={tab}
                    groups={tab === "Teams" ? options.teams : options.batches}
                    value={tab === "Teams" ? teams : batches}
                    onChange={tab === "Teams" ? setTeams : setBatches}
                    people={people}
                    onPeopleChange={setPeople}
                  />
                )}
                {tab === "Intern Batches" && !options.batches.length && (
                  <p className="mw-muted">{options.batch_reason}</p>
                )}
              </fieldset>
            )}
          </div>
          <footer>
            <strong>
              Selected: {people.length} people · {teams.length} teams ·{" "}
              {batches.length} batches
            </strong>
            <div className="mw-chips">
              {people.map((id) => (
                <button
                  key={`p${id}`}
                  disabled={busy || protectedIds.includes(id)}
                  onClick={() => setPeople((p) => p.filter((i) => i !== id))}
                >
                  {options?.people.find((p) => p.id === id)?.name ||
                    `Person #${id}`}{" "}
                  <X size={12} />
                </button>
              ))}
              {[
                ...teams.map((id) => ({
                  id,
                  kind: "team",
                  name: options?.teams.find((g) => g.id === id)?.name,
                })),
                ...batches.map((id) => ({
                  id,
                  kind: "batch",
                  name: options?.batches.find((g) => g.id === id)?.name,
                })),
              ].map((g) => (
                <button
                  key={g.kind + g.id}
                  disabled={busy}
                  onClick={() =>
                    g.kind === "team"
                      ? setTeams((v) => v.filter((id) => id !== g.id))
                      : setBatches((v) => v.filter((id) => id !== g.id))
                  }
                >
                  {g.name}
                  <X size={12} />
                </button>
              ))}
            </div>
            <label>
              <input
                type="checkbox"
                checked={notify}
                disabled={busy}
                onChange={(e) => setNotify(e.target.checked)}
              />{" "}
              Notify individual assignees
            </label>
            <label>
              Assignment note
              <textarea
                maxLength={2000}
                value={note}
                disabled={busy}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Add a short note…"
              />
            </label>
            <div className="mw-actions">
              <button disabled={busy} onClick={onClose}>
                Cancel
              </button>
              <button
                className="mw-primary"
                disabled={busy || !loaded || details.some((d) => !d.can_edit)}
                onClick={() => void save()}
              >
                {busy ? "Saving…" : "Assign Task"}
              </button>
            </div>
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
