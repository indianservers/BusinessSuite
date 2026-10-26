import { RichTextField, RichTextContent } from "../../src/components/rich-text/LazyRichText";
import { useState, type CSSProperties } from "react";
import { PhoneInput } from "./validation/PhoneInput";
import { UnifiedProfile, type ProfileRequest } from "../../src/features/profiles/UnifiedProfile";
import { request } from "./api";
import {
  Mail,
  Phone,
  MapPin,
  UserRound,
  GraduationCap,
  Star,
  FileText,
  Trophy,
  Download,
  LockKeyhole,
  CheckCircle2,
  Clock,
  Send,
  MessageCircle,
} from "lucide-react";
import { hub, send, download } from "./api";
import {
  useHub,
  Row,
  Badge,
  Empty,
  Card,
  Ring,
  Heading,
  Avatar,
  formatDate,
} from "./ui";
const sharedProfileRequest: ProfileRequest = (path, options) => request(path.replace(/^\/profiles\/me(?=\/|$)/, "/interns-hub/profile"), options?.body instanceof FormData ? { method: options.method || "POST", body: options.body } : options ? send(options.method || "GET", options.body) : {});
export function Profile() { const { refresh } = useHub(); return <div style={{ "--primary": "246 100% 63%", "--muted": "220 50% 97%", "--foreground": "238 55% 14%", "--background": "0 0% 100%", "--border": "228 28% 90%", "--muted-foreground": "228 18% 43%" } as CSSProperties}><UnifiedProfile request={sharedProfileRequest} onSaved={() => { void refresh(); }} /></div>; }
function LegacyProfile() {
  const { data, act, busy } = useHub();
  const e = data.me;
  const [tab, setTab] = useState("Personal Details");
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Row>({});
  const name = `${e.first_name} ${e.last_name}`;
  const fields = [
    ["personal_email", "Email"],
    ["phone_number", "Phone"],
    ["present_city", "City"],
    ["present_address", "Address"],
    ["bio", "Bio"],
    ["interests", "Interests"],
  ];
  const completeness = Math.round(
    ([
      e.phone_number,
      e.personal_email,
      e.present_address,
      e.education.length,
      e.skills.length,
      e.bio,
      e.profile_photo_url,
    ].filter(Boolean).length *
      100) /
      7,
  );
  return (
    <>
      <Heading
        title="My Profile"
        description="Manage your personal information, education, skills and internship details."
      >
        <button
          className="button"
          onClick={() => {
            setForm({...Object.fromEntries(fields.map(([k]) => [k, e[k] || ""])),phone_number_country_code:e.phone_number_country_code || (e.phone_number ? "" : "+91")});
            setEditing(!editing);
          }}
        >
          <UserRound size={17} />
          {editing ? "Cancel" : "Edit Profile"}
        </button>
      </Heading>
      <Card className="profile-banner">
        <Avatar name={name} photo={e.profile_photo_url} large />
        <div>
          <h2>
            {name} <Badge>Active Intern</Badge>
          </h2>
          <p>
            <Mail size={15} />
            {e.work_email || e.personal_email || "Email not provided"}
          </p>
          <p>
            <Phone size={15} />
            {e.phone_number ? `${e.phone_number_country_code || ""} ${e.phone_number}` : "Phone not provided"}
          </p>
          <p>
            <MapPin size={15} />
            {e.present_city || "City not provided"}
          </p>
        </div>
        <blockquote>
          “{e.bio || "Learning new skills and building a brighter future."}”
        </blockquote>
      </Card>
      <div className="tabs profile-tabs">
        {[
          "Personal Details",
          "Education",
          "Skills & Interests",
          "Documents",
          "Internship Details",
        ].map((t) => (
          <button
            key={t}
            className={t === tab ? "active" : ""}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>
      {editing && (
        <Card title="Edit Personal Details">
          <form
            onSubmit={async (event) => {
              event.preventDefault();
              if (
                await act(
                  () => hub("/me", send("PATCH",Object.fromEntries(Object.entries(form).filter(([key,value])=>value!==e[key] && !(key==='phone_number_country_code'&&!value&&!e[key]))))),
                  "Profile updated in HRMS",
                )
              )
                setEditing(false);
            }}
          >
            <div className="form-grid">
              {fields.map(([key, label]) => (
                <label key={key}>
                  {label}
                  {key==='phone_number' ? <PhoneInput label={label} value={form[key] || ''} countryCode={form.phone_number_country_code || ''} onChange={value=>setForm({...form,[key]:value})} onCountryCodeChange={value=>setForm({...form,phone_number_country_code:value})} /> : <input
                    value={form[key] || ""}
                    maxLength={key === "phone_number" ? 20 : 1000}
                    type={key === "personal_email" ? "email" : "text"}
                    onChange={(event) =>
                      setForm({ ...form, [key]: event.target.value })
                    }
                  />}
                </label>
              ))}
            </div>
            <button className="button" disabled={busy}>
              Save Changes
            </button>
          </form>
        </Card>
      )}
      <div className="grid-main">
        <div className="stack">
          {tab === "Personal Details" && (
            <Card title="Personal Information" icon={UserRound}>
              <dl className="profile-fields">
                {[
                  ["Full Name", name],
                  ["Father's Name", e.father_name],
                  ["Mother's Name", e.mother_name],
                  ["Gender", e.gender],
                  ["Date of Birth", formatDate(e.date_of_birth)],
                  ["City", e.present_city],
                  ["Address", e.present_address],
                ].map(([k, v]) => (
                  <div key={k}>
                    <dt>{k}</dt>
                    <dd>{v || "—"}</dd>
                  </div>
                ))}
              </dl>
            </Card>
          )}
          {(tab === "Education" || tab === "Personal Details") && (
            <Card title="Education Details" icon={GraduationCap}>
              {e.education.length ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Qualification</th>
                        <th>Board/University</th>
                        <th>Marks/CGPA</th>
                        <th>Year</th>
                      </tr>
                    </thead>
                    <tbody>
                      {e.education.map((r: Row) => (
                        <tr key={r.id}>
                          <td>{r.degree}</td>
                          <td>{r.board_university || r.institution || "—"}</td>
                          <td>{r.percentage_cgpa || "—"}</td>
                          <td>{r.pass_year || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="muted">
                  Education records are maintained by your HRMS team.
                </p>
              )}
            </Card>
          )}
          {(tab === "Skills & Interests" || tab === "Personal Details") && (
            <Card title="Skills & Area of Interest" icon={Star}>
              <h4>Technical Skills</h4>
              <div className="pills">
                {e.skills.map((s: Row) => (
                  <Badge key={s.id}>{s.skill_name}</Badge>
                ))}
                {!e.skills.length && (
                  <p className="muted">No skills recorded yet.</p>
                )}
              </div>
              <h4>Area of Interest</h4>
              <p>{e.interests || "Add your interests using Edit Profile."}</p>
            </Card>
          )}
          {tab === "Documents" && (
            <Card title="Documents" icon={FileText}>
              {e.documents.map((d: Row) => (
                <div className="list-button" key={d.id}>
                  <FileText size={20} />
                  <b>{d.name}</b>
                  <Badge>{d.status}</Badge>
                </div>
              ))}
              <p className="muted">
                Contact HR to upload or update identity documents.
              </p>
            </Card>
          )}
          {tab === "Internship Details" && (
            <Card title="Internship Details" icon={GraduationCap}>
              <dl className="definition">
                {[
                  ["Employee ID", e.employee_id],
                  ["Department", e.department],
                  ["Designation", e.designation],
                  ["Reporting Manager", e.manager],
                  ["Branch", e.branch],
                  ["Joining Date", formatDate(e.date_of_joining)],
                  ["End Date", formatDate(e.date_of_exit)],
                  ["Employment Type", e.employment_type],
                ].map(([k, v]) => (
                  <div key={k}>
                    <dt>{k}</dt>
                    <dd>{v || "Unassigned"}</dd>
                  </div>
                ))}
              </dl>
              <p className="muted">
                Job details are managed in HRMS and reflect your current
                employee record.
              </p>
            </Card>
          )}
        </div>
        <div className="stack">
          <Card title="Profile Completion">
            <div className="center">
              <Ring value={completeness} green />
            </div>
            <p className="tip">
              <CheckCircle2 size={18} /> Personal Details
            </p>
            <p className="tip">
              <CheckCircle2 size={18} /> HRMS Employee Linked
            </p>
          </Card>
          <Card title="Current Status">
            <dl className="definition">
              {[
                ["Department", e.department],
                ["Designation", e.designation],
                ["Reporting Manager", e.manager],
                ["Status", e.status],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v || "Unassigned"}</dd>
                </div>
              ))}
            </dl>
          </Card>
        </div>
      </div>
      <PasswordForm />
    </>
  );
}
export function Certificates() {
  const { data } = useHub();
  const final = data.certificates.find(
    (c) => c.certificate_type === "Internship",
  );
  return (
    <>
      <Heading
        title="Certificates & Completion"
        description="Track your progress, earn certificates and complete your internship successfully."
      />
      <Card className="completion-banner">
        <Trophy size={85} />
        <div>
          <h2>Keep Going, {data.me.first_name}!</h2>
          <p>
            You are {data.overview.progress}% towards completing your assigned
            tasks.
          </p>
          <p>Complete remaining tasks to earn your final certificate.</p>
        </div>
        <Ring value={data.overview.progress} green />
      </Card>
      <Card>
        <div className="milestones">
          {[
            "Profile",
            "Tasks",
            "Assessments",
            "Final Review",
            "Certificate",
          ].map((s, i) => (
            <div key={s}>
              <span
                className={
                  i === 0 ||
                  (i === 1 && data.overview.progress === 100) ||
                  (i === 2 && data.learning.some((c) => c.score >= 70)) ||
                  (i > 2 && final)
                    ? "done"
                    : ""
                }
              >
                {i + 1}
              </span>
              <b>{s}</b>
              <small>
                {i === 0
                  ? "Connected"
                  : i === 1
                    ? `${data.overview.progress}% completed`
                    : i === 2
                      ? `${data.learning.filter((c) => c.score >= 70).length} passed`
                      : final
                        ? "Completed"
                        : "Pending"}
              </small>
            </div>
          ))}
        </div>
      </Card>
      <Card title="Certificate Eligibility" icon={GraduationCap}>
        <div className="stats four">
          {[
            [
              "Task Completion",
              `${data.overview.progress}%`,
              "Complete all assigned tasks",
            ],
            [
              "Daily Reports",
              data.overview.reports,
              "Keep your manager updated",
            ],
            [
              "Assessments",
              data.learning.filter((c) => c.score >= 70).length,
              "Passed assessments",
            ],
            [
              "Mentor Review",
              final ? "Approved" : "Pending",
              "Requires HRMS approval",
            ],
          ].map(([label, value, note]) => (
            <div className="eligibility" key={label}>
              <small>{label}</small>
              <h2>{value}</h2>
              <p>{note}</p>
            </div>
          ))}
        </div>
      </Card>
      <Card title="Available Certificates" icon={FileText}>
        <div className="course-grid">
          {data.certificates.map((c) => (
            <div className="certificate-card" key={c.id}>
              <div className="certificate-preview">
                <GraduationCap />
                <b>InternHub</b>
                <small>{c.certificate_type}</small>
                <h3>{c.title}</h3>
                <p>
                  {data.me.first_name} {data.me.last_name}
                </p>
                <span className="seal">✹</span>
              </div>
              <p>Issued on {formatDate(c.issued_at)}</p>
              <button
                className="button full"
                onClick={() =>
                  download(
                    `/certificates/${c.id}/download`,
                    `internhub-certificate-${c.id}.pdf`,
                  ).catch((e) => alert(e.message))
                }
              >
                <Download size={16} />
                Download
              </button>
            </div>
          ))}
        </div>
        {!data.certificates.length && (
          <Empty title="Your achievements will live here">
            Certificates become available when your HRMS team issues them.
          </Empty>
        )}
      </Card>
      <Card title="Final Internship Certificate" icon={GraduationCap}>
        <div className="completion-banner">
          <div className="final-certificate">
            <GraduationCap size={30} />
            <h2>Certificate of Internship</h2>
            <p>This is to certify that</p>
            <h2>
              {data.me.first_name} {data.me.last_name}
            </h2>
            <p>has completed the internship program</p>
            <Trophy size={46} />
          </div>
          <div>
            <p>
              <CheckCircle2 size={18} /> Tasks completed:{" "}
              {data.overview.completed} / {data.overview.total_tasks}
            </p>
            <p>
              <Clock size={18} /> Mentor approval:{" "}
              {final ? "Approved" : "Pending review"}
            </p>
            <p>Your final certificate is available after HRMS approval.</p>
            {final ? (
              <button
                className="button"
                onClick={() =>
                  download(
                    `/certificates/${final.id}/download`,
                    "internship-certificate.pdf",
                  )
                }
              >
                <Download size={16} />
                Download Certificate
              </button>
            ) : (
              <button className="button soft" disabled>
                <LockKeyhole size={16} />
                Certificate Locked
              </button>
            )}
          </div>
        </div>
      </Card>
    </>
  );
}
export function Support() {
  const { data, act, busy } = useHub();
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  return (
    <>
      <Heading
        title="Help & Support"
        description="Get support from your HRMS team and keep moving forward."
      />
      <div className="grid-main">
        <Card title="How can we help?" icon={MessageCircle}>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (
                await act(
                  () => hub("/support", send("POST", { subject, message })),
                  "Support request created",
                )
              ) {
                setSubject("");
                setMessage("");
              }
            }}
          >
            <label>
              Subject
              <input
                required
                maxLength={200}
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
              />
            </label>
            <label>
              Message
              <RichTextField
                required
                rows={6}
                maxLength={4000}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
              />
            </label>
            <button className="button" disabled={busy}>
              <Send size={17} />
              Send to HRMS
            </button>
          </form>
        </Card>
        <Card title="Your HRMS Connection">
          <h2>{data.me.manager || "Manager unassigned"}</h2>
          <p>{data.me.department || "Department unassigned"}</p>
          <p>{data.me.designation || "Designation unassigned"}</p>
          <p>
            For account access or employee record changes, contact your HRMS
            administrator.
          </p>
        </Card>
      </div>
      <Card title="Your Support Requests">
        {data.support.map((t) => (
          <div className="feedback" key={t.id}>
            <h3>
              {t.subject} <Badge>{t.status}</Badge>
            </h3>
            <div><RichTextContent legacyFormat="plain" value={t.message}/></div>
            {t.reply && (
              <div className="callout green">
                <b>HRMS reply</b>
                <div><RichTextContent legacyFormat="plain" value={t.reply}/></div>
              </div>
            )}
          </div>
        ))}
        {!data.support.length && (
          <p className="muted">You haven't raised any requests yet.</p>
        )}
      </Card>
    </>
  );
}

function PasswordForm() {
  const { act, busy } = useHub();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  return (
    <Card title="Account Security" icon={LockKeyhole}>
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          if (next !== confirm) return;
          if (
            await act(
              () =>
                hub(
                  "/password",
                  send("POST", {
                    current_password: current,
                    new_password: next,
                  }),
                ),
              "Password changed",
            )
          ) {
            setCurrent("");
            setNext("");
            setConfirm("");
          }
        }}
      >
        <div className="form-grid">
          <label>
            Current password
            <input
              type="password"
              autoComplete="current-password"
              required
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
            />
          </label>
          <label>
            New password
            <input
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              value={next}
              onChange={(e) => setNext(e.target.value)}
            />
          </label>
          <label>
            Confirm new password
            <input
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          </label>
        </div>
        {confirm && next !== confirm && (
          <p className="error">The new passwords must match.</p>
        )}
        <button
          className="button"
          disabled={busy || !current || next.length < 8 || next !== confirm}
        >
          Change Password
        </button>
      </form>
    </Card>
  );
}
