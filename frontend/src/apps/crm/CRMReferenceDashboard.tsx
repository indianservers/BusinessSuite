import ModuleWorkflowBoard from "@/shared/workflow-board/ModuleWorkflowBoard";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart3,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Folder,
  Handshake,
  Plus,
  Sparkles,
  Target,
  Trophy,
  Users,
  Zap,
  Briefcase,
  CheckSquare,
  Phone,
} from "lucide-react";
import {
  Bar,
  ComposedChart,
  Line,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { crmApi, type CRMCalendarEvent } from "./api";
import { api } from "@/services/api";
import { useRefreshableEffect } from "@/lib/page-refresh";
import "./crm-reference-dashboard.css";

type Deal = {
  id: number;
  name: string;
  stageId: number;
  stage: string;
  amount: number;
  currency?: string;
  owner: string;
  closeDate: string;
};
type Statistics = {
  leads_created: number;
  open_deals: number;
  won_deals: number;
  lost_deals: number;
  win_rate: number | null;
  pipeline_by_currency: { currency: string; amount: string }[];
  overdue_followups: number;
  lead_sources: { name: string; value: number }[];
  context: { as_of: string; definition: string; timezone: string };
};
type Props = {
  statistics?: Statistics;
  loading: boolean;
  error?: string;
  range: "month" | "quarter" | "all";
  onRange: (value: "month" | "quarter" | "all") => void;
  onCreate: (
    kind: "leads" | "contacts" | "companies" | "deals" | "tasks",
  ) => void;
  stages: { id: number; name: string }[];
  deals: Deal[];
  briefing: { title: string; reason: string; action: string; path: string }[];
  today: {
    id: string;
    title: string;
    time: string;
    path: string;
    overdue: boolean;
  }[];
  events: { start: string; type: string }[];
  tasks: { [key: string]: unknown }[];
};
const colors = [
  "#9470ff",
  "#36c5f8",
  "#df72f3",
  "#ff999d",
  "#ffd86d",
  "#64d975",
];
const money = (amount: number, currency = "INR") => {
  try {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${currency} ${amount.toLocaleString("en-IN")}`;
  }
};
export default function CRMReferenceDashboard(p: Props) {
  const navigate = useNavigate();
  const [month, setMonth] = useState(
    () => new Date(new Date().getFullYear(), new Date().getMonth(), 1),
  );
  const [chartCurrency, setChartCurrency] = useState("");
  const [monthEvents, setMonthEvents] = useState<CRMCalendarEvent[]>([]);
  const [calendarError, setCalendarError] = useState("");
  useRefreshableEffect(() => {
    let active = true;
    const key = (d: Date) =>
      `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    setCalendarError("");
    setMonthEvents([]);
    crmApi
      .calendar({
        startDate: key(month),
        endDate: key(new Date(month.getFullYear(), month.getMonth() + 1, 0)),
      })
      .then((r) => {
        if (active) setMonthEvents(r.data.items || []);
      })
      .catch(() => {
        if (active) setCalendarError("Calendar unavailable");
      });
    return () => {
      active = false;
    };
  }, [month]);
  const sources = p.statistics?.lead_sources || [];
  const total = sources.reduce((n, r) => n + r.value, 0);
  const currencies = [...new Set(p.deals.map((d) => d.currency || "Unknown"))];
  const currency = currencies.includes(chartCurrency)
    ? chartCurrency
    : currencies[0] || "INR";
  const chart = useMemo(
    () =>
      Array.from({ length: 6 }, (_, i) => {
        const d = new Date(
          new Date().getFullYear(),
          new Date().getMonth() - 5 + i,
          1,
        );
        const rows = p.deals.filter((r) => {
          const close = new Date(r.closeDate);
          return (
            close.getMonth() === d.getMonth() &&
            close.getFullYear() === d.getFullYear() &&
            (r.currency || "Unknown") === currency
          );
        });
        const wonCount = rows.filter((r) => /won/i.test(r.stage)).length;
        const closedCount = rows.filter((r) =>
          /won|lost/i.test(r.stage),
        ).length;
        return {
          winRate: closedCount
            ? Math.round((wonCount / closedCount) * 100)
            : null,
          month: d.toLocaleDateString(undefined, { month: "short" }),
          won: rows
            .filter((r) => /won/i.test(r.stage))
            .reduce((n, r) => n + r.amount, 0),
          open: rows
            .filter((r) => !/won|lost/i.test(r.stage))
            .reduce((n, r) => n + r.amount, 0),
        };
      }),
    [p.deals, currency],
  );
  const [portfolio, setPortfolio] = useState<{
    active_projects?: number;
    total_projects?: number;
    open_tasks?: number;
    completed_tasks?: number;
  }>();
  useRefreshableEffect(() => {
    let active = true;
    api
      .get("/project-management/portfolio/summary")
      .then((r) => {
        if (active) setPortfolio(r.data);
      })
      .catch(() => {
        if (active) setPortfolio(undefined);
      });
    return () => {
      active = false;
    };
  }, []);
  const stat = p.statistics;
  const metrics = [
    {
      title: "New leads",
      value: stat?.leads_created,
      detail: "Created in selected period",
      icon: Users,
      tone: "mint",
      path: "leads",
    },
    {
      title: "Open deals",
      value: stat?.open_deals,
      detail: "In selected reporting period",
      icon: Handshake,
      tone: "violet",
      path: "open-deals",
    },
    {
      title: "Pipeline value",
      value: stat
        ? stat.pipeline_by_currency
            .map((r) => money(Number(r.amount), r.currency))
            .join(" / ") || "0"
        : undefined,
      detail: "Open pipeline · by currency",
      icon: BarChart3,
      tone: "blue",
      path: "open-deals",
    },
    {
      title: "Win rate",
      value: stat?.win_rate == null ? undefined : `${stat.win_rate}%`,
      detail: stat
        ? `${stat.won_deals} won / ${stat.lost_deals} lost`
        : "Closed deals in period",
      icon: Trophy,
      tone: "gold",
      path: "reports",
    },
    {
      title: "Overdue follow-ups",
      value: stat?.overdue_followups,
      detail: "Active lead and task commitments",
      icon: CalendarDays,
      tone: "rose",
      path: "overdue",
    },
  ];
  const days = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const offset = (month.getDay() + 6) % 7;
  const today = new Date();
  return (
    <main className="crm-reference">
      <header className="crm-ref-heading">
        <div>
          <h1>
            CRM Dashboard{" "}
            <span className="crm-ref-live">
              <i />
              {p.loading ? "Refreshing" : stat ? "Updated" : "Unavailable"}
            </span>
          </h1>
          <p>
            Your sales priorities, upcoming commitments and pipeline
            performance.
          </p>
        </div>
        <div className="crm-ref-actions">
          <select
            aria-label="Dashboard range"
            value={p.range}
            onChange={(e) => p.onRange(e.target.value as Props["range"])}
          >
            <option value="month">This month</option>
            <option value="quarter">This quarter</option>
            <option value="all">All data</option>
          </select>
          <button onClick={() => navigate("/crm/reports")}>
            <BarChart3 />
            Reports
          </button>
          <button onClick={() => navigate("/crm/forecasting")}>
            <Target />
            Forecast
          </button>
          <button className="primary" onClick={() => p.onCreate("leads")}>
            <Plus />
            Create
          </button>
        </div>
      </header>
      {p.error && (
        <p className="crm-ref-error" role="alert">
          {p.error}
        </p>
      )}
      <div className="crm-ref-layout">
        <div className="crm-ref-main">
          <section className="crm-ref-metrics" aria-label="CRM metrics">
            {metrics.map((m) => (
              <button
                key={m.title}
                className={`crm-ref-metric ${m.tone}`}
                onClick={() =>
                  navigate(
                    m.path === "reports"
                      ? "/crm/reports"
                      : `/crm/statistics/${m.path}?period=${p.range}`,
                  )
                }
              >
                <span className="crm-ref-metric-icon">
                  <m.icon />
                </span>
                <div>
                  <span>{m.title}</span>
                  <strong>{m.value ?? (p.loading ? "…" : "—")}</strong>
                  <small>{m.detail}</small>
                </div>
                <svg
                  viewBox="0 0 240 45"
                  preserveAspectRatio="none"
                  aria-hidden="true"
                >
                  <path d="M0 25 Q20 0 40 20 T95 27 T150 30 T200 30 T240 22 V45 H0Z" />
                </svg>
              </button>
            ))}
          </section>
          <ModuleWorkflowBoard module="crm" />
          <div className="crm-ref-analysis">
            <section className="crm-ref-panel">
              <div className="crm-ref-panel-heading">
                <h2>
                  <BarChart3 />
                  Forecast and sales analysis
                </h2>
                {currencies.length > 1 && (
                  <select
                    aria-label="Chart currency"
                    value={currency}
                    onChange={(e) => setChartCurrency(e.target.value)}
                  >
                    {currencies.map((c) => (
                      <option key={c}>{c}</option>
                    ))}
                  </select>
                )}
              </div>
              <div className="crm-ref-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chart}>
                    <CartesianGrid vertical={false} stroke="var(--crm-line)" />
                    <XAxis
                      dataKey="month"
                      axisLine={false}
                      tickLine={false}
                      fontSize={10}
                    />
                    <YAxis
                      width={48}
                      tickFormatter={(v) =>
                        Intl.NumberFormat("en-IN", {
                          notation: "compact",
                        }).format(v)
                      }
                      axisLine={false}
                      tickLine={false}
                      fontSize={10}
                    />
                    <Tooltip
                      formatter={(v, name) =>
                        name === "Win rate"
                          ? `${v}%`
                          : money(Number(v), currency)
                      }
                    />
                    <Bar
                      isAnimationActive={false}
                      name="Won revenue"
                      dataKey="won"
                      fill="#9560fa"
                      radius={[3, 3, 0, 0]}
                    />
                    <Bar
                      isAnimationActive={false}
                      name="Open pipeline"
                      dataKey="open"
                      fill="#d0baff"
                      radius={[3, 3, 0, 0]}
                    />
                    <YAxis
                      yAxisId="rate"
                      orientation="right"
                      domain={[0, 100]}
                      hide
                    />
                    <Line
                      yAxisId="rate"
                      type="monotone"
                      dataKey="winRate"
                      name="Win rate"
                      stroke="#28b443"
                      strokeWidth={2}
                      isAnimationActive={false}
                      connectNulls={false}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
              <p className="crm-ref-chart-caption">
                <i />
                Won revenue <i />
                Open pipeline · {currency}{" "}
                <i style={{ background: "#28b443" }} /> Win rate
              </p>
            </section>
            <section className="crm-ref-panel">
              <div className="crm-ref-panel-heading">
                <h2>
                  <Users />
                  Leads by source
                </h2>
              </div>
              <div className="crm-ref-sources">
                <div className="crm-ref-donut">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        isAnimationActive={false}
                        data={sources}
                        dataKey="value"
                        nameKey="name"
                        innerRadius="65%"
                        outerRadius="95%"
                        paddingAngle={1}
                      >
                        {sources.map((s, i) => (
                          <Cell key={s.name} fill={colors[i % colors.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                  <div>
                    <strong>{stat ? total : "—"}</strong>
                    <small>Total Leads</small>
                  </div>
                </div>
                <div className="crm-ref-legend">
                  {sources.map((s, i) => (
                    <div key={s.name}>
                      <i style={{ background: colors[i % colors.length] }} />
                      <span>{s.name}</span>
                      <b>{total ? Math.round((s.value / total) * 100) : 0}%</b>
                      <small>({s.value})</small>
                    </div>
                  ))}
                  {!sources.length && <p>No lead sources for this period.</p>}
                </div>
              </div>
            </section>
          </div>
          <section className="crm-ref-panel">
            <div className="crm-ref-panel-heading">
              <h2>
                <Briefcase />
                Projects & tasks (PMS)
              </h2>
              <button onClick={() => navigate("/pms")}>
                View PMS <ChevronRight />
              </button>
            </div>
            <div className="crm-ref-pms">
              {[
                ["Active projects", portfolio?.active_projects],
                ["Total projects", portfolio?.total_projects],
                [
                  "Open CRM tasks",
                  p.tasks.filter(
                    (t) =>
                      !/completed|cancelled|done/i.test(String(t.status || "")),
                  ).length,
                ],
                [
                  "Completed CRM tasks",
                  p.tasks.filter((t) =>
                    /completed|done/i.test(String(t.status || "")),
                  ).length,
                ],
              ].map(([label, value]) => (
                <button
                  key={String(label)}
                  onClick={() =>
                    navigate(
                      String(label).includes("CRM")
                        ? "/crm/tasks"
                        : "/pms/projects",
                    )
                  }
                >
                  <Briefcase />
                  <span>
                    <strong>{value ?? "—"}</strong>
                    <small>{label}</small>
                  </span>
                </button>
              ))}
            </div>
          </section>
        </div>
        <aside className="crm-ref-aside">
          <section className="crm-ref-panel">
            <div className="crm-ref-panel-heading">
              <h2>
                <Sparkles />
                Smart briefing
              </h2>
              <Sparkles size={15} />
            </div>
            <div className="crm-ref-briefing">
              {p.briefing.map((row) => (
                <button key={row.title} onClick={() => navigate(row.path)}>
                  <span className="crm-ref-brief-icon">
                    <Target />
                  </span>
                  <span>
                    <strong>{row.title}</strong>
                    <small>{row.reason}</small>
                  </span>
                  <b>{row.action}</b>
                </button>
              ))}
              {!p.briefing.length && (
                <p className="crm-ref-empty">
                  {p.loading
                    ? "Loading sales insights…"
                    : p.error
                      ? "Sales insights are unavailable."
                      : "You're all caught up. No items need attention."}
                </p>
              )}
            </div>
          </section>
          <section className="crm-ref-panel">
            <div className="crm-ref-panel-heading">
              <h2>
                <CalendarDays />
                Today
              </h2>
              <button onClick={() => navigate("/crm/calendar")}>
                Calendar <ChevronRight />
              </button>
            </div>
            <div className="crm-ref-today">
              {p.today.slice(0, 4).map((row) => (
                <button key={row.id} onClick={() => navigate(row.path)}>
                  <CheckSquare />
                  <strong>{row.title}</strong>
                  <small>{row.time}</small>
                  {row.overdue && <b>Overdue</b>}
                </button>
              ))}
              {!p.today.length && (
                <p className="crm-ref-empty">
                  {p.error
                    ? "Today’s commitments are unavailable."
                    : "No commitments scheduled for today."}
                </p>
              )}
            </div>
            <div className="crm-ref-calendar-wrap">
              <div className="crm-ref-calendar">
                <div className="crm-ref-calendar-heading">
                  <button
                    aria-label="Previous month"
                    onClick={() =>
                      setMonth(
                        new Date(month.getFullYear(), month.getMonth() - 1, 1),
                      )
                    }
                  >
                    <ChevronLeft />
                  </button>
                  <strong>
                    {month.toLocaleDateString(undefined, {
                      month: "long",
                      year: "numeric",
                    })}
                  </strong>
                  <button
                    aria-label="Next month"
                    onClick={() =>
                      setMonth(
                        new Date(month.getFullYear(), month.getMonth() + 1, 1),
                      )
                    }
                  >
                    <ChevronRight />
                  </button>
                </div>
                <div className="crm-ref-days">
                  {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(
                    (d) => (
                      <small key={d}>{d}</small>
                    ),
                  )}
                  {Array.from({ length: offset }, (_, i) => (
                    <span key={`blank-${i}`} />
                  ))}
                  {Array.from({ length: days }, (_, i) => {
                    const d = i + 1;
                    const date = new Date(
                      month.getFullYear(),
                      month.getMonth(),
                      d,
                    );
                    const marked = monthEvents.some(
                      (e) =>
                        new Date(e.start).toDateString() ===
                        date.toDateString(),
                    );
                    return (
                      <button
                        key={d}
                        className={`${date.toDateString() === today.toDateString() ? "selected" : ""} ${marked ? "has-event" : ""}`}
                        onClick={() =>
                          navigate(
                            `/crm/calendar?date=${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`,
                          )
                        }
                      >
                        {d}
                      </button>
                    );
                  })}
                </div>
              </div>
              <div className="crm-ref-month">
                <strong>
                  {month.toLocaleDateString(undefined, { month: "short" })}{" "}
                  overview
                </strong>
                {calendarError && <p role="status">{calendarError}</p>}
                {[
                  ["Meetings", CalendarDays],
                  ["Calls", Phone],
                  ["Follow-ups", CheckSquare],
                  ["Demos", Folder],
                ].map(([label, Icon]) => {
                  const Glyph = Icon as typeof Folder;
                  const count = monthEvents.filter((e) => {
                    const d = new Date(e.start);
                    return (
                      d.getMonth() === month.getMonth() &&
                      d.getFullYear() === month.getFullYear() &&
                      e.type
                        .toLowerCase()
                        .includes(String(label).toLowerCase().replace(/s$/, ""))
                    );
                  }).length;
                  return (
                    <button
                      key={String(label)}
                      onClick={() => navigate("/crm/calendar")}
                    >
                      <Glyph />
                      <span>
                        <b>{calendarError ? "\u2014" : count}</b>{" "}
                        {String(label)}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          </section>
          <section className="crm-ref-panel">
            <div className="crm-ref-panel-heading">
              <h2>
                <Zap />
                Quick actions
              </h2>
            </div>
            <div className="crm-ref-quick">
              {[
                ["New lead", Users, "leads"],
                ["New deal", Handshake, "deals"],
                ["New task", CheckSquare, "tasks"],
                ["New project", Folder, "project"],
              ].map(([label, Icon, kind]) => {
                const Glyph = Icon as typeof Users;
                return (
                  <button
                    key={String(label)}
                    onClick={() =>
                      kind === "project"
                        ? navigate("/pms/projects/new")
                        : p.onCreate(kind as "leads" | "deals" | "tasks")
                    }
                  >
                    <Glyph />
                    {String(label)}
                  </button>
                );
              })}
            </div>
          </section>
        </aside>
      </div>
      <details className="crm-ref-definition">
        <summary>Data scope & metric definitions</summary>
        <p>
          {stat?.context.definition || "Statistics are unavailable."}{" "}
          {stat &&
            `Updated ${new Date(stat.context.as_of).toLocaleString()} · ${stat.context.timezone}.`}{" "}
          Deal previews and charts use the first 100 permitted records; metric
          cards use full-dataset statistics. Calendar markers and counts cover
          the displayed month.
        </p>
      </details>
    </main>
  );
}
