import { RichTextField, RichTextContent, richTextPlainText } from "@/components/rich-text/LazyRichText";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { GraduationCap, Plus, ExternalLink, Download } from "lucide-react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/hooks/use-toast";
type Row = Record<string, any>;
const base = "/interns-hub/admin";
const inputClass =
  "flex min-h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm";
export default function InternsHubAdminPage({ resourceOnly = false }: { resourceOnly?: boolean }) {
  const qc = useQueryClient();
  const [selected, setSelected] = useState("");
  const [tab, setTab] = useState(resourceOnly ? "Learning" : "Tasks");
  const [task, setTask] = useState<Row>({
    title: "",
    description: "",
    category: "Project",
    priority: "Medium",
    points: 10,
    due_date: "",
    instructions: "",
    objectives: "",
    deliverables: "",
  });
  const [course, setCourse] = useState({
    title: "",
    description: "",
    department_id: "",
    lessons: [{ title: "", url: "" }],
    questions: [] as Array<{
      prompt: string;
      options: string[];
      answer: number;
    }>,
  });
  const [certificate, setCertificate] = useState({
    title: "",
    certificate_type: "Module Completion",
  });
  const [reviews, setReviews] = useState<Record<number, Row>>({});
  const [replies, setReplies] = useState<Record<number, string>>({});
  const {
    data: interns = [],
    isLoading,
    error,
  } = useQuery<Row[]>({
    queryKey: ["intern-hub-admin"],
    queryFn: () => api.get(`${base}/interns`).then((r) => r.data),
  });
  const employeeId = Number(selected || interns[0]?.id);
  const { data: detail } = useQuery<Row>({
    queryKey: ["intern-hub-admin-detail", employeeId],
    queryFn: () => api.get(`${base}/interns/${employeeId}`).then((r) => r.data),
    enabled: !!employeeId,
  });
  const mutation = useMutation({
    mutationFn: ({ path, payload }: { path: string; payload: unknown }) =>
      api.post(`${base}${path}`, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["intern-hub-admin"] });
      qc.invalidateQueries({ queryKey: ["intern-hub-admin-detail"] });
      toast({ title: "Interns Hub updated" });
    },
    onError: (error: any) =>
      toast({
        title: "Could not save",
        description:
          typeof error.response?.data?.detail === "string"
            ? error.response.data.detail
            : "Check the required fields and try again.",
        variant: "destructive",
      }),
  });
  const employee = interns.find((i) => i.id === employeeId);
  async function downloadFile(id: number) {
    try {
      const r = await api.get(`/interns-hub/files/${id}`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `intern-submission-${id}`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      toast({ title: "Download unavailable", variant: "destructive" });
    }
  }
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="page-title flex items-center gap-2">
            <GraduationCap />
            Interns Hub Management
          </h1>
          <p className="page-description">
            Manage the separate intern portal using your existing HRMS employee
            records.
          </p>
        </div>
        <Link to="/hrms/interns-hub/applications">
          <Button variant="outline">Review Applications</Button>
        </Link>
        <Link to="/hrms/employees/new">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            Add Intern Employee
          </Button>
        </Link>
      </div>
      {error ? (
        <p role="alert" className="text-destructive">
          Unable to load interns. HRMS management permission is required.
        </p>
      ) : isLoading ? (
        <p>Loading interns…</p>
      ) : !interns.length ? (
        <Card>
          <CardContent className="pt-6">
            No interns yet. Create an employee with employment type Intern,
            assign their department, designation and reporting manager, then
            link an employee user account.
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardContent className="grid gap-4 pt-6 sm:grid-cols-2">
              <div>
                <Label htmlFor="managed-intern">Intern</Label>
                <select
                  id="managed-intern"
                  className={inputClass}
                  value={employeeId || ""}
                  onChange={(e) => setSelected(e.target.value)}
                >
                  {interns.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.first_name} {i.last_name} ({i.employee_id})
                    </option>
                  ))}
                </select>
              </div>
              {employee && (
                <div className="space-y-1 text-sm">
                  <p>
                    <b>Department:</b> {employee.department || "Unassigned"} ·{" "}
                    <b>Designation:</b> {employee.designation || "Unassigned"}
                  </p>
                  <p>
                    <b>Manager:</b> {employee.manager || "Unassigned"}
                  </p>
                  <Link
                    className="inline-flex items-center gap-1 text-primary"
                    to={`/hrms/employees/${employeeId}`}
                  >
                    Manage HRMS employee <ExternalLink className="h-3 w-3" />
                  </Link>
                </div>
              )}
            </CardContent>
          </Card>
          <div className="flex gap-2 overflow-auto">
            {[
              "Tasks",
              "Submissions",
              "Daily Reports",
              "Learning",
              "Certificates",
              "Support",
            ].filter(t => !resourceOnly || ["Learning", "Certificates", "Support"].includes(t)).map((t) => (
              <Button
                key={t}
                variant={tab === t ? "default" : "outline"}
                onClick={() => setTab(t)}
              >
                {t}
              </Button>
            ))}
          </div>
          {tab === "Tasks" && (
            <div className="grid gap-6 xl:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Assign Task</CardTitle>
                </CardHeader>
                <CardContent>
                  <form
                    className="space-y-4"
                    onSubmit={(e) => {
                      e.preventDefault();
                      mutation.mutate(
                        {
                          path: "/tasks",
                          payload: { ...task, employee_id: employeeId },
                        },
                        {
                          onSuccess: () =>
                            setTask({ ...task, title: "", description: "" }),
                        },
                      );
                    }}
                  >
                    <div className="grid gap-4 sm:grid-cols-2">
                      {[
                        ["title", "Title"],
                        ["category", "Category"],
                        ["due_date", "Due Date"],
                        ["points", "Points"],
                      ].map(([key, label]) => (
                        <div key={key}>
                          <Label htmlFor={`task-${key}`}>{label}</Label>
                          <Input
                            id={`task-${key}`}
                            required
                            type={
                              key === "due_date"
                                ? "date"
                                : key === "points"
                                  ? "number"
                                  : "text"
                            }
                            min={key === "points" ? 0 : undefined}
                            max={key === "points" ? 100 : undefined}
                            value={task[key]}
                            onChange={(e) =>
                              setTask({
                                ...task,
                                [key]:
                                  key === "points"
                                    ? Number(e.target.value)
                                    : e.target.value,
                              })
                            }
                          />
                        </div>
                      ))}
                      <div>
                        <Label>Priority</Label>
                        <select
                          className={inputClass}
                          value={task.priority}
                          onChange={(e) =>
                            setTask({ ...task, priority: e.target.value })
                          }
                        >
                          {["High", "Medium", "Low"].map((p) => (
                            <option key={p}>{p}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                    {[
                      ["description", "Description"],
                      ["objectives", "Objectives"],
                      ["instructions", "Instructions"],
                      ["deliverables", "Deliverables"],
                    ].map(([key, label]) => (
                      <div key={key}>
                        <Label htmlFor={`task-${key}`}>{label}</Label>
                        <RichTextField
                          id={`task-${key}`}
                          className={inputClass}
                          rows={3}
                          required={key === "description"}
                          value={task[key]}
                          onChange={(e) =>
                            setTask({ ...task, [key]: e.target.value })
                          }
                        />
                      </div>
                    ))}
                    <Button disabled={mutation.isPending}>Assign Task</Button>
                  </form>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Assigned Tasks</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {detail?.tasks.map((t: Row) => (
                    <div className="rounded-lg border p-4" key={t.id}>
                      <div className="flex justify-between gap-2">
                        <b>{t.title}</b>
                        <Badge variant="outline">{t.status}</Badge>
                      </div>
                      <div className="mt-2 text-sm text-muted-foreground"><RichTextContent legacyFormat="plain" value={t.description}/></div>
                      <p className="mt-2 text-xs">
                        Due {t.due_date} · {t.points} pts
                      </p>
                    </div>
                  ))}
                  {!detail?.tasks.length && (
                    <p className="text-muted-foreground">
                      No tasks assigned yet.
                    </p>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
          {tab === "Submissions" && (
            <div className="space-y-4">
              {detail?.submissions
                .filter((s: Row) => s.status !== "Draft")
                .map((s: Row) => {
                  const form = reviews[s.id] || {
                    status: "Approved",
                    score: s.score ?? 0,
                    feedback: s.feedback || "",
                    strengths: s.strengths || "",
                    improvements: s.improvements || "",
                  };
                  const update = (key: string, value: any) =>
                    setReviews({
                      ...reviews,
                      [s.id]: { ...form, [key]: value },
                    });
                  return (
                    <Card key={s.id}>
                      <CardHeader>
                        <CardTitle>
                          {
                            detail.tasks.find((t: Row) => t.id === s.task_id)
                              ?.title
                          }{" "}
                          <Badge variant="outline">{s.status}</Badge>
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="whitespace-pre-line text-sm"><RichTextContent legacyFormat="plain" value={s.notes}/></div>
                        <div className="my-3 flex flex-wrap gap-2">
                          {s.files.map((id: number) => (
                            <Button
                              key={id}
                              variant="outline"
                              size="sm"
                              onClick={() => downloadFile(id)}
                            >
                              <Download className="mr-1 h-3 w-3" />
                              Attachment {id}
                            </Button>
                          ))}
                          {s.links.map((url: string) => (
                            <a
                              key={url}
                              className="text-sm text-primary underline"
                              href={url}
                              target="_blank"
                              rel="noreferrer"
                            >
                              {url}
                            </a>
                          ))}
                        </div>
                        <form
                          className="grid gap-4 sm:grid-cols-2"
                          onSubmit={(e) => {
                            e.preventDefault();
                            mutation.mutate({
                              path: `/submissions/${s.id}/review`,
                              payload: form,
                            });
                          }}
                        >
                          <div>
                            <Label>Review Status</Label>
                            <select
                              className={inputClass}
                              value={form.status}
                              onChange={(e) => update("status", e.target.value)}
                            >
                              {["Approved", "Reviewed", "Needs Revision"].map(
                                (status) => (
                                  <option key={status}>{status}</option>
                                ),
                              )}
                            </select>
                          </div>
                          <div>
                            <Label>Score / 100</Label>
                            <Input
                              type="number"
                              min={0}
                              max={100}
                              required
                              value={form.score}
                              onChange={(e) =>
                                update("score", Number(e.target.value))
                              }
                            />
                          </div>
                          {[
                            ["feedback", "Feedback"],
                            ["strengths", "Strengths"],
                            ["improvements", "Improvements"],
                          ].map(([key, label]) => (
                            <div key={key}>
                              <Label>{label}</Label>
                              <RichTextField
                                className={inputClass}
                                required={key === "feedback"}
                                value={form[key]}
                                onChange={(e) => update(key, e.target.value)}
                              />
                            </div>
                          ))}
                          <div className="self-end">
                            <Button disabled={mutation.isPending}>
                              Save Review
                            </Button>
                          </div>
                        </form>
                      </CardContent>
                    </Card>
                  );
                })}
              {!detail?.submissions.some((s: Row) => s.status !== "Draft") && (
                <p>No work submitted yet.</p>
              )}
            </div>
          )}
          {tab === "Daily Reports" && (
            <div className="space-y-4">
              {detail?.reports
                .filter((r: Row) => r.status === "Submitted")
                .map((r: Row) => (
                  <Card key={r.id}>
                    <CardHeader>
                      <CardTitle>
                        {r.report_date} · {r.mood} · {r.minutes} minutes
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="grid gap-4 sm:grid-cols-2">
                      {[
                        ["work", "Work"],
                        ["learning", "Learning"],
                        ["blockers", "Blockers"],
                        ["tomorrow", "Tomorrow"],
                      ].map(([key, label]) => (
                        <div key={key}>
                          <h3 className="font-semibold">{label}</h3>
                          <p className="whitespace-pre-line text-sm text-muted-foreground">
                            {r[key] || "—"}
                          </p>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                ))}
              {!detail?.reports.length && <p>No reports yet.</p>}
            </div>
          )}
          {tab === "Learning" && (
            <Card>
              <CardHeader>
                <CardTitle>Publish Learning Module</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="mb-4 text-sm text-muted-foreground">
                  Publish learning resources and assessments for a department,
                  or make them available to all interns.
                </p>
                <form
                  className="space-y-4"
                  onSubmit={(e) => {
                    e.preventDefault();
                    mutation.mutate({
                      path: "/learning",
                      payload: {
                        ...course,
                        department_id: course.department_id
                          ? Number(course.department_id)
                          : null,
                      },
                    });
                  }}
                >
                  <Label>
                    Title
                    <Input
                      required
                      value={course.title}
                      onChange={(e) =>
                        setCourse({ ...course, title: e.target.value })
                      }
                    />
                  </Label>
                  <Label>
                    Description
                    <RichTextField
                      className={inputClass}
                      value={course.description}
                      onChange={(e) =>
                        setCourse({ ...course, description: e.target.value })
                      }
                    />
                  </Label>
                  <Label>
                    Department
                    <select
                      className={inputClass}
                      value={course.department_id}
                      onChange={(e) =>
                        setCourse({ ...course, department_id: e.target.value })
                      }
                    >
                      <option value="">All Departments</option>
                      {Array.from(
                        new Map(
                          interns
                            .filter((i) => i.department_id)
                            .map((i) => [i.department_id, i.department]),
                        ).entries(),
                      ).map(([id, name]) => (
                        <option key={id} value={id}>
                          {name}
                        </option>
                      ))}
                    </select>
                  </Label>
                  <h3 className="font-semibold">Lessons</h3>
                  {course.lessons.map((lesson, index) => (
                    <div
                      className="grid gap-3 rounded-lg border p-3 sm:grid-cols-2"
                      key={index}
                    >
                      <Label>
                        Lesson title
                        <Input
                          required
                          value={lesson.title}
                          onChange={(e) =>
                            setCourse({
                              ...course,
                              lessons: course.lessons.map((item, i) =>
                                i === index
                                  ? { ...item, title: e.target.value }
                                  : item,
                              ),
                            })
                          }
                        />
                      </Label>
                      <Label>
                        Resource URL
                        <Input
                          type="url"
                          required
                          placeholder="https://"
                          value={lesson.url}
                          onChange={(e) =>
                            setCourse({
                              ...course,
                              lessons: course.lessons.map((item, i) =>
                                i === index
                                  ? { ...item, url: e.target.value }
                                  : item,
                              ),
                            })
                          }
                        />
                      </Label>
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={() =>
                          setCourse({
                            ...course,
                            lessons: course.lessons.filter(
                              (_, i) => i !== index,
                            ),
                          })
                        }
                      >
                        Remove lesson
                      </Button>
                    </div>
                  ))}
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() =>
                      setCourse({
                        ...course,
                        lessons: [...course.lessons, { title: "", url: "" }],
                      })
                    }
                  >
                    Add Lesson
                  </Button>
                  <h3 className="font-semibold">Assessment Questions</h3>
                  {course.questions.map((q, index) => (
                    <div
                      className="space-y-3 rounded-lg border p-4"
                      key={index}
                    >
                      <Label>
                        Question
                        <Input
                          required
                          value={q.prompt}
                          onChange={(e) =>
                            setCourse({
                              ...course,
                              questions: course.questions.map((item, i) =>
                                i === index
                                  ? { ...item, prompt: e.target.value }
                                  : item,
                              ),
                            })
                          }
                        />
                      </Label>
                      {q.options.map((option, j) => (
                        <Label key={j}>
                          Option {j + 1}
                          <Input
                            required
                            value={option}
                            onChange={(e) =>
                              setCourse({
                                ...course,
                                questions: course.questions.map((item, i) =>
                                  i === index
                                    ? {
                                        ...item,
                                        options: item.options.map((value, k) =>
                                          k === j ? e.target.value : value,
                                        ),
                                      }
                                    : item,
                                ),
                              })
                            }
                          />
                        </Label>
                      ))}
                      <Label>
                        Correct answer
                        <select
                          className={inputClass}
                          value={q.answer}
                          onChange={(e) =>
                            setCourse({
                              ...course,
                              questions: course.questions.map((item, i) =>
                                i === index
                                  ? { ...item, answer: Number(e.target.value) }
                                  : item,
                              ),
                            })
                          }
                        >
                          {q.options.map((option, j) => (
                            <option key={j} value={j}>
                              Option {j + 1}: {option}
                            </option>
                          ))}
                        </select>
                      </Label>
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={() =>
                          setCourse({
                            ...course,
                            questions: course.questions.filter(
                              (_, i) => i !== index,
                            ),
                          })
                        }
                      >
                        Remove question
                      </Button>
                    </div>
                  ))}
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() =>
                      setCourse({
                        ...course,
                        questions: [
                          ...course.questions,
                          { prompt: "", options: ["", ""], answer: 0 },
                        ],
                      })
                    }
                  >
                    Add Question
                  </Button>
                  <div>
                    <Button disabled={mutation.isPending}>
                      Publish Module
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          )}
          {tab === "Certificates" && (
            <Card>
              <CardHeader>
                <CardTitle>Issue Certificate</CardTitle>
              </CardHeader>
              <CardContent>
                <form
                  className="flex flex-wrap items-end gap-4"
                  onSubmit={(e) => {
                    e.preventDefault();
                    mutation.mutate({
                      path: "/certificates",
                      payload: { ...certificate, employee_id: employeeId },
                    });
                  }}
                >
                  <Label>
                    Certificate title
                    <Input
                      required
                      value={certificate.title}
                      onChange={(e) =>
                        setCertificate({
                          ...certificate,
                          title: e.target.value,
                        })
                      }
                    />
                  </Label>
                  <Label>
                    Type
                    <select
                      className={inputClass}
                      value={certificate.certificate_type}
                      onChange={(e) =>
                        setCertificate({
                          ...certificate,
                          certificate_type: e.target.value,
                        })
                      }
                    >
                      {[
                        "Module Completion",
                        "Skill Assessment",
                        "Project Completion",
                        "Internship",
                      ].map((t) => (
                        <option key={t}>{t}</option>
                      ))}
                    </select>
                  </Label>
                  <Button disabled={mutation.isPending}>
                    Issue Certificate
                  </Button>
                </form>
                <p className="my-4 text-sm text-muted-foreground">
                  Final internship certificates require all assigned tasks to be
                  completed and reviewed.
                </p>
                {detail?.certificates.map((c: Row) => (
                  <p className="border-t py-3 text-sm" key={c.id}>
                    {c.title} · {c.certificate_type}
                  </p>
                ))}
              </CardContent>
            </Card>
          )}
          {tab === "Support" && (
            <div className="space-y-4">
              {detail?.tickets.map((t: Row) => (
                <Card key={t.id}>
                  <CardHeader>
                    <CardTitle>
                      {t.subject} <Badge variant="outline">{t.status}</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="mb-4 whitespace-pre-line text-sm"><RichTextContent legacyFormat="plain" value={t.message}/></div>
                    <form
                      className="space-y-3"
                      onSubmit={(e) => {
                        e.preventDefault();
                        mutation.mutate({
                          path: `/support/${t.id}/reply`,
                          payload: {
                            reply: replies[t.id] ?? t.reply,
                            status: "Resolved",
                          },
                        });
                      }}
                    >
                      <RichTextField
                        className={inputClass}
                        required
                        placeholder="Reply to intern…"
                        value={replies[t.id] ?? t.reply ?? ""}
                        onChange={(e) =>
                          setReplies({ ...replies, [t.id]: e.target.value })
                        }
                      />
                      <Button disabled={mutation.isPending}>
                        Reply & Resolve
                      </Button>
                    </form>
                  </CardContent>
                </Card>
              ))}
              {!detail?.tickets.length && <p>No support requests.</p>}
            </div>
          )}
        </>
      )}
    </div>
  );
}
