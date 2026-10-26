import { RichTextContent, richTextPlainText } from "../../src/components/rich-text/RichTextContent";
import React, { createContext, useContext, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  GraduationCap,
  ClipboardList,
  BarChart3,
  CheckCircle2,
  FileText,
  Sparkles,
  ArrowRight,
  CalendarDays,
} from "lucide-react";
import { API, hub, send } from "./api";
export function Avatar({
  name,
  photo,
  large = false,
}: {
  name: string;
  photo?: string;
  large?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  const src = photo
    ? new URL(photo, new URL(API, window.location.origin).origin).href
    : "";
  return (
    <span className={`avatar ${large ? "large" : ""}`}>
      {src && !failed ? (
        <img src={src} alt={name} onError={() => setFailed(true)} />
      ) : (
        initials(name)
      )}
    </span>
  );
}
export type Row = Record<string, any>;
export type Data = {
  me: Row;
  overview: Row;
  tasks: Row[];
  submissions: Row[];
  reports: Row[];
  attendance: Row[];
  learning: Row[];
  leaderboard: Row[];
  certificates: Row[];
  support: Row[];
};
export const Context = createContext<{
  data: Data;
  refresh: () => Promise<void>;
  act: (work: () => Promise<any>, message: string) => Promise<boolean>;
  busy: boolean;
}>({} as any);
export const useHub = () => useContext(Context);
export const localDay = () =>
  new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
export const formatDate = (value?: string) =>
  value
    ? new Date(
        value.length === 10 ? `${value}T12:00:00` : value,
      ).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "—";
export const time = (value?: string) =>
  value
    ? new Date(value).toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";
export const initials = (name: string) =>
  name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((n) => n[0])
    .join("");
export function Logo() {
  return (
    <div className="logo">
      <GraduationCap size={40} fill="currentColor" />
      <div>
        Interns<span>Hub</span>
        <small>Learn ・ Grow ・ Build</small>
      </div>
    </div>
  );
}
export function Badge({ children }: { children: React.ReactNode }) {
  const s = String(children);
  return (
    <span
      className={`badge ${/Completed|Approved|Present|Passed|Active/.test(s) ? "green" : /Pending|Revision|Medium/.test(s) ? "orange" : /High|Absent/.test(s) ? "pink" : /Progress/.test(s) ? "blue" : "purple"}`}
    >
      {children}
    </span>
  );
}
export function Empty({
  title = "Nothing here yet",
  children = "Your HRMS team will update this space.",
}: {
  title?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <GraduationCap size={34} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function Card({
  title,
  icon: Icon = ClipboardList,
  action,
  children,
  className = "",
}: {
  title?: string;
  icon?: any;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {title && (
        <div className="card-head">
          <h3>
            <span className="icon-small">
              <Icon size={19} />
            </span>
            {title}
          </h3>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
export function Ring({
  value = 0,
  label = "Completed",
  green = false,
}: {
  value?: number;
  label?: string;
  green?: boolean;
}) {
  return (
    <div
      className={`ring ${green ? "success" : ""}`}
      style={{ "--progress": `${value * 3.6}deg` } as React.CSSProperties}
    >
      <div>
        <b>{value}%</b>
        <span>{label}</span>
      </div>
    </div>
  );
}
export function Stat({
  icon: Icon,
  label,
  value,
  note,
  color = "purple",
}: {
  icon: any;
  label: string;
  value: React.ReactNode;
  note?: string;
  color?: string;
}) {
  return (
    <div className="stat card">
      <span className={`stat-icon ${color}`}>
        <Icon size={30} />
      </span>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
        <small>{note}</small>
      </div>
    </div>
  );
}
export function Heading({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="heading">
      <div>
        <h1>{title}</h1>
        <div><RichTextContent legacyFormat="plain" value={description}/></div>
      </div>
      {children || (
        <div className="date-label">
          <CalendarDays />
          <div>
            <b>
              {new Date().toLocaleDateString("en-IN", {
                weekday: "long",
                day: "numeric",
                month: "short",
                year: "numeric",
              })}
            </b>
            <small>A new day, a new opportunity to grow.</small>
          </div>
        </div>
      )}
    </div>
  );
}
export function Hero({ learning = false }: { learning?: boolean }) {
  const { data } = useHub();
  return (
    <div className="hero">
      <div className="hero-copy">
        <small>
          <Sparkles size={17} />
          {learning ? "FEATURED TRAINING" : "You're Doing Great!"}
        </small>
        <h2>
          {learning
            ? "Become a Future-Ready Professional"
            : "Consistency turns small efforts into big achievements."}
        </h2>
        <p>
          {learning
            ? "Build in-demand skills, follow your learning path and grow with every lesson."
            : "Every task you complete is a step closer to the professional you want to become. Keep learning, keep building!"}
        </p>
        <Link
          className="button white"
          to={
            learning && data.learning[0]
              ? `/learning/${data.learning[0].id}`
              : "/tasks"
          }
        >
          {learning ? "Start Learning" : "Keep Going"}
          <ArrowRight size={17} />
        </Link>
      </div>
      <div className="hero-art" aria-hidden="true">
        <div className="orbit o1" />
        <div className="orbit o2" />
        <span className="floating-star">✦</span>
        <div className="illustration-person">
          <div className="hair" />
          <div className="face" />
          <div className="shirt" />
        </div>
        <div className="laptop">
          <GraduationCap size={40} />
          <small>
            Good ideas
            <br />
            grow here
          </small>
        </div>
        <div className="plant">✦</div>
      </div>
    </div>
  );
}
export function TaskTable({
  compact = false,
  filter = "",
  search = "",
}: {
  compact?: boolean;
  filter?: string;
  search?: string;
}) {
  const { data, act } = useHub();
  const navigate = useNavigate();
  const items = data.tasks.filter(
    (t) =>
      (!filter || t.status === filter) &&
      `${t.title} ${t.category}`.toLowerCase().includes(search.toLowerCase()),
  );
  return items.length ? (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Task Title</th>
            <th>Category</th>
            {!compact && (
              <>
                <th>Due Date</th>
                <th>Mentor</th>
                <th>Priority</th>
              </>
            )}
            <th>Status</th>
            <th>Points</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {items.slice(0, compact ? 4 : undefined).map((t) => (
            <tr key={t.id}>
              <td>
                <Link className="task-title" to={`/tasks/${t.id}`}>
                  <span className="task-icon">
                    <FileText size={20} />
                  </span>
                  <div>
                    <b>{t.title}</b>
                    <small>{richTextPlainText(t.description).slice(0, 75)}</small>
                  </div>
                </Link>
              </td>
              <td>
                <Badge>{t.category}</Badge>
              </td>
              {!compact && (
                <>
                  <td className="nowrap">{formatDate(t.due_date)}</td>
                  <td>{data.me.manager || "Unassigned"}</td>
                  <td>
                    <Badge>{t.priority}</Badge>
                  </td>
                </>
              )}
              <td>
                <Badge>{t.status}</Badge>
              </td>
              <td className="nowrap">
                <b>{t.points} pts</b>
              </td>
              <td>
                <button
                  className={
                    t.status === "Pending"
                      ? "button soft small"
                      : "button small"
                  }
                  onClick={async () => {
                    if (t.status === "Pending")
                      await act(
                        () => hub(`/tasks/${t.id}/start`, send("POST")),
                        "Task started",
                      );
                    navigate(`/tasks/${t.id}`);
                  }}
                >
                  {t.status === "Completed"
                    ? "View"
                    : t.status === "Pending"
                      ? "Start"
                      : "Continue"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <Empty title="No tasks to show">
      Assigned tasks will appear here. Try a different filter or contact your
      manager.
    </Empty>
  );
}
export function ProgressCard() {
  const { data } = useHub();
  return (
    <Card
      title="Internship Progress"
      icon={BarChart3}
      action={<Link to="/certificates">View Details →</Link>}
    >
      <div className="progress-layout">
        <Ring value={data.overview.progress} />
        <div className="progress-list">
          <b>
            {data.overview.completed} of {data.overview.total_tasks} tasks
          </b>
          <small>Joined {formatDate(data.me.date_of_joining)}</small>
          {[
            ["Core Tasks", `${data.overview.progress}%`],
            ["Daily Reports", data.overview.reports],
            ["Certificates", data.overview.certificates],
            ["Manager", data.me.manager || "Unassigned"],
          ].map(([label, value]) => (
            <div key={label}>
              <CheckCircle2 size={17} />
              <span>{label}</span>
              <b>{value}</b>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
