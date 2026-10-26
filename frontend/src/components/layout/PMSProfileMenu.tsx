import { RichTextField, RichTextContent, richTextPlainText } from "@/components/rich-text/LazyRichText";
import { useEffect, useState } from "react";
import * as Menu from "@radix-ui/react-dropdown-menu";
import * as Dialog from "@radix-ui/react-dialog";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useLocation } from "react-router-dom";
import {
  Bell,
  BellOff,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock,
  FileText,
  HelpCircle,
  Keyboard,
  LayoutDashboard,
  LogOut,
  Palette,
  Pin,
  Settings,
  Smile,
  StickyNote,
  Trash2,
  Users,
  KeyRound,
  X,
  type LucideIcon,
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { defaultPersonal, usePersonalStore } from "@/store/personalStore";
import { palettes, type Palette as ThemePalette, useThemeStore } from "@/store/themeStore";
import { useSignOut } from "@/hooks/use-sign-out";
import { notificationsApi } from "@/services/api";
import { toast } from "@/hooks/use-toast";
import { canAccessRoute } from "@/lib/roles";
import KeyboardShortcuts from "@/components/app/KeyboardShortcuts";
import "./PMSProfileMenu.css";
type AlertItem = {
  id: number;
  title: string;
  message?: string;
  body?: string;
  is_read: boolean;
  created_at: string;
};
export default function PMSProfileMenu({
  onChangePassword,
  onCreateTask,
  onMyWork,
  onViewPeople,
}: {
  onChangePassword?: () => void;
  onCreateTask?: () => void;
  onMyWork?: () => void;
  onViewPeople?: () => void;
}) {
  const user = useAuthStore((s) => s.user);
  const prefs =
    usePersonalStore((s) => s.users[user?.id || 0]) || defaultPersonal;
  const update = usePersonalStore((s) => s.update);
  const { theme, setTheme, palette, setPalette } = useThemeStore();
  const signOut = useSignOut("/pms/login");
  const navigate = useNavigate();
  const location = useLocation();
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [panel, setPanel] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(Date.now());
  const [status, setStatus] = useState("");
  const [availability, setAvailability] = useState<
    "available" | "away" | "busy"
  >("available");
  const [expires, setExpires] = useState("240");
  const [notes, setNotes] = useState("");
  const [page, setPage] = useState(1);
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 30000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    setPanel("");
    setOpen(false);
    setError("");
  }, [user?.id]);
  const muted = prefs.mutedUntil > now;
  const activeStatus =
    !prefs.statusUntil || prefs.statusUntil > now ? prefs.status : "";
  const name = user?.name || user?.email?.split("@")[0] || "Your account";
  const initials = name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((s) => s[0])
    .join("")
    .toUpperCase();
  const wid = new URLSearchParams(location.search).get("workspace");
  const query = wid ? `&workspace=${encodeURIComponent(wid)}` : "";
  const tools: {
    id: string;
    label: string;
    icon: LucideIcon;
    path?: string;
    action: () => void;
  }[] = [
    {
      id: "task",
      label: "Create task",
      icon: CheckCircle2,
      action: () =>
        onCreateTask
          ? onCreateTask()
          : navigate(`/pms/workspaces?new=task${query}`),
    },
    {
      id: "work",
      label: "My Work",
      icon: CheckCircle2,
      action: () =>
        onMyWork ? onMyWork() : navigate(`/pms/workspaces?mine=1${query}`),
    },
    {
      id: "time",
      label: "Track Time",
      icon: Clock,
      path: "/pms/time-tracking",
      action: () => navigate("/pms/time-tracking"),
    },
    {
      id: "notes",
      label: "Notepad",
      icon: StickyNote,
      action: () => {
        setNotes(prefs.notes);
        setPanel("notes");
      },
    },
    {
      id: "docs",
      label: "Docs",
      icon: FileText,
      path: "/pms/docs",
      action: () => navigate("/pms/docs"),
    },
    {
      id: "people",
      label: "View People",
      icon: Users,
      action: () =>
        onViewPeople
          ? onViewPeople()
          : navigate(`/pms/workspaces?people=1${query}`),
    },
    {
      id: "dashboard",
      label: "Dashboards",
      icon: LayoutDashboard,
      path: "/pms/dashboards",
      action: () => navigate("/pms/dashboards"),
    },
  ].filter(
    (t) => !t.path || canAccessRoute(t.path, user?.role, user?.is_superuser),
  );
  const alerts = useQuery<{ items: AlertItem[]; total: number; pages: number }>(
    {
      queryKey: ["profile-notifications", user?.id, page],
      queryFn: () =>
        notificationsApi.list({ page, per_page: 15 }).then((r) => r.data),
      enabled: panel === "notifications" && !!user,
      retry: false,
    },
  );
  const save = (patch: Partial<typeof prefs>) => {
    try {
      if (!user) return false;
      update(user.id, patch);
      setNow(Date.now());
      return true;
    } catch {
      const message =
        "Browser storage is unavailable or full. Your changes have not been saved to this device.";
      setError(message);
      toast({
        title: "Could not save preferences",
        description: message,
        variant: "destructive",
      });
      return false;
    }
  };
  const show = (value: string) => {
    setError("");
    setPanel(value);
  };
  async function read(id: number) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await notificationsApi.markRead(id);
      await Promise.all([
        client.invalidateQueries({
          queryKey: ["profile-notifications", user?.id],
        }),
        client.invalidateQueries({ queryKey: ["notifications-unread-count"] }),
      ]);
    } catch {
      setError("Could not mark the notification as read. Please retry.");
    } finally {
      setBusy(false);
    }
  }
  const item = (label: string, Icon: LucideIcon, action: () => void) => (
    <Menu.Item key={label} className="pms-profile-item" onSelect={action}>
      <Icon size={16} />
      <span>{label}</span>
    </Menu.Item>
  );
  return (
    <>
      <Menu.Root open={open} onOpenChange={setOpen}>
        <Menu.Trigger asChild>
          <button
            className="pms-profile-trigger"
            aria-label="Profile menu"
            title={name}
          >
            <span>{initials}</span>
            <i className={activeStatus ? prefs.availability : "signed-in"} />
          </button>
        </Menu.Trigger>
        <Menu.Portal>
          <Menu.Content
            className="pms-profile-menu"
            align="end"
            sideOffset={10}
            collisionPadding={10}
          >
            <div className="pms-profile-identity">
              <span className="pms-profile-avatar">{initials}</span>
              <div>
                <strong>{name}</strong>
                <small>
                  {activeStatus || "Signed in"}
                  {muted ? " · Muted" : ""}
                </small>
              </div>
            </div>
            {item(activeStatus ? "Edit status" : "Set status", Smile, () => {
              setStatus(activeStatus);
              setAvailability(prefs.availability);
              show("status");
            })}
            <Menu.Sub>
              <Menu.SubTrigger className="pms-profile-item">
                <BellOff size={16} />
                <span>
                  {muted ? "Notifications muted" : "Mute notifications"}
                </span>
                <ChevronRight size={14} />
              </Menu.SubTrigger>
              <Menu.Portal>
                <Menu.SubContent
                  className="pms-profile-submenu"
                  sideOffset={5}
                  collisionPadding={10}
                >
                  <Menu.Label>On this browser · PMS alerts</Menu.Label>
                  {[
                    [30, "30 minutes"],
                    [60, "1 hour"],
                    [240, "4 hours"],
                    [1440, "24 hours"],
                  ].map(([minutes, label]) =>
                    item(String(label), BellOff, () =>
                      save({
                        mutedUntil: Date.now() + Number(minutes) * 60000,
                      }),
                    ),
                  )}
                  {item("Resume notifications", Bell, () =>
                    save({ mutedUntil: 0 }),
                  )}
                </Menu.SubContent>
              </Menu.Portal>
            </Menu.Sub>
            <Menu.Separator className="pms-profile-divider" />
            {item("My settings", Settings, () => navigate("/pms/profile"))}
            {item("Notifications", Bell, () => {
              setPage(1);
              show("notifications");
            })}
            <Menu.Sub>
              <Menu.SubTrigger className="pms-profile-item">
                <Palette size={16} />
                <span>Themes</span>
                <ChevronRight size={14} />
              </Menu.SubTrigger>
              <Menu.Portal>
                <Menu.SubContent
                  className="pms-profile-submenu"
                  sideOffset={5}
                  collisionPadding={10}
                >
                  <Menu.RadioGroup
                    value={theme}
                    onValueChange={(v) =>
                      setTheme(v as "light" | "dark" | "system")
                    }
                  >
                    {["light", "dark", "system"].map((value) => (
                      <Menu.RadioItem
                        className="pms-profile-item"
                        key={value}
                        value={value}
                      >
                        <span className="pms-profile-check">
                          <Menu.ItemIndicator>
                            <Check size={14} />
                          </Menu.ItemIndicator>
                        </span>
                        {value[0].toUpperCase() + value.slice(1)}
                      </Menu.RadioItem>
                    ))}
                  </Menu.RadioGroup>
                  <Menu.Separator className="pms-profile-divider" />
                  <Menu.Label className="pms-profile-caption">Color palette</Menu.Label>
                  <Menu.RadioGroup value={palette} onValueChange={(v) => setPalette(v as ThemePalette)} className="theme-palette-grid">
                    {palettes.map((p) => (
                      <Menu.RadioItem key={p.id} value={p.id} className="theme-palette-option">
                        <span className="theme-palette-preview" style={{ background: `hsl(${p.color} / .12)`, borderColor: `hsl(${p.color})` }}>
                          <i style={{ background: `hsl(${p.color})` }} />
                          <span><b /><b /><b /></span>
                          <Menu.ItemIndicator className="theme-palette-selected"><Check size={14} /></Menu.ItemIndicator>
                        </span>
                        {p.name}
                      </Menu.RadioItem>
                    ))}
                  </Menu.RadioGroup>
                </Menu.SubContent>
              </Menu.Portal>
            </Menu.Sub>
            {item("Keyboard shortcuts", Keyboard, () => show("shortcuts"))}
            {onChangePassword &&
              item("Change password", KeyRound, onChangePassword)}
            {item("Help", HelpCircle, () => show("help"))}
            <Menu.Separator className="pms-profile-divider" />
            <Menu.Label className="pms-profile-caption">
              Personal tools
            </Menu.Label>
            {tools
              .filter((t) => prefs.pins.includes(t.id))
              .map((t) => item(t.label, t.icon, t.action))}
            <Menu.Sub>
              <Menu.SubTrigger className="pms-profile-item">
                <Settings size={16} />
                <span>Customize quick tools</span>
                <ChevronRight size={14} />
              </Menu.SubTrigger>
              <Menu.Portal>
                <Menu.SubContent
                  className="pms-profile-submenu"
                  collisionPadding={10}
                >
                  {tools.map((t) => (
                    <Menu.CheckboxItem
                      className="pms-profile-item"
                      key={t.id}
                      checked={prefs.pins.includes(t.id)}
                      onSelect={(e) => e.preventDefault()}
                      onCheckedChange={(checked) =>
                        save({
                          pins: checked
                            ? [...prefs.pins, t.id]
                            : prefs.pins.filter((p) => p !== t.id),
                        })
                      }
                    >
                      <span className="pms-profile-check">
                        <Menu.ItemIndicator>
                          <Check size={14} />
                        </Menu.ItemIndicator>
                      </span>
                      <t.icon size={15} />
                      <span>{t.label}</span>
                      <Pin size={12} />
                    </Menu.CheckboxItem>
                  ))}
                </Menu.SubContent>
              </Menu.Portal>
            </Menu.Sub>
            {tools
              .filter((t) => !prefs.pins.includes(t.id))
              .map((t) => item(t.label, t.icon, t.action))}
            <Menu.Separator className="pms-profile-divider" />
            {canAccessRoute("/pms/trash", user?.role, user?.is_superuser) &&
              item("Trash", Trash2, () => navigate("/pms/trash"))}
            {item("Log out", LogOut, () => void signOut())}
          </Menu.Content>
        </Menu.Portal>
      </Menu.Root>
      {panel === "shortcuts" && (
        <KeyboardShortcuts
          open
          onOpenChange={(value) => {
            if (!value) setPanel("");
          }}
        />
      )}
      <Dialog.Root
        open={!!panel && panel !== "shortcuts"}
        onOpenChange={(value) => {
          if (!value && !busy) setPanel("");
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="pms-profile-overlay" />
          <Dialog.Content className="pms-profile-dialog">
            <Dialog.Title>
              {
                (
                  {
                    status: "Set your status",
                    notes: "Personal notepad",
                    notifications: "Your notifications",
                    help: "KaryaFlow help",
                  } as Record<string, string>
                )[panel]
              }
            </Dialog.Title>
            <Dialog.Description>
              {panel === "notifications"
                ? "Your saved in-app notifications."
                : panel === "help"
                  ? "Find your way around your workspace."
                  : "Saved per account on this browser. These preferences do not sync to other devices."}
            </Dialog.Description>
            <button
              className="pms-profile-close"
              aria-label="Close profile dialog"
              disabled={busy}
              onClick={() => setPanel("")}
            >
              <X size={18} />
            </button>
            {panel === "status" && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  save({
                    status: status.trim(),
                    availability,
                    statusUntil:
                      expires === "0"
                        ? 0
                        : Date.now() + Number(expires) * 60000,
                  });
                  setPanel("");
                }}
              >
                <label>
                  Status message
                  <input
                    aria-label="Status message"
                    maxLength={100}
                    placeholder="What are you focused on?"
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                  />
                </label>
                <label>
                  Self-set availability
                  <select
                    value={availability}
                    onChange={(e) =>
                      setAvailability(e.target.value as "available")
                    }
                  >
                    <option value="available">Available</option>
                    <option value="away">Away</option>
                    <option value="busy">Do not disturb</option>
                  </select>
                </label>
                <label>
                  Clear after
                  <select
                    value={expires}
                    onChange={(e) => setExpires(e.target.value)}
                  >
                    <option value="60">1 hour</option>
                    <option value="240">4 hours</option>
                    <option value="1440">24 hours</option>
                    <option value="0">Do not clear</option>
                  </select>
                </label>
                <small>
                  This is a personal label, not live online presence. Use Mute
                  notifications to silence PMS alerts.
                </small>
                <footer>
                  <button
                    type="button"
                    onClick={() => {
                      save({ status: "", statusUntil: 0 });
                      setPanel("");
                    }}
                  >
                    Clear status
                  </button>
                  <button className="pms-profile-primary">Save status</button>
                </footer>
              </form>
            )}
            {panel === "notes" && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (save({ notes })) setPanel("");
                }}
              >
                <label>
                  Notes
                  <RichTextField
                    aria-label="Personal notes"
                    maxLength={20000}
                    rows={10}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Ideas, links and things to remember…"
                  />
                </label>
                <small>
                  {notes.length.toLocaleString()} / 20,000 characters · Stored
                  locally; use Docs for shared work.
                </small>
                <footer>
                  <button type="button" onClick={() => setPanel("")}>
                    Cancel
                  </button>
                  <button className="pms-profile-primary">Save notes</button>
                </footer>
              </form>
            )}
            {panel === "notifications" && (
              <div className="pms-profile-alerts">
                {alerts.isLoading ? (
                  <p role="status">Loading notifications…</p>
                ) : alerts.isError ? (
                  <div role="alert">
                    Could not load notifications.
                    <button onClick={() => void alerts.refetch()}>Retry</button>
                  </div>
                ) : (
                  <>
                    {alerts.data?.items.map((n) => (
                      <article key={n.id}>
                        <strong>{n.title}</strong>
                        <div><RichTextContent value={n.message || n.body}/></div>
                        <small>{new Date(n.created_at).toLocaleString()}</small>
                        {!n.is_read && (
                          <button
                            disabled={busy}
                            onClick={() => void read(n.id)}
                          >
                            Mark read
                          </button>
                        )}
                      </article>
                    ))}
                    {!alerts.data?.items.length && <p>You’re all caught up.</p>}
                    <footer>
                      <button
                        disabled={page === 1}
                        onClick={() => setPage((p) => p - 1)}
                      >
                        Previous
                      </button>
                      <span>Page {page}</span>
                      <button
                        disabled={page >= (alerts.data?.pages || 1)}
                        onClick={() => setPage((p) => p + 1)}
                      >
                        Next
                      </button>
                    </footer>
                  </>
                )}
                {error && <p role="alert">{error}</p>}
              </div>
            )}
            {panel === "help" && (
              <div className="pms-profile-help">
                <p>
                  Use your workspace to create tasks, assign people and follow
                  progress. Open a task for its details, comments, files and
                  subtasks.
                </p>
                <button
                  onClick={() => {
                    setPanel("");
                    navigate("/pms/workspaces");
                  }}
                >
                  Open workspaces
                </button>
                <button onClick={() => setPanel("shortcuts")}>
                  View keyboard shortcuts
                </button>
                <p>
                  Use Docs for shared notes and Planner to schedule work.
                  Workspace admins manage people, reporting lines and access.
                </p>
              </div>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
