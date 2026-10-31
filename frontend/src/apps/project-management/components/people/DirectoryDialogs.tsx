import { useEffect, useState, type ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { X, Search, Plus, ChevronLeft, ChevronRight } from "lucide-react";
import { api } from "@/services/api";
import {
  directoryRoot,
  directoryGet,
  type DirectoryPerson,
  type DirectoryPage,
  type DirectoryReference,
  type GroupPage,
} from "./peopleWorkspace";
import { DirectoryAvatar } from "./DirectoryPersonCard";
import { workspaceError } from "../../pages/workspaceTypes";
export function PeopleDialog({
  open,
  onClose,
  title,
  description,
  children,
  className,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(v) => {
        if (!v) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="pd-dialog-overlay" />
        <Dialog.Content className={`pd-dialog ${className || ""}`}>
          <Dialog.Title>{title}</Dialog.Title>
          <Dialog.Description>{description}</Dialog.Description>
          <Dialog.Close className="pd-dialog-close" aria-label="Close dialog">
            <X size={19} />
          </Dialog.Close>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function DirectoryPagination({
  page,
  pages,
  onChange,
}: {
  page: number;
  pages: number;
  onChange: (page: number) => void;
}) {
  return (
    <div className="pd-pagination">
      <button
        type="button"
        disabled={page <= 1}
        aria-label="Previous page"
        onClick={() => onChange(page - 1)}
      >
        <ChevronLeft size={15} />
      </button>
      <span>
        Page {page} of {Math.max(1, pages)}
      </span>
      <button
        type="button"
        disabled={page >= pages}
        aria-label="Next page"
        onClick={() => onChange(page + 1)}
      >
        <ChevronRight size={15} />
      </button>
    </div>
  );
}
export function TeamEditor({
  open,
  onClose,
  reference,
  initialWorkspace,
  teamId,
}: {
  open: boolean;
  onClose: () => void;
  reference?: DirectoryReference;
  initialWorkspace?: number;
  teamId?: number;
}) {
  const qc = useQueryClient();
  const [wid, setWid] = useState(
    initialWorkspace ||
      reference?.workspaces.find((w) => w.can_manage)?.id ||
      0,
  );
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [alias, setAlias] = useState("");
  const [lead, setLead] = useState("");
  const [visibility, setVisibility] = useState("workspace");
  const [selected, setSelected] = useState<number[]>([]);
  const [known, setKnown] = useState<Record<number, DirectoryPerson>>({});
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!open) return;
    setError("");
    setName("");
    setDescription("");
    setAlias("");
    setLead("");
    setSelected([]);
    setQ("");
    setPage(1);
    setKnown({});
    setWid(
      initialWorkspace ||
        reference?.workspaces.find((w) => w.can_manage)?.id ||
        0,
    );
    if (teamId)
      void directoryGet<{
        group: {
          name: string;
          description: string;
          alias: string;
          lead_user_id?: number;
          visibility: string;
          workspace_id: number;
        };
      }>(`/groups/teams/${teamId}`)
        .then(async ({ group }) => {
          setWid(group.workspace_id);
          setName(group.name);
          setDescription(group.description || "");
          setAlias(group.alias);
          setLead(String(group.lead_user_id || ""));
          setVisibility(group.visibility);
          const { data } = await api.get<{
            teams: { id: number; member_ids: number[] }[];
          }>(`/project-management/workspaces/${group.workspace_id}/teams`);
          setSelected(
            data.teams.find((team) => team.id === teamId)?.member_ids || [],
          );
        })
        .catch((e) => setError(workspaceError(e)));
  }, [open, teamId]);
  const people = useQuery({
    queryKey: ["people-workspace", "team-editor", wid, q, page],
    enabled: open && !!wid,
    queryFn: () =>
      directoryGet<DirectoryPage>(`/workspaces/${wid}/people`, {
        q,
        page,
        page_size: 30,
      }),
  });
  useEffect(() => {
    if (people.data)
      setKnown((old) => ({
        ...old,
        ...Object.fromEntries(
          people.data.items.map((person) => [person.id, person]),
        ),
      }));
  }, [people.data]);
  return (
    <PeopleDialog
      open={open}
      onClose={onClose}
      title={teamId ? "Manage team" : "Create team"}
      description="Organize existing workspace members. Team membership does not grant workspace administration access."
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            const data = {
              name,
              alias,
              description,
              lead_user_id: lead ? Number(lead) : null,
              visibility,
              member_ids: selected,
            };
            if (teamId)
              await api.put(
                `/project-management/workspaces/${wid}/teams/${teamId}`,
                data,
              );
            else
              await api.post(
                `/project-management/workspaces/${wid}/teams`,
                data,
              );
            await qc.invalidateQueries({ queryKey: ["people-workspace"] });
            onClose();
          } catch (e) {
            setError(workspaceError(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        {error && (
          <p role="alert" className="pd-error">
            {error}
          </p>
        )}
        <fieldset disabled={busy}>
          <div className="pd-form-grid">
            <label>
              Workspace
              <select
                required
                disabled={!!teamId}
                value={wid || ""}
                onChange={(e) => {
                  setWid(Number(e.target.value));
                  setSelected([]);
                  setKnown({});
                  setPage(1);
                }}
              >
                <option value="">Select workspace</option>
                {reference?.workspaces
                  .filter((w) => w.can_manage)
                  .map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.name}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Team name
              <input
                aria-label="Team name"
                required
                maxLength={120}
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  if (!teamId)
                    setAlias(
                      e.target.value
                        .toLowerCase()
                        .replace(/[^a-z0-9]+/g, "-")
                        .replace(/^-|-$/g, ""),
                    );
                }}
              />
            </label>
            <label>
              Alias
              <input
                aria-label="Team alias"
                required
                minLength={2}
                maxLength={60}
                pattern="[a-z0-9]+(-[a-z0-9]+)*"
                value={alias}
                onChange={(e) => setAlias(e.target.value)}
              />
            </label>
            <label>
              Visibility
              <select
                aria-label="Team visibility"
                value={visibility}
                onChange={(e) => setVisibility(e.target.value)}
              >
                <option value="workspace">Workspace</option>
                <option value="members">Members and administrators</option>
              </select>
            </label>
          </div>
          <label>
            Description
            <textarea
              aria-label="Team description"
              maxLength={4000}
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </label>
          <label>
            Find members
            <input
              aria-label="Search team members"
              placeholder="Name or email…"
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
            />
          </label>
          <div className="pd-selection-summary">
            {selected.length} selected · {people.data?.total || 0} eligible
            workspace members
            <button
              type="button"
              onClick={() =>
                setSelected((ids) => [
                  ...new Set([
                    ...ids,
                    ...(people.data?.items.map((p) => p.id) || []),
                  ]),
                ])
              }
            >
              Select this page
            </button>
            <button
              type="button"
              onClick={() => {
                setSelected([]);
                setLead("");
              }}
            >
              Clear
            </button>
          </div>
          <div className="pd-people-picker">
            {people.isLoading && (
              <p role="status">Loading eligible workspace members…</p>
            )}
            {people.error && <p role="alert">{workspaceError(people.error)}</p>}
            {people.data?.items.map((person) => (
              <label key={person.id}>
                <input
                  type="checkbox"
                  aria-label={`Team member ${person.email}`}
                  checked={selected.includes(person.id)}
                  onChange={(e) => {
                    setSelected((ids) =>
                      e.target.checked
                        ? [...ids, person.id]
                        : ids.filter((id) => id !== person.id),
                    );
                    if (!e.target.checked && Number(lead) === person.id)
                      setLead("");
                  }}
                />
                <DirectoryAvatar person={person} size="small" />
                <span>
                  <strong>{person.name}</strong>
                  <small>{person.email}</small>
                </span>
              </label>
            ))}
          </div>
          <DirectoryPagination
            page={page}
            pages={people.data?.pages || 1}
            onChange={setPage}
          />
          <label>
            Team lead
            <select
              aria-label="Team lead"
              value={lead}
              onChange={(e) => setLead(e.target.value)}
            >
              <option value="">No lead appointed</option>
              {lead && !selected.some((id) => String(id) === lead) && (
                <option value={lead}>Current lead</option>
              )}
              {selected.map((id) => (
                <option key={id} value={id}>
                  {known[id]?.name || `Member #${id}`}
                </option>
              ))}
            </select>
          </label>
          <div className="pd-dialog-actions">
            <button type="button" className="pd-button" onClick={onClose}>
              Cancel
            </button>
            <button className="pd-primary" disabled={!wid}>
              {busy ? "Saving…" : "Save team"}
            </button>
          </div>
        </fieldset>
      </form>
    </PeopleDialog>
  );
}
export function AddPeopleToTeam({
  open,
  onClose,
  personIds,
  reference,
}: {
  open: boolean;
  onClose: () => void;
  personIds: number[];
  reference?: DirectoryReference;
}) {
  const qc = useQueryClient();
  const [team, setTeam] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [preview, setPreview] = useState<{
    workspace_name: string;
    missing_user_ids: number[];
    selected: number;
    changed: number;
  }>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (open) {
      setTeam("");
      setPreview(undefined);
      setError("");
    }
  }, [open]);
  const groups = useQuery({
    queryKey: ["people-workspace", "choose-team", q, page],
    enabled: open,
    queryFn: () =>
      directoryGet<GroupPage>("/groups", {
        kind: "teams",
        q,
        page,
        page_size: 20,
      }),
  });
  const body = {
    user_ids: personIds,
    action: "add",
    reason: "Add existing people to workspace team",
    add_workspace_members: true,
  };
  return (
    <PeopleDialog
      open={open}
      onClose={onClose}
      title="Add to team"
      description="Select a team. New members automatically receive Member access to its workspace."
    >
      <input
        aria-label="Find destination team"
        placeholder="Search teams…"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setPage(1);
        }}
      />
      <div className="pd-choose-list">
        {groups.data?.items
          .filter((t) => t.can_manage)
          .map((t) => (
            <label key={t.id}>
              <input
                type="radio"
                name="destination-team"
                aria-label={`Choose ${t.name}`}
                value={t.id}
                checked={team === String(t.id)}
                onChange={() => {
                  setTeam(String(t.id));
                  setPreview(undefined);
                }}
              />
              <strong>{t.name}</strong>
              <small>
                {t.members} members ·{" "}
                {
                  reference?.workspaces.find((w) => w.id === t.workspace_id)
                    ?.name
                }
              </small>
            </label>
          ))}
        {groups.data && !groups.data.items.some((t) => t.can_manage) && (
          <p>
            No manageable teams in this view. Create a team or ask a workspace
            administrator.
          </p>
        )}
      </div>
      <DirectoryPagination
        page={page}
        pages={groups.data?.pages || 1}
        onChange={setPage}
      />
      {error && (
        <p role="alert" className="pd-error">
          {error}
        </p>
      )}
      {preview && (
        <div className="pd-operation-preview">
          <strong>{preview.workspace_name}</strong>
          <p>
            {preview.selected} people selected · {preview.changed} new team
            memberships.
          </p>
          {preview.missing_user_ids.length > 0 && (
            <p>
              {preview.missing_user_ids.length} people will automatically join
              this workspace as Members.
            </p>
          )}
        </div>
      )}
      <div className="pd-dialog-actions">
        <button className="pd-button" onClick={onClose}>
          Cancel
        </button>
        <button
          className="pd-primary"
          disabled={!team || busy}
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              if (!preview)
                setPreview(
                  (
                    await api.post(
                      `${directoryRoot}/teams/${team}/members/preview`,
                      body,
                    )
                  ).data,
                );
              else {
                await api.post(`${directoryRoot}/teams/${team}/members`, body);
                await qc.invalidateQueries({ queryKey: ["people-workspace"] });
                onClose();
              }
            } catch (e) {
              setError(workspaceError(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy
            ? "Working…"
            : preview
              ? "Add selected people"
              : "Preview changes"}
        </button>
      </div>
    </PeopleDialog>
  );
}
