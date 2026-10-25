import React, { useEffect, useState } from "react";
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  GripVertical,
  CalendarClock,
  MessageSquare,
  ArrowRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Bootstrap, Lead, leadsApi, errorMessage } from "./api";

export function localDate(value: Date) {
  return new Date(value.getTime() - value.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}
export function followUpDate(bucket: string) {
  const date = new Date();
  if (bucket === "today") date.setHours(date.getHours() + 1, 0, 0, 0);
  else {
    date.setDate(date.getDate() + (bucket === "tomorrow" ? 1 : 7));
    date.setHours(10, 0, 0, 0);
  }
  return localDate(date);
}
function dueBucket(lead: Lead) {
  if (!lead.next_follow_up_at) return "unscheduled";
  const due = new Date(lead.next_follow_up_at);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const after = new Date(tomorrow);
  after.setDate(after.getDate() + 1);
  if (due.getTime() < Date.now()) return "overdue";
  if (due < tomorrow) return "today";
  if (due < after) return "tomorrow";
  return "later";
}
type BoardProps = {
  group: string;
  groupChanged: (value: string) => void;
  leads: Lead[];
  bootstrap: Bootstrap;
  busy: boolean;
  open: (id: number) => void;
  move: (lead: Lead, values: Record<string, unknown>) => void;
  schedule: (lead: Lead, date?: string) => void;
};
function Lane({
  id,
  title,
  count,
  value,
  disabled,
  children,
}: {
  id: string;
  title: string;
  count: number;
  value: number;
  disabled: boolean;
  children: React.ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({ id, disabled });
  return (
    <section
      ref={setNodeRef}
      className={`lm-lane ${isOver ? "lm-lane-over" : ""}`}
      aria-label={`${title} lane`}
      data-lane={id}
    >
      <h2>
        <strong>{title}</strong>
        <span>{count}</span>
      </h2>
      <p className="lm-lane-value">Pipeline value {value.toLocaleString()}</p>
      {children}
      {!count && (
        <p className="lm-drop-hint">
          {disabled ? "No leads" : "Drop a lead here"}
        </p>
      )}
    </section>
  );
}
function LeadCard({
  lead,
  owner,
  canMove,
  busy,
  open,
  schedule,
  options,
  choose,
}: {
  lead: Lead;
  owner: string;
  canMove: boolean;
  busy: boolean;
  open: () => void;
  schedule: () => void;
  options: { id: string; title: string }[];
  choose: (id: string) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({ id: lead.id, disabled: !canMove || busy });
  return (
    <article
      ref={setNodeRef}
      className={`lm-lead-card lm-work-card ${isDragging ? "lm-dragging" : ""}`}
      style={{
        transform: transform
          ? `translate3d(${transform.x}px,${transform.y}px,0)`
          : undefined,
      }}
      data-lead={lead.id}
    >
      <div className="lm-card-heading">
        <button className="lm-name" onClick={open}>
          {lead.full_name}
        </button>
        {canMove && (
          <button
            className="lm-drag-handle"
            aria-label={`Drag ${lead.full_name}`}
            disabled={busy}
            {...attributes}
            {...listeners}
          >
            <GripVertical size={18} />
          </button>
        )}
      </div>
      <span>{lead.company_name || lead.email || "Contact details needed"}</span>
      <span className="lm-card-owner">{owner}</span>
      <span className="lm-stage">
        {lead.status} · Score {lead.lead_score || 0}
      </span>
      <span className={lead.signals.overdue ? "lm-danger-text" : ""}>
        {lead.signals.followUpLabel}
      </span>
      {lead.next_follow_up_at && (
        <time>{new Date(lead.next_follow_up_at).toLocaleString()}</time>
      )}
      <small>{lead.signals.nextAction}</small>
      <div className="lm-card-actions">
        <Button size="sm" variant="outline" onClick={open}>
          Open <ArrowRight size={12} />
        </Button>
        {canMove && (
          <Button
            size="sm"
            variant="outline"
            disabled={busy || !lead.signals.active}
            onClick={schedule}
          >
            <CalendarClock size={13} />
            Follow up
          </Button>
        )}
      </div>
      {canMove && (
        <select
          aria-label={`Move ${lead.full_name}`}
          value=""
          disabled={busy}
          onChange={(e) => choose(e.target.value)}
        >
          <option value="">Move to…</option>
          {options.map((o) => (
            <option value={o.id} key={o.id}>
              {o.title}
            </option>
          ))}
        </select>
      )}
    </article>
  );
}
export function LeadWorkflowBoard({
  group: mode,
  groupChanged: setMode,
  leads,
  bootstrap,
  busy,
  open,
  move,
  schedule,
}: BoardProps) {
  const [dragged, setDragged] = useState<Lead>();
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, {
      activationConstraint: { delay: 250, tolerance: 8 },
    }),
    useSensor(KeyboardSensor),
  );
  const canMove = bootstrap.canManage;
  const lanes =
    mode === "stage"
      ? bootstrap.settings.stages.map((s) => ({ id: s.name, title: s.name }))
      : mode === "owner"
        ? [
            { id: "unassigned", title: "Unassigned" },
            ...bootstrap.owners.map((o) => ({
              id: String(o.id),
              title: o.name,
            })),
            ...Array.from(
              new Set(
                leads
                  .map((l) => l.owner_user_id)
                  .filter(
                    (id) => id && !bootstrap.owners.some((o) => o.id === id),
                  ),
              ),
            ).map((id) => ({
              id: String(id),
              title: `Unavailable assignee (${id})`,
            })),
          ]
        : [
            { id: "overdue", title: "Overdue" },
            { id: "today", title: "Today" },
            { id: "tomorrow", title: "Tomorrow" },
            { id: "later", title: "Later" },
            { id: "unscheduled", title: "No follow-up" },
          ];
  const key = (lead: Lead) =>
    mode === "stage"
      ? lead.status
      : mode === "owner"
        ? String(lead.owner_user_id || "unassigned")
        : dueBucket(lead);
  const options = (lead: Lead) =>
    lanes.filter((l) =>
      mode === "stage"
        ? l.id !== "Converted" &&
          !!bootstrap.settings.stages
            .find((s) => s.name === lead.status)
            ?.allowedNext.includes(l.id)
        : mode === "owner"
          ? (bootstrap.canAssign ?? bootstrap.canAdmin) &&
            l.id !== "unassigned" &&
            bootstrap.owners.some((o) => String(o.id) === l.id) &&
            l.id !== key(lead)
          : !["overdue", "unscheduled"].includes(l.id) && lead.signals.active,
    );
  const choose = (lead: Lead, lane: string) => {
    if (!options(lead).some((o) => o.id === lane) || busy) return;
    if (mode === "stage") move(lead, { status: lane });
    else if (mode === "owner") move(lead, { owner_user_id: Number(lane) });
    else schedule(lead, followUpDate(lane));
  };
  const end = ({ active, over }: DragEndEvent) => {
    const lead = leads.find((l) => l.id === active.id);
    setDragged(undefined);
    if (lead && over) choose(lead, String(over.id));
  };
  return (
    <div className="lm-workflow">
      <div className="lm-board-toolbar">
        <label>
          Group board by{" "}
          <select
            aria-label="Group board by"
            value={mode}
            onChange={(e) => setMode(e.target.value)}
          >
            <option value="stage">Current status</option>
            <option value="owner">Team member</option>
            <option value="follow">Follow-up date</option>
          </select>
        </label>
        <p>
          {canMove
            ? "Drag the grip to move a lead, or use Move to. Follow-up drops open the scheduler. Required stage fields still apply."
            : "Read-only pipeline"}
        </p>
      </div>
      <DndContext
        sensors={sensors}
        onDragStart={(e) => setDragged(leads.find((l) => l.id === e.active.id))}
        onDragCancel={() => setDragged(undefined)}
        onDragEnd={end}
        accessibility={{
          screenReaderInstructions: {
            draggable:
              "Press Space to pick up a lead. Use arrow keys to move, Space to drop, or Escape to cancel. You can also use the Move to menu.",
          },
        }}
      >
        <div className="lm-board">
          {lanes.map((lane) => {
            const items = leads.filter((l) => key(l) === lane.id);
            return (
              <Lane
                key={lane.id}
                {...lane}
                count={items.length}
                value={items.reduce(
                  (sum, l) => sum + Number(l.estimated_value || 0),
                  0,
                )}
                disabled={
                  !canMove ||
                  busy ||
                  (!!dragged && !options(dragged).some((o) => o.id === lane.id))
                }
              >
                {items.map((lead) => (
                  <LeadCard
                    key={lead.id}
                    lead={lead}
                    owner={
                      bootstrap.owners.find((o) => o.id === lead.owner_user_id)
                        ?.name || "Unassigned / unavailable"
                    }
                    canMove={
                      canMove && !lead.is_converted && !lead.details.archived
                    }
                    busy={busy}
                    open={() => open(lead.id)}
                    schedule={() => schedule(lead)}
                    options={options(lead)}
                    choose={(id) => choose(lead, id)}
                  />
                ))}
              </Lane>
            );
          })}
        </div>
        <DragOverlay>
          {dragged && (
            <div className="lm-lead-card lm-drag-preview">
              <strong>{dragged.full_name}</strong>
              <span>{dragged.status}</span>
            </div>
          )}
        </DragOverlay>
      </DndContext>
    </div>
  );
}

export function FollowUpDialog({
  lead,
  bootstrap,
  initialDate,
  close,
  saved,
}: {
  lead: Lead;
  bootstrap: Bootstrap;
  initialDate?: string;
  close: () => void;
  saved: () => void;
}) {
  const [title, setTitle] = useState("Follow up with " + lead.full_name);
  const canAssign = bootstrap.canAssign ?? bootstrap.canAdmin;
  const [due, setDue] = useState(initialDate || followUpDate("tomorrow"));
  const [type, setType] = useState("call");
  const [owner, setOwner] = useState(
    String(
      canAssign ? lead.owner_user_id || bootstrap.userId : bootstrap.userId,
    ),
  );
  const [detail, setDetail] = useState<Lead>();
  const [activityId, setActivityId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    leadsApi
      .detail(lead.id)
      .then((r) => {
        if (!active) return;
        setDetail(r.data);
        const pending = r.data.activities
          ?.filter((a) => a.status === "Pending" && a.due_date)
          .sort((a, b) => Date.parse(a.due_date!) - Date.parse(b.due_date!))[0];
        if (pending) {
          setActivityId(String(pending.id));
          setTitle(pending.subject);
          setType(
            ["call", "email", "meeting", "task"].includes(pending.activity_type)
              ? pending.activity_type
              : "task",
          );
          setOwner(
            String(
              canAssign
                ? pending.owner_user_id ||
                    r.data.owner_user_id ||
                    bootstrap.userId
                : bootstrap.userId,
            ),
          );
          if (
            !initialDate &&
            pending.due_date &&
            Date.parse(pending.due_date) > Date.now()
          )
            setDue(localDate(new Date(pending.due_date)));
        }
      })
      .catch((e) => active && setError(errorMessage(e)));
    return () => {
      active = false;
    };
  }, [lead.id]);
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !busy) close();
      }}
    >
      <DialogContent className="lm-root lm-dialog">
        <DialogTitle>Schedule follow-up · {lead.full_name}</DialogTitle>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            if (!detail) return;
            setBusy(true);
            setError("");
            try {
              await leadsApi.followUp(lead.id, {
                title,
                dueAt: new Date(due).toISOString(),
                type,
                ownerId: Number(owner),
                activityId: activityId ? Number(activityId) : undefined,
                version: detail.version,
              });
              saved();
              close();
            } catch (e) {
              setError(errorMessage(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          {error && (
            <div role="alert" className="lm-error">
              {error}
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={busy}
                onClick={async () => {
                  try {
                    const response = await leadsApi.detail(lead.id);
                    setDetail(response.data);
                    setError("");
                  } catch (e) {
                    setError(errorMessage(e));
                  }
                }}
              >
                Refresh lead, keep draft
              </Button>
            </div>
          )}
          <label className="lm-work-field">
            Follow-up action
            <select
              aria-label="Follow-up action"
              value={activityId}
              onChange={(e) => {
                setActivityId(e.target.value);
                const item = detail?.activities?.find(
                  (a) => String(a.id) === e.target.value,
                );
                if (item) {
                  setTitle(item.subject);
                  setType(
                    ["call", "email", "meeting", "task"].includes(
                      item.activity_type,
                    )
                      ? item.activity_type
                      : "task",
                  );
                  setOwner(
                    String(
                      canAssign
                        ? item.owner_user_id ||
                            lead.owner_user_id ||
                            bootstrap.userId
                        : bootstrap.userId,
                    ),
                  );
                }
              }}
            >
              <option value="">Create a new follow-up</option>
              {detail?.activities
                ?.filter((a) => a.status === "Pending")
                .map((a) => (
                  <option key={a.id} value={a.id}>
                    Reschedule: {a.subject}
                  </option>
                ))}
            </select>
          </label>
          <label className="lm-work-field">
            Next step
            <input
              aria-label="Follow-up title"
              required
              maxLength={180}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <div className="lm-card-actions">
            {["today", "tomorrow", "later"].map((bucket) => (
              <Button
                key={bucket}
                type="button"
                size="sm"
                variant="outline"
                onClick={() => setDue(followUpDate(bucket))}
              >
                {bucket === "later"
                  ? "Next week"
                  : bucket === "today"
                    ? "In one hour"
                    : "Tomorrow"}
              </Button>
            ))}
          </div>
          <label className="lm-work-field">
            Due date and time
            <input
              aria-label="Follow-up due"
              type="datetime-local"
              required
              min={localDate(new Date())}
              value={due}
              onChange={(e) => setDue(e.target.value)}
            />
          </label>
          <label className="lm-work-field">
            Type
            <select
              aria-label="Follow-up type"
              value={type}
              onChange={(e) => setType(e.target.value)}
            >
              {["call", "email", "meeting", "task"].map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </label>
          <label className="lm-work-field">
            Responsible teammate
            <select
              aria-label="Follow-up assignee"
              value={owner}
              disabled={!canAssign}
              onChange={(e) => setOwner(e.target.value)}
            >
              {bootstrap.owners.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </select>
          </label>
          <p className="lm-help">
            Times use your device timezone. Scheduling creates a CRM task;
            meetings are booked in Activities.
          </p>
          <Button type="submit" disabled={busy || !detail || !title.trim()}>
            {busy ? "Saving…" : "Save follow-up"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function LeadTeamPanel({
  lead,
  canManage,
  disabled,
  changed,
  draftChanged,
}: {
  lead: Lead;
  canManage: boolean;
  disabled: boolean;
  changed: () => void;
  draftChanged: (value: boolean) => void;
}) {
  const [members, setMembers] = useState<Bootstrap["owners"]>([]);
  const [body, setBody] = useState("");
  const [mentions, setMentions] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    draftChanged(Boolean(body.trim() || mentions.length));
  }, [body, mentions, draftChanged]);
  useEffect(() => {
    if (body.trim() || mentions.length || busy || disabled) return;
    const timer = window.setInterval(changed, 30000);
    return () => window.clearInterval(timer);
  }, [body, mentions, busy, disabled, changed]);
  useEffect(() => {
    if (!body.trim() && !mentions.length) return;
    const protect = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", protect);
    return () => window.removeEventListener("beforeunload", protect);
  }, [body, mentions]);
  useEffect(() => {
    let active = true;
    leadsApi
      .team(lead.id)
      .then((r) => {
        if (active) setMembers(r.data.members || []);
      })
      .catch((e) => active && setError(errorMessage(e)));
    return () => {
      active = false;
    };
  }, [lead.id, lead.version]);
  return (
    <section className="lm-team-panel">
      <h3>
        <MessageSquare size={18} /> Team collaboration
      </h3>
      <p className="lm-help">
        Keep decisions and handoff context on this lead. Mentions notify
        teammates who already have access. Updates refresh every 30 seconds
        while you have no unsaved draft.
      </p>
      {error && (
        <div role="alert" className="lm-error">
          {error}
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={disabled || busy}
            onClick={changed}
          >
            Refresh lead, keep draft
          </Button>
        </div>
      )}
      <div className="lm-team-members">
        {members.map((m) => (
          <span key={m.id}>
            {m.name}
            {m.id === lead.owner_user_id ? " · Lead owner" : ""}
          </span>
        ))}
      </div>
      {canManage && (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await leadsApi.teamNote(lead.id, body, mentions, lead.version);
              setBody("");
              setMentions([]);
              changed();
            } catch (e) {
              setError(errorMessage(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          <label className="lm-work-field">
            Team update
            <textarea
              aria-label="Team update"
              rows={4}
              required
              maxLength={4000}
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </label>
          <details>
            <summary>Notify teammates ({mentions.length})</summary>
            {members.map((m) => (
              <label className="lm-check" key={m.id}>
                <input
                  type="checkbox"
                  checked={mentions.includes(m.id)}
                  onChange={(e) =>
                    setMentions((current) =>
                      e.target.checked
                        ? [...current, m.id]
                        : current.filter((id) => id !== m.id),
                    )
                  }
                />
                {m.name}
              </label>
            ))}
          </details>
          <Button type="submit" disabled={busy || disabled || !body.trim()}>
            Post team update
          </Button>
        </form>
      )}
      <div className="lm-team-thread">
        {lead.timeline
          ?.filter((e) => e.event_type === "team_note")
          .map((e) => (
            <article key={e.id}>
              <strong>
                {e.metadata_json?.authorName ||
                  members.find((m) => m.id === e.actor_user_id)?.name ||
                  "Team member"}
              </strong>
              <time>{new Date(e.occurred_at).toLocaleString()}</time>
              <p>{e.description}</p>
              {!!e.metadata_json?.mentionIds?.length && (
                <small>
                  Notified:{" "}
                  {e.metadata_json.mentionIds
                    .map(
                      (id) =>
                        members.find((m) => m.id === id)?.name || `User ${id}`,
                    )
                    .join(", ")}
                </small>
              )}
            </article>
          ))}
      </div>
    </section>
  );
}
