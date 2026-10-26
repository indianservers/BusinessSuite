import { RichTextContent } from "@/components/rich-text/RichTextContent";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Funnel,
  FunnelChart,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  RadialBar,
  RadialBarChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  Treemap,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import {
  AlertCircle,
  ArrowUpRight,
  CalendarDays,
  CheckCircle2,
  Clock3,
  Link2,
  RefreshCw,
} from "lucide-react";
import { StatusBadge } from "@/design-system/components";
import {
  formatMetric,
  type Widget,
  type WidgetData,
  type Row,
  type Spec,
} from "./model";
const colors = [
  "#6d3df5",
  "#1673f9",
  "#0b9d78",
  "#eaa12c",
  "#ea5275",
  "#7c8ba5",
  "#09a8b2",
  "#af6acb",
];
const axis = {
  tick: { fontSize: 11, fill: "hsl(var(--muted-foreground))" },
  axisLine: false,
  tickLine: false,
};
const tooltipStyle = {
  background: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 9,
  color: "hsl(var(--foreground))",
};
function MarkdownNote({ text }: { text: string }) {
  const inline = (line: string) =>
    line
      .split(/(\*\*[^*]+\*\*|_[^_]+_|`[^`]+`)/g)
      .map((part, i) =>
        part.startsWith("**") ? (
          <strong key={i}>{part.slice(2, -2)}</strong>
        ) : part.startsWith("_") ? (
          <em key={i}>{part.slice(1, -1)}</em>
        ) : part.startsWith("`") ? (
          <code key={i}>{part.slice(1, -1)}</code>
        ) : (
          part
        ),
      );
  return (
    <div className="db-notes">
      {text.split("\n").map((line, i) =>
        line.startsWith("## ") ? (
          <h4 key={i}>{inline(line.slice(3))}</h4>
        ) : line.startsWith("# ") ? (
          <h3 key={i}>{inline(line.slice(2))}</h3>
        ) : line.startsWith("- ") ? (
          <ul key={i}>
            <li>{inline(line.slice(2))}</li>
          </ul>
        ) : (
          <p key={i}>{inline(line) || "\u00a0"}</p>
        ),
      )}
    </div>
  );
}
export function DataTable({
  rows,
  source = "tasks",
}: {
  rows: Row[];
  source?: string;
}) {
  if (!rows.length) return <Empty />;
  return (
    <div className="db-table-scroll">
      <table className="db-data-table">
        <thead>
          <tr>
            <th>{source === "projects" ? "Project" : "Record"}</th>
            <th>Status</th>
            <th>{source === "projects" ? "Progress" : "Assignee"}</th>
            <th>Due date</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={String(row.id ?? i)}>
              <td>
                {row.url ? (
                  <Link to={row.url}>{row.title || row.name}</Link>
                ) : (
                  row.name
                )}
              </td>
              <td>
                <StatusBadge value={row.status || "Unspecified"} />
              </td>
              <td>
                {row.progress != null
                  ? `${row.progress}%`
                  : row.assignees?.join(", ") || "—"}
              </td>
              <td>{row.due_date || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function Empty({
  message = "No matching data yet.",
}: {
  message?: string;
}) {
  return (
    <div className="db-empty">
      <CalendarDays size={24} />
      <p>{message}</p>
    </div>
  );
}
export default function WidgetContent({
  widget,
  spec,
  data,
  onDrill,
  onRetry,
}: {
  widget: Widget;
  spec: Spec;
  data?: WidgetData;
  onDrill: (label?: string) => void;
  onRetry: () => void;
}) {
  const [hidden, setHidden] = useState<string[]>([]);
  const [calendarOffset, setCalendarOffset] = useState(0);
  if (!data)
    return (
      <div role="status" className="db-widget-skeleton">
        Loading widget…
      </div>
    );
  if (data.state !== "ready")
    return (
      <div
        className="db-widget-unavailable"
        role={data.state === "error" ? "alert" : "status"}
      >
        <AlertCircle size={20} />
        <div><RichTextContent value={data.message}/></div>
        {data.state === "error" && (
          <button onClick={onRetry}>
            <RefreshCw size={14} />
            Retry widget
          </button>
        )}
      </div>
    );
  const type = spec.view;
  const rows = data.rows || [];
  const original = data.series || [];
  const series = original.filter((row) => !hidden.includes(row.name));
  const tip = widget.tooltips ? <Tooltip contentStyle={tooltipStyle} /> : null;
  const grid = widget.gridlines ? (
    <CartesianGrid
      strokeDasharray="3 3"
      stroke="hsl(var(--border))"
      vertical={false}
    />
  ) : null;
  const legend = (keys: string[]) =>
    widget.legend ? (
      <Legend
        onClick={(event: any) => {
          const key = String(event.dataKey || event.value);
          setHidden((current) =>
            current.includes(key)
              ? current.filter((k) => k !== key)
              : [...current, key],
          );
        }}
        wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
      />
    ) : null;
  if (type === "metric")
    return (
      <button
        className="db-metric-body"
        onClick={() => onDrill()}
        aria-label={`View records for ${widget.title}`}
      >
        <strong>{formatMetric(data.value, widget)}</strong>
        {data.change != null ? (
          <span className={data.change >= 0 ? "db-positive" : "db-negative"}>
            {data.change >= 0 ? "+" : ""}
            {data.change.toFixed(1)}% <small>vs previous period</small>
          </span>
        ) : (
          <small>
            {widget.comparison
              ? "Comparison needs a date range and nonzero previous period."
              : data.message}
          </small>
        )}
      </button>
    );
  if (type === "notes")
    return (
      <MarkdownNote text={widget.notes || "Add a note in widget settings."} />
    );
  if (type === "image")
    return widget.url ? (
      <img
        className="db-image"
        src={widget.url}
        alt={widget.description || widget.title}
        referrerPolicy="no-referrer"
      />
    ) : (
      <Empty message="Add an HTTPS image URL in settings." />
    );
  if (type === "bookmark")
    return widget.url ? (
      <a
        className="db-bookmark"
        href={widget.url}
        target="_blank"
        rel="noopener noreferrer"
      >
        <Link2 size={24} />
        <strong>{widget.title}</strong>
        <span>{new URL(widget.url).hostname}</span>
        <ArrowUpRight size={16} />
      </a>
    ) : (
      <Empty message="Add an HTTPS link in settings." />
    );
  if (type === "table" && data.series)
    return (
      <div className="db-table-scroll">
        <table className="db-data-table">
          <thead>
            <tr>
              <th>Group</th>
              <th>Value</th>
              <th>Records</th>
            </tr>
          </thead>
          <tbody>
            {series.map((row) => (
              <tr key={row.name}>
                <td>
                  <button onClick={() => onDrill(row.name)}>{row.name}</button>
                </td>
                <td>{Number(row.value).toLocaleString()}</td>
                <td>{row.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  if (type === "table")
    return (
      <>
        <DataTable
          rows={
            rows.length
              ? rows
              : series.map((r, i) => ({
                  ...r,
                  id: i,
                  title: r.name,
                  status: "",
                  assignees: [String(r.value)],
                }))
          }
          source={widget.source}
        />
        {data.total != null && data.total > rows.length && (
          <small className="db-data-note">
            Showing {rows.length} of {data.total} matching records. Increase the
            widget limit to show more.
          </small>
        )}
      </>
    );
  if (type === "timeline") {
    const dated = rows.filter(
      (r) => r.start_date && r.due_date && r.start_date <= r.due_date,
    );
    if (!dated.length)
      return (
        <Empty message="Set project start and due dates to see a timeline." />
      );
    const first = Math.min(
        ...dated.map((r) => Date.parse(r.start_date + "T12:00:00Z")),
      ),
      last = Math.max(
        ...dated.map((r) => Date.parse(r.due_date + "T12:00:00Z")),
      );
    const span = Math.max(86400000, last - first);
    return (
      <div className="db-timeline">
        <small>
          {new Date(first).toLocaleDateString()} —{" "}
          {new Date(last).toLocaleDateString()}
        </small>
        {dated.map((r) => (
          <a href={r.url} key={r.id}>
            <strong>{r.title}</strong>
            <div>
              <i
                style={{
                  marginLeft: `${((Date.parse(r.start_date + "T12:00:00Z") - first) / span) * 100}%`,
                  width: `${Math.max(1, ((Date.parse(r.due_date + "T12:00:00Z") - Date.parse(r.start_date + "T12:00:00Z")) / span) * 100)}%`,
                  background: widget.color,
                }}
              />
            </div>
            <small>
              {r.start_date} → {r.due_date}
            </small>
          </a>
        ))}
      </div>
    );
  }
  if (type === "calendar") {
    const now = new Date();
    const month = new Date(
      now.getFullYear(),
      now.getMonth() + calendarOffset,
      1,
    );
    const first = new Date(month);
    first.setDate(1 - first.getDay());
    const iso = (date: Date) =>
      `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
    return (
      <div className="db-calendar">
        <header>
          <button
            aria-label="Previous calendar month"
            onClick={() => setCalendarOffset((v) => v - 1)}
          >
            ‹
          </button>
          <strong>
            {month.toLocaleDateString(undefined, {
              month: "long",
              year: "numeric",
            })}
          </strong>
          <button
            aria-label="Next calendar month"
            onClick={() => setCalendarOffset((v) => v + 1)}
          >
            ›
          </button>
        </header>
        <div>
          {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => (
            <small key={day}>{day}</small>
          ))}
          {Array.from({ length: 42 }, (_, i) => {
            const date = new Date(first);
            date.setDate(date.getDate() + i);
            return (
              <section
                key={i}
                data-outside={date.getMonth() !== month.getMonth()}
              >
                <small>{date.getDate()}</small>
                {rows
                  .filter((r) => r.due_date === iso(date))
                  .map((r) => (
                    <Link to={r.url} key={r.id} title={r.title}>
                      {r.title}
                    </Link>
                  ))}
              </section>
            );
          })}
        </div>
      </div>
    );
  }
  if (type === "progress")
    return rows.length ? (
      <div className="db-progress-list">
        {rows.map((row, i) => (
          <Link key={row.id} to={row.url}>
            <div>
              <strong>{row.title}</strong>
              <span>
                {row.progress != null ? `${row.progress}%` : row.status}
              </span>
            </div>
            {row.progress != null && (
              <div className="db-progress-track">
                <i
                  style={{
                    width: `${Math.max(0, Math.min(100, row.progress))}%`,
                    background: colors[i % colors.length],
                  }}
                />
              </div>
            )}
            <small>{row.health || "Project progress"}</small>
          </Link>
        ))}
      </div>
    ) : (
      <Empty />
    );
  if (type === "deadlines")
    return rows.length ? (
      <div className="db-deadlines">
        {rows.map((row) => (
          <Link key={row.id} to={row.url}>
            <time dateTime={row.due_date}>
              <small>
                {new Date(row.due_date + "T12:00:00").toLocaleDateString(
                  undefined,
                  { month: "short" },
                )}
              </small>
              <strong>{new Date(row.due_date + "T12:00:00").getDate()}</strong>
            </time>
            <span>
              <strong>{row.title}</strong>
              <small>{row.project}</small>
            </span>
            <StatusBadge value={row.priority} />
          </Link>
        ))}
      </div>
    ) : (
      <Empty message="No upcoming deadlines in this scope." />
    );
  if (type === "activity")
    return rows.length ? (
      <div className="db-activity">
        {rows.map((row) => (
          <article key={row.id}>
            <i />
            <div>
              <strong>{row.actor}</strong>
              <p>{row.title}</p>
              <time>{new Date(row.created_at).toLocaleString()}</time>
              {row.task_id && (
                <Link to={`/pms/tasks/${row.task_id}`}>Open task</Link>
              )}
            </div>
          </article>
        ))}
      </div>
    ) : (
      <Empty message="No recorded activity in this scope." />
    );
  if (type === "sprints")
    return rows.length ? (
      <div className="db-progress-list">
        {rows.map((row, i) => (
          <div key={row.id}>
            <strong>{row.title}</strong>
            <StatusBadge value={row.status} />
            <div className="db-progress-track">
              <i
                style={{
                  width: `${row.committed ? Math.min(100, (row.completed / row.committed) * 100) : 0}%`,
                  background: colors[i % colors.length],
                }}
              />
            </div>
            <small>
              {row.completed || 0} completed / {row.committed || 0} committed
              story points
            </small>
          </div>
        ))}
      </div>
    ) : (
      <Empty message="No visible sprints. Configure sprint commitments to track progress." />
    );
  if (type === "radial" || type === "gauge") {
    const value = data.value;
    if (value == null)
      return <Empty message="No eligible records for this percentage." />;
    return (
      <div
        className="db-chart"
        role="img"
        aria-label={`${widget.title}: ${value}%`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            innerRadius="65%"
            outerRadius="90%"
            data={[{ value, fill: widget.color }]}
            startAngle={type === "gauge" ? 180 : 90}
            endAngle={type === "gauge" ? 0 : -270}
          >
            <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
            <RadialBar background dataKey="value" cornerRadius={8} />
            {tip}
            <text
              x="50%"
              y="50%"
              textAnchor="middle"
              dominantBaseline="middle"
              fill="hsl(var(--foreground))"
              fontSize={28}
              fontWeight={700}
            >
              {value}%
            </text>
          </RadialBarChart>
        </ResponsiveContainer>
      </div>
    );
  }
  if (!series.length) return <Empty />;
  const chartProps = {
    data: series,
    margin: { top: 12, right: 16, bottom: 5, left: 0 },
  };
  const onClick = (row: any) => onDrill(row?.name || row?.payload?.name);
  let chart: React.ReactNode;
  if (["pie", "donut", "health"].includes(type)) {
    const total = series.reduce((n, r) => n + Number(r.value || 0), 0);
    return (
      <div className="db-donut-wrap">
        <div
          className="db-chart"
          role="img"
          aria-label={`${widget.title}: ${total} records`}
        >
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={series}
                nameKey="name"
                dataKey="value"
                innerRadius={type === "pie" ? 0 : "60%"}
                outerRadius="85%"
                paddingAngle={2}
                onClick={onClick}
                label={widget.labels}
              >
                {series.map((r, i) => (
                  <Cell
                    key={r.name}
                    fill={colors[i % colors.length]}
                    aria-label={`${r.name}: ${r.value}`}
                  />
                ))}
              </Pie>
              {tip}
              {type !== "pie" && (
                <text
                  x="50%"
                  y="50%"
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fill="hsl(var(--foreground))"
                  fontWeight={750}
                  fontSize={28}
                >
                  {total}
                </text>
              )}
            </PieChart>
          </ResponsiveContainer>
        </div>
        {widget.legend && (
          <div className="db-donut-legend">
            {original.map((row, i) => (
              <button
                key={row.name}
                aria-pressed={!hidden.includes(row.name)}
                onClick={() =>
                  setHidden((current) =>
                    current.includes(row.name)
                      ? current.filter((v) => v !== row.name)
                      : [...current, row.name],
                  )
                }
              >
                <i style={{ background: colors[i % colors.length] }} />
                <span>{row.name}</span>
                <strong>{row.value}</strong>
                <small>
                  {total ? Math.round((row.value / total) * 100) : 0}%
                </small>
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }
  if (type === "heatmap")
    return (
      <div className="db-heatmap">
        {series.map((row) => (
          <button
            key={row.name}
            onClick={() => onDrill(row.name)}
            style={{
              background: `color-mix(in srgb, ${widget.color} ${Math.round(10 + (row.value / Math.max(1, ...series.map((r) => r.value))) * 65)}%, hsl(var(--card)))`,
            }}
          >
            <strong>{row.name}</strong>
            <span>{row.value}</span>
          </button>
        ))}
      </div>
    );
  if (type === "treemap")
    chart = (
      <Treemap
        data={series}
        nameKey="name"
        dataKey="value"
        stroke="hsl(var(--card))"
        fill={widget.color}
      >
        {tip}
      </Treemap>
    );
  else if (type === "funnel")
    chart = (
      <FunnelChart>
        <Funnel data={series} nameKey="name" dataKey="value" onClick={onClick}>
          {series.map((r, i) => (
            <Cell
              key={r.name}
              fill={colors[i % colors.length]}
              aria-label={`${r.name}: ${r.value}`}
            />
          ))}
        </Funnel>
        {tip}
        {widget.legend && <Legend />}
      </FunnelChart>
    );
  else if (type === "radar")
    chart = (
      <RadarChart {...chartProps} outerRadius="75%">
        <PolarGrid stroke="hsl(var(--border))" />
        <PolarAngleAxis
          dataKey="name"
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
        />
        <PolarRadiusAxis />
        <Radar
          dataKey="value"
          stroke={widget.color}
          fill={widget.color}
          fillOpacity={0.22}
        />
        {tip}
      </RadarChart>
    );
  else if (type === "scatter" || type === "bubble")
    chart = (
      <ScatterChart margin={{ top: 12, right: 18, left: 0, bottom: 6 }}>
        {grid}
        <XAxis {...axis} type="number" dataKey="x" name="Estimated hours" />
        <YAxis {...axis} type="number" dataKey="y" name="Actual hours" />
        {type === "bubble" && (
          <ZAxis dataKey="z" name="Story points" range={[30, 350]} />
        )}
        <Scatter
          data={series}
          fill={widget.color}
          onClick={(r: any) =>
            r.id
              ? window.open(`/pms/tasks/${r.id}`, "_blank", "noopener")
              : onDrill()
          }
        />
        {tip}
      </ScatterChart>
    );
  else if (type === "trend") {
    chart = (
      <AreaChart {...chartProps}>
        {grid}
        <XAxis {...axis} dataKey="name" minTickGap={22} />
        <YAxis {...axis} allowDecimals={false} />
        {tip}
        {legend(["created", "completed"])}
        {!hidden.includes("created") && (
          <Area
            name="Created"
            type="monotone"
            dataKey="created"
            stroke={widget.color}
            fill={widget.color}
            fillOpacity={0.1}
          />
        )}{" "}
        {!hidden.includes("completed") && (
          <Area
            name="Completed"
            type="monotone"
            dataKey="completed"
            stroke="#0b9d78"
            fill="#0b9d78"
            fillOpacity={0.1}
          />
        )}
      </AreaChart>
    );
  } else if (type === "waterfall") {
    let running = 0;
    const values = series.map((r) => {
      const start = running;
      running += r.value;
      return {
        ...r,
        range: [Math.min(start, running), Math.max(start, running)],
      };
    });
    chart = (
      <BarChart {...chartProps} data={values}>
        {grid}
        <XAxis {...axis} dataKey="name" />
        <YAxis {...axis} />
        {tip}
        <Bar
          dataKey="range"
          name="Running total contributions"
          fill={widget.color}
          radius={[4, 4, 0, 0]}
        />
      </BarChart>
    );
  } else if (type === "pareto") {
    const sum = series.reduce((n, r) => n + r.value, 0);
    if (series.some((r) => r.value < 0))
      return <Empty message="Pareto requires non-negative values." />;
    let total = 0;
    const values = [...series]
      .sort((a, b) => b.value - a.value)
      .map((r) => {
        total += r.value;
        return { ...r, cumulative: sum ? (total / sum) * 100 : 0 };
      });
    chart = (
      <ComposedChart {...chartProps} data={values}>
        {grid}
        <XAxis {...axis} dataKey="name" />
        <YAxis {...axis} />
        <YAxis
          {...axis}
          yAxisId="percent"
          orientation="right"
          domain={[0, 100]}
        />
        {tip}
        <Bar dataKey="value" fill={widget.color} />
        <Line
          yAxisId="percent"
          dataKey="cumulative"
          name="Cumulative %"
          stroke="#eaa12c"
        />
      </ComposedChart>
    );
  } else if (type === "combo")
    chart = (
      <ComposedChart {...chartProps}>
        {grid}
        <XAxis {...axis} dataKey="name" />
        <YAxis {...axis} />
        {tip}
        {legend(["value", "completed"])}
        <Bar dataKey="value" name="Total" fill={widget.color} />
        <Line dataKey="completed" name="Completed" stroke="#0b9d78" />
      </ComposedChart>
    );
  else if (type === "line" || type === "area" || type === "smooth_area") {
    const C = type === "line" ? LineChart : AreaChart;
    chart = (
      <C {...chartProps}>
        {grid}
        <XAxis {...axis} dataKey="name" minTickGap={15} />
        <YAxis {...axis} />
        {tip}
        {type === "line" ? (
          <Line
            type="linear"
            dataKey="value"
            stroke={widget.color}
            strokeWidth={2}
            dot={{ r: 3 }}
            onClick={onClick}
          />
        ) : (
          <Area
            type={type === "smooth_area" ? "monotone" : "linear"}
            dataKey="value"
            stroke={widget.color}
            fill={widget.color}
            fillOpacity={0.12}
          />
        )}
      </C>
    );
  } else {
    const stacked = ["stacked_bar", "percent_bar"].includes(type);
    const grouped = stacked || type === "grouped_bar" || type === "commitment";
    chart = (
      <BarChart
        {...chartProps}
        layout={type === "horizontal_bar" ? "vertical" : "horizontal"}
        stackOffset={type === "percent_bar" ? "expand" : "none"}
      >
        {grid}
        <XAxis
          {...axis}
          type={type === "horizontal_bar" ? "number" : "category"}
          dataKey={type === "horizontal_bar" ? undefined : "name"}
        />
        <YAxis
          {...axis}
          type={type === "horizontal_bar" ? "category" : "number"}
          dataKey={type === "horizontal_bar" ? "name" : undefined}
          width={type === "horizontal_bar" ? 95 : 40}
        />
        {tip}
        {grouped ? (
          <>
            <Bar
              name={type === "commitment" ? "Committed points" : "Open"}
              dataKey={type === "commitment" ? "committed" : "open"}
              stackId={stacked ? "total" : undefined}
              fill={widget.color}
            />
            <Bar
              name="Completed"
              dataKey="completed"
              stackId={stacked ? "total" : undefined}
              fill="#0b9d78"
            />
          </>
        ) : (
          <Bar
            dataKey="value"
            fill={widget.color}
            radius={[4, 4, 0, 0]}
            onClick={onClick}
          />
        )}{" "}
        {grouped && widget.legend && <Legend wrapperStyle={{ fontSize: 11 }} />}
      </BarChart>
    );
  }
  return (
    <div
      className="db-chart"
      role="img"
      aria-label={`${widget.title}. ${series.length} data groups. Use View data for accessible records.`}
    >
      <ResponsiveContainer width="100%" height="100%">
        {chart as React.ReactElement}
      </ResponsiveContainer>
    </div>
  );
}
