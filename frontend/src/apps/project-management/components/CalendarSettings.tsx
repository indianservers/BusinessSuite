import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Link } from "react-router-dom";
import { api } from "@/services/api";
import { workspaceError } from "../pages/workspaceTypes";
import {
  calendarDefaults,
  type CalendarPrefs,
  type CalendarSection,
} from "../pages/calendarTypes";
import "./CalendarSettings.css";
const tabs = [
  "Appearance",
  "Accounts",
  "Sidebar",
  "Upcoming meeting",
  "Time blocking",
  "Meeting notes",
  "Automations",
];
export default function CalendarSettings({
  open,
  onClose,
  value,
  revision,
  onSaved,
  projects,
  onExport,
}: {
  open: boolean;
  onClose: () => void;
  value: CalendarPrefs;
  revision: number;
  onSaved: (data: { revision: number; preferences: CalendarPrefs }) => void;
  projects: { id: number; name: string; can_schedule: boolean }[];
  onExport: () => void;
}) {
  const [tab, setTab] = useState("Appearance");
  const [draft, setDraft] = useState(value);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [drag, setDrag] = useState<number | null>(null);
  const [providers, setProviders] = useState<
    { id: string; name: string; state: string; requirements: string[] }[]
  >([]);
  const [setup, setSetup] = useState("");
  useEffect(() => {
    if (open) {
      setDraft(value);
      setError("");
    }
  }, [open, value]);
  useEffect(() => {
    if (!open || tab !== "Accounts") return;
    let active = true;
    void api
      .get("/project-management/planner/connections")
      .then((r) => {
        if (active) setProviders(r.data.providers);
      })
      .catch((e) => {
        if (active) setError(workspaceError(e));
      });
    return () => {
      active = false;
    };
  }, [open, tab]);
  const patch = (p: Partial<CalendarPrefs>) =>
    setDraft((d) => ({ ...d, ...p }));
  const toggle = (key: keyof CalendarPrefs, label: string, detail: string) => (
    <label className="cal-setting-toggle">
      <input
        type="checkbox"
        checked={!!draft[key]}
        onChange={(e) => patch({ [key]: e.target.checked })}
      />
      <span>
        <strong>{label}</strong>
        <small>{detail}</small>
      </span>
    </label>
  );
  const choose = (
    key: keyof CalendarPrefs,
    label: string,
    description: string,
    options: [string, string][],
    numeric = false,
  ) => (
    <label className="cal-setting-row">
      <span>
        <strong>{label}</strong>
        <small>{description}</small>
      </span>
      <select
        aria-label={label}
        value={String(draft[key] ?? "")}
        onChange={(e) =>
          patch({
            [key]: numeric
              ? e.target.value === ""
                ? null
                : Number(e.target.value)
              : e.target.value,
          })
        }
      >
        {options.map(([v, n]) => (
          <option key={v} value={v}>
            {n}
          </option>
        ))}
      </select>
    </label>
  );
  function move(from: number, to: number) {
    if (to < 0 || to >= draft.sections.length) return;
    const sections = [...draft.sections];
    const [item] = sections.splice(from, 1);
    sections.splice(to, 0, item);
    patch({ sections });
  }
  async function save() {
    setBusy(true);
    setError("");
    try {
      const r = await api.put("/project-management/planner/preferences", {
        revision,
        preferences: draft,
      });
      onSaved(r.data);
      onClose();
    } catch (e) {
      setError(workspaceError(e));
    } finally {
      setBusy(false);
    }
  }
  const zones = Array.from(
    new Set([
      draft.timezone,
      Intl.DateTimeFormat().resolvedOptions().timeZone,
      "UTC",
      "Asia/Kolkata",
      "Asia/Dubai",
      "Asia/Singapore",
      "Europe/London",
      "Europe/Paris",
      "America/New_York",
      "America/Chicago",
      "America/Los_Angeles",
      "Australia/Sydney",
      ...((
        Intl as typeof Intl & { supportedValuesOf?: (key: string) => string[] }
      ).supportedValuesOf?.("timeZone") || []),
    ]),
  );
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(v) => {
        if (!v && !busy) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="cal-settings-overlay" />
        <Dialog.Content className="cal-settings-dialog">
          <aside>
            <Dialog.Title>⚙ Calendar settings</Dialog.Title>
            <nav aria-label="Calendar settings sections">
              {tabs.map((t) => (
                <button
                  key={t}
                  disabled={busy}
                  className={tab === t ? "active" : ""}
                  onClick={() => {
                    setTab(t);
                    setError("");
                  }}
                >
                  {t}
                </button>
              ))}
            </nav>
            <small>Preferences follow your account.</small>
          </aside>
          <main>
            <header>
              <span>{tab}</span>
              <button
                aria-label="Close calendar settings"
                disabled={busy}
                onClick={onClose}
              >
                ×
              </button>
            </header>
            <div className="cal-settings-scroll">
              <h2>{tab}</h2>
              <Dialog.Description>
                Customize your calendar and planning experience.
              </Dialog.Description>
              {error && (
                <p role="alert" className="cal-settings-error">
                  {error}
                </p>
              )}
              <fieldset disabled={busy}>
                {tab === "Appearance" && (
                  <>
                    <div className="cal-setting-row">
                      <span>
                        <strong>Grid size</strong>
                        <small>Choose how much room each date has.</small>
                      </span>
                      <div className="cal-choice-cards">
                        {(["default", "large", "xl"] as const).map((v) => (
                          <button
                            aria-pressed={draft.grid_size === v}
                            key={v}
                            onClick={() => patch({ grid_size: v })}
                          >
                            <i>
                              Team sync
                              <br />
                              <small>9 – 11am</small>
                            </i>
                            {v === "xl"
                              ? "XL"
                              : v[0].toUpperCase() + v.slice(1)}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="cal-setting-row">
                      <span>
                        <strong>Event style</strong>
                        <small>Choose subtle tints or solid color pills.</small>
                      </span>
                      <div className="cal-choice-cards">
                        {(["subtle", "solid"] as const).map((v) => (
                          <button
                            aria-pressed={draft.event_style === v}
                            key={v}
                            onClick={() => patch({ event_style: v })}
                          >
                            <i className={v}>Team sync</i>
                            {v}
                          </button>
                        ))}
                      </div>
                    </div>
                    {choose(
                      "duration",
                      "Default event duration",
                      "Used when adding meetings and focus blocks.",
                      [15, 30, 45, 60, 90, 120].map((n) => [
                        String(n),
                        `${n} minutes`,
                      ]),
                      true,
                    )}
                    {choose(
                      "color_by",
                      "Color tasks by",
                      "Change the color of task pills.",
                      [
                        ["project", "Project"],
                        ["status", "Status"],
                        ["priority", "Priority"],
                      ],
                    )}
                    {choose(
                      "week_start",
                      "Start week on",
                      "Choose the first day of your calendar.",
                      [
                        "Sunday",
                        "Monday",
                        "Tuesday",
                        "Wednesday",
                        "Thursday",
                        "Friday",
                        "Saturday",
                      ].map((d, i) => [String(i), d]),
                      true,
                    )}
                    {choose(
                      "timezone",
                      "Timezone",
                      "Timed events use this zone. Task deadlines stay date-only.",
                      zones.map((z) => [z, z]),
                    )}
                    {toggle(
                      "weekends",
                      "Show weekends",
                      "Include Saturday and Sunday.",
                    )}
                    {toggle(
                      "week_numbers",
                      "Show week numbers",
                      "Display ISO week numbers in Week view.",
                    )}
                  </>
                )}
                {tab === "Accounts" && (
                  <>
                    <article className="cal-account">
                      <strong>BusinessSuite calendar</strong>
                      <span className="cal-connected">Available</span>
                      <p>
                        Private meetings, shared workspace events, task
                        deadlines and focus blocks.
                      </p>
                    </article>
                    {providers.map((p) => (
                      <article className="cal-account" key={p.id}>
                        <strong>{p.name}</strong>
                        <span>Not configured</span>
                        <button
                          onClick={() => setSetup(setup === p.id ? "" : p.id)}
                        >
                          Setup requirements
                        </button>
                        {setup === p.id && (
                          <>
                            <ul>
                              {p.requirements.map((r) => (
                                <li key={r}>{r}</li>
                              ))}
                            </ul>
                            <p>
                              Configure provider OAuth credentials and a
                              redirect URL on the server before connecting an
                              account. No account is connected yet.
                            </p>
                          </>
                        )}
                      </article>
                    ))}
                    {choose(
                      "focus_visibility",
                      "Default focus visibility",
                      "Workspace events can be seen by workspace members.",
                      [
                        ["private", "Private"],
                        ["workspace", "Workspace"],
                      ],
                    )}
                    <p className="cal-settings-note">
                      BusinessSuite is the default and busy calendar. External
                      accounts and conferencing require provider setup.
                    </p>
                    <button onClick={onExport}>Export calendar (.ics)</button>
                  </>
                )}
                {tab === "Sidebar" && (
                  <>
                    <p className="cal-settings-note">
                      Show, hide, rename and reorder your task sections. Drag a
                      row or use its arrow buttons.
                    </p>
                    {draft.sections.map((s, i) => (
                      <div
                        className="cal-sidebar-row"
                        key={s.id}
                        draggable
                        onDragStart={() => setDrag(i)}
                        onDragOver={(e) => e.preventDefault()}
                        onDrop={() => {
                          if (drag !== null) move(drag, i);
                          setDrag(null);
                        }}
                      >
                        <input
                          type="checkbox"
                          aria-label={`Show ${s.title}`}
                          checked={s.enabled}
                          onChange={(e) =>
                            patch({
                              sections: draft.sections.map((v) =>
                                v.id === s.id
                                  ? { ...v, enabled: e.target.checked }
                                  : v,
                              ),
                            })
                          }
                        />
                        <input
                          aria-label={`Section name ${i + 1}`}
                          maxLength={60}
                          value={s.title}
                          onChange={(e) =>
                            patch({
                              sections: draft.sections.map((v) =>
                                v.id === s.id
                                  ? { ...v, title: e.target.value }
                                  : v,
                              ),
                            })
                          }
                        />
                        <select
                          aria-label={`Section filter ${i + 1}`}
                          value={s.filter}
                          onChange={(e) =>
                            patch({
                              sections: draft.sections.map((v) =>
                                v.id === s.id
                                  ? {
                                      ...v,
                                      filter: e.target
                                        .value as CalendarSection["filter"],
                                    }
                                  : v,
                              ),
                            })
                          }
                        >
                          {[
                            "priorities",
                            "people",
                            "assigned",
                            "overdue",
                            "backlog",
                            "high_priority",
                          ].map((v) => (
                            <option key={v}>{v}</option>
                          ))}
                        </select>
                        <button
                          aria-label={`Move ${s.title} up`}
                          onClick={() => move(i, i - 1)}
                        >
                          ↑
                        </button>
                        <button
                          aria-label={`Move ${s.title} down`}
                          onClick={() => move(i, i + 1)}
                        >
                          ↓
                        </button>
                        <button
                          aria-label={`Remove ${s.title}`}
                          onClick={() =>
                            patch({
                              sections: draft.sections.filter(
                                (v) => v.id !== s.id,
                              ),
                            })
                          }
                        >
                          ×
                        </button>
                      </div>
                    ))}
                    <button
                      disabled={draft.sections.length >= 12}
                      onClick={() =>
                        patch({
                          sections: [
                            ...draft.sections,
                            {
                              id: "custom_" + crypto.randomUUID().slice(0, 8),
                              title: "High priority",
                              enabled: true,
                              filter: "high_priority",
                            },
                          ],
                        })
                      }
                    >
                      ＋ Add a new section
                    </button>
                  </>
                )}
                {tab === "Upcoming meeting" && (
                  <>
                    {toggle(
                      "show_event_details",
                      "Show event details on button",
                      "Display the next meeting title in your planner header.",
                    )}
                    {toggle(
                      "show_time_left",
                      "Show time left",
                      "Show remaining time for an ongoing meeting.",
                    )}
                    {choose(
                      "quick_join",
                      "Quick join duration",
                      "Show Join shortly before a meeting starts. Join remains available during the meeting.",
                      [1, 2, 5, 10, 15].map((n) => [String(n), `${n} minutes`]),
                      true,
                    )}
                    {toggle(
                      "browser_reminders",
                      "Browser meeting reminders",
                      "Show a reminder while this calendar is open and notifications are permitted.",
                    )}
                    <button
                      onClick={() =>
                        void (async () => {
                          if (!("Notification" in window)) {
                            setError(
                              "This browser does not support notifications.",
                            );
                            return;
                          }
                          const permission =
                            await Notification.requestPermission();
                          if (permission !== "granted")
                            setError(
                              "Notifications were not permitted. Enable them in your browser settings.",
                            );
                          else patch({ browser_reminders: true });
                        })()
                      }
                    >
                      Enable browser notifications
                    </button>
                    <p className="cal-settings-note">
                      Browser reminders require the planner tab to stay open. A
                      native desktop menubar integration is not available.
                    </p>
                  </>
                )}
                {tab === "Time blocking" && (
                  <>
                    {toggle(
                      "show_task_dates",
                      "Show task due dates",
                      "Display assigned and accessible task deadlines on the calendar.",
                    )}
                    {choose(
                      "task_scope",
                      "Task scope",
                      "Choose which task deadlines are visible.",
                      [
                        ["all", "All accessible tasks"],
                        ["mine", "Assigned to me"],
                      ],
                    )}
                    {toggle(
                      "closed_tasks",
                      "Show closed tasks",
                      "Include completed task deadlines.",
                    )}
                    {toggle(
                      "recurring",
                      "Show future recurring tasks",
                      "Preview the next 12 occurrences. Projections do not create tasks.",
                    )}
                    {choose(
                      "default_project",
                      "Default project for new tasks",
                      "Used by the planner task composer.",
                      [
                        ["", "Choose automatically"],
                        ...projects
                          .filter((p) => p.can_schedule)
                          .map(
                            (p) => [String(p.id), p.name] as [string, string],
                          ),
                      ],
                      true,
                    )}
                    <label className="cal-setting-row">
                      <span>
                        <strong>Timeblock prefix</strong>
                        <small>Prefix for focus blocks linked to tasks.</small>
                      </span>
                      <input
                        aria-label="Timeblock prefix"
                        maxLength={60}
                        value={draft.prefix}
                        onChange={(e) => patch({ prefix: e.target.value })}
                      />
                    </label>
                    {choose(
                      "focus_visibility",
                      "Default focus visibility",
                      "Choose who can see new focus blocks.",
                      [
                        ["private", "Private"],
                        ["workspace", "Workspace"],
                      ],
                    )}
                    <h3>Custom work schedule</h3>
                    <p className="cal-settings-note">
                      Free-slot suggestions use these hours in your selected
                      timezone.
                    </p>
                    {draft.workdays.map((w) => (
                      <div className="cal-workday" key={w.day}>
                        <label>
                          <input
                            type="checkbox"
                            checked={w.enabled}
                            onChange={(e) =>
                              patch({
                                workdays: draft.workdays.map((v) =>
                                  v.day === w.day
                                    ? { ...v, enabled: e.target.checked }
                                    : v,
                                ),
                              })
                            }
                          />
                          {
                            ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][
                              w.day
                            ]
                          }
                        </label>
                        <input
                          aria-label={`Start ${w.day}`}
                          type="time"
                          disabled={!w.enabled}
                          value={w.start}
                          onChange={(e) =>
                            patch({
                              workdays: draft.workdays.map((v) =>
                                v.day === w.day
                                  ? { ...v, start: e.target.value }
                                  : v,
                              ),
                            })
                          }
                        />
                        <span>–</span>
                        <input
                          aria-label={`End ${w.day}`}
                          type="time"
                          disabled={!w.enabled}
                          value={w.end}
                          onChange={(e) =>
                            patch({
                              workdays: draft.workdays.map((v) =>
                                v.day === w.day
                                  ? { ...v, end: e.target.value }
                                  : v,
                              ),
                            })
                          }
                        />
                      </div>
                    ))}
                  </>
                )}
                {tab === "Meeting notes" && (
                  <>
                    <p className="cal-settings-note">
                      Customize the notes template available from each meeting.
                      Automated recording, auto-join, transcription and agent
                      sharing require a conferencing/AI integration.
                    </p>
                    <label className="cal-setting-row">
                      <span>
                        <strong>Notes display name</strong>
                        <small>
                          Heading for your downloadable meeting notes.
                        </small>
                      </span>
                      <input
                        maxLength={100}
                        value={draft.notes_name}
                        onChange={(e) => patch({ notes_name: e.target.value })}
                      />
                    </label>
                    <label>
                      Included in notes
                      <textarea
                        rows={10}
                        maxLength={4000}
                        value={draft.notes_template}
                        onChange={(e) =>
                          patch({ notes_template: e.target.value })
                        }
                      />
                    </label>
                    <Link to="/pms/docs">Open shared Docs →</Link>
                  </>
                )}
                {tab === "Automations" && (
                  <>
                    <article className="cal-account">
                      <strong>Task workflows</strong>
                      <p>
                        Use the existing workspace automation engine for
                        task-created and status-change rules.
                      </p>
                      <Link to="/pms/automation">
                        Manage task automations →
                      </Link>
                    </article>
                    <article className="cal-account">
                      <strong>Calendar exchange</strong>
                      <p>
                        Export the visible calendar as an ICS file for import
                        into Google Calendar, Outlook or Apple Calendar.
                      </p>
                      <button onClick={onExport}>Export calendar (.ics)</button>
                    </article>
                    <p className="cal-settings-note">
                      Continuous external sync requires a connected provider.
                      Exporting a file does not enable automatic sync.
                    </p>
                  </>
                )}
              </fieldset>
            </div>
            <footer>
              <button
                disabled={busy}
                onClick={() => setDraft({ ...calendarDefaults })}
              >
                Reset defaults
              </button>
              <div>
                <button disabled={busy} onClick={onClose}>
                  Cancel
                </button>
                <button
                  className="cal-primary"
                  disabled={busy}
                  onClick={() => void save()}
                >
                  {busy ? "Saving…" : "Save settings"}
                </button>
              </div>
            </footer>
          </main>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
