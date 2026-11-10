import BusinessProfileFields from "@/shared/master-data/BusinessProfileFields";
import { locationFields, locationValue } from "@/shared/data-grid/record-location";
import { SmartCreateAction } from "@/shared/creation/SmartCreateAction";
import {useRecordAutosave,useRecordDraft} from "@/hooks/use-record-autosave";
import {recordSavedEvent,type RecordSaved} from "@/lib/record-changes";
import {useModuleAction} from "@/hooks/use-module-action";
import {useDefinitionPermission} from "@/components/RecordDefinitionActions";
import { withRecordViewHost } from "@/shared/data-grid/RecordViewHost";
import WorkspaceViewBar, { type WorkspaceView } from "@/shared/workspace/WorkspaceViewBar";
import RecordLensViews from "@/shared/workspace/RecordLensViews";
import { useInitialLoading } from "@/hooks/use-initial-loading";
import { defaultText, leadSourceOptions } from "@/lib/form-defaults";
import { leadsApi as defaultLeadsApi } from "./api";
import { LeadRecordContext, useLeadRecord } from "./LeadRecordContext";
import CrmRecordFields, { useCrmFieldForm, CrmFieldsReadOnly } from "@/shared/custom-fields/CrmRecordFields";
import Record360Workspace from "@/shared/records/Record360Workspace";
import GridTable from "@/shared/data-grid/GridTable";
import { RecordStatusIcon } from "@/shared/data-grid/GroupLabel";
import PhoneActions from "@/components/PhoneActions";
import { SharedNumberConfirmation } from "@/shared/master-data/CompanySelect";
import { PersonPreviewHeader } from "@/components/PersonPreviewDialog";
import { useRecordView } from "@/lib/smart-cache/use-record-view";
import { NativeSelect } from "@/components/ui/native-select";
import { useMobile } from "@/components/mobile/useMobile";
import { MobileContactActions, MobileFilters } from "@/components/mobile/MobilePrimitives";
import CompactForm from "@/components/forms/CompactForm";
import { emailError, phoneError } from "@/lib/validation";
import { recordPreviewProps } from "@/components/RecordQuickPreview";
import { DataExportButton } from "@/shared/data-transfer";
import { LeadSpreadsheetImport } from "../CRMDataTransfer";
import CatalogAssociations, { CatalogLinesEditor } from "@/shared/catalog/CatalogLinesEditor";
import { linePayload, type CatalogLine } from "@/shared/catalog/api";
import {CRMInteractionDialog} from "../SalesActions";
import { api } from "@/services/api";
import { useRefreshableEffect } from "@/lib/page-refresh";
import { RichTextField, RichTextContent, richTextPlainText } from "@/components/rich-text/LazyRichText";
import React, { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useCreateIntent } from "@/hooks/use-create-intent";
import {
  UserRound, UserRoundPlus, Zap, BarChart3, Target, Flag, FileText, ChevronRight, Building2,
  ArrowRight,
  Check,
  Download,
  FileSpreadsheet,
  Loader2,
  Mail,
  Phone,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  Users,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { useAuthStore } from "@/store/authStore";
import { PhoneInput } from "@/lib/validation/PhoneInput";
import {
  Bootstrap,
  ConversionPreview,
  ImportPreview,
  Lead,
  LeadDetails,
  LeadPatch,
  ListResult,
  Settings,
  download,
  errorMessage,
  potentialClientsApi,
  publicUrl,
  captureEmbed,
} from "./api";
import "./leads.css";
import { LeadAnalyticsPanel } from "./LeadAnalyticsPanel";
import {
  FollowUpDialog,
  LeadTeamPanel,
  LeadWorkflowBoard,
} from "./LeadWorkflow";

const leadLenses = ["gallery", "gantt", "timeline", "calendar", "team", "mindmap", "whiteboard"];
// Follow-ups are instants; display their date in the user's timezone before
// passing them to the date-only planning lenses.
const leadCalendarDay = (value?: string) => {
  if (!value) return undefined;
  const date = new Date(/(Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`);
  return Number.isFinite(date.getTime()) ? `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}` : undefined;
};
const leadViews: WorkspaceView[] = [
  {id:"table",label:"Table",description:"Detailed qualification and inline actions",color:"#159d8c"},
  {id:"board",label:"Board",description:"Move leads through their qualification stages",color:"#6585e8"},
  {id:"compact",label:"List",icon:"list",description:"Focus on people and their next follow-up"},
  {id:"gallery",label:"Gallery",description:"Relationship cards with owner and next action",color:"#c36596"},
  {id:"gantt",label:"Gantt",description:"Lead age and upcoming follow-up windows",category:"Plan",color:"#e98279"},
  {id:"timeline",label:"Timeline",description:"See relationship and follow-up schedules",category:"Plan",color:"#cb9138"},
  {id:"calendar",label:"Calendar",description:"Follow-ups arranged by their due date",category:"Plan",color:"#e2a15d"},
  {id:"team",label:"Team",description:"Lead ownership across your team",category:"Explore",color:"#159d8c"},
  {id:"mindmap",label:"Mind map",description:"Explore relationships by stage or owner",category:"Explore",color:"#c36596"},
  {id:"whiteboard",label:"Whiteboard",description:"Arrange relationship cards in your personal workspace",category:"Explore",color:"#cb9138"},
  {id:"channel",label:"Channel",description:"Sales conversations with your team",category:"Collaborate",href:"/crm/messages"},
  {id:"files",label:"Files",description:"Shared collateral and customer documents",category:"Collaborate",href:"/crm/files",color:"#528bd2"},
  {id:"form",label:"Forms",description:"Structured enquiry and lead capture",category:"Collaborate",href:"/crm/webforms"},
];

const formatDate = (date?: string) =>
  date
    ? new Date(date).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "Not scheduled";
const dateInput = (date?: string | null) => {
  if (!date) return "";
  const d = new Date(date);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
};
const iso = (value: string) => (value ? new Date(value).toISOString() : null);
const emptyQualification = {
  need: "",
  budget: "",
  decisionMaker: "",
  timeline: "",
};
const queues = [
  ["all", "All leads"],
  ["my_day", "My day"],
  ["active", "Active"],
  ["sla", "SLA missed"],
  ["untouched", "Untouched"],
  ["overdue", "Overdue"],
  ["stale", "Inactive"],
  ["unassigned", "Unassigned / enquiry inbox"],
  ["reactivation", "Review due"],
  ["archived", "Archived"],
];
type SavedView = {
  name: string;
  search: string;
  stage: string;
  owner: string;
  queue: string;
  view: string;
};

function ErrorNotice({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div className="lm-error" role="alert">
      {message}
      {retry && (
        <Button size="sm" variant="outline" onClick={retry}>
          Try again
        </Button>
      )}
    </div>
  );
}
function StageBadge({ stage }: { stage: string }) {
  return (
    <span
      className={`lm-stage lm-stage-${stage.toLowerCase().replace(/[^a-z]/g, "")}`}
    >
      {stage}
    </span>
  );
}
function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  const controlId = React.useId();
  return (
    <div className="lm-field">
      <label htmlFor={controlId}>{label}</label>
      {React.isValidElement(children)
        ? React.cloneElement(children as React.ReactElement<{ id?: string }>, {
            id: controlId,
          })
        : children}
    </div>
  );
}

function LeadManagementPage({potential = false}: {potential?: boolean}) {
  return <LeadRecordContext.Provider value={{api: potential ? potentialClientsApi : defaultLeadsApi, potential}}><LeadWorkbench key={potential ? "potential" : "lead"}/></LeadRecordContext.Provider>;
}
function LeadWorkbench() {
  const {api: leadsApi, potential} = useLeadRecord();
  const { toast } = useToast();
  const userId = useAuthStore((s) => s.user?.id);
  const canEdit=useModuleAction("edit"),canAssign=useModuleAction("assign"),canDelete=useModuleAction("delete");
  const bulkAllowed=(action:string)=>action.startsWith("owner:")?canAssign:["archive","restore"].includes(action)?canDelete:canEdit;
  const canCreate=useDefinitionPermission(["crm_leads_manage","crm_manage","crm_admin"],"create");
  const [params, setParams] = useSearchParams();
  const [bootstrap, setBootstrap] = useState<Bootstrap>();
  const [result, setResult] = useState<ListResult>();
  const [loading, setLoading] = useState(true);
  const initialLoading = useInitialLoading(loading);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [selected, setSelected] = useState<number[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  useCreateIntent(kind => { if (kind === "leads") setCreateOpen(true); });
  const [importOpen, setImportOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [insights, setInsights] = useState(false);
  const [busy, setBusy] = useState(false);
  const [followUp, setFollowUp] = useState<{ lead: Lead; date?: string }>();
  const [bulk, setBulk] = useState<{
    patch: LeadPatch;
    workload?:{owner_id:number;visible_active_leads:number;selected_leads:number;pending_followups:number}|null;
    organization_id?:number;
    items: { id: number; name: string; stage: string }[];
  }>();
  const [bulkAction, setBulkAction] = useState("");
  const [savedViews, setSavedViews] = useState<SavedView[]>(() => {
    try {
      return JSON.parse(sessionStorage.getItem(`${potential ? "potential" : "lead"}-views-${userId}`) || "[]");
    } catch {
      return [];
    }
  });
  const [sharedViews,setSharedViews]=useState<SavedView[]>([]);
  useEffect(()=>{void api.get<{items:SavedView[]}>("/crm/productivity/shared-views").then(r=>setSharedViews(r.data.items)).catch(()=>{});},[]);
  const [viewName, setViewName] = useState("");
  const [showViewSave, setShowViewSave] = useState(false);
  const [columns, setColumns] = useState(() => {
    try {
      return JSON.parse(
        sessionStorage.getItem(`${potential ? "potential" : "lead"}-columns-${userId}`) ||
          '["company","owner","score","follow","action"]',
      ) as string[];
    } catch {
      return ["company", "owner", "score", "follow", "action"];
    }
  });
  const search = params.get("search") || "",
    stage = params.get("stage") || "",
    owner = params.get("owner") || "",
    queue = params.get("queue") || "all",
    view = params.get("view") || "table";
  const page = Number(params.get("page") || 1),
    opened = Number(params.get("lead") || 0);
  const [searchDraft, setSearchDraft] = useState(search);
  const updateParams = (values: Record<string, string>) =>
    setParams((current) => {
      const next = new URLSearchParams(current);
      Object.entries(values).forEach(([key, value]) =>
        value ? next.set(key, value) : next.delete(key),
      );
      return next;
    });
  const refresh = () => setRevision((v) => v + 1);
  useEffect(()=>{
    const changed=(event:Event)=>{
      const change=(event as CustomEvent<RecordSaved>).detail;
      if(!/^\/crm\/lead-management\/leads(?:\/\d+)?$/.test(change.url))return;
      const lead=change.record as unknown as Lead;
      if(!lead?.id||!lead.full_name)return;
      setResult(current=>{
        if(!current)return current;
        const exists=current.items.some(row=>row.id===lead.id);
        const hidden=queue!=="archived"&&lead.details?.archived||queue==="archived"&&!lead.details?.archived;
        if(hidden){const items=current.items.filter(row=>row.id!==lead.id);return {...current,items,total:Math.max(0,current.total-(current.items.length-items.length))};}
        if(!exists&&(page!==1||search||stage||owner||queue!=="all"||(lead.details?.recordType==="Potential")!==potential))return current;
        return {...current,items:exists?current.items.map(row=>row.id===lead.id?{...row,...lead}:row):[lead,...current.items],total:current.total+(exists?0:1)};
      });
    };
    window.addEventListener(recordSavedEvent,changed);return()=>window.removeEventListener(recordSavedEvent,changed);
  },[page,search,stage,owner,queue,potential]);

  const report = (err: unknown) =>
    toast({
      title: "Action could not be completed",
      description: errorMessage(err),
      variant: "destructive",
    });

  useRefreshableEffect(() => {
    let active = true;
    leadsApi
      .bootstrap()
      .then((r) => {
        if (active) setBootstrap(r.data);
      })
      .catch((err) => {
        if (active) setError(errorMessage(err));
      });
    return () => {
      active = false;
    };
  }, [revision]);
  useEffect(() => {
    setSearchDraft(search);
  }, [search]);
  useEffect(() => {
    if (searchDraft === search) return;
    const timer = setTimeout(
      () => updateParams({ search: searchDraft, page: "1" }),
      300,
    );
    return () => clearTimeout(timer);
  }, [searchDraft, search]);
  useRefreshableEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    leadsApi
      .list(
        {
          search,
          stage,
          ...(owner ? { owner } : {}),
          queue,
          page,
          per_page: 40,
        },
        controller.signal,
      )
      .then((r) => setResult(r.data))
      .catch((err) => {
        if (!controller.signal.aborted) setError(errorMessage(err));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [search, stage, owner, queue, page, revision]);
  useEffect(() => {
    setSelected([]);
  }, [search, stage, owner, queue, page]);
  useEffect(() => {
    sessionStorage.setItem(`${potential ? "potential" : "lead"}-columns-${userId}`, JSON.stringify(columns));
  }, [columns, userId]);
  useRecordView<ListResult>("/crm/lead-management/leads", { search, stage, ...(owner ? {owner} : {}), queue, page, per_page: 40 }, snapshot => { setResult(snapshot); setSelected(ids => ids.filter(id => snapshot.items.some(row => row.id === id))); }, () => { setResult(undefined); setSelected([]); });
  const ownerName = (id?: number) =>
    bootstrap?.owners.find((o) => o.id === id)?.name ||
    (id ? `User ${id}` : "Unassigned");
  const openLead = (id: number) => {
    sessionStorage.setItem(`${potential ? "potential" : "lead"}-scroll-${userId}`, String(window.scrollY));
    updateParams({ lead: String(id) });
  };
  const closeLead = () => {
    updateParams({ lead: "", transition: "" });
    requestAnimationFrame(() =>
      window.scrollTo(
        0,
        Number(sessionStorage.getItem(`${potential ? "potential" : "lead"}-scroll-${userId}`) || 0),
      ),
    );
  };
  const mutate = async (lead: Lead, patch: LeadPatch) => {
    setBusy(true);
    try {
      await leadsApi.update(lead.id, { ...patch, version: lead.version });
      toast({ title: "Lead saved" });
      refresh();
    } catch (err) {
      report(err);
      updateParams({
        lead: String(lead.id),
        transition: String(patch.values?.status || ""),
      });
    } finally {
      setBusy(false);
    }
  };
  const previewBulk = async () => {
    if(!bulkAllowed(bulkAction))return;
    let patch: LeadPatch;
    if (bulkAction.startsWith("owner:")) {
      const reason=window.prompt("Reason for reassigning these leads and their pending follow-ups");if(!reason?.trim())return;
      patch = { values: { owner_user_id: Number(bulkAction.slice(6)) },details:{assignmentReason:reason} };
    }
    else if (bulkAction === "promote")
      patch = {details: {recordType: "Lead"}};
    else if (bulkAction.startsWith("stage:"))
      patch = { values: { status: bulkAction.slice(6) } };
    else if (bulkAction === "archive") {
      const reason = window.prompt("Reason for archiving these leads");
      if (!reason) return;
      patch = { details: { archived: true, archiveReason: reason } };
    } else if (bulkAction === "restore")
      patch = { details: { archived: false } };
    else return;
    setBusy(true);
    try {
      const response = await leadsApi.bulkPreview(selected, patch);
      setBulk({ patch, items: response.data.items,workload:response.data.workload,organization_id:response.data.organization_id });
    } catch (err) {
      report(err);
    } finally {
      setBusy(false);
    }
  };
  const saveView = () => {
    if (!viewName.trim()) return;
    const next = [
      ...savedViews.filter((v) => v.name !== viewName.trim()),
      { name: viewName.trim(), search, stage, owner, queue, view },
    ].slice(-20);
    setSavedViews(next);
    sessionStorage.setItem(`${potential ? "potential" : "lead"}-views-${userId}`, JSON.stringify(next));
    setShowViewSave(false);
    setViewName("");
  };

  return (
    <div className="lm-root" aria-label="Lead workbench">
      {followUp && bootstrap && (
        <FollowUpDialog
          lead={followUp.lead}
          bootstrap={bootstrap}
          initialDate={followUp.date}
          close={() => setFollowUp(undefined)}
          saved={() => {
            refresh();
            toast({ title: "Follow-up saved" });
          }}
        />
      )}
      <header className="lm-header">
        <div>
          <div className="lm-eyebrow">CUSTOMER RELATIONSHIPS</div>
          <h1>
            {potential ? "Potential Clients" : "Lead workbench"}{" "}
            <span className="lm-count">{result?.total ?? "—"}</span>
          </h1>
          <p>Know where every enquiry stands. Make the next move.</p>
        </div>
        <div className="lm-actions">
          <DataExportButton filename={potential ? "potential-clients.xlsx" : "leads.xlsx"} description={selected.length?`${selected.length} selected leads`:"All permitted leads matching search, stage and owner filters. Includes archived leads."} load={async()=> (await leadsApi.export(selected.length?{ids:selected.join(",")}:{search,stage,...(owner?{owner}:{})})).data}/>

          {bootstrap?.canManage && canCreate && (
            <>
              <Button variant="outline" onClick={() => setImportOpen(true)}>
                <FileSpreadsheet size={16} />
                Import Excel
              </Button>
              <Button onClick={() => setCreateOpen(true)}>
                <Plus size={16} />
                {potential ? "Add potential client" : "Add lead"}
              </Button>
            </>
          )}
          {bootstrap?.canAdmin && (
            <Button
              variant="outline"
              aria-label="Lead workflow settings"
              onClick={() => setSettingsOpen(true)}
            >
              <Settings2 size={17} />
            </Button>
          )}
        </div>
      </header>
      <nav className="lm-links" aria-label="Related CRM tools">
        <Link to={potential ? "/crm/leads" : "/crm/potential-clients"}>{potential ? "Leads" : "Potential Clients"}</Link>
        <Link to="/crm/webforms">Website forms</Link>
        <Link to="/crm/communication-hub">Communications</Link>
        <Link to="/crm/calendar">Calendar & scheduling</Link>
        <Link to="/crm/duplicates?entity=lead">Duplicate review & merge</Link>
      </nav>
      <section className="lm-metrics" aria-label="Lead health">
        {[
          ["active", "Active leads"],
          ["overdue", "Overdue follow-ups"],
          ["slaBreached", "Response SLA missed"],
          ["stale", "Inactive leads"],
        ].map(([key, label]) => (
          <button
            key={key}
            onClick={() =>
              updateParams({
                queue:
                  key === "overdue"
                    ? "overdue"
                    : key === "stale"
                      ? "stale"
                      : key === "slaBreached"
                        ? "sla"
                        : "active",
                page: "1",
              })
            }
          >
            <span>{label}</span>
            <strong>{result?.summary[key] ?? "—"}</strong>
            <span className="lm-metric-caption">
              {search || stage || owner
                ? "Within current filters"
                : "Visible CRM records"}
            </span>
          </button>
        ))}
      </section>
      <div className="lm-tabs" role="group" aria-label="Lead queues">
        {queues.map(([key, label]) => (
          <button
            key={key}
            aria-pressed={queue === key}
            className={queue === key ? "active" : ""}
            onClick={() => updateParams({ queue: key, page: "1" })}
          >
            {label}
          </button>
        ))}
        <button
          className={insights ? "active" : ""}
          aria-pressed={insights}
          onClick={() => setInsights((v) => !v)}
        >
          Insights
        </button>
      </div>
      {insights && result && (
        <section className="lm-insights">
          <div>
            <h2>Current lead stages</h2>
            <p>Snapshot counts, not historical stage conversion.</p>
            {Object.entries(result.byStage).map(([name, count]) => (
              <div className="lm-bar-row" key={name}>
                <span>{name}</span>
                <meter
                  min="0"
                  max={Math.max(result.summary.total, 1)}
                  value={count}
                />
                <strong>{count}</strong>
              </div>
            ))}
          </div>
          <div>
            <h2>Source quality</h2>
            <p>Converted leads / total leads from each source.</p>
            {Object.entries(result.bySource).map(([name, count]) => (
              <div className="lm-bar-row" key={name}>
                <span>{name}</span>
                <span>
                  {result.convertedBySource[name] || 0} / {count} converted
                </span>
                <strong>
                  {Math.round(
                    ((result.convertedBySource[name] || 0) / count) * 100,
                  )}
                  %
                </strong>
              </div>
            ))}
          </div>
          <div>
            <h2>Why leads were lost</h2>
            {Object.entries(result.lostReasons).length ? (
              Object.entries(result.lostReasons).map(([reason, count]) => (
                <p key={reason}>
                  {reason} <strong>{count}</strong>
                </p>
              ))
            ) : (
              <p>No lost leads in the current filters.</p>
            )}
            <Link to="/crm/reports">
              Open CRM funnel report <ArrowRight size={14} />
            </Link>
          </div>
        </section>
      )}
      {insights && bootstrap && (
        <LeadAnalyticsPanel owners={bootstrap.owners} revision={revision} />
      )}
      <section className="lm-workspace" aria-label="Lead records">
        <div className="lm-toolbar">
          <label className="lm-search">
            <Search size={17} />
            <input
              aria-label="Search leads"
              placeholder="Search name, company, email or phone"
              value={searchDraft}
              onChange={(e) => setSearchDraft(e.target.value)}
            />
          </label>
          <MobileFilters chips={[stage,owner ? `Owner ${owner}` : ""].filter(Boolean)} onClear={()=>updateParams({stage:"",owner:"",page:"1"})}>
          <NativeSelect
            aria-label="Filter stage"
            value={stage}
            onChange={(e) => updateParams({ stage: e.target.value, page: "1" })}
          >
            <option value="">All stages</option>
            {bootstrap?.settings.stages.map((s) => (
              <option key={s.name}>{s.name}</option>
            ))}
          </NativeSelect>
          <NativeSelect
            aria-label="Filter owner"
            value={owner}
            onChange={(e) => updateParams({ owner: e.target.value, page: "1" })}
          >
            <option value="">All visible owners</option>
            {bootstrap?.owners.map((o) => (
              <option value={o.id} key={o.id}>
                {o.name}
              </option>
            ))}
          </NativeSelect>
          </MobileFilters>
          <details className="lm-personal-options"><summary>View options</summary><div className="lm-view-tools">
          <NativeSelect
            aria-label="Saved views"
            value=""
            onChange={(e) => {
              const saved = e.target.value.startsWith("shared:")?sharedViews.find(v=>v.name===e.target.value.slice(7)):savedViews.find((v) => v.name === e.target.value);
              if (saved) {
                const { name: _, ...values } = saved;
                updateParams({ ...values, page: "1" });
              }
            }}
          >
            <option value="">Saved views</option>
            {savedViews.map((v) => (
              <option key={v.name} value={v.name}>Personal: {v.name}</option>
            ))}{sharedViews.map(v=><option key={`shared:${v.name}`} value={`shared:${v.name}`}>Shared: {v.name}</option>)}
          </NativeSelect>
          <Button type="submit" variant="outline" onClick={() => setShowViewSave((v) => !v)}>
            Save current view
          </Button>
          {showViewSave && (
            <>
              <input
                aria-label="View name"
                maxLength={80}
                placeholder="Name this view"
                value={viewName}
                onChange={(e) => setViewName(e.target.value)}
              />
              <Button type="submit" variant="outline" disabled={!viewName.trim()} onClick={saveView}>Save personal view</Button>{bootstrap?.canAssign&&<SmartCreateAction title="Publish shared view"><button disabled={!viewName.trim()} onClick={()=>{void api.post("/crm/productivity/shared-views",{name:viewName,search,stage,owner,queue,view}).then(()=>{setSharedViews(v=>[...v,{name:viewName,search,stage,owner,queue,view}]);setShowViewSave(false);setViewName("");toast({title:"Shared lead view saved"});}).catch(report);}}>Publish shared view</button></SmartCreateAction>}
            </>
          )}
          {view === "table" && <details>
            <summary>Columns</summary>
            <div className="lm-column-options">
              {["company", "owner", "score", "follow", "action"].map(
                (column) => (
                  <label key={column}>
                    <input
                      type="checkbox"
                      checked={columns.includes(column)}
                      onChange={(e) =>
                        setColumns((current) =>
                          e.target.checked
                            ? [...current, column]
                            : current.filter((c) => c !== column),
                        )
                      }
                    />
                    {column}
                  </label>
                ),
              )}
            </div>
          </details>}
          {bootstrap?.canManage && (
            <button
              onClick={async () => {
                try {
                  const r = await leadsApi.alerts();
                  toast({
                    title: `${r.data.notificationsCreated} response alerts created`,
                  });
                } catch (err) {
                  report(err);
                }
              }}
            >
              Escalate missed response deadlines
            </button>
          )}
        </div></details>
          <Button
            size="sm"
            variant="ghost"
            onClick={refresh}
            aria-label="Refresh leads"
          >
            <RefreshCw size={16} />
          </Button>
        </div>
        <WorkspaceViewBar label="Lead views" scope={potential ? "crm-potential-clients" : "crm-leads"} active={view} views={leadViews} onChange={view=>updateParams({view})} primary={["table","board","compact","gallery","calendar","team"]}/>
        {!!selected.length && bootstrap?.canManage && (
          <div className="lm-bulk">
            <strong>{selected.length} selected</strong>
            <NativeSelect
              aria-label="Bulk action"
              value={bulkAction}
              onChange={(e) => setBulkAction(e.target.value)}
            >
              <option value="">Choose action</option>
              <optgroup label="Change stage">
                {bootstrap.settings.stages
                  .filter((s) => !["Converted", "Lost"].includes(s.name))
                  .map((s) => (
                    <option disabled={!canEdit} value={`stage:${s.name}`} key={s.name}>
                      {s.name}
                    </option>
                  ))}
              </optgroup>
              <optgroup label="Assign owner">
                {bootstrap.owners.map((o) => (
                  <option disabled={!canAssign} value={`owner:${o.id}`} key={o.id}>
                    {o.name}
                  </option>
                ))}
              </optgroup>
              {potential && <option disabled={!canEdit} value="promote">Move to Leads</option>}
              <option disabled={!canDelete} value="archive">Archive with reason</option>
              <option disabled={!canDelete} value="restore">Restore from archive</option>
            </NativeSelect>
            <Button
              size="sm"
              variant="outline"
              onClick={previewBulk}
              disabled={!bulkAction || busy || !bulkAllowed(bulkAction)}
            >
              Preview changes
            </Button>
            <button onClick={() => setSelected([])}>Clear selection</button>
          </div>
        )}
        {error && <ErrorNotice message={error} retry={refresh} />}
        {result?.truncated && (
          <div className="lm-warning">
            Showing the newest {result.limit.toLocaleString()} permitted leads.
            Narrow search, stage or owner filters to review older records.
          </div>
        )}
        {initialLoading ? (
          <div className="lm-loading" role="status">
            <Loader2 className="animate-spin" />
            Loading lead records…
          </div>
        ) : !result?.items.length ? (
          <div className="lm-empty">
            <Users size={30} />
            <h2>
              {queue === "my_day" ? "Your queue is clear" : potential ? "No matching potential clients" : "No matching leads"}
            </h2>
            <p>
              {queue === "my_day"
                ? "New assignments and due follow-ups will appear here."
                : "Adjust your filters, add a lead or import an Excel workbook."}
            </p>
            <Button
              variant="outline"
              onClick={() => {
                setSearchDraft("");
                updateParams({
                  search: "",
                  stage: "",
                  owner: "",
                  queue: "all",
                  page: "1",
                });
              }}
            >
              Reset filters
            </Button>
          </div>
        ) : leadLenses.includes(view) ? (
          <><RecordLensViews view={view} scope={potential ? "crm-potential-clients" : "crm-leads"} records={result.items.map(lead=>({id:String(lead.id),title:lead.full_name,subtitle:lead.company_name || lead.job_title,status:lead.status,owner:bootstrap?.owners.find(owner=>owner.id===lead.owner_user_id)?.name,start:leadCalendarDay(lead.created_at),due:leadCalendarDay(lead.next_follow_up_at),tags:[lead.source || "Other",lead.signals.followUpLabel].filter(Boolean)}))} onOpen={record=>openLead(Number(record.id))}/><p className="lm-help">Current result page · Calendar uses next follow-up dates. Open a lead to update its schedule.</p></>
        ) : view === "board" ? (
          bootstrap && (
            <LeadWorkflowBoard
              group={params.get("group") || "stage"}
              groupChanged={(group) => updateParams({ group })}
              leads={result.items}
              bootstrap={bootstrap}
              busy={busy}
              open={openLead}
              move={(lead, values) => void mutate(lead, { values })}
              schedule={(lead, date) => setFollowUp({ lead, date })}
            />
          )
        ) : view === "compact" ? (
          <div className="lm-compact">
            {result.items.map((lead) => (
              <button key={lead.id} onClick={() => openLead(lead.id)}>
                <div>
                  <strong>{lead.full_name}</strong>
                  <span>{lead.company_name || lead.email}</span>
                </div>
                <StageBadge stage={lead.status} />
                <span className={lead.signals.overdue ? "lm-danger-text" : ""}>
                  {lead.signals.followUpLabel}
                </span>
                <ArrowRight size={17} />
              </button>
            ))}
          </div>
        ) : (
          <div className="lm-table-scroll">
            <GridTable gridId="apps/crm/leads/LeadManagementPage:table-1" hideSearch externalPagination className="lm-table">
              <thead>
                <tr>
                  <th>
                    {bootstrap?.canManage && (
                      <input
                        type="checkbox"
                        aria-label="Select all leads on this page"
                        checked={
                          result.items.length > 0 &&
                          result.items.every((l) => selected.includes(l.id))
                        }
                        onChange={(e) =>
                          setSelected(
                            e.target.checked
                              ? result.items.map((l) => l.id)
                              : [],
                          )
                        }
                      />
                    )}
                  </th>
                  <th>Lead</th>
                  <th>Stage</th>
                  {locationFields.map(field=><th key={field.id}>{field.label}</th>)}
                  {columns.includes("company") && <th>Company</th>}
                  {columns.includes("owner") && <th>Assigned employee</th>}
                  {columns.includes("score") && <th>Score</th>}
                  {columns.includes("follow") && <th>Follow-up</th>}
                  {columns.includes("action") && <th>Next action</th>}
                </tr>
              </thead>
              <tbody>
                {result.items.map((lead) => (
                  <tr {...recordPreviewProps(lead)} key={lead.id}>
                    <td>
                      {bootstrap?.canManage && (
                        <input
                          type="checkbox"
                          aria-label={`Select ${lead.full_name}`}
                          checked={selected.includes(lead.id)}
                          onChange={(e) =>
                            setSelected((current) =>
                              e.target.checked
                                ? [...current, lead.id]
                                : current.filter((id) => id !== lead.id),
                            )
                          }
                        />
                      )}
                    </td>
                    <td>
                      <div className="lm-record-identity"><span aria-hidden="true"><RecordStatusIcon label={lead.status} field="Stage"/></span><div>
                      <button
                        className="lm-name"
                        onClick={() => openLead(lead.id)}
                      >
                        {lead.full_name}
                      </button>
                      <span className="lm-secondary">
                        {lead.email || (lead.phone ? <PhoneActions value={lead.phone} record={lead} /> : "No contact details")}
                      </span>
                      </div></div>
                    </td>
                    <td>
                      {bootstrap?.canManage && canEdit && !lead.is_converted ? (
                        <NativeSelect
                          className="lm-inline"
                          aria-label={`Stage for ${lead.full_name}`}
                          disabled={busy}
                          value={lead.status}
                          onChange={(e) => {
                            if (e.target.value === "Lost") {
                              updateParams({
                                lead: String(lead.id),
                                transition: "Lost",
                              });
                            } else
                              void mutate(lead, {
                                values: { status: e.target.value },
                              });
                          }}
                        >
                          <option>{lead.status}</option>
                          {bootstrap.settings.stages
                            .find((s) => s.name === lead.status)
                            ?.allowedNext.filter((name) => name !== "Converted")
                            .map((name) => (
                              <option key={name}>{name}</option>
                            ))}
                        </NativeSelect>
                      ) : (
                        <StageBadge stage={lead.status} />
                      )}
                    </td>
                    {locationFields.map(field=><td key={field.id}>{locationValue(lead,field) || "Not set"}</td>)}
                    {columns.includes("company") && (
                      <td>{lead.company_name || "—"}</td>
                    )}
                    {columns.includes("owner") && (
                      <td>
                        {bootstrap?.canManage && canAssign && bootstrap.owners.length > 1 ? (
                          <NativeSelect
                            className="lm-inline"
                            aria-label={`Owner for ${lead.full_name}`}
                            value={lead.owner_user_id || ""}
                            disabled={busy}
                            onChange={(e) =>
                              void mutate(lead, {
                                values: {
                                  owner_user_id: Number(e.target.value),
                                },
                              })
                            }
                          >
                            <option value="" disabled>
                              Unassigned
                            </option>
                            {!!lead.owner_user_id &&
                              !bootstrap.owners.some(
                                (o) => o.id === lead.owner_user_id,
                              ) && (
                                <option value={lead.owner_user_id} disabled>
                                  Current assignee (unavailable)
                                </option>
                              )}
                            {bootstrap.owners.map((o) => (
                              <option value={o.id} key={o.id}>
                                {o.name}
                              </option>
                            ))}
                          </NativeSelect>
                        ) : (
                          ownerName(lead.owner_user_id)
                        )}
                      </td>
                    )}
                    {columns.includes("score") && (
                      <td>
                        <span className="lm-score">{lead.lead_score || 0}</span>
                        <span className="lm-secondary">
                          {lead.lead_score_mode}
                        </span>
                      </td>
                    )}
                    {columns.includes("follow") && (
                      <td>
                        <span
                          className={
                            lead.signals.overdue ? "lm-danger-text" : ""
                          }
                        >
                          {lead.signals.followUpLabel}
                        </span>
                        <span className="lm-secondary">
                          {lead.next_follow_up_at
                            ? formatDate(lead.next_follow_up_at)
                            : "Choose a next step"}
                        </span>
                      </td>
                    )}
                    {columns.includes("action") && (
                      <td className="lm-next-action">
                        {lead.signals.slaBreached && (
                          <span className="lm-alert-dot" />
                        )}
                        <span className="lm-next-action-text" title={lead.signals.nextAction}>{lead.signals.nextAction}</span>
                        {bootstrap?.canManage && lead.signals.active && (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={busy}
                            onClick={() => setFollowUp({ lead })}
                          >
                            Follow up
                          </Button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </GridTable>
          </div>
        )}
        <footer className="lm-pagination">
          <span>
            {result?.total || 0} matching leads ·{" "}
            {view === "board" ? "Board shows current page" : "40 per page"}
          </span>
          <div>
            <Button
              size="sm"
              variant="outline"
              disabled={page <= 1 || loading}
              onClick={() => updateParams({ page: String(page - 1) })}
            >
              Previous
            </Button>
            <span>
              Page {page} of {Math.max(1, Math.ceil((result?.total || 0) / 40))}
            </span>
            <Button
              size="sm"
              variant="outline"
              disabled={page * 40 >= (result?.total || 0) || loading}
              onClick={() => updateParams({ page: String(page + 1) })}
            >
              Next
            </Button>
          </div>
        </footer>
      </section>
      {bootstrap && createOpen && (
        <CaptureDialog
          bootstrap={bootstrap}
          close={() => setCreateOpen(false)}
          saved={() => {
            setCreateOpen(false);
            refresh();
            toast({ title: potential ? "Potential client created" : "Lead created" });
          }}
        />
      )}
      {bootstrap && opened > 0 && (
        <LeadDrawer
          id={opened}
          targetStage={params.get("transition") || ""}
          bootstrap={bootstrap}
          close={closeLead}
          changed={refresh}
          previous={result&&result.items.findIndex(l=>l.id===opened)>0?()=>openLead(result.items[result.items.findIndex(l=>l.id===opened)-1].id):undefined}
          next={result&&result.items.findIndex(l=>l.id===opened)>=0&&result.items.findIndex(l=>l.id===opened)<result.items.length-1?()=>openLead(result.items[result.items.findIndex(l=>l.id===opened)+1].id):undefined}
        />
      )}
      {importOpen && (
        <ExcelDialog
          close={() => setImportOpen(false)}
          imported={() => {
            setImportOpen(false);
            refresh();
          }}
        />
      )}
      {bootstrap && settingsOpen && (
        <WorkflowSettings
          bootstrap={bootstrap}
          close={() => setSettingsOpen(false)}
          saved={() => {
            setSettingsOpen(false);
            refresh();
          }}
        />
      )}
      <Dialog
        open={!!bulk}
        onOpenChange={(open) => {
          if (!open && !busy) setBulk(undefined);
        }}
      >
        <DialogContent className="lm-dialog">
          <DialogTitle>Review bulk changes</DialogTitle>
          <p>
            {bulk?.items.length} leads will be updated. Changes are applied
            together; a validation failure keeps all records unchanged.
          </p>
          <pre className="lm-change-preview">
            {bulk?.patch.values?.status
              ? `Stage → ${bulk.patch.values.status}`
              : bulk?.patch.values?.owner_user_id
                ? `Owner → ${ownerName(Number(bulk.patch.values.owner_user_id))}`
                : bulk?.patch.details?.archived
                  ? `Archive: ${bulk.patch.details.archiveReason}`
                  : "Restore archived leads"}
          </pre>
          {bulk?.workload&&<p className="rounded border p-3 text-sm">Organization #{bulk.organization_id} · Replacement currently owns {bulk.workload.visible_active_leads} visible active leads. This operation affects {bulk.workload.selected_leads} selected leads and {bulk.workload.pending_followups} pending follow-ups.</p>}
          <ul className="lm-preview-list">
            {bulk?.items.map((item) => (
              <li key={item.id}>
                {item.name}
                <StageBadge stage={item.stage} />
              </li>
            ))}
          </ul>
          <Button
            disabled={busy}
            onClick={async () => {
              if (!bulk) return;
              setBusy(true);
              try {
                const response = await leadsApi.bulkApply(
                  bulk.items.map((i) => i.id),
                  bulk.patch,
                );
                const ids=new Set(bulk.items.map(item=>item.id));
                if(response.data.updated===ids.size)setResult(current=>{
                  if(!current)return current;
                  const items=current.items.map(row=>ids.has(row.id)?{...row,...bulk.patch.values,details:{...row.details,...bulk.patch.details}}:row).filter(row=>queue==="archived"?!!row.details.archived:!row.details.archived);
                  return {...current,items,total:Math.max(0,current.total-(current.items.length-items.length))};
                });
                toast({ title: `${response.data.updated} leads updated` });
                setBulk(undefined);
                setSelected([]);
                refresh();
              } catch (err) {
                report(err);
              } finally {
                setBusy(false);
              }
            }}
          >
            Apply to {bulk?.items.length} leads
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export function CaptureDialog({
  placement="create",
  bootstrap,
  close,
  saved,
}: {
  placement?:"create"|"quick_create";
  bootstrap: Bootstrap;
  close: () => void;
  saved: (id: number) => void;
}) {
  const {api: leadsApi, potential} = useLeadRecord();
  const customFieldForm=useCrmFieldForm("leads",placement);
  const mobile = useMobile();
  const [expandedMobileCapture, setExpandedMobileCapture] = useState(false);
  const key = `${potential ? "potential" : "lead"}-capture-draft-${bootstrap.userId}`;
  const automaticRouting =
    bootstrap.settings.assignment.mode !== "manual" ||
    bootstrap.settings.assignment.rules.length > 0;
  const defaultOwner = automaticRouting
    ? ""
    : String(bootstrap.owners.find((o) => o.id === bootstrap.userId)?.id || "");
  const [values, setValues] = useState<Record<string, string>>(() => {
    try {
      return JSON.parse(
        sessionStorage.getItem(key) ||
          JSON.stringify({full_name:"",email:"",phone:"",company_name:"",source:defaultText("lead_source", "crm")}),
      );
    } catch {
      return { full_name: "", source: defaultText("lead_source", "crm") };
    }
  });
  const [catalogLines, setCatalogLines] = useState<CatalogLine[]>(() => { try { const draft = JSON.parse(sessionStorage.getItem(`${key}:catalog`) || "[]"); return Array.isArray(draft) ? draft : []; } catch { return []; } });
  useEffect(() => { sessionStorage.setItem(`${key}:catalog`, JSON.stringify(catalogLines)); }, [key, catalogLines]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const captureSubmitting = useRef(false);
  const [sharedConfirmed,setSharedConfirmed]=useState(false);const [sharedReason,setSharedReason]=useState("");
  const [duplicate,setDuplicate]=useState<{matched:boolean;items:{id:number;name:string}[];message:string}>();
  useEffect(()=>{const controller=new AbortController();const timer=setTimeout(()=>{if(!values.email&&!values.phone){setDuplicate(undefined);return;}void api.get("/crm/productivity/duplicate-check",{params:{email:values.email||"",phone:values.phone||"",phone_country_code:values.phone_country_code||""},signal:controller.signal}).then(r=>setDuplicate(r.data)).catch(()=>{});},350);return()=>{clearTimeout(timer);controller.abort();};},[values.email,values.phone,values.phone_country_code]);
  useEffect(() => {
    sessionStorage.setItem(key, JSON.stringify(values));
  }, [values, key]);
  const dismiss = () => {if(!saving)close();};
  const clearFullDraft=useRecordDraft(`${potential?"potential":"lead"}:capture`,{values,catalogLines,customValues:customFieldForm.values,sharedConfirmed,sharedReason},draft=>{setValues(draft.values);setCatalogLines(draft.catalogLines||[]);customFieldForm.setValues(draft.customValues||{});setSharedConfirmed(draft.sharedConfirmed);setSharedReason(draft.sharedReason);},!customFieldForm.loading);
  const [step, setStep] = useState(0);
  const captureForm = useRef<HTMLFormElement>(null);
  const captureTabs = ["Basic Details", "Contact Info", "Company Details", "Additional", "Products & services"];
  const priority = values.capture_priority || "Medium";
  const setPriority = (priority: string) => setValues(v => ({...v, capture_priority: priority}));
  const update = (name: string, value: string) => {
    setValues(v => ({...v, [name]: value}));
    if (name === "full_name") setError("");
  };
  const field = (name: string, label: string, placeholder = "", type = "text") => <label className="lead-create-field">{label}<span className="lead-create-control"><UserRound size={19}/><input aria-label={label} autoFocus={name === "full_name"} required={name === "full_name"} type={type} maxLength={name === "full_name" ? 220 : 180} placeholder={placeholder} value={values[name] || ""} onChange={e => update(name, e.target.value)}/></span></label>;
  return <Dialog open onOpenChange={open => {if (!open) dismiss();}}>
    <DialogContent className="lead-create-dialog" overlayClassName="lead-create-overlay">
      <aside className="lead-create-aside">
        <div className="lead-create-emblem"><UserRoundPlus size={34}/></div>
        <DialogTitle>{potential ? "Create Potential Client" : "Create New Lead"}</DialogTitle>
        <p className="lead-create-intro">Capture potential business opportunities and start the conversation.</p>
        <div className="lead-create-benefits">{[[Zap, "Quick & Easy", "Add essential details in seconds"], [Users, "Organize Better", "Keep all lead information in one place"], [BarChart3, "Convert Faster", "Track and move leads through pipeline"]].map(([Icon, title, text]) => {const Glyph = Icon as typeof Zap; return <div key={String(title)}><span><Glyph size={28}/></span><p><strong>{String(title)}</strong><small>{String(text)}</small></p></div>;})}</div>
        <div className="lead-create-art" aria-hidden="true">
          <div className="lead-art-card"><UserRound size={32}/><i/><i/><i/></div>
          <div className="lead-art-chart"><BarChart3 size={43}/></div>
          <div className="lead-art-target"><div><div><div/></div></div></div>
          <div className="lead-art-arrow"><span/><i/></div>
          <div className="lead-art-check"><Check size={29}/></div>
        </div>
      </aside>
      <CompactForm noValidate ref={captureForm} className="lead-create-main"
          onSubmit={async (e) => {
            e.preventDefault();
            if (captureSubmitting.current) return;
            const nameMissing = !values.full_name?.trim();
            const contactError = emailError(values.email) || phoneError(values.phone, values.phone_country_code);
            if (nameMissing || contactError) {
              setStep(nameMissing ? 0 : 1);
              setError(nameMissing ? "Lead name is required. Everything else can be added later." : String(contactError));
              requestAnimationFrame(() => captureForm.current?.querySelector<HTMLInputElement>(nameMissing ? '[aria-label="Lead Name *"]' : values.email ? '[aria-label="Email"]' : 'input[type="tel"]')?.focus());
              return;
            }
            if (duplicate?.matched && bootstrap.settings.preventDuplicates && !sharedConfirmed) { setStep(1); setError("Review the matching lead before creating another record."); return; }
            let customFields;
            try { customFields=customFieldForm.validate(); } catch(error) { setError(error instanceof Error?error.message:"Check the custom fields."); return; }
            captureSubmitting.current = true;
            setSaving(true);
            setError("");
            try {
              const response = await leadsApi.create({
                customFields,
                confirmShared:sharedConfirmed,sharedReason:sharedReason||undefined,
                catalog_lines: catalogLines.map(linePayload),
                values: Object.fromEntries(
                  Object.entries({
                    ...values,
                    full_name: values.full_name.trim(),
                    source: values.source || defaultText("lead_source", "crm"),
                    status: values.status || bootstrap.settings.stages[0]?.name || "New",
                    notes: [values.notes, `Priority: ${priority}`].filter(Boolean).join("\n"),
                    owner_user_id: values.owner_user_id ?? defaultOwner,
                  }).filter(([name, value]) => value !== "" && name !== "capture_priority"),
                ),
              });
              clearFullDraft();
              sessionStorage.removeItem(key);
              sessionStorage.removeItem(`${key}:catalog`);
              saved(response.data.id);
            } catch (err) {
              setError(errorMessage(err));
            } finally {
              captureSubmitting.current = false;
              setSaving(false);
            }
          }}
        >

          <nav className="lead-create-steps" role="tablist" aria-label="Lead creation sections" onKeyDown={event => { const next = event.key === "ArrowRight" ? (step + 1) % captureTabs.length : event.key === "ArrowLeft" ? (step - 1 + captureTabs.length) % captureTabs.length : event.key === "Home" ? 0 : event.key === "End" ? captureTabs.length - 1 : -1; if (next >= 0) { event.preventDefault(); setStep(next); event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus(); } }}>{captureTabs.map((title, index) => <button key={title} type="button" role="tab" id={`lead-capture-tab-${index}`} aria-controls="lead-capture-panel" aria-selected={step === index} tabIndex={step === index ? 0 : -1} onClick={() => setStep(index)}><span aria-hidden="true">{index + 1}</span>{title}{index === 4 && catalogLines.length > 0 ? ` (${catalogLines.length})` : ""}</button>)}</nav>
          <div className="lead-create-body" id="lead-capture-panel" role="tabpanel" aria-labelledby={`lead-capture-tab-${step}`}>
            <h3>{["Basic Information", "Contact Information", "Company Details", "Additional Information", "Products & services"][step]}</h3>
            <p className="lead-create-subtitle">{["Only the lead name is required. Fill other details now or add them later.", "Email and phone are optional. Add whichever you have.", "Company details are optional and can be updated later.", "Use the default assignment or choose who will take this opportunity forward.", "Link relevant products and services. This section is optional."][step]}</p>
            {step === 0 && <div className="lead-create-grid">
              {field("full_name", "Lead Name *", "e.g. John Smith")}
              {mobile && <label className="lead-create-field">Phone<PhoneInput value={values.phone || ""} countryCode={values.phone_country_code || ""} onChange={phone => update("phone", phone)} onCountryCodeChange={code => update("phone_country_code", code)}/></label>}
              <label className="lead-create-field">Lead Source<span className="lead-create-control"><Target size={20}/><NativeSelect value={values.source || defaultText("lead_source", "crm")} onChange={e => update("source", e.target.value)}>{[...new Set([...(values.source ? [values.source] : [defaultText("lead_source", "crm")]), ...leadSourceOptions()])].map(source => <option key={source} value={source}>{source === "Manual" ? "Manual Entry" : source}</option>)}</NativeSelect></span></label>
              {mobile && <button type="button" className="mobile-filter-trigger" onClick={() => setExpandedMobileCapture(v => !v)} aria-expanded={expandedMobileCapture}>{expandedMobileCapture ? "Fewer details" : "More details"}</button>}
              {(!mobile || expandedMobileCapture) && <><label className="lead-create-field">Lead Stage<span className="lead-create-control"><BarChart3 size={20}/><NativeSelect value={values.status || bootstrap.settings.stages[0]?.name || "New"} onChange={e => update("status", e.target.value)}>{bootstrap.settings.stages.filter(stage => stage.name !== "Converted").map(stage => <option key={stage.name} value={stage.name}>{stage.name === "New" ? "New Lead" : stage.name}</option>)}</NativeSelect></span></label>
              <label className="lead-create-field">Priority<span data-priority-badge data-priority={priority} className="lead-create-control"><Flag size={20}/><span className={`lead-priority-dot lead-priority-${priority.toLowerCase()}`}/><NativeSelect value={priority} onChange={e => setPriority(e.target.value)}>{["Low", "Medium", "High"].map(value => <option key={value}>{value}</option>)}</NativeSelect></span></label>
              <label className="lead-create-field lead-create-notes">Notes<span className="lead-create-control"><FileText size={20}/><textarea maxLength={500} placeholder="Add a quick note about this lead, requirements, or context..." value={values.notes || ""} onChange={e => update("notes", e.target.value)}/></span><small>{values.notes?.length || 0}/500</small></label></>}
            </div>}
            {step === 1 && <div className="lead-create-grid">{field("email", "Email", "e.g. john@company.com", "email")}<label className="lead-create-field">Phone<PhoneInput value={values.phone || ""} countryCode={values.phone_country_code || ""} onChange={phone => update("phone", phone)} onCountryCodeChange={code => update("phone_country_code", code)}/></label>{field("job_title", "Job Title", "e.g. Sales Manager")}</div>}
            {step === 2 && <div className="lead-create-grid">{field("company_name", "Company", "Company name")}{field("industry", "Industry", "e.g. Technology")}{field("city", "City")}{field("country", "Country")}<BusinessProfileFields services={values.services_offered} types={values.business_types} onChange={update} disabled={saving}/></div>}
            {step === 3 && <><label className="lead-create-field">Assign to employee<span className="lead-create-control"><Building2 size={20}/><NativeSelect aria-label="Assign to employee" value={values.owner_user_id ?? defaultOwner} onChange={e => update("owner_user_id", e.target.value)}><option value="">{automaticRouting ? "Use automatic assignment rules" : "Assign to me"}</option>{bootstrap.owners.map(owner => <option key={owner.id} value={owner.id}>{owner.name}</option>)}</NativeSelect></span></label><p className="lead-create-subtitle">Review your details, then create {values.full_name || "your new lead"}.</p>{!!bootstrap.unavailableEmployees?.length && <p className="lm-help">{bootstrap.unavailableEmployees.length} employees are unavailable for assignment because they are missing CRM access.</p>}</>}
            <SharedNumberConfirmation phone={values.phone} countryCode={values.phone_country_code} email={values.email} confirmed={sharedConfirmed} reason={sharedReason} onChange={(a,b)=>{setSharedConfirmed(a);setSharedReason(b);}}/>{duplicate?.matched && <div className="lm-error" role="status">{duplicate.message}{duplicate.items.map(item => <p key={item.id}><Link to={`/crm/leads?lead=${item.id}`} onClick={close}>Review {item.name}</Link></p>)}</div>}
            {step === 4 && <CatalogLinesEditor selectionOnly value={catalogLines} onChange={setCatalogLines} disabled={saving}/>}
            <CrmRecordFields state={customFieldForm}/>
            {error && <ErrorNotice message={error}/>}
          </div>
          <footer className="lead-create-footer"><Button type="button" variant="outline" onClick={() => {sessionStorage.setItem(key, JSON.stringify(values)); close();}} disabled={saving}><FileText size={18}/>Save as Draft</Button><div>{step > 0 && <Button type="button" variant="ghost" onClick={() => setStep(step - 1)} disabled={saving}>Back</Button>}{step < 4 && <Button type="button" variant="outline" onClick={() => setStep(step + 1)} disabled={saving}>Next<ArrowRight size={16}/></Button>}<Button type="submit" data-save-action disabled={saving||customFieldForm.loading||!!customFieldForm.error}>{saving ? "Saving…" : "Create lead"}</Button>{customFieldForm.loading&&<span role="status">Loading custom fields...</span>}{customFieldForm.error&&<p role="alert">{customFieldForm.error}</p>}</div></footer>
        </CompactForm>
    </DialogContent>
  </Dialog>;
}

export function LeadDrawer({
  id,
  targetStage,
  bootstrap,
  close,
  changed,
  previous,
  next,
}: {
  id: number;
  targetStage: string;
  bootstrap: Bootstrap;
  close: () => void;
  changed: () => void;
  previous?: () => void;
  next?: () => void;
}) {
  const {api: leadsApi, potential} = useLeadRecord();
  const canEdit=useModuleAction("edit"),canCreate=useModuleAction("create"),canAssign=useModuleAction("assign"),canDelete=useModuleAction("delete");
  const { toast } = useToast();
  const [lead, setLead] = useState<Lead>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  const [tab, setTab] = useState("overview");
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [details, setDetails] = useState<LeadDetails>({});
  const [dirty, setDirty] = useState(false);
  const [teamDirty, setTeamDirty] = useState(false);
  const [activity, setActivity] = useState({
    type: "call",
    outcome: "",
    nextFollowUp: "",
    responded: false,
    startAt: "",
  });
  const [sequence, setSequence] = useState(
    bootstrap.settings.sequences[0]?.name || "",
  );
  const [conversion, setConversion] = useState<ConversionPreview>();
  const [conversionIds, setConversionIds] = useState({
    existingContactId: "",
    existingCompanyId: "",
    dealName: "",
    createDeal: true,
  });
  const [booking, setBooking] = useState("");
  const [scheduling, setScheduling] = useState(false);
  const [loggingInteraction,setLoggingInteraction]=useState(false);
  const customFieldForm=useCrmFieldForm("leads","edit",id,undefined,reload);
  const [editingCustomFields,setEditingCustomFields]=useState(false);
  const editingSection = useRef<HTMLDetailsElement>(null);
  useRefreshableEffect(() => {
    const controller = new AbortController();
    setError("");
    leadsApi
      .detail(id, controller.signal)
      .then((r) => {
        setLead(r.data);
        const pendingTransition = targetStage && targetStage !== r.data.status;
        setValues(pendingTransition ? { status: targetStage } : {});
        setDetails(r.data.details);
        setDirty(Boolean(pendingTransition));
        if (pendingTransition) setTab("qualification");
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(errorMessage(err));
      });
    return () => controller.abort();
  }, [id, reload, targetStage]);
  const dismiss = () => {
    if (
      !busy &&
      (!(dirty || teamDirty) ||
        window.confirm("Discard unsaved changes to this lead?"))
    )
      close();
  };
  const setValue = (key: string, value: unknown) => {
    if (JSON.stringify(value ?? null) === JSON.stringify(values[key] ?? (lead as unknown as Record<string, unknown>)?.[key] ?? null)) return;
    setValues((current) => ({ ...current, [key]: value }));
    setDirty(true);
  };
  const setDetail = (patch: Partial<LeadDetails>) => {
    setDetails((current) => ({ ...current, ...patch }));
    setDirty(true);
  };
  const value = (key: keyof Lead) => String(values[key] ?? lead?.[key] ?? "");
  const act = async (operation: () => Promise<unknown>, message: string) => {
    setBusy(true);
    setError("");
    try {
      await operation();
      toast({ title: message });
      changed();
      setReload((v) => v + 1);
      return true;
    } catch (err) {
      setError(errorMessage(err));
      return false;
    } finally {
      setBusy(false);
    }
  };
  const leadSaving=useRef(false);
  const latestDraft=useRef({values,details,customValues:customFieldForm.values});latestDraft.current={values,details,customValues:customFieldForm.values};
  const save = async (automatic=false) => {
    if (!lead||!canEdit||leadSaving.current) return false;
    const writable = [
      "qualification",
      "interests",
      "lossReason",
      "competitor",
      "scoreOverrideReason",
      "archived",
      "archiveReason",
      "reviewAt",
      "assignmentReason",
      "customerTimezone",
    ];
    const patch = Object.fromEntries(
      Object.entries(details).filter(([key]) => writable.includes(key)),
    );
    leadSaving.current=true;setBusy(true);setError("");
    const captured=JSON.stringify(latestDraft.current);
    try{
      const response=await leadsApi.update(id,{values,details:patch,customFields:customFieldForm.validate(),version:lead.version});
      setLead(response.data);
      setValues(current=>Object.fromEntries(Object.entries(current).filter(([key,value])=>JSON.stringify(value)!==JSON.stringify(values[key]))));
      if(JSON.stringify(latestDraft.current)===captured){setDirty(false);setDetails(response.data.details);}
      if(!automatic){setEditingCustomFields(false);toast({title:"Lead saved"});}
      changed();return true;
    }catch(error){setError(errorMessage(error));return false;}
    finally{leadSaving.current=false;setBusy(false);}
  };
  const auto=useRecordAutosave({value:{values,details,customValues:customFieldForm.values},enabled:!!lead&&canEdit&&!busy&&!customFieldForm.loading&&!teamDirty&&!targetStage,dirty,save:()=>save(true)});
  const qualification = { ...emptyQualification, ...details.qualification };
  const allowed =
    bootstrap.settings.stages.find((s) => s.name === lead?.status)
      ?.allowedNext || [];
  const stageConfig = bootstrap.settings.stages.find(
    (s) => s.name === (values.status || lead?.status),
  );
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) dismiss();
      }}
    >
      <DialogContent className="lm-drawer wf-preview lm-person-preview r360-dialog">
        {loggingInteraction&&lead&&<CRMInteractionDialog record={{entity:"leads",id:lead.id,name:lead.full_name,timezone:lead.details.customerTimezone}} activities={lead.activities||[]} close={()=>setLoggingInteraction(false)} saved={()=>{setLoggingInteraction(false);changed();setReload(v=>v+1);}} next={next?()=>{setLoggingInteraction(false);changed();next();}:undefined}/>}
        {scheduling && lead && (
          <FollowUpDialog
            lead={lead}
            bootstrap={bootstrap}
            close={() => setScheduling(false)}
            saved={() => {
              changed();
              setReload((v) => v + 1);
            }}
          />
        )}
        <PersonPreviewHeader name={lead?.full_name || "Lead details"} identifier={`#${id}`} status={lead?.status}/>
        {bootstrap.canManage && canEdit && lead && !lead.is_converted && <div className="lm-lead-save-toolbar"><span role="status">{busy ? "Saving…" : auto.message || (dirty ? "Unsaved changes" : "All changes saved")}</span><Button type="button" variant="outline" onClick={() => { if (editingSection.current) { editingSection.current.open = true; editingSection.current.scrollIntoView({block:"start",behavior:"smooth"}); } }}>Edit lead</Button><Button type="button" disabled={busy || !dirty || customFieldForm.loading || !!customFieldForm.error} onClick={() => void save()}>Save changes</Button></div>}
        <Record360Workspace key={id} kind="lead" id={id} actions={<Button variant="outline" onClick={()=>setScheduling(true)}>Schedule lead follow-up</Button>}/>
        <details ref={editingSection}><summary className="cursor-pointer font-semibold">Lead qualification & editing</summary>
        <div className="wfp-body wf-space">
        <div className="flex gap-2"><Button variant="outline" disabled={!previous||busy} onClick={()=>{if(!(dirty||teamDirty)||window.confirm("Discard unsaved changes before opening the previous record?"))previous?.();}}>Previous</Button><Button variant="outline" disabled={!next||busy} onClick={()=>{if(!(dirty||teamDirty)||window.confirm("Discard unsaved changes before opening the next record?"))next?.();}}>Next</Button></div>
        {!lead ? (
          error ? (
            <ErrorNotice
              message={error}
              retry={() => setReload((v) => v + 1)}
            />
          ) : (
            <div className="lm-loading" role="status">
              Loading lead…
            </div>
          )
        ) : (
          <>
            {lead.permissions&&<p className="text-xs text-muted-foreground">{["edit","assign","export","convert"].filter(k=>!lead.permissions?.[k]).map(k=>String(lead.permissions?.[`${k}_reason`]||"")).filter(Boolean).join(" · ")}</p>}
            <header className="lm-record-header">
              <div>
                <StageBadge stage={lead.status} />
                <span>{lead.company_name || "Individual enquiry"}</span>
              </div>
              <p>{lead.signals.nextAction}</p>{!lead.next_follow_up_at&&!lead.is_converted&&lead.status!=="Lost"&&<p className="text-amber-700">No next action — schedule a follow-up or record a decision.</p>}
              <div className="lm-contact-actions">{bootstrap.canManage&&<Button size="sm" disabled={dirty||busy} onClick={()=>setLoggingInteraction(true)}>Log call or meeting outcome</Button>}
                {lead.phone && (
                  <a href={`tel:${lead.phone_country_code || ""}${lead.phone}`}>
                    <Phone size={15} />
                    Call
                  </a>
                )}
                {lead.email && (
                  <a href={`mailto:${lead.email}`}>
                    <Mail size={15} />
                    Email
                  </a>
                )}
                <Link to={`/crm/leads/${id}`}>
                  Full record <ArrowRight size={14} />
                </Link>
              </div>
            </header>
            <MobileContactActions phone={lead.phone ? `${lead.phone_country_code || ""}${lead.phone}` : undefined} email={lead.email} onNote={bootstrap.canManage ? () => setLoggingInteraction(true) : undefined}/>
            <nav className="lm-tabs" aria-label="Lead detail sections">
              {[
                "overview",
                "qualification",
                "activities",
                "team",
                "score",
                "history",
              ].map((name) => (
                <button
                  key={name}
                  className={tab === name ? "active" : ""}
                  aria-pressed={tab === name}
                  onClick={() => {
                    if (
                      name !== tab &&
                      teamDirty &&
                      !window.confirm("Discard your unsaved team update?")
                    )
                      return;
                    if (name !== tab) setTeamDirty(false);
                    setTab(name);
                  }}
                >
                  {name}
                </button>
              ))}
            </nav>
            {error && <ErrorNotice message={error} />}
            <fieldset
              className="lm-fieldset"
              disabled={!bootstrap.canManage || !canEdit || busy}
            >
              {tab === "overview" && (
                <><CatalogAssociations source="crm" target="lead" id={id}/>
                  <div className="lm-form-grid">
                    <Field label="Current stage">
                      <NativeSelect
                        value={value("status")}
                        onChange={(e) => setValue("status", e.target.value)}
                        disabled={lead.is_converted}
                      >
                        <option>{lead.status}</option>
                        {allowed
                          .filter((s) => s !== "Converted")
                          .map((s) => (
                            <option key={s}>{s}</option>
                          ))}
                      </NativeSelect>
                    </Field>
                    <Field label="Reassignment reason"><input value={details.assignmentReason||""} onChange={e=>setDetail({assignmentReason:e.target.value})} placeholder="Explain ownership changes for the timeline"/></Field><Field label="Customer time zone"><input value={details.customerTimezone||""} onChange={e=>setDetail({customerTimezone:e.target.value})} placeholder="Asia/Kolkata"/></Field>
                    <Field label="Assigned employee">
                      <NativeSelect
                        value={value("owner_user_id")}
                        disabled={!canAssign}
                        onChange={(e) =>
                          setValue("owner_user_id", Number(e.target.value))
                        }
                      >
                        <option value="" disabled>
                          Unassigned
                        </option>
                        {!!lead.owner_user_id &&
                          !bootstrap.owners.some(
                            (o) => o.id === lead.owner_user_id,
                          ) && (
                            <option value={lead.owner_user_id} disabled>
                              Current assignee (unavailable)
                            </option>
                          )}
                        {bootstrap.owners.map((o) => (
                          <option key={o.id} value={o.id}>
                            {o.name}
                          </option>
                        ))}
                      </NativeSelect>
                    </Field>
                    {[
                      ["full_name", "Name"],
                      ["company_name", "Company"],
                      ["email", "Email"],
                      ["source", "Source"],
                      ["estimated_value", "Estimated value"],
                    ].map(([key, label]) => (
                      <Field label={label} key={key}>
                        <input
                          type={
                            key === "email"
                              ? "email"
                              : key === "estimated_value"
                                ? "number"
                                : "text"
                          }
                          min={key === "estimated_value" ? 0 : undefined}
                          step={key === "estimated_value" ? "0.01" : undefined}
                          value={value(key as keyof Lead)}
                          onChange={(e) =>
                            setValue(
                              key,
                              key === "estimated_value"
                                ? e.target.value === ""
                                  ? null
                                  : Number(e.target.value)
                                : e.target.value,
                            )
                          }
                        />
                      </Field>
                    ))}
                    <BusinessProfileFields services={values.services_offered ?? lead.services_offered} types={values.business_types ?? lead.business_types} onChange={setValue} disabled={!canEdit || busy}/>
                    <Field label="Phone">
                      <PhoneInput
                        value={value("phone")}
                        countryCode={value("phone_country_code") || defaultText("phone_country_code", "crm")}
                        onChange={(number) => setValue("phone", number)}
                        onCountryCodeChange={(code) =>
                          setValue("phone_country_code", code)
                        }
                      />
                    </Field>
                    <Field label="Next follow-up">
                      <input
                        type="datetime-local"
                        value={dateInput(value("next_follow_up_at"))}
                        onChange={(e) =>
                          setValue("next_follow_up_at", iso(e.target.value))
                        }
                      />
                    </Field>
                  </div>
                  <Field label="Notes">
                    <RichTextField
                      rows={3}
                      value={value("notes")}
                      onChange={(e) => setValue("notes", e.target.value)}
                    />
                  </Field>
                  <section className="lm-section">
                    <h3>Follow-up sequence</h3>
                    <p>
                      Schedules tasks for your team. Record a response to stop
                      pending steps.
                    </p>
                    {details.sequence && (
                      <p>
                        {details.sequence.name} ·{" "}
                        {details.sequence.active
                          ? "Active"
                          : `Stopped: ${details.sequence.stopReason}`}
                      </p>
                    )}
                    <div className="lm-actions">
                      <NativeSelect
                        aria-label="Follow-up sequence"
                        value={sequence}
                        onChange={(e) => setSequence(e.target.value)}
                      >
                        {bootstrap.settings.sequences.map((s) => (
                          <option key={s.name}>{s.name}</option>
                        ))}
                      </NativeSelect>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={!sequence || busy}
                        onClick={() =>
                          void act(
                            () => leadsApi.sequence(id, sequence),
                            "Sequence scheduled",
                          )
                        }
                      >
                        Start sequence
                      </Button>
                      {details.sequence?.active && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            void act(
                              () => leadsApi.sequence(id, sequence, true),
                              "Sequence stopped",
                            )
                          }
                        >
                          Stop
                        </Button>
                      )}
                    </div>
                  </section>
                  <section className="lm-section">
                    <h3>Nurture & review</h3>
                    <Field label="Review on">
                      <input
                        type="datetime-local"
                        value={dateInput(details.reviewAt)}
                        onChange={(e) =>
                          setDetail({
                            reviewAt: iso(e.target.value),
                          })
                        }
                      />
                    </Field>
                    <label className="lm-check">
                      <input
                        type="checkbox"
                        checked={!!details.archived}
                        disabled={!canDelete}
                        onChange={(e) =>
                          setDetail({ archived: e.target.checked })
                        }
                      />
                      Archive from the active queue
                    </label>
                    {details.archived && (
                      <Field label="Archive reason">
                        <input
                          value={details.archiveReason || ""}
                          onChange={(e) =>
                            setDetail({ archiveReason: e.target.value })
                          }
                        />
                      </Field>
                    )}
                    {lead.status === "Lost" && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setValue("status", "New");
                          setDetail({ archived: false });
                        }}
                      >
                        Reactivate as New — save to apply
                      </Button>
                    )}
                  </section>
                </>
              )}
              {tab === "qualification" && (
                <>
                  <p className="lm-help">
                    Required for {stageConfig?.name}:{" "}
                    {stageConfig?.required.join(", ") || "No additional fields"}
                    . Complete these before saving a stage change.
                  </p>
                  <div className="lm-form-grid">
                    {Object.entries(qualification).map(([key, val]) => (
                      <Field
                        label={
                          {
                            need: "Business need",
                            budget: "Budget",
                            decisionMaker: "Decision-maker",
                            timeline: "Purchase timeline",
                          }[key] || key
                        }
                        key={key}
                      >
                        <RichTextField
                          rows={2}
                          value={val}
                          onChange={(e) =>
                            setDetail({
                              qualification: {
                                ...qualification,
                                [key]: e.target.value,
                              },
                            })
                          }
                        />
                      </Field>
                    ))}
                  </div>
                  <h3>Product & service interests</h3>
                  {(details.interests || []).map((interest, index) => (
                    <div className="lm-interest" key={index}>
                      <Field label="Product or service">
                        <input
                          value={interest.name}
                          onChange={(e) =>
                            setDetail({
                              interests: details.interests?.map((v, i) =>
                                i === index
                                  ? { ...v, name: e.target.value }
                                  : v,
                              ),
                            })
                          }
                        />
                      </Field>
                      <Field label="Estimated value">
                        <input
                          type="number"
                          min="0"
                          value={interest.value}
                          onChange={(e) =>
                            setDetail({
                              interests: details.interests?.map((v, i) =>
                                i === index
                                  ? { ...v, value: Number(e.target.value) }
                                  : v,
                              ),
                            })
                          }
                        />
                      </Field>
                      <Field label="Requirements">
                        <RichTextField
                          value={interest.requirements}
                          onChange={(e) =>
                            setDetail({
                              interests: details.interests?.map((v, i) =>
                                i === index
                                  ? { ...v, requirements: e.target.value }
                                  : v,
                              ),
                            })
                          }
                        />
                      </Field>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          setDetail({
                            interests: details.interests?.filter(
                              (_, i) => i !== index,
                            ),
                          })
                        }
                      >
                        Remove interest
                      </Button>
                    </div>
                  ))}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      setDetail({
                        interests: [
                          ...(details.interests || []),
                          { name: "", value: 0, requirements: "" },
                        ],
                      })
                    }
                  >
                    Add interest
                  </Button>
                  <section className="lm-section">
                    <h3>Loss details</h3>
                    <Field label="Loss reason (required when Lost)">
                      <NativeSelect
                        value={details.lossReason || ""}
                        onChange={(e) =>
                          setDetail({ lossReason: e.target.value })
                        }
                      >
                        <option value="">Choose a reason</option>
                        {[
                          "Budget",
                          "Timing",
                          "No response",
                          "Competitor",
                          "Poor fit",
                          "Other",
                        ].map((reason) => (
                          <option key={reason}>{reason}</option>
                        ))}
                        {details.lossReason &&
                          ![
                            "Budget",
                            "Timing",
                            "No response",
                            "Competitor",
                            "Poor fit",
                            "Other",
                          ].includes(details.lossReason) && (
                            <option>{details.lossReason}</option>
                          )}
                      </NativeSelect>
                    </Field>
                    <Field label="Competitor">
                      <input
                        value={details.competitor || ""}
                        onChange={(e) =>
                          setDetail({ competitor: e.target.value })
                        }
                      />
                    </Field>
                  </section>
                </>
              )}
              {tab === "team" && (
                <LeadTeamPanel
                  draftChanged={setTeamDirty}
                  lead={lead}
                  canManage={bootstrap.canManage}
                  disabled={busy || dirty}
                  changed={() => {
                    changed();
                    setReload((v) => v + 1);
                  }}
                />
              )}
              {tab === "activities" && (
                <>
                  <h3>Log an outcome & next step</h3>
                  {bootstrap.canManage && lead.signals.active && (
                    <Button
                      variant="outline"
                      disabled={busy || dirty}
                      onClick={() => setScheduling(true)}
                    >
                      Schedule or reschedule follow-up
                    </Button>
                  )}
                  <p className="lm-help">
                    Record completed interactions here. Use Communications to
                    send through connected providers.
                  </p>
                  <div className="lm-form-grid">
                    <Field label="Activity type">
                      <NativeSelect
                        value={activity.type}
                        onChange={(e) =>
                          setActivity((v) => ({ ...v, type: e.target.value }))
                        }
                      >
                        {["call", "email", "meeting", "note", "task"].map(
                          (type) => (
                            <option key={type}>{type}</option>
                          ),
                        )}
                      </NativeSelect>
                    </Field>
                    <Field label="Next follow-up">
                      <input
                        type="datetime-local"
                        value={activity.nextFollowUp}
                        onChange={(e) =>
                          setActivity((v) => ({
                            ...v,
                            nextFollowUp: e.target.value,
                          }))
                        }
                      />
                    </Field>
                    {activity.type === "meeting" && (
                      <Field label="Schedule meeting for (optional)">
                        <input
                          type="datetime-local"
                          value={activity.startAt}
                          onChange={(e) =>
                            setActivity((v) => ({
                              ...v,
                              startAt: e.target.value,
                            }))
                          }
                        />
                      </Field>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2" aria-label="Quick call outcomes">{["Connected","No Answer","Callback Requested","Not Interested"].map(outcome=><Button size="sm" variant="outline" key={outcome} onClick={()=>setActivity(v=>({...v,outcome}))}>{outcome}</Button>)}</div>
                  <Field label="Outcome or meeting purpose">
                    <RichTextField
                      rows={3}
                      value={activity.outcome}
                      onChange={(e) =>
                        setActivity((v) => ({ ...v, outcome: e.target.value }))
                      }
                    />
                  </Field>
                  <label className="lm-check">
                    <input
                      type="checkbox"
                      checked={activity.responded}
                      onChange={(e) =>
                        setActivity((v) => ({
                          ...v,
                          responded: e.target.checked,
                        }))
                      }
                    />
                    Lead responded — stop pending sequence tasks
                  </label>
                  <Button
                    disabled={!activity.outcome.trim() || busy}
                    onClick={async () => {
                      const ok = await act(
                        () =>
                          leadsApi.activity(id, {
                            ...activity,
                            nextFollowUp: iso(activity.nextFollowUp),
                            startAt: iso(activity.startAt),
                          }),
                        "Activity and follow-up saved",
                      );
                      if (ok)
                        setActivity((v) => ({
                          ...v,
                          outcome: "",
                          responded: false,
                        }));
                    }}
                  >
                    Save activity & next step
                  </Button>
                  <section className="lm-section">
                    <h3>Let the lead book a meeting</h3>
                    <p>
                      Create a private, single-use booking link, valid for 30
                      days. Availability checks use the assigned BusinessSuite
                      calendar.
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busy || dirty}
                      onClick={async () => {
                        try {
                          const response = await leadsApi.bookingLink(id);
                          setBooking(publicUrl(response.data.path));
                          setReload((v) => v + 1);
                          changed();
                        } catch (err) {
                          setError(errorMessage(err));
                        }
                      }}
                    >
                      Create booking link
                    </Button>
                    {booking && (
                      <Field label="Share this booking link">
                        <input
                          readOnly
                          value={booking}
                          onFocus={(e) => e.target.select()}
                        />
                      </Field>
                    )}
                  </section>
                  <section className="lm-section">
                    <h3>Scheduled & completed activities</h3>
                    {lead.activities?.map((item) => (
                      <div className="lm-activity-row" key={item.id}>
                        <strong>{item.subject}</strong>
                        <span>
                          {item.activity_type} · {item.status}
                          {item.due_date
                            ? ` · ${formatDate(item.due_date)}`
                            : ""}
                        </span>
                        {item.status === "Pending" && bootstrap.canManage && (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={busy || dirty}
                            onClick={() =>
                              void act(
                                () => leadsApi.completeTask(id, item.id),
                                "Activity completed; next follow-up updated",
                              )
                            }
                          >
                            Complete task
                          </Button>
                        )}
                      </div>
                    ))}
                  </section>
                </>
              )}
              {tab === "score" && (
                <>
                  <div className="lm-score-heading">
                    <strong>
                      {lead.lead_score || 0}
                      <small>/100</small>
                    </strong>
                    <span>
                      {lead.lead_score_mode === "manual"
                        ? "Manual override"
                        : "Calculated from active scoring rules"}
                    </span>
                  </div>
                  <p>
                    Rule contributions below show the current automatic
                    calculation. A manual score can differ.
                  </p>
                  {lead.scoreReasons?.map((reason, index) => (
                    <div className="lm-rule-row" key={index}>
                      <span>
                        {reason.matched ? "Matched" : "Not matched"} ·{" "}
                        {reason.name}
                      </span>
                      <strong>
                        {reason.points > 0 ? "+" : ""}
                        {reason.points}
                      </strong>
                    </div>
                  ))}
                  <div className="lm-form-grid">
                    <Field label="Manual score (0–100)">
                      <input
                        type="number"
                        min="0"
                        max="100"
                        value={value("lead_score")}
                        onChange={(e) =>
                          setValue("lead_score", Number(e.target.value))
                        }
                      />
                    </Field>
                    <Field label="Reason for score override">
                      <input
                        value={details.scoreOverrideReason || ""}
                        onChange={(e) =>
                          setDetail({ scoreOverrideReason: e.target.value })
                        }
                      />
                    </Field>
                  </div>
                  <Link to="/crm/lead-scoring">Manage scoring rules</Link>
                </>
              )}
            </fieldset>
            {tab === "history" && (
              <section className="lm-timeline">
                <p className="lm-help">
                  Status changes include actor, timestamp and time in the
                  previous stage where recorded.
                </p>
                {lead.timeline?.length ? (
                  lead.timeline.map((item) => (
                    <article key={item.id}>
                      <span className="lm-timeline-kind">
                        {item.event_type.replace(/_/g, " ")}
                      </span>
                      <h3>{item.title}</h3>
                      {item.description && <div><RichTextContent legacyFormat="plain" value={item.description}/></div>}
                      <small>
                        {formatDate(item.occurred_at)} ·{" "}
                        {bootstrap.owners.find(
                          (o) => o.id === item.actor_user_id,
                        )?.name || `User ${item.actor_user_id || "system"}`}
                        {item.metadata_json?.durationHours !== undefined &&
                          ` · ${item.metadata_json.durationHours} hours in previous stage`}
                      </small>
                    </article>
                  ))
                ) : (
                  <p>No recorded events yet.</p>
                )}
              </section>
            )}
            {bootstrap.canManage && (
              <footer className="lm-drawer-footer">
                <span role="status">
                  {busy
                    ? "Saving…"
                    : dirty
                      ? "Unsaved changes"
                      : "All changes saved"}
                </span>
                <Button
                  variant="outline"
                  disabled={
                    busy ||
                    dirty ||
                    !(potential?canEdit:canCreate) ||
                    (!potential && lead.status !== "Qualified") ||
                    lead.is_converted
                  }
                  onClick={async () => {
                    try {
                      if (potential) {
                        await leadsApi.update(id, {details: {recordType: "Lead"}, version: lead.version});
                        changed(); close();
                        return;
                      }
                      const response = await leadsApi.previewConversion(id);
                      setConversion(response.data);
                      setConversionIds({
                        dealName:"",createDeal:true,
                        existingContactId: String(
                          response.data.matches.contacts[0]?.id || "",
                        ),
                        existingCompanyId: String(
                          response.data.matches.companies[0]?.id || "",
                        ),
                      });
                    } catch (err) {
                      setError(errorMessage(err));
                    }
                  }}
                >
                  {potential ? "Move to Leads" : "Convert to customer"}
                </Button>
                <div className="w-full space-y-3">{editingCustomFields?<><CrmRecordFields state={{...customFieldForm,setValues:next=>{customFieldForm.setValues(next);setDirty(true);}}}/><Button type="button" variant="ghost" onClick={()=>setEditingCustomFields(false)}>View saved fields</Button></>:<><CrmFieldsReadOnly key={reload} entity="leads" recordId={id}/>{customFieldForm.fields.length>0&&<Button type="button" variant="outline" onClick={()=>setEditingCustomFields(true)}>Edit custom fields</Button>}</>}</div>
              </footer>
            )}
            {lead.is_converted && (
              <div className="lm-converted">
                Converted successfully.{" "}
                {lead.converted_contact_id && (
                  <Link to={`/crm/contacts/${lead.converted_contact_id}`}>
                    Contact
                  </Link>
                )}
                {lead.converted_company_id && (
                  <Link to={`/crm/accounts/${lead.converted_company_id}`}>
                    Company
                  </Link>
                )}
                {lead.converted_deal_id && (
                  <Link to={`/crm/deals/${lead.converted_deal_id}`}>Deal</Link>
                )}
              </div>
            )}
            <Dialog
              open={!!conversion}
              onOpenChange={(open) => {
                if (!open) setConversion(undefined);
              }}
            >
              <DialogContent className="lm-dialog">
                <DialogTitle>Review lead conversion</DialogTitle>
                <p>
                  Create or reuse a contact and company, and create a deal for
                  this qualified lead. Existing lead history is retained.
                </p>
                <Field label="Contact">
                  <NativeSelect
                    value={conversionIds.existingContactId}
                    onChange={(e) =>
                      setConversionIds((v) => ({
                        ...v,
                        existingContactId: e.target.value,
                      }))
                    }
                  >
                    <option value="">Create a new contact</option>
                    {conversion?.matches.contacts.map((c) => (
                      <option value={c.id} key={c.id}>
                        Reuse {c.name}
                      </option>
                    ))}
                  </NativeSelect>
                </Field>
                <Field label="Company">
                  <NativeSelect
                    value={conversionIds.existingCompanyId}
                    onChange={(e) =>
                      setConversionIds((v) => ({
                        ...v,
                        existingCompanyId: e.target.value,
                      }))
                    }
                  >
                    <option value="">
                      {lead.company_name
                        ? "Create or match company by name"
                        : "No company will be created"}
                    </option>
                    {conversion?.matches.companies.map((c) => (
                      <option value={c.id} key={c.id}>
                        Reuse {c.name}
                      </option>
                    ))}
                  </NativeSelect>
                </Field>
                <Field label="New deal name"><input value={conversionIds.dealName} placeholder={`${lead.full_name} opportunity`} onChange={e=>setConversionIds(v=>({...v,dealName:e.target.value}))}/></Field><label className="lm-check"><input type="checkbox" checked={conversionIds.createDeal} onChange={e=>setConversionIds(v=>({...v,createDeal:e.target.checked}))}/>Create a linked deal</label><div className="rounded border p-3 text-sm"><strong>Survivor / destination preview</strong><p>Contact: {conversionIds.existingContactId?`Reuse #${conversionIds.existingContactId}`:"Create a new contact"}</p><p>Company: {conversionIds.existingCompanyId?`Reuse #${conversionIds.existingCompanyId}`:lead.company_name?`Create or reuse ${lead.company_name}`:"No company"}</p><p>Deal: {conversionIds.createDeal?conversionIds.dealName||`${lead.full_name} opportunity`:"No new deal"}</p><p>Lead ownership, communication history, notes and follow-ups remain linked to the conversion.</p></div>
                <Button
                  disabled={busy || !canCreate || !conversion?.ready}
                  onClick={async () => {
                    if (
                      await act(
                        () =>
                          leadsApi.convert(id, {
                            dealName:conversionIds.dealName||null,createDeal:conversionIds.createDeal,
                            existingContactId: conversionIds.existingContactId
                              ? Number(conversionIds.existingContactId)
                              : null,
                            existingCompanyId: conversionIds.existingCompanyId
                              ? Number(conversionIds.existingCompanyId)
                              : null,
                          }),
                        "Lead converted; customer records are linked below",
                      )
                    )
                      setConversion(undefined);
                  }}
                >
                  Convert & open linked records
                </Button>
              </DialogContent>
            </Dialog>
          </>
        )}
        </div>
      </details>
      </DialogContent>
    </Dialog>
  );
}

