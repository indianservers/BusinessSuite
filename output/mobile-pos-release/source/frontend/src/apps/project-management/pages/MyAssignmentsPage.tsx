import "./my-assignments-mobile.css";
import {useMobile} from "@/components/mobile/useMobile";
import {useModuleAction} from "@/hooks/use-module-action";
import GridTable from "@/shared/data-grid/GridTable";
import { recordPreviewProps } from "@/components/RecordQuickPreview";
import {
  RichTextField,
  RichTextContent,
  richTextPlainText,
} from "@/components/rich-text/LazyRichText";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
type Row = Record<string, any>;
export default function MyAssignmentsPage() {
  const phone=useMobile(480);
  const canExecute=useModuleAction("create");
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number>();
  const [notes, setNotes] = useState("");
  const [links, setLinks] = useState("");
  const [files, setFiles] = useState<Row[]>([]);
  const [percent, setPercent] = useState(0);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const saving=useRef(false);
  const detailHeading=useRef<HTMLHeadingElement>(null);
  const [failed,setFailed]=useState(false);
  const [dirty,setDirty]=useState(false);
  const changed=()=>{if(phone)setDirty(true);};
  function leaveDraft() {
    if(!phone)return true;
    if(saving.current)return false;
    if(dirty && !window.confirm("Discard unsaved assignment changes? Notes, progress, and unsubmitted evidence will be lost."))return false;
    setDirty(false);return true;
  }
  useEffect(()=>{
    if(!phone || !dirty && !busy)return;
    const warn=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue="";};
    const linkClick=(event:MouseEvent)=>{
      if(event.defaultPrevented || event.button!==0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)return;
      const anchor=(event.target as Element)?.closest?.("a[href]") as HTMLAnchorElement|null;
      if(!anchor || anchor.hasAttribute("download") || anchor.target && anchor.target!=="_self")return;
      const destination=new URL(anchor.href,window.location.href),current=new URL(window.location.href);
      if(destination.origin===current.origin && destination.pathname===current.pathname && destination.search===current.search)return;
      if(!leaveDraft()){event.preventDefault();event.stopPropagation();}
    };
    window.addEventListener("beforeunload",warn);document.addEventListener("click",linkClick,true);
    return()=>{window.removeEventListener("beforeunload",warn);document.removeEventListener("click",linkClick,true);};
  },[phone,dirty,busy]);
  const source = useQuery<Row>({
    queryKey: ["pms-my-assignments", page],
    queryFn: () =>
      api
        .get("/project-management/work/assignments", { params: { page } })
        .then((r) => r.data),
  });
  const {data,error}=source;
  const task = data?.items.find((r: Row) => r.id === selected);
  const locked =
    task &&
    ((task.blocked_by?.length || 0) > 0 ||
      (task.pack_run_id &&
        task.start_date &&
        task.start_date > new Date().toLocaleDateString("en-CA")));
  const editable =
    task &&
    !locked &&
    !["Done", "In Review", "Cancelled"].includes(task.status);
  async function action(operation: () => Promise<any>, clearsDraft=false) {
    if(!canExecute || phone && saving.current)return;
    if(phone)saving.current=true;
    setFailed(false);
    setBusy(true);
    setMessage("");
    try {
      await operation();
      if(phone && clearsDraft)setDirty(false);
      await qc.invalidateQueries({ queryKey: ["pms-my-assignments"] });
      setMessage("Saved in the shared PMS history.");
    } catch (e: any) {
      setFailed(true);
      setMessage(
        e.response?.data?.detail ||
          "Could not save; check the required fields.",
      );
    } finally {
      saving.current=false;
      setBusy(false);
    }
  }
  return (
    <div className="my-assignments-page space-y-5">
      <h1 className="text-2xl font-bold">My PMS Assignments</h1>
      <p>
        Interns and employees use the same PMS execution and review records.
      </p>
      <Link className="text-primary" to="/pms/batches">
        Batch Management →
      </Link>
      {error && <p role="alert">Assignments could not load.{phone && data && " Showing the last loaded assignments."}</p>}
      {phone && error && <Button variant="outline" disabled={source.isFetching || source.fetchStatus==="paused"} onClick={()=>void source.refetch()}>Retry assignments</Button>}
      {phone && (source.isFetching || source.fetchStatus==="paused") && <p role="status">{source.fetchStatus==="paused" ? "Waiting for a connection to load assignments." : data ? "Refreshing assignments…" : "Loading assignments…"}</p>}
      {phone && source.isSuccess && !source.isFetching && !data?.items?.length && <p role="status">No assignments on this page.</p>}
      {(!phone || data !== undefined) && <div className="overflow-auto rounded-xl border bg-card">
        <GridTable gridId="apps/project-management/pages/MyAssignmentsPage:table-1" className="w-full text-left text-sm">
          <thead>
            <tr>
              {["Task", "Status", "Deadline", "Progress", "Action"].map((h) => (
                <th className="p-3" key={h}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data?.items.map((r: Row) => (
              <tr {...recordPreviewProps(r)} className="border-t" key={r.id}>
                <td className="p-3">{r.title}</td>
                <td>{r.status}</td>
                <td>{r.due_date}</td>
                <td>{r.progress}%</td>
                <td>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={phone && busy}
                    onClick={() => {
                      if(phone && selected===r.id) {detailHeading.current?.scrollIntoView({block:"start"});detailHeading.current?.focus({preventScroll:true});return;}
                      if(!leaveDraft())return;
                      if(phone)setLinks("");
                      setSelected(r.id);
                      setNotes(r.notes || "");
                      setPercent(r.progress);
                      setFiles([]);
                      if(phone)requestAnimationFrame(()=>{detailHeading.current?.scrollIntoView({block:"start"});detailHeading.current?.focus({preventScroll:true});});
                    }}
                  >
                    Open Assignment
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </GridTable>
      </div>}
      <div className="assignments-pagination flex gap-3">
        <Button disabled={page === 1 || phone && busy} onClick={() => {if(leaveDraft()){if(phone)setSelected(undefined);setPage(page-1);}}}>
          Previous
        </Button>
        <span>
          Page {page} · {phone && data===undefined ? "—" : data?.total || 0} assignments
        </span>
        <Button
          disabled={page * 50 >= (data?.total || 0) || phone && busy}
          onClick={() => {if(leaveDraft()){if(phone)setSelected(undefined);setPage(page+1);}}}
        >
          Next
        </Button>
      </div>
      {message && <p role={phone && failed ? "alert" : "status"}>{message}</p>}
      {task && (
        <section aria-busy={phone ? busy : undefined} className="grid gap-4 rounded-xl border bg-card p-5">
          <h2 ref={detailHeading} tabIndex={phone ? -1 : undefined} className="text-lg font-semibold">{task.title}</h2>
          <div className="whitespace-pre-wrap">
            <RichTextContent value={task.description} />
          </div>
          <p>
            Reviewer #{task.reviewer_user_id} · Maximum score{" "}
            {task.maximum_score}
            {task.skill_level && ` · ${task.skill_level}`}
          </p>
          {!!task.blocked_by?.length && (
            <p role="status" className="rounded border p-3">
              Waiting for approval of your own prerequisites:{" "}
              {task.blocked_by.map((p: Row) => p.title).join(", ")}
            </p>
          )}
          {task.pack_run_id &&
            task.start_date &&
            task.start_date > new Date().toLocaleDateString("en-CA") && (
              <p role="status">Opens on {task.start_date}.</p>
            )}
          {phone && busy && <p role="status">Saving assignment changes…</p>}
          {editable ? (
            <>
              <Button
                disabled={busy||!canExecute}
                onClick={() =>
                  action(() =>
                    api.post(`/project-management/work/tasks/${task.id}/start`),
                  )
                }
              >
                Start Task
              </Button>
              <label>
                Progress %
                <Input
                  disabled={phone && busy}
                  aria-label="Progress percent"
                  type="number"
                  min={0}
                  max={99}
                  value={percent}
                  onChange={(e) => {changed();setPercent(Number(e.target.value));}}
                />
              </label>
              <label>
                Work notes
                <RichTextField
                  disabled={phone && busy}
                  data-legacy-format="markdown"
                  aria-label="Work notes"
                  className="min-h-28 w-full rounded border bg-background p-3"
                  value={notes}
                  onChange={(e) => {changed();setNotes(e.target.value);}}
                />
              </label>
              <Button
                disabled={busy||!canExecute}
                onClick={() =>
                  action(() =>
                    api.post(
                      `/project-management/work/tasks/${task.id}/progress`,
                      { progress_percent: percent, notes },
                    ),
                  )
                }
              >
                Save Progress
              </Button>
              <label>
                Evidence links (one per line)
                <textarea
                  disabled={phone && busy}
                  aria-label="Evidence links"
                  className="w-full rounded border p-3"
                  value={links}
                  onChange={(e) => {changed();setLinks(e.target.value);}}
                />
              </label>
              <label>
                Upload evidence
                <input
                  aria-label="Upload evidence"
                  type="file"
                  multiple
                  disabled={busy||!canExecute}
                  onChange={async (e) => {
                    if(phone) {
                      const input=e.currentTarget, chosen=Array.from(input.files || []);
                      if(!chosen.length || !canExecute || saving.current) return;
                      changed();
                      await action(async()=>{
                        const failedNames:string[]=[];
                        for(const file of chosen) {
                          try {
                            const form=new FormData();form.append("file",file);
                            const response=await api.post(`/project-management/work/tasks/${task.id}/files`,form);
                            setFiles(current=>[...current,response.data]);
                          } catch { failedNames.push(file.name); }
                        }
                        if(failedNames.length) throw {response:{data:{detail:`Could not upload: ${failedNames.join(", ")}. Successful files are retained. Select the failed files to retry.`}}};
                      });
                      input.value="";
                      return;
                    }
                    for (const file of Array.from(e.target.files || [])) {
                      await action(async () => {
                        const form = new FormData();
                        form.append("file", file);
                        const r = await api.post(
                          `/project-management/work/tasks/${task.id}/files`,
                          form,
                        );
                        setFiles((f) => [...f, r.data]);
                      });
                    }
                  }}
                />
              </label>
              {files.map((f) => (
                <p key={f.id}>{f.name}</p>
              ))}
              <div className="flex gap-3">
                {[true, false].map((draft) => (
                  <Button
                    key={String(draft)}
                    disabled={busy || !canExecute || !notes.trim()}
                    onClick={() =>
                      action(() =>
                        api.post(
                          `/project-management/work/tasks/${task.id}/submissions`,
                          {
                            notes,
                            links: links
                              .split("\n")
                              .map((l) => l.trim())
                              .filter(Boolean),
                            files: files.map((f) => f.id),
                            draft,
                            confirmed: !draft,
                          },
                        ),
                        true,
                      )
                    }
                  >
                    {draft ? "Save Draft" : "Submit for Review"}
                  </Button>
                ))}
              </div>
            </>
          ) : (
            <p>
              {locked
                ? "This task opens after its release date and your prerequisites are approved."
                : `This assignment is ${task.status}. Historical evidence and review decisions remain available in PMS.`}
            </p>
          )}
          <Link className="text-primary" to="/pms/reviews">
            Submission and Review History →
          </Link>
        </section>
      )}
    </div>
  );
}
