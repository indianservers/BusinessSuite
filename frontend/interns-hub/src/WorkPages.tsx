import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import {
  FileText,
  CheckCircle2,
  Trophy,
  Flame,
  BarChart3,
  MessageCircle,
  Clock,
  Star,
  Upload,
  Target,
  ArrowRight,
  Save,
  Send,
  Paperclip,
  X,
  BookOpen,
  Sparkles,
} from "lucide-react";
import { hub, send, download } from "./api";
import {
  useHub,
  Row,
  Badge,
  Empty,
  Card,
  Stat,
  Heading,
  Hero,
  TaskTable,
  ProgressCard,
  formatDate,
  localDay,
  time,
} from "./ui";
export function Dashboard() {
  const { data } = useHub();
  const s = data.overview;
  return (
    <>
      <Heading
        title={`Good ${new Date().getHours() < 12 ? "Morning" : "Afternoon"}, ${data.me.first_name}! 👋`}
        description="Here's your internship overview for today. Keep up the great work!"
      />
      {!!s.legacy_tasks_pending && <div role="status" className="notice">Your HRMS team needs to link {s.legacy_tasks_pending} previous task histories to a PMS project. Your earlier evidence is preserved.</div>}
      <div className="stats four">
        <Stat
          icon={FileText}
          label="Tasks Assigned"
          value={s.total_tasks}
          note="Assigned by your HRMS team"
        />
        <Stat
          icon={CheckCircle2}
          color="green"
          label="Tasks Completed"
          value={s.completed}
          note={`${s.progress}% completed`}
        />
        <Stat
          icon={Trophy}
          color="orange"
          label="Overall Score"
          value={s.score === null ? "—" : `${s.score}/100`}
          note="Based on mentor reviews"
        />
        <Stat
          icon={Flame}
          color="peach"
          label="Current Streak"
          value={`${s.streak} Days`}
          note="Keep it going!"
        />
      </div>
      <div className="grid-main">
        <Hero />
        <ProgressCard />
      </div>
      <div className="grid-main">
        <Card
          title="Today's Tasks"
          action={<Link to="/tasks">View All →</Link>}
        >
          <TaskTable compact />
        </Card>
        <div className="stack">
          <Card title="Quick Metrics" icon={BarChart3}>
            <div className="quick-metrics">
              {[
                ["Attendance", `${s.attendance_rate}%`],
                ["Reports Submitted", s.reports],
                ["Certificates", s.certificates],
                ["Overall Score", s.score ?? "—"],
              ].map(([label, value]) => (
                <div key={label}>
                  <small>{label}</small>
                  <b>{value}</b>
                </div>
              ))}
            </div>
          </Card>
          <Card
            title="Recent Feedback"
            icon={MessageCircle}
            action={<Link to="/reviews">View All →</Link>}
          >
            {data.submissions
              .filter((s) => s.feedback)
              .slice(0, 2)
              .map((s) => (
                <div className="feedback" key={s.id}>
                  <b>{data.me.manager || "Your HRMS team"}</b>
                  <p>{s.feedback}</p>
                  <Badge>{s.status}</Badge>
                </div>
              ))}
            {!data.submissions.some((s) => s.feedback) && (
              <p className="muted">
                Mentor feedback will appear after your first review.
              </p>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
export function Tasks() {
  const { data } = useHub();
  const location = useLocation();
  const [filter, setFilter] = useState("");
  const [search, setSearch] = useState("");
  useEffect(
    () => setSearch(new URLSearchParams(location.search).get("q") || ""),
    [location.search],
  );
  return (
    <>
      <Heading
        title="My Tasks"
        description="Track and manage all your assigned work in one place. Stay organized and keep making progress! 🚀"
      />
      <div className="stats four">
        <Stat
          icon={FileText}
          label="Total Tasks"
          value={data.overview.total_tasks}
          note="Assigned to you"
        />
        <Stat
          icon={Clock}
          label="Overdue"
          value={data.overview.overdue}
          color="pink"
          note="Needs attention"
        />
        <Stat
          icon={CheckCircle2}
          label="Completed"
          value={data.overview.completed}
          color="green"
          note="Great progress!"
        />
        <Stat
          icon={Star}
          label="Average Score"
          value={data.overview.score ?? "—"}
          color="orange"
          note="Across reviewed tasks"
        />
      </div>
      <Card>
        <div className="toolbar">
          <div className="tabs">
            {[
              ["", "All Tasks"],
              ["Pending", "Pending"],
              ["In Progress", "In Progress"],
              ["Completed", "Completed"],
            ].map(([value, label]) => (
              <button
                key={value}
                className={filter === value ? "active" : ""}
                onClick={() => setFilter(value)}
              >
                {label}
                <span>
                  {
                    data.tasks.filter((t) => !value || t.status === value)
                      .length
                  }
                </span>
              </button>
            ))}
          </div>
          <input
            aria-label="Search tasks"
            placeholder="Search tasks…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <TaskTable filter={filter} search={search} />
      </Card>
    </>
  );
}
function useTask() {
  const { data } = useHub();
  const { id } = useParams();
  return (
    data.tasks.find((t) => t.id === Number(id)) ||
    (!id ? data.tasks[0] : undefined)
  );
}
export function TaskDetail() {
  const { data, act } = useHub();
  const task = useTask();
  const [progress,setProgress]=useState(0);
  const [workNotes,setWorkNotes]=useState("");
  if (!task)
    return (
      <Empty title="No task selected">
        <Link to="/tasks">Go to My Tasks</Link>
      </Empty>
    );
  return (
    <>
      <Link className="back" to="/tasks">
        ← Back to My Tasks
      </Link>
      <Heading
        title="Task Details"
        description="View complete details, follow the instructions, and submit your work."
      />
      <div className="grid-main">
        <div className="stack">
          <Card>
            <div className="task-detail-title">
              <span className="stat-icon pink">
                <FileText />
              </span>
              <div>
                <h2>{task.title}</h2>
                <p>{task.description}</p>
              </div>
              <Badge>{task.status}</Badge>
            </div>
            <div className="detail-metrics">
              {[
                ["Points", `${task.points} pts`],
                ["Category", task.category],
                ["Assigned Date", formatDate(task.created_at)],
                ["Due Date", formatDate(task.due_date)],
                ["Mentor", data.me.manager || "Unassigned"],
              ].map(([label, value]) => (
                <div key={label}>
                  <small>{label}</small>
                  <b>{value}</b>
                </div>
              ))}
            </div>
          </Card>
          <Card>
            {[
              ["Description", task.description],
              ["Objectives", task.objectives],
              ["Instructions", task.instructions],
              ["Deliverables", task.deliverables],
            ].map(([label, value]) => (
              <div className="instruction" key={label}>
                <h3>
                  <Target size={19} />
                  {label}
                </h3>
                <p>
                  {value || "Your mentor has not added additional details."}
                </p>
              </div>
            ))}
          </Card>
          {!["Completed","In Review","Cancelled"].includes(task.status)&&<Card title="Work Progress"><label>Progress %<input aria-label="Progress percent" type="number" min={0} max={99} value={progress} onChange={e=>setProgress(Number(e.target.value))}/></label><label>Work notes<textarea aria-label="Work notes" value={workNotes} onChange={e=>setWorkNotes(e.target.value)}/></label><button className="button" onClick={()=>act(()=>hub(`/tasks/${task.id}/progress`,send("POST",{progress_percent:progress,notes:workNotes})),"PMS progress updated")}>Save Progress</button></Card>}
          <div className="actions">
            <button
              className="button outline"
              onClick={() =>
                act(
                  () => hub(`/tasks/${task.id}/start`, send("POST")),
                  "Task started",
                )
              }
            >
              Start Task
            </button>
            <Link className="button" to={`/submit/${task.id}`}>
              <Upload size={17} />
              Submit Work
            </Link>
          </div>
        </div>
        <div className="stack">
          <Card title="Task Summary">
            <dl className="definition">
              {[
                ["Status", task.status],
                ["Points", `${task.points} pts`],
                ["Category", task.category],
                ["Due Date", formatDate(task.due_date)],
                ["Mentor", data.me.manager || "Unassigned"],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
          </Card>
          <Card title="Deadline Reminder" icon={Clock} className="reminder">
            <p>
              This task is due on <b>{formatDate(task.due_date)}</b>. Make sure
              to submit your work on time!
            </p>
          </Card>
          <Card title="Discussion & Support" icon={MessageCircle}>
            <p>
              Need help with the task? Share your question with your HRMS team.
            </p>
            <Link to="/support" className="button soft">
              Ask for help <ArrowRight size={16} />
            </Link>
          </Card>
        </div>
      </div>
    </>
  );
}
export function SubmitWork() {
  const { data, act, busy } = useHub();
  const navigate = useNavigate();
  const task = useTask();
  const [notes, setNotes] = useState("");
  const [links, setLinks] = useState(["", "", ""]);
  const [files, setFiles] = useState<Row[]>([]);
  const [revision, setRevision] = useState("");
  const [confirmed, setConfirmed] = useState([false, false, false]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const latest = data.submissions.find((s) => s.task_id === task?.id);
    const draft = latest?.status === "Draft" ? latest : undefined;
    setNotes(draft?.notes || "");
    setLinks([0, 1, 2].map((i) => draft?.links[i] || ""));
    setFiles(
      (draft?.files || []).map((id: number) => ({
        id,
        name: `Attachment #${id}`,
      })),
    );
    setRevision(draft?.revision_note || "");
    setConfirmed([false, false, false]);
  }, [task?.id]);
  async function uploadFiles(list: FileList | null) {
    if (!list) return;
    setUploading(true);
    setError("");
    try {
      for (const file of Array.from(list)) {
        const form = new FormData();
        form.append("file", file);
        form.append("task_id", String(task!.id));
        const result = await hub("/files", { method: "POST", body: form });
        setFiles((prev) => [...prev, result]);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
    }
  }
  if (!task)
    return (
      <Empty title="No task available">
        <Link to="/tasks">Choose an assigned task first.</Link>
      </Empty>
    );
  async function submit(draft: boolean) {
    const ok = await act(
      () =>
        hub(
          `/tasks/${task!.id}/submissions`,
          send("POST", {
            notes,
            links: links.filter(Boolean),
            files: files.map((f) => f.id),
            revision_note: revision,
            draft,
            confirmed: confirmed.every(Boolean),
          }),
        ),
      draft ? "Draft saved" : "Work submitted for review",
    );
    if (ok && !draft) navigate("/reviews");
  }
  return (
    <>
      <Heading
        title="Submit Work"
        description="Upload your task proof and show what you've built. Follow the guidelines for a faster review."
      />
      <div className="grid-main">
        <div className="stack">
          <Card title="Selected Task">
            <select
              aria-label="Select task"
              value={task.id}
              onChange={(e) => navigate(`/submit/${e.target.value}`)}
            >
              {data.tasks.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.title}
                </option>
              ))}
            </select>
            <p>{task.description}</p>
            <div className="detail-metrics">
              <div>
                <small>Category</small>
                <Badge>{task.category}</Badge>
              </div>
              <div>
                <small>Due Date</small>
                <b>{formatDate(task.due_date)}</b>
              </div>
              <div>
                <small>Mentor</small>
                <b>{data.me.manager || "Unassigned"}</b>
              </div>
              <div>
                <small>Points</small>
                <b>{task.points} pts</b>
              </div>
            </div>
          </Card>
          <Card title="Upload Your Work" icon={Upload}>
            <p>Upload files or provide links to your project.</p>
            <label
              className="dropzone"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                uploadFiles(e.dataTransfer.files);
              }}
            >
              <Upload size={38} />
              <b>
                {uploading ? "Uploading…" : "Drag and drop your files here"}
              </b>
              <span>or click to browse from your device</span>
              <span className="button small">Choose Files</span>
              <input
                type="file"
                multiple
                accept=".pdf,.zip,.docx,.png,.jpg,.jpeg,.mp4,.txt"
                onChange={(e) => uploadFiles(e.target.files)}
              />
            </label>
            <small className="muted">
              PDF, ZIP, DOCX, PNG, JPG, MP4, TXT · Server upload limit applies
            </small>
            {error && (
              <p role="alert" className="error">
                {error}
              </p>
            )}
            <div className="file-list">
              {files.map((f) => (
                <div key={f.id}>
                  <Paperclip size={16} />
                  {f.name}
                  <button
                    aria-label={`Remove ${f.name}`}
                    onClick={() => setFiles(files.filter((a) => a.id !== f.id))}
                  >
                    <X size={16} />
                  </button>
                </div>
              ))}
            </div>
            <div className="form-grid">
              {[
                "GitHub Repository URL",
                "Live Demo URL",
                "Google Drive Link",
              ].map((label, index) => (
                <label key={label}>
                  {label}
                  <input
                    type="url"
                    placeholder="https://"
                    value={links[index]}
                    onChange={(e) =>
                      setLinks(
                        links.map((v, i) => (i === index ? e.target.value : v)),
                      )
                    }
                  />
                </label>
              ))}
            </div>
            <label>
              Explanation / Notes *
              <textarea
                maxLength={5000}
                rows={4}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Explain your work, what you've done, and any information for your mentor…"
              />
            </label>
            <label>
              Revision / Resubmission Note
              <textarea
                value={revision}
                maxLength={2000}
                onChange={(e) => setRevision(e.target.value)}
                rows={2}
                placeholder="What changed in this submission?"
              />
            </label>
            <div className="confirm">
              <b>Confirm Before Submitting</b>
              {[
                "I confirm that this work is my own and original.",
                "I have completed all requirements mentioned in the task.",
                "I understand that late submissions may affect my internship progress.",
              ].map((label, i) => (
                <label key={label}>
                  <input
                    type="checkbox"
                    checked={confirmed[i]}
                    onChange={(e) =>
                      setConfirmed(
                        confirmed.map((v, j) =>
                          i === j ? e.target.checked : v,
                        ),
                      )
                    }
                  />
                  {label}
                </label>
              ))}
            </div>
            <div className="actions">
              <button
                disabled={busy || uploading || !notes.trim()}
                className="button outline"
                onClick={() => submit(true)}
              >
                <Save size={17} />
                Save Draft
              </button>
              <button
                disabled={
                  busy ||
                  uploading ||
                  !notes.trim() ||
                  !confirmed.every(Boolean)
                }
                className="button"
                onClick={() => submit(false)}
              >
                <Send size={17} />
                Submit for Review
              </button>
            </div>
          </Card>
        </div>
        <div className="stack">
          <ProgressCard />
          <Card title="Submission Guidelines" icon={BookOpen}>
            <ol className="guidelines">
              <li>Upload your completed work as per task requirements.</li>
              <li>Include source files, screenshots or relevant links.</li>
              <li>Provide a clear explanation of your work.</li>
              <li>Make sure your submission is original.</li>
              <li>Your mentor will review and provide feedback.</li>
            </ol>
          </Card>
        </div>
      </div>
    </>
  );
}
export function DailyReport() {
  const { data, act, busy } = useHub();
  const [day, setDay] = useState(localDay());
  const blank = {
    work: "",
    learning: "",
    blockers: "",
    tomorrow: "",
    minutes: 0,
    in_progress:"",task_entries:[] as Row[],evidence:[] as number[],
    mood: "Good",
  };
  const [form, setForm] = useState<Row>(blank);
  useEffect(() => {
    setForm(data.reports.find((r) => r.report_date === day) || blank);
  }, [day, data.reports]);
  const checked = data.attendance.find((a) => a.attendance_date === day);
  return (
    <>
      <Heading
        title="Daily Report"
        description="Track your progress, reflect on your learning, and keep your mentor updated."
      >
        <input
          aria-label="Report date"
          type="date"
          value={day}
          max={localDay()}
          min={data.me.date_of_joining}
          onChange={(e) => setDay(e.target.value)}
        />
      </Heading>
      <div className="stats three">
        <Stat
          icon={CheckCircle2}
          color="green"
          label="Attendance / Check-in"
          value={checked?.check_in ? "Checked In" : "Not checked in"}
          note={
            checked?.check_in ? time(checked.check_in) : "Mark your attendance"
          }
        />
        <Stat
          icon={Clock}
          label="Total Time Logged"
          value={`${Math.floor(form.minutes / 60)}h ${form.minutes % 60}m`}
        />
        <Stat
          icon={Target}
          label="Tasks Progress"
          value={`${data.overview.completed} / ${data.overview.total_tasks}`}
        />
      </div>
      <div className="grid-main">
        <div className="stack">
          <Card title="Assigned Tasks">
            <TaskTable compact />
          </Card>
          <div className="form-grid">
            {[
              ["work", "What did you do today? *"],
              ["learning", "What did you learn today? *"],
              ["blockers", "Any blockers or challenges?"],
              ["tomorrow", "Plan for tomorrow"],
            ].map(([key, label]) => (
              <Card key={key}>
                <label>
                  {label}
                  <textarea
                    maxLength={2000}
                    rows={4}
                    value={form[key]}
                    onChange={(e) =>
                      setForm({ ...form, [key]: e.target.value })
                    }
                    placeholder={label}
                  />
                </label>
              </Card>
            ))}
          </div>
          <Card title="Task time (self-reported)">{data.tasks.filter(t=>t.status!=="Cancelled").map(t=><label key={t.id}>{t.title}<input aria-label={`Minutes for ${t.title}`} type="number" min={0} max={1440} value={form.task_entries?.find((v:Row)=>v.task_id===t.id)?.minutes||0} onChange={e=>setForm({...form,task_entries:[...(form.task_entries||[]).filter((v:Row)=>v.task_id!==t.id),{task_id:t.id,minutes:Number(e.target.value),notes:""}]})}/></label>)}<label>Work in progress<textarea value={form.in_progress||""} onChange={e=>setForm({...form,in_progress:e.target.value})}/></label></Card>
          <Card title="How was your day?" icon={Sparkles}>
            <div className="tabs moods">
              {["Great", "Good", "Okay", "Stressed", "Tired"].map((m, i) => (
                <button
                  key={m}
                  className={form.mood === m ? "active" : ""}
                  onClick={() => setForm({ ...form, mood: m })}
                >
                  {["😄", "🙂", "😐", "😟", "😴"][i]} {m}
                </button>
              ))}
            </div>
            <label>
              Time logged (minutes)
              <input
                type="number"
                min={0}
                max={1440}
                value={form.minutes}
                onChange={(e) =>
                  setForm({ ...form, minutes: Number(e.target.value) })
                }
              />
            </label>
          </Card>
          <div className="actions">
            {["Draft", "Submitted"].map((status) => (
              <button
                key={status}
                className={`button ${status === "Draft" ? "outline" : ""}`}
                disabled={busy || !form.work.trim() || !form.learning.trim()}
                onClick={() =>
                  act(
                    () =>
                      hub(
                        "/reports",
                        send("PUT", {
                          ...Object.fromEntries(
                            Object.keys(blank).map((k) => [k, form[k]]),
                          ),
                          report_date: day,
                          status,
                        }),
                      ),
                    status === "Draft"
                      ? "Report draft saved"
                      : "Daily report submitted",
                  )
                }
              >
                {status === "Draft" ? <Save size={17} /> : <Send size={17} />}
                {status === "Draft" ? "Save Report" : "Submit Daily Report"}
              </button>
            ))}
          </div>
        </div>
        <div className="stack">
          <Card title="Daily Streak" icon={Flame} className="reminder">
            <h2>{data.overview.streak} Days</h2>
            <p>Keep it going! You've been consistent.</p>
          </Card>
          <Card title="Report Tips" icon={Sparkles}>
            {[
              "Be specific and concise",
              "Log accurate time",
              "Share what you learned",
              "Be honest about blockers",
            ].map((t) => (
              <p className="tip" key={t}>
                <CheckCircle2 size={20} />
                {t}
              </p>
            ))}
          </Card>
          <Card title="Recent Reports">
            {data.reports.slice(0, 5).map((r) => (
              <button
                className="list-button"
                key={r.id}
                onClick={() => setDay(r.report_date)}
              >
                {formatDate(r.report_date)}
                <Badge>{r.status}</Badge>
              </button>
            ))}
            {!data.reports.length && (
              <p className="muted">Your saved reports will appear here.</p>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
export function Reviews() {
  const { data } = useHub();
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState<number>();
  const list = data.submissions.filter(
    (s) => s.status !== "Draft" && (!filter || s.status === filter),
  );
  const item = list.find((s) => s.id === selected) || list[0];
  const task = data.tasks.find((t) => t.id === item?.task_id);
  return (
    <>
      <Heading
        title="Reviews & Feedback"
        description="Track your submissions, read mentor feedback, and keep improving."
      />
      <div className="grid-main">
        <div className="stack">
          <div className="tabs">
            {[
              "",
              "Approved",
              "Needs Revision",
              "Reviewed",
              "Pending Review",
            ].map((f) => (
              <button
                key={f}
                className={f === filter ? "active" : ""}
                onClick={() => setFilter(f)}
              >
                {f || "All Submissions"}
                <span>
                  {
                    data.submissions.filter(
                      (s) => s.status !== "Draft" && (!f || s.status === f),
                    ).length
                  }
                </span>
              </button>
            ))}
          </div>
          <Card title="Submitted Tasks">
            {list.map((s) => (
              <button
                key={s.id}
                className={`submission-row ${item?.id === s.id ? "selected" : ""}`}
                onClick={() => setSelected(s.id)}
              >
                <span className="task-icon">
                  <FileText size={22} />
                </span>
                <div>
                  <b>{data.tasks.find((t) => t.id === s.task_id)?.title}</b>
                  <small>Submitted {formatDate(s.created_at)}</small>
                </div>
                <strong>
                  {s.score ?? "—"}
                  <small>/100</small>
                </strong>
                <Badge>{s.status}</Badge>
              </button>
            ))}
            {!list.length && (
              <Empty title="No submissions yet">
                <Link to="/submit">Submit your first task</Link>
              </Empty>
            )}
          </Card>
          {item && (
            <Card title={task?.title || "Submission"} icon={FileText}>
              <div className="tabs">
                <span className="active">Feedback</span>
              </div>
              <div className="feedback">
                <b>{data.me.manager || "Your HRMS team"}</b>
                <p>
                  {item.feedback ||
                    "Your submission is waiting for a mentor review."}
                </p>
              </div>
              <div className="form-grid">
                <div className="callout green">
                  <h3>Strengths</h3>
                  <p>
                    {item.strengths || "Feedback will appear after review."}
                  </p>
                </div>
                <div className="callout orange">
                  <h3>Areas for Improvement</h3>
                  <p>
                    {item.improvements ||
                      "Your mentor will share suggestions here."}
                  </p>
                </div>
              </div>
              <h3>Submission notes</h3>
              <p className="preline">{item.notes}</p>
              {item.links.map((link: string) => (
                <p key={link}>
                  <a href={link} target="_blank" rel="noreferrer">
                    {link}
                  </a>
                </p>
              ))}
            </Card>
          )}
        </div>
        <div className="stack">
          <Card title="Overall Score" icon={Trophy}>
            <div className="large-score">
              {data.overview.score ?? "—"}
              <small>/100</small>
            </div>
            <p>Based on your reviewed submissions.</p>
          </Card>
          <Card title="Submitted Files" icon={Paperclip}>
            {item?.files.map((id: number) => (
              <button
                key={id}
                className="list-button"
                onClick={() =>
                  download(`/files/${id}`, `submission-file-${id}`).catch((e) =>
                    alert(e.message),
                  )
                }
              >
                <FileText size={20} />
                Attachment #{id}
              </button>
            ))}
            {!item?.files.length && (
              <p className="muted">No attachments for this submission.</p>
            )}
            {item && (
              <Link to={`/submit/${item.task_id}`} className="button full">
                Resubmit <Upload size={16} />
              </Link>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