function ExcelDialog({close,imported}:{close:()=>void;imported:()=>void}) {const {potential} = useLeadRecord(); return <LeadSpreadsheetImport potential={potential} autoOpen onClose={()=>{imported();close();}}/>;}

function WorkflowSettings({
  bootstrap,
  close,
  saved,
}: {
  bootstrap: Bootstrap;
  close: () => void;
  saved: () => void;
}) {
  const {api: leadsApi, potential} = useLeadRecord();
  const [settings, setSettings] = useState<Settings>(() =>
    JSON.parse(JSON.stringify(bootstrap.settings)),
  );
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState("stages");
  const [stageName, setStageName] = useState("");
  const [capture, setCapture] = useState<{
    enabled: boolean;
    path?: string;
    ownerId?: number;
  }>();
  const [captureOwner, setCaptureOwner] = useState(
    bootstrap.owners[0]?.id || bootstrap.userId,
  );
  useRefreshableEffect(() => {
    leadsApi
      .captureSettings()
      .then((r) => {
        setCapture(r.data);
        if (r.data.ownerId) setCaptureOwner(r.data.ownerId);
      })
      .catch((err) => setError(errorMessage(err)));
  }, []);
  const updateStage = (
    index: number,
    patch: Partial<Settings["stages"][number]>,
  ) =>
    setSettings((s) => ({
      ...s,
      stages: s.stages.map((v, i) => (i === index ? { ...v, ...patch } : v)),
    }));
  const required = [
    "email",
    "phone",
    "company_name",
    "need",
    "budget",
    "decisionMaker",
    "timeline",
    "lossReason",
    "competitor",
    "next_follow_up_at",
  ];
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !busy) close();
      }}
    >
      <DialogContent className="lm-dialog lm-settings-dialog">
        <DialogTitle>Lead workflow settings</DialogTitle>
        <p>
          Organization-wide rules apply to lead workbench operations and Excel
          imports.
        </p>
        <nav className="lm-tabs">
          {["stages", "assignment", "sequences", "automation", "website"].map(
            (name) => (
              <button
                key={name}
                aria-pressed={tab === name}
                className={tab === name ? "active" : ""}
                onClick={() => setTab(name)}
              >
                {name}
              </button>
            ),
          )}
        </nav>
        <fieldset disabled={busy} className="lm-fieldset">
          {tab === "stages" && (
            <>
              <div className="lm-form-grid">
                <Field label="First-response deadline (hours)">
                  <input
                    type="number"
                    min="1"
                    max="8760"
                    value={settings.slaHours}
                    onChange={(e) =>
                      setSettings((s) => ({
                        ...s,
                        slaHours: Number(e.target.value),
                      }))
                    }
                  />
                </Field>
                <Field label="Flag inactive after (days)">
                  <input
                    type="number"
                    min="1"
                    max="365"
                    value={settings.staleDays}
                    onChange={(e) =>
                      setSettings((s) => ({
                        ...s,
                        staleDays: Number(e.target.value),
                      }))
                    }
                  />
                </Field>
              </div>
              <label className="lm-check">
                <input
                  type="checkbox"
                  checked={settings.preventDuplicates}
                  onChange={(e) =>
                    setSettings((s) => ({
                      ...s,
                      preventDuplicates: e.target.checked,
                    }))
                  }
                />
                Prevent matching email / phone duplicates
              </label>
              {settings.stages.map((stage, index) => (
                <section className="lm-section" key={index}>
                  <h3>{stage.name}</h3>
                  <div className="lm-form-grid">
                    <div>
                      <p>Allowed next stages</p>
                      {settings.stages
                        .filter(
                          (s) =>
                            s.name !== stage.name && s.name !== "Converted",
                        )
                        .map((next) => (
                          <label className="lm-check" key={next.name}>
                            <input
                              type="checkbox"
                              checked={stage.allowedNext.includes(next.name)}
                              disabled={stage.name === "Converted"}
                              onChange={(e) =>
                                updateStage(index, {
                                  allowedNext: e.target.checked
                                    ? [...stage.allowedNext, next.name]
                                    : stage.allowedNext.filter(
                                        (n) => n !== next.name,
                                      ),
                                })
                              }
                            />
                            {next.name}
                          </label>
                        ))}
                    </div>
                    <div>
                      <p>Required before entering</p>
                      {required.map((field) => (
                        <label className="lm-check" key={field}>
                          <input
                            type="checkbox"
                            checked={stage.required.includes(field)}
                            onChange={(e) =>
                              updateStage(index, {
                                required: e.target.checked
                                  ? [...stage.required, field]
                                  : stage.required.filter((n) => n !== field),
                              })
                            }
                          />
                          {field.replace(/_/g, " ")}
                        </label>
                      ))}
                    </div>
                  </div>
                </section>
              ))}
              <div className="lm-actions">
                <input
                  aria-label="New stage name"
                  maxLength={40}
                  value={stageName}
                  onChange={(e) => setStageName(e.target.value)}
                  placeholder="Add a custom stage"
                />
                <Button
                  variant="outline"
                  size="sm"
                  disabled={
                    !stageName.trim() ||
                    settings.stages.some((s) => s.name === stageName.trim())
                  }
                  onClick={() => {
                    setSettings((s) => ({
                      ...s,
                      stages: [
                        ...s.stages,
                        {
                          name: stageName.trim(),
                          required: [],
                          allowedNext: ["Qualified", "Lost"],
                        },
                      ],
                    }));
                    setStageName("");
                  }}
                >
                  Add stage
                </Button>
              </div>
            </>
          )}
          {tab === "assignment" && (
            <>
              <Field label="Distribution method">
                <NativeSelect
                  value={settings.assignment.mode}
                  onChange={(e) =>
                    setSettings((s) => ({
                      ...s,
                      assignment: { ...s.assignment, mode: e.target.value },
                    }))
                  }
                >
                  <option value="manual">
                    Manual / existing territory rules
                  </option>
                  <option value="round_robin">Round-robin</option>
                  <option value="workload">Fewest active leads</option>
                </NativeSelect>
              </Field>
              <h3>Eligible owners</h3>
              {bootstrap.owners.map((owner) => (
                <label className="lm-check" key={owner.id}>
                  <input
                    type="checkbox"
                    checked={settings.assignment.ownerIds.includes(owner.id)}
                    onChange={(e) =>
                      setSettings((s) => ({
                        ...s,
                        assignment: {
                          ...s.assignment,
                          ownerIds: e.target.checked
                            ? [...s.assignment.ownerIds, owner.id]
                            : s.assignment.ownerIds.filter(
                                (id) => id !== owner.id,
                              ),
                        },
                      }))
                    }
                  />
                  {owner.name}
                </label>
              ))}
              <section className="lm-section">
                <h3>Assignment rules</h3>
                <p>
                  First matching rule wins; otherwise use the distribution
                  method.
                </p>
                {settings.assignment.rules.map((rule, index) => (
                  <div className="lm-rule-editor" key={index}>
                    <NativeSelect
                      aria-label="Assignment condition field"
                      value={rule.field}
                      onChange={(e) =>
                        setSettings((s) => ({
                          ...s,
                          assignment: {
                            ...s.assignment,
                            rules: s.assignment.rules.map((r, i) =>
                              i === index ? { ...r, field: e.target.value } : r,
                            ),
                          },
                        }))
                      }
                    >
                      {[
                        "source",
                        "city",
                        "state",
                        "country",
                        "industry",
                        "territory_id",
                        "product",
                      ].map((name) => (
                        <option key={name}>{name}</option>
                      ))}
                    </NativeSelect>
                    <input
                      aria-label="Assignment match value"
                      placeholder="Equals"
                      value={rule.equals}
                      onChange={(e) =>
                        setSettings((s) => ({
                          ...s,
                          assignment: {
                            ...s.assignment,
                            rules: s.assignment.rules.map((r, i) =>
                              i === index
                                ? { ...r, equals: e.target.value }
                                : r,
                            ),
                          },
                        }))
                      }
                    />
                    <NativeSelect
                      aria-label="Rule owner"
                      value={rule.ownerId}
                      onChange={(e) =>
                        setSettings((s) => ({
                          ...s,
                          assignment: {
                            ...s.assignment,
                            rules: s.assignment.rules.map((r, i) =>
                              i === index
                                ? { ...r, ownerId: Number(e.target.value) }
                                : r,
                            ),
                          },
                        }))
                      }
                    >
                      {bootstrap.owners.map((o) => (
                        <option key={o.id} value={o.id}>
                          {o.name}
                        </option>
                      ))}
                    </NativeSelect>
                    <button
                      aria-label="Remove assignment rule"
                      onClick={() =>
                        setSettings((s) => ({
                          ...s,
                          assignment: {
                            ...s.assignment,
                            rules: s.assignment.rules.filter(
                              (_, i) => i !== index,
                            ),
                          },
                        }))
                      }
                    >
                      <X size={16} />
                    </button>
                  </div>
                ))}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    setSettings((s) => ({
                      ...s,
                      assignment: {
                        ...s.assignment,
                        rules: [
                          ...s.assignment.rules,
                          {
                            field: "source",
                            equals: "Website",
                            ownerId:
                              bootstrap.owners[0]?.id || bootstrap.userId,
                          },
                        ],
                      },
                    }))
                  }
                >
                  Add assignment rule
                </Button>
              </section>
            </>
          )}
          {tab === "sequences" && (
            <>
              <p>
                Sequence steps become scheduled call, email, meeting or
                follow-up tasks. They stop when a response is logged.
              </p>
              {settings.sequences.map((sequence, index) => (
                <section className="lm-section" key={index}>
                  <Field label="Sequence name">
                    <input
                      value={sequence.name}
                      onChange={(e) =>
                        setSettings((s) => ({
                          ...s,
                          sequences: s.sequences.map((v, i) =>
                            i === index ? { ...v, name: e.target.value } : v,
                          ),
                        }))
                      }
                    />
                  </Field>
                  {sequence.steps.map((step, stepIndex) => (
                    <div className="lm-rule-editor" key={stepIndex}>
                      <Field label="Days after start">
                        <input
                          type="number"
                          min="0"
                          max="365"
                          value={step.day}
                          onChange={(e) =>
                            setSettings((s) => ({
                              ...s,
                              sequences: s.sequences.map((v, i) =>
                                i === index
                                  ? {
                                      ...v,
                                      steps: v.steps.map((st, j) =>
                                        j === stepIndex
                                          ? {
                                              ...st,
                                              day: Number(e.target.value),
                                            }
                                          : st,
                                      ),
                                    }
                                  : v,
                              ),
                            }))
                          }
                        />
                      </Field>
                      <Field label="Task type">
                        <NativeSelect
                          value={step.type}
                          onChange={(e) =>
                            setSettings((s) => ({
                              ...s,
                              sequences: s.sequences.map((v, i) =>
                                i === index
                                  ? {
                                      ...v,
                                      steps: v.steps.map((st, j) =>
                                        j === stepIndex
                                          ? { ...st, type: e.target.value }
                                          : st,
                                      ),
                                    }
                                  : v,
                              ),
                            }))
                          }
                        >
                          {["call", "email", "task", "meeting"].map((name) => (
                            <option key={name}>{name}</option>
                          ))}
                        </NativeSelect>
                      </Field>
                      <Field label="Task title">
                        <input
                          value={step.title}
                          onChange={(e) =>
                            setSettings((s) => ({
                              ...s,
                              sequences: s.sequences.map((v, i) =>
                                i === index
                                  ? {
                                      ...v,
                                      steps: v.steps.map((st, j) =>
                                        j === stepIndex
                                          ? { ...st, title: e.target.value }
                                          : st,
                                      ),
                                    }
                                  : v,
                              ),
                            }))
                          }
                        />
                      </Field>
                      <button
                        aria-label="Remove sequence step"
                        onClick={() =>
                          setSettings((s) => ({
                            ...s,
                            sequences: s.sequences.map((v, i) =>
                              i === index
                                ? {
                                    ...v,
                                    steps: v.steps.filter(
                                      (_, j) => j !== stepIndex,
                                    ),
                                  }
                                : v,
                            ),
                          }))
                        }
                      >
                        <X size={16} />
                      </button>
                    </div>
                  ))}
                  <div className="lm-actions">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setSettings((s) => ({
                          ...s,
                          sequences: s.sequences.map((v, i) =>
                            i === index
                              ? {
                                  ...v,
                                  steps: [
                                    ...v.steps,
                                    {
                                      day: 1,
                                      type: "task",
                                      title: "Follow up",
                                    },
                                  ],
                                }
                              : v,
                          ),
                        }))
                      }
                    >
                      Add step
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        setSettings((s) => ({
                          ...s,
                          sequences: s.sequences.filter((_, i) => i !== index),
                        }))
                      }
                    >
                      Remove sequence
                    </Button>
                  </div>
                </section>
              ))}
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  setSettings((s) => ({
                    ...s,
                    sequences: [
                      ...s.sequences,
                      {
                        name: `Follow-up ${s.sequences.length + 1}`,
                        steps: [
                          { day: 0, type: "call", title: "Make first contact" },
                        ],
                      },
                    ],
                  }))
                }
              >
                New sequence
              </Button>
            </>
          )}
          {tab === "automation" && (
            <>
              <p>
                Create tasks, notify owners or assign leads when a lead is
                created, changes stage or responds.
              </p>
              {settings.workflows.map((rule, index) => {
                const update = (patch: Partial<typeof rule>) =>
                  setSettings((s) => ({
                    ...s,
                    workflows: s.workflows.map((r, i) =>
                      i === index ? { ...r, ...patch } : r,
                    ),
                  }));
                return (
                  <section className="lm-section" key={index}>
                    <div className="lm-form-grid">
                      <Field label="Rule name">
                        <input
                          value={rule.name}
                          onChange={(e) => update({ name: e.target.value })}
                        />
                      </Field>
                      <Field label="When">
                        <NativeSelect
                          value={rule.trigger}
                          onChange={(e) => update({ trigger: e.target.value })}
                        >
                          <option value="created">Lead created</option>
                          <option value="stage_changed">Stage changed</option>
                          <option value="responded">Lead responded</option>
                        </NativeSelect>
                      </Field>
                      <Field label="Only in stage">
                        <NativeSelect
                          value={rule.stage}
                          onChange={(e) => update({ stage: e.target.value })}
                        >
                          <option value="">Any stage</option>
                          {settings.stages.map((s) => (
                            <option key={s.name}>{s.name}</option>
                          ))}
                        </NativeSelect>
                      </Field>
                      <Field label="Then">
                        <NativeSelect
                          value={rule.action}
                          onChange={(e) => update({ action: e.target.value })}
                        >
                          <option value="task">Create task</option>
                          <option value="notify">Notify owner</option>
                          <option value="assign">Assign owner</option>
                        </NativeSelect>
                      </Field>
                      <Field label="Task or notification title">
                        <input
                          value={rule.title}
                          onChange={(e) => update({ title: e.target.value })}
                        />
                      </Field>
                      {rule.action === "assign" ? (
                        <Field label="Assign to">
                          <NativeSelect
                            value={rule.ownerId || ""}
                            onChange={(e) =>
                              update({ ownerId: Number(e.target.value) })
                            }
                          >
                            <option value="">Choose owner</option>
                            {bootstrap.owners.map((o) => (
                              <option value={o.id} key={o.id}>
                                {o.name}
                              </option>
                            ))}
                          </NativeSelect>
                        </Field>
                      ) : (
                        <Field label="Task due after (hours)">
                          <input
                            type="number"
                            min="0"
                            value={rule.delayHours}
                            onChange={(e) =>
                              update({ delayHours: Number(e.target.value) })
                            }
                          />
                        </Field>
                      )}
                    </div>
                    <label className="lm-check">
                      <input
                        type="checkbox"
                        checked={rule.enabled}
                        onChange={(e) => update({ enabled: e.target.checked })}
                      />
                      Enabled
                    </label>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        setSettings((s) => ({
                          ...s,
                          workflows: s.workflows.filter((_, i) => i !== index),
                        }))
                      }
                    >
                      Remove rule
                    </Button>
                  </section>
                );
              })}
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  setSettings((s) => ({
                    ...s,
                    workflows: [
                      ...s.workflows,
                      {
                        name: `Workflow ${s.workflows.length + 1}`,
                        enabled: true,
                        trigger: "created",
                        stage: "",
                        action: "task",
                        title: "Review new enquiry",
                        delayHours: 1,
                      },
                    ],
                  }))
                }
              >
                Add automation
              </Button>
            </>
          )}
          {tab === "website" && (
            <>
              <h3>Website enquiry form</h3>
              <p>
                Publish a dedicated enquiry link. Submissions enter the enquiry
                inbox with an accountable owner, source, consent timestamp and
                duplicate prevention.
              </p>
              <Field label="Responsible intake owner">
                <NativeSelect
                  value={captureOwner}
                  onChange={(e) => setCaptureOwner(Number(e.target.value))}
                >
                  {bootstrap.owners.map((o) => (
                    <option value={o.id} key={o.id}>
                      {o.name}
                    </option>
                  ))}
                </NativeSelect>
              </Field>
              <p>Form status: {capture?.enabled ? "Active" : "Disabled"}</p>
              <div className="lm-actions">
                <Button
                  variant="outline"
                  onClick={async () => {
                    setBusy(true);
                    try {
                      setCapture(
                        (await leadsApi.enableCapture(true, captureOwner)).data,
                      );
                    } catch (err) {
                      setError(errorMessage(err));
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  {capture?.enabled
                    ? "Rotate link & update owner"
                    : "Enable enquiry form"}
                </Button>
                {capture?.enabled && (
                  <Button
                    variant="outline"
                    onClick={async () => {
                      try {
                        setCapture(
                          (await leadsApi.enableCapture(false, captureOwner))
                            .data,
                        );
                      } catch (err) {
                        setError(errorMessage(err));
                      }
                    }}
                  >
                    Disable form
                  </Button>
                )}
              </div>
              {capture?.enabled && capture.path && (
                <Field label="Share or link from your website">
                  <input
                    readOnly
                    value={publicUrl(capture.path)}
                    onFocus={(e) => e.target.select()}
                  />
                </Field>
              )}
              {capture?.enabled && capture.path && (
                <Field label="Embed this HTML form on your website">
                  <textarea
                    readOnly
                    rows={6}
                    value={captureEmbed(capture.path)}
                    onFocus={(e) => e.target.select()}
                  />
                </Field>
              )}
              <p>
                Rotating the link revokes the old form. The form accepts up to
                100 enquiries per hour for this organization, including repeat
                submissions.
              </p>
            </>
          )}{" "}
        </fieldset>
        {error && <ErrorNotice message={error} />}
        <div className="lm-dialog-actions">
          <span>Changes apply after saving</span>
          <Button
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setError("");
              try {
                await leadsApi.settings(settings);
                saved();
              } catch (err) {
                setError(errorMessage(err));
              } finally {
                setBusy(false);
              }
            }}
          >
            Save workflow settings
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default withRecordViewHost(LeadManagementPage);
