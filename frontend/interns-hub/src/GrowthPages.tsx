import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  BarChart3,
  Trophy,
  CheckCircle2,
  Send,
  CalendarDays,
  MessageCircle,
  BookOpen,
  Check,
  ExternalLink,
  SquareCheck,
  Clock,
  Play,
} from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  BarChart,
  Bar,
} from "recharts";
import { hub, send } from "./api";
import {
  useHub,
  Row,
  Badge,
  Empty,
  Card,
  Ring,
  Stat,
  Heading,
  Hero,
  initials,
  formatDate,
  localDay,
  time,
} from "./ui";
export function Analytics() {
  const { data } = useHub();
  const [period, setPeriod] = useState("week");
  const days = period === "week" ? 7 : period === "month" ? 30 : 3650;
  const since = Date.now() - days * 86400000;
  const submissions = data.submissions
    .filter(
      (s) => s.score !== null && new Date(s.reviewed_at).getTime() >= since,
    )
    .slice()
    .reverse();
  const categories = Array.from(new Set(data.tasks.map((t) => t.category))).map(
    (name) => {
      const ids = data.tasks
        .filter((t) => t.category === name)
        .map((t) => t.id);
      const scored = submissions.filter((s) => ids.includes(s.task_id));
      return {
        name,
        score: scored.length
          ? Math.round(scored.reduce((n, s) => n + s.score, 0) / scored.length)
          : 0,
      };
    },
  );
  return (
    <>
      <Heading
        title="Performance Analytics"
        description="Track your progress, discover insights, and keep growing. 📊"
      >
        <div className="tabs">
          {["week", "month", "overall"].map((p) => (
            <button
              key={p}
              className={p === period ? "active" : ""}
              onClick={() => setPeriod(p)}
            >
              {p === "overall" ? "Overall" : `This ${p}`}
            </button>
          ))}
        </div>
      </Heading>
      <div className="stats four">
        <Stat
          icon={Trophy}
          label="Overall Score"
          value={data.overview.score ?? "—"}
          color="orange"
        />
        <Stat
          icon={CheckCircle2}
          label="Tasks Completed"
          value={data.overview.completed}
          color="green"
        />
        <Stat
          icon={Send}
          label="Submission Rate"
          value={`${data.overview.submission_rate}%`}
          color="blue"
        />
        <Stat
          icon={CalendarDays}
          label="Attendance"
          value={`${data.overview.attendance_rate}%`}
        />
      </div>
      <div className="grid-thirds">
        <Card title="Score Trend" icon={BarChart3}>
          <p>Mentor scores for the selected period</p>
          {submissions.length ? (
            <div className="chart">
              <ResponsiveContainer width="100%" height={230}>
                <AreaChart
                  data={submissions.map((s) => ({
                    name: formatDate(s.reviewed_at),
                    score: s.score,
                  }))}
                >
                  <defs>
                    <linearGradient id="score-fill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#5946ff" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#5946ff" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                  <YAxis domain={[0, 100]} width={28} />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="score"
                    stroke="#5141ff"
                    strokeWidth={3}
                    fill="url(#score-fill)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <Empty title="No reviewed scores yet" />
          )}
        </Card>
        <Card title="Category-wise Performance" icon={BarChart3}>
          {categories.length ? (
            <div className="chart">
              <ResponsiveContainer width="100%" height={265}>
                <BarChart data={categories}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                  <YAxis domain={[0, 100]} width={28} />
                  <Tooltip />
                  <Bar dataKey="score" fill="#8064ff" radius={[5, 5, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <Empty title="No categories yet" />
          )}
        </Card>
        <Card title="Task Completion Status">
          <div className="center">
            <Ring value={data.overview.progress} green />
          </div>
          <div className="legend">
            <Badge>Completed</Badge>
            <b>{data.overview.completed}</b>
            <Badge>In Progress</Badge>
            <b>{data.overview.in_progress}</b>
            <Badge>Pending</Badge>
            <b>{data.overview.pending}</b>
          </div>
        </Card>
      </div>
      <div className="grid-main">
        <Card title="Daily Activity" icon={CalendarDays}>
          <div className="heatmap">
            {Array.from({ length: 28 }, (_, i) => {
              const d = new Date();
              d.setDate(d.getDate() - (27 - i));
              const key = d.toLocaleDateString("en-CA");
              const active = data.reports.some(
                (r) => r.report_date === key && r.status === "Submitted",
              );
              return (
                <div
                  key={i}
                  title={`${key}: ${active ? "Report submitted" : "No report"}`}
                  className={active ? "heat active" : "heat"}
                />
              );
            })}
          </div>
          <p className="muted">Daily reports across the last 4 weeks</p>
        </Card>
        <Card title="Mentor Evaluation Summary" icon={MessageCircle}>
          {submissions.length ? (
            <>
              <h2>{data.me.manager || "Your HRMS team"}</h2>
              <p>{submissions.at(-1)?.feedback}</p>
            </>
          ) : (
            <Empty title="Your first review is ahead" />
          )}
        </Card>
      </div>
    </>
  );
}
export function Learning() {
  const { data } = useHub();
  const progress = data.learning.reduce(
    (n, c) => n + c.completed_lessons.length,
    0,
  );
  const total = data.learning.reduce((n, c) => n + (c.lessons || []).length, 0);
  return (
    <>
      <Heading
        title="Learning & Assessments 📚"
        description="Build new skills, complete assessments, and grow into a future-ready professional."
      />
      <div className="grid-main">
        <Hero learning />
        <Card title="My Learning Progress" icon={BarChart3}>
          <div className="progress-layout">
            <Ring value={total ? Math.round((progress * 100) / total) : 0} />
            <div className="progress-list">
              <b>
                {progress} / {total} lessons
              </b>
              <p>Assessments cleared</p>
              <h2>
                {
                  data.learning.filter((c) => c.score !== null && c.score >= 70)
                    .length
                }
              </h2>
              <p>Certificates earned</p>
              <h2>{data.certificates.length}</h2>
            </div>
          </div>
        </Card>
      </div>
      <Card title="Learning Modules" icon={BookOpen}>
        <p>
          Explore curated modules to build in-demand skills for your career.
        </p>
        <div className="course-grid">
          {data.learning.map((c, i) => (
            <div className="course" key={c.id}>
              <span
                className={`stat-icon ${["blue", "green", "pink", "purple"][i % 4]}`}
              >
                <BookOpen size={28} />
              </span>
              <h3>{c.title}</h3>
              <small>
                {c.level} · {c.lessons?.length || 0} Lessons
              </small>
              <progress
                max={Math.max(c.lessons?.length || 0, 1)}
                value={c.completed_lessons.length}
              />
              <p>{c.description}</p>
              <div className="actions">
                <Link to={`/learning/${c.id}`} className="button small">
                  Continue Learning
                </Link>
                <Link
                  to={`/learning/${c.id}#assessment`}
                  className="button soft small"
                >
                  Start Assessment
                </Link>
              </div>
            </div>
          ))}
        </div>
        {!data.learning.length && (
          <Empty title="Your learning journey starts here">
            Your HRMS team can publish courses and assessments for your
            department.
          </Empty>
        )}
      </Card>
    </>
  );
}
export function Course() {
  const { id } = useParams();
  const { data, act, busy } = useHub();
  const course = data.learning.find((c) => c.id === Number(id));
  const [answers, setAnswers] = useState<Record<number, number>>({});
  if (!course) return <Empty title="Course not found" />;
  return (
    <>
      <Link className="back" to="/learning">
        ← All Learning Modules
      </Link>
      <Heading title={course.title} description={course.description} />
      <div className="grid-main">
        <Card title="Lessons" icon={BookOpen}>
          {course.lessons.map((lesson: Row, i: number) => (
            <div className="lesson" key={i}>
              <span className="icon-small">
                {course.completed_lessons.includes(i) ? <Check /> : i + 1}
              </span>
              <div>
                <h3>{lesson.title}</h3>
                <a href={lesson.url} target="_blank" rel="noreferrer">
                  Open resource <ExternalLink size={15} />
                </a>
              </div>
              <button
                className="button soft small"
                disabled={busy || course.completed_lessons.includes(i)}
                onClick={() =>
                  act(
                    () =>
                      hub(
                        `/learning/${id}/progress`,
                        send("POST", { lesson: i }),
                      ),
                    "Lesson marked complete",
                  )
                }
              >
                {course.completed_lessons.includes(i)
                  ? "Completed"
                  : "Mark complete"}
              </button>
            </div>
          ))}
        </Card>
        <Card title="Your Progress">
          <Ring
            value={
              course.lessons.length
                ? Math.round(
                    (course.completed_lessons.length * 100) /
                      course.lessons.length,
                  )
                : 0
            }
          />
          <p>Assessment score: {course.score ?? "Not attempted"}</p>
        </Card>
      </div>
      <div id="assessment">
        <Card title="Assessment" icon={SquareCheck}>
          {course.questions.map((q: Row, i: number) => (
            <fieldset key={i}>
              <legend>
                {i + 1}. {q.prompt}
              </legend>
              {q.options.map((option: string, j: number) => (
                <label className="radio-option" key={j}>
                  <input
                    type="radio"
                    name={`question-${i}`}
                    checked={answers[i] === j}
                    onChange={() => setAnswers({ ...answers, [i]: j })}
                  />
                  {option}
                </label>
              ))}
            </fieldset>
          ))}
          {course.questions.length ? (
            <button
              className="button"
              disabled={
                busy || Object.keys(answers).length !== course.questions.length
              }
              onClick={() =>
                act(
                  () =>
                    hub(
                      `/learning/${id}/progress`,
                      send("POST", {
                        answers: course.questions.map(
                          (_: any, i: number) => answers[i],
                        ),
                      }),
                    ),
                  "Assessment scored",
                )
              }
            >
              Submit Assessment
            </button>
          ) : (
            <p className="muted">
              No assessment has been published for this module.
            </p>
          )}
        </Card>
      </div>
    </>
  );
}
export function Leaderboard() {
  const { data } = useHub();
  return (
    <>
      <Heading
        title="Leaderboard 🏆"
        description="Celebrate progress, see how you rank, and get inspired by your peers!"
      />
      <div className="toolbar">
        <span className="badge purple">Your Department</span>
        <Badge>{data.me.department || "Unassigned"}</Badge>
      </div>
      <div className="grid-main">
        <div className="podium">
          {[1, 0, 2].map((index) => {
            const p = data.leaderboard[index];
            return p ? (
              <Card key={p.id} className={`podium-card rank-${index + 1}`}>
                <span className="rank">{index + 1}</span>
                <Trophy size={28} />
                <div className="avatar large">{initials(p.name)}</div>
                <h2>{p.name}</h2>
                <p>{p.department || "Intern"}</p>
                <strong>
                  {p.score ?? "—"}
                  <small>/100</small>
                </strong>
                <div className="podium-details">
                  <Badge>{p.completed} Tasks</Badge>
                  <Badge>{p.streak} Days</Badge>
                </div>
              </Card>
            ) : null;
          })}
        </div>
        <div className="stack">
          <div className="hero trophy-hero">
            <h2>
              Great Interns
              <br />
              Build Greater Tomorrows.
            </h2>
            <p>Your consistent efforts today are shaping a brighter future!</p>
            <Trophy size={90} />
          </div>
          <Card title="How scores are calculated">
            <p>
              Scores are the average of the latest reviewed submission for each
              task. Rankings break ties by completed tasks.
            </p>
            <p className="muted">
              Only interns in your own HRMS department are shown.
            </p>
          </Card>
        </div>
      </div>
      <Card title="Intern Rankings" icon={Trophy}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {[
                  "#",
                  "Intern",
                  "Department / Track",
                  "Tasks Completed",
                  "Score",
                  "Attendance",
                  "Streak",
                ].map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.leaderboard.map((p, i) => (
                <tr key={p.id} className={p.id === data.me.id ? "you" : ""}>
                  <td>{i + 1}</td>
                  <td>
                    <b>{p.name}</b> {p.id === data.me.id && <Badge>You</Badge>}
                  </td>
                  <td>{p.department || "—"}</td>
                  <td>
                    {p.completed}/{p.total_tasks}
                  </td>
                  <td>
                    <b>★ {p.score ?? "—"}</b>
                  </td>
                  <td>{p.attendance_rate}%</td>
                  <td>🔥 {p.streak} Days</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
export function Attendance() {
  const { data, act, busy } = useHub();
  const [month, setMonth] = useState(localDay().slice(0, 7));
  const records = data.attendance.filter((a) =>
    a.attendance_date.startsWith(month),
  );
  const checked = data.attendance.find((a) => a.attendance_date === localDay());
  const start = new Date(`${month}-01T12:00:00`);
  const offset = start.getDay();
  const total = new Date(
    start.getFullYear(),
    start.getMonth() + 1,
    0,
  ).getDate();
  return (
    <>
      <Heading
        title="Attendance & Activity"
        description="Track your daily presence, work activity and stay consistent on your internship journey."
      >
        <input
          type="month"
          aria-label="Attendance month"
          value={month}
          onChange={(e) => setMonth(e.target.value)}
        />
      </Heading>
      <div className="stats four">
        <Stat
          icon={CheckCircle2}
          color="green"
          label="Present Days"
          value={records.filter((a) => a.status === "Present").length}
          note="In the selected month"
        />
        <Stat
          icon={XIcon}
          color="pink"
          label="Absent Days"
          value={records.filter((a) => a.status === "Absent").length}
        />
        <Stat
          icon={Clock}
          color="orange"
          label="Late Days"
          value={records.filter((a) => a.is_late).length}
        />
        <Stat
          icon={BarChart3}
          label="Attendance Rate"
          value={`${data.overview.attendance_rate}%`}
        />
      </div>
      <div className="grid-main">
        <Card
          title={start.toLocaleDateString("en-IN", {
            month: "long",
            year: "numeric",
          })}
          icon={CalendarDays}
        >
          <div className="calendar">
            {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
              <b key={d}>{d}</b>
            ))}
            {Array.from({ length: offset }, (_, i) => (
              <span key={`blank-${i}`} />
            ))}
            {Array.from({ length: total }, (_, i) => {
              const day = `${month}-${String(i + 1).padStart(2, "0")}`;
              const row = records.find((a) => a.attendance_date === day);
              return (
                <div key={day} className={day === localDay() ? "today" : ""}>
                  <b>{i + 1}</b>
                  <span
                    className={`dot ${row?.status === "Absent" ? "absent" : row?.check_in ? "present" : ""}`}
                  />
                  <small>{row?.status || ""}</small>
                </div>
              );
            })}
          </div>
          <p className="muted">
            ● Green: Present　 ● Red: Absent　 ● Gray: No record
          </p>
        </Card>
        <div className="stack">
          <Card title="Today's Check-in" icon={Clock}>
            <div className="center">
              <Badge>
                {checked?.check_out
                  ? "Checked Out"
                  : checked?.check_in
                    ? "Checked In"
                    : "Ready to begin?"}
              </Badge>
              <div className="large-score">{time(checked?.check_in)}</div>
              <p>
                {checked?.check_out
                  ? `Checked out at ${time(checked.check_out)}`
                  : "Your attendance is synced with HRMS."}
              </p>
              <button
                className="button full"
                disabled={busy || !!checked?.check_out}
                onClick={() =>
                  act(
                    () =>
                      hub(
                        `/attendance/${checked?.check_in ? "check-out" : "check-in"}`,
                        send("POST"),
                      ),
                    checked?.check_in ? "Checked out" : "Checked in",
                  )
                }
              >
                <Play size={18} />
                {checked?.check_out
                  ? "Day completed"
                  : checked?.check_in
                    ? "Check Out"
                    : "Mark Attendance"}
              </button>
            </div>
          </Card>
          <Card title="Working Hours Today" icon={Clock}>
            <div className="large-score">
              {checked?.total_hours ? `${checked.total_hours} hrs` : "—"}
            </div>
            <p>Check-in: {time(checked?.check_in)}</p>
            <p>Check-out: {time(checked?.check_out)}</p>
          </Card>
        </div>
      </div>
      <Card title="Recent Activity Log" icon={Clock}>
        {records.slice(0, 12).map((a) => (
          <div className="list-button" key={a.id}>
            <b>{formatDate(a.attendance_date)}</b>
            <span>
              {time(a.check_in)} – {time(a.check_out)}
            </span>
            <Badge>{a.status}</Badge>
            <span>
              {a.total_hours ? `${a.total_hours} hrs` : "In progress"}
            </span>
          </div>
        ))}
        {!records.length && <Empty title="No attendance for this month" />}
      </Card>
    </>
  );
}
function XIcon() {
  return <span>×</span>;
}
