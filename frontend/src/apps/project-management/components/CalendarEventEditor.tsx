import { RichTextField, RichTextContent, richTextPlainText } from "@/components/rich-text/LazyRichText";
import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { workspaceError } from "../pages/workspaceTypes";
import {
  localToUTC,
  zonedInput,
  saveCalendarFile,
  type CalendarEvent,
  type CalendarPrefs,
} from "../pages/calendarTypes";
export default function CalendarEventEditor({
  open,
  event,
  day,
  taskId,
  tasks,
  prefs,
  onClose,
  onSaved,
}: {
  open: boolean;
  event: CalendarEvent | null;
  day: string;
  taskId?: number;
  tasks: { id: number; title: string }[];
  prefs: CalendarPrefs;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [draft, setDraft] = useState({
    title: "",
    description: "",
    start: "",
    end: "",
    kind: "meeting",
    visibility: "private",
    workspace_id: "",
    task_id: "",
    meeting_url: "",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [slots, setSlots] = useState<{ start_at: string; end_at: string }[]>(
    [],
  );
  const spaces = useQuery<{ id: number; name: string; role: string }[]>({
    queryKey: ["calendar-event-workspaces"],
    queryFn: () =>
      api.get("/project-management/workspaces").then((r) => r.data),
    enabled: open,
  });
  const readonly = !!event && !event.can_edit;
  useEffect(() => {
    if (!open) return;
    setError("");
    setSlots([]);
    const base = event?.start_at || localToUTC(day + "T09:00", prefs.timezone);
    const end =
      event?.end_at ||
      new Date(Date.parse(base) + prefs.duration * 60000).toISOString();
    const task = tasks.find((t) => t.id === taskId);
    setDraft({
      title:
        event?.title || (task ? `${prefs.prefix} ${task.title}`.trim() : ""),
      description: event?.description || "",
      start: zonedInput(base, prefs.timezone),
      end: zonedInput(end, prefs.timezone),
      kind: event?.kind || (task ? "focus" : "meeting"),
      visibility:
        event?.visibility || (task ? prefs.focus_visibility : "private"),
      workspace_id: event?.workspace_id ? String(event.workspace_id) : "",
      task_id: String(event?.task_id || taskId || ""),
      meeting_url: event?.meeting_url || "",
    });
  }, [open, event, day, taskId, prefs.timezone, prefs.duration]);
  async function save() {
    if (busy || readonly) return;
    setBusy(true);
    setError("");
    try {
      const data = {
        title: draft.title,
        description: draft.description,
        start_at: localToUTC(draft.start, prefs.timezone),
        end_at: localToUTC(draft.end, prefs.timezone),
        timezone: prefs.timezone,
        kind: draft.kind,
        visibility: draft.visibility,
        workspace_id: Number(draft.workspace_id) || null,
        task_id: Number(draft.task_id) || null,
        meeting_url: draft.meeting_url,
      };
      if (event)
        await api.put(`/project-management/planner/events/${event.id}`, {
          ...data,
          revision: event.revision,
        });
      else await api.post("/project-management/planner/events", data);
      onSaved();
      onClose();
    } catch (e) {
      setError(
        e instanceof Error && !("response" in e)
          ? e.message
          : workspaceError(e),
      );
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    if (!event || readonly || !window.confirm("Delete this calendar event?"))
      return;
    setBusy(true);
    setError("");
    try {
      await api.delete(`/project-management/planner/events/${event.id}`, {
        params: { revision: event.revision },
      });
      onSaved();
      onClose();
    } catch (e) {
      setError(workspaceError(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(v) => {
        if (!v && !busy) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="cal-settings-overlay" />
        <Dialog.Content className="cal-event-dialog">
          <Dialog.Title>
            {event ? "Calendar event" : "Create meeting or focus block"}
          </Dialog.Title>
          <Dialog.Description>
            Times shown in {prefs.timezone}.{" "}
            {readonly
              ? "This shared event can only be edited by its owner."
              : "Private unless you choose workspace visibility."}
          </Dialog.Description>
          <button
            className="cal-event-close"
            aria-label="Close calendar event"
            disabled={busy}
            onClick={onClose}
          >
            ×
          </button>
          {error && (
            <p role="alert" className="cal-settings-error">
              {error}
            </p>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void save();
            }}
          >
            <fieldset disabled={busy || readonly}>
              <label>
                Title
                <input
                  aria-label="Event title"
                  required
                  maxLength={220}
                  value={draft.title}
                  onChange={(e) =>
                    setDraft({ ...draft, title: e.target.value })
                  }
                />
              </label>
              <div className="cal-event-grid">
                <label>
                  Type
                  <select
                    value={draft.kind}
                    onChange={(e) =>
                      setDraft({ ...draft, kind: e.target.value })
                    }
                  >
                    <option value="meeting">Meeting</option>
                    <option value="focus">Focus time</option>
                  </select>
                </label>
                <label>
                  Visibility
                  <select
                    value={draft.visibility}
                    onChange={(e) =>
                      setDraft({ ...draft, visibility: e.target.value })
                    }
                  >
                    <option value="private">Private</option>
                    <option value="workspace">Workspace</option>
                  </select>
                </label>
              </div>
              {draft.visibility === "workspace" && (
                <label>
                  Workspace
                  <select
                    required
                    value={draft.workspace_id}
                    onChange={(e) =>
                      setDraft({ ...draft, workspace_id: e.target.value })
                    }
                  >
                    <option value="">Choose workspace</option>
                    {spaces.data
                      ?.filter((w) => w.role !== "Guest")
                      .map((w) => (
                        <option key={w.id} value={w.id}>
                          {w.name}
                        </option>
                      ))}
                  </select>
                </label>
              )}
              <div className="cal-event-grid">
                <label>
                  Start
                  <input
                    aria-label="Event start"
                    type="datetime-local"
                    required
                    value={draft.start}
                    onChange={(e) =>
                      setDraft({ ...draft, start: e.target.value })
                    }
                  />
                </label>
                <label>
                  End
                  <input
                    aria-label="Event end"
                    type="datetime-local"
                    required
                    value={draft.end}
                    onChange={(e) =>
                      setDraft({ ...draft, end: e.target.value })
                    }
                  />
                </label>
              </div>
              <label>
                Link task
                <select
                  value={draft.task_id}
                  onChange={(e) => {
                    const t = tasks.find(
                      (t) => t.id === Number(e.target.value),
                    );
                    setDraft({
                      ...draft,
                      task_id: e.target.value,
                      title:
                        draft.kind === "focus" && t
                          ? `${prefs.prefix} ${t.title}`.trim()
                          : draft.title,
                    });
                  }}
                >
                  <option value="">No linked task</option>
                  {tasks.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.title}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Meeting URL
                <input
                  type="url"
                  placeholder="https://…"
                  value={draft.meeting_url}
                  onChange={(e) =>
                    setDraft({ ...draft, meeting_url: e.target.value })
                  }
                />
              </label>
              <label>
                Description
                <RichTextField data-legacy-format="markdown"
                  maxLength={10000}
                  rows={3}
                  value={draft.description}
                  onChange={(e) =>
                    setDraft({ ...draft, description: e.target.value })
                  }
                />
              </label>
              <button
                type="button"
                onClick={() =>
                  void (async () => {
                    setError("");
                    try {
                      const r = await api.get(
                        "/project-management/planner/free-slots",
                        {
                          params: {
                            day: draft.start.slice(0, 10),
                            minutes: prefs.duration,
                          timezone: prefs.timezone,
                          },
                        },
                      );
                      setSlots(r.data);
                      if (!r.data.length)
                        setError(
                          "No free slots in your work schedule for this date.",
                        );
                    } catch (e) {
                      setError(workspaceError(e));
                    }
                  })()
                }
              >
                Find free time
              </button>
              {slots.length > 0 && (
                <div className="cal-free-slots">
                  {slots.map((s) => (
                    <button
                      type="button"
                      key={s.start_at}
                      onClick={() =>
                        setDraft({
                          ...draft,
                          start: zonedInput(s.start_at, prefs.timezone),
                          end: zonedInput(s.end_at, prefs.timezone),
                        })
                      }
                    >
                      {new Date(s.start_at).toLocaleTimeString([], {
                        timeZone: prefs.timezone,
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </button>
                  ))}
                </div>
              )}
            </fieldset>
            <footer>
              {event?.can_edit && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void remove()}
                >
                  Delete
                </button>
              )}
              <button
                type="button"
                onClick={() =>
                  saveCalendarFile(
                    `${prefs.notes_name}\n${draft.title}\n${draft.start} (${prefs.timezone})\n\n${prefs.notes_template}`,
                    "meeting-notes.txt",
                    "text/plain",
                  )
                }
              >
                Notes template
              </button>
              {event?.meeting_url.startsWith("https://") && (
                <a href={event.meeting_url} target="_blank" rel="noreferrer">
                  Join meeting ↗
                </a>
              )}
              {!readonly && (
                <button className="cal-primary" disabled={busy}>
                  {busy ? "Saving…" : "Save event"}
                </button>
              )}
            </footer>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
