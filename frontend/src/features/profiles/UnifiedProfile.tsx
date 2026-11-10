import { useMobile } from "@/components/mobile/useMobile";
import { MobileSheet } from "@/components/mobile/MobilePrimitives";
import { syncScope } from "@/shared/record-sync/store";
import { useAuthStore } from "@/store/authStore";
import { ArrowLeft } from "lucide-react";
import RecordSectionNav from "@/components/RecordSectionNav";
import { NativeSelect } from "@/components/ui/native-select";
import PhoneActions from "../../components/PhoneActions";
import CompactForm from "../../components/forms/CompactForm";
import React, { useEffect, useId, useRef, useState } from "react";
import { PhoneInput } from "../../lib/validation/PhoneInput";
import "./profiles.css";
import "./profile-management-mobile.css";

export type ProfileRequest = (
  path: string,
  options?: { method?: string; body?: unknown },
) => Promise<any>;
type Values = Record<string, any>;
type Profile = {
  userId: number;
  employeeId?: number;
  displayName: string;
  loginEmail: string;
  kind: string;
  role?: string;
  photoUrl?: string;
  accountActive: boolean;
  values: Values;
  version: string;
  completeness: number;
  completionFields?: string[];
  missingFields: string[];
  canEdit: boolean;
  canManage: boolean;
  canReview?: boolean;
  requiresApprovalFields: string[];
  employment?: Values;
  application?: Values;
  documents: Values[];
  pendingRequests: Values[];
  certificationAlerts?: Array<{name:string;expires:string;expired:boolean}>;
};
type Spec = [string, string, string?];
const sections: Record<string, Spec[]> = {
  Personal: [
    ["first_name", "First name"],
    ["middle_name", "Middle name"],
    ["last_name", "Last name"],
    ["preferred_display_name", "Preferred name"],
    ["gender", "Gender"],
    ["date_of_birth", "Date of birth", "date"],
    ["marital_status", "Marital status"],
    ["guardian_name", "Parent / guardian name"],
    ["bio", "About me", "textarea"],
  ],
  Contact: [
    ["personal_email", "Personal email", "email"],
    ["phone_number", "Phone", "phone"],
    ["present_address", "Current address", "textarea"],
    ["present_city", "City"],
    ["present_state", "State"],
    ["present_pincode", "Postal code"],
    ["present_country", "Country"],
    ["permanent_address", "Permanent address", "textarea"],
    ["permanent_city", "Permanent city"],
    ["permanent_state", "Permanent state"],
    ["permanent_pincode", "Permanent postal code"],
    ["emergency_contact_name", "Emergency contact name"],
    ["emergency_contact_number", "Emergency phone", "phone"],
    ["emergency_contact_relation", "Emergency contact relationship"],
  ],
  Academic: [
    ["degree", "Degree"],
    ["college", "College / institution"],
    ["specialization", "Specialization"],
    ["current_year", "Current academic year"],
    ["passout_year", "Pass-out year", "number"],
    ["tenth_marks", "10th marks (%)", "number"],
    ["twelfth_marks", "12th marks (%)", "number"],
  ],
  Professional: [
    ["interests", "Areas of interest", "textarea"],
    ["skills", "Skills", "skills"],
    ["languages", "Languages"],
    ["requested_role", "Role applied for"],
    ["preferred_mode", "Preferred work mode"],
    ["available_from", "Available from", "date"],
    ["duration", "Internship duration"],
    ["linkedin_url", "LinkedIn", "url"],
    ["github_url", "GitHub", "url"],
    ["portfolio_url", "Portfolio", "url"],
    ["timezone", "Time zone"],
    ["locale", "Language / locale"],
  ],
};
const labels: Record<string, string> = Object.fromEntries(
  Object.values(sections)
    .flat()
    .map(([key, label]) => [key, label]),
);
const text = (value: unknown) =>
  value === null || value === undefined || value === ""
    ? "Not provided"
    : Array.isArray(value)
      ? value.join(", ")
      : typeof value === "boolean"
        ? value
          ? "Yes"
          : "No"
        : String(value);
function errorText(error: any) {
  const value = error?.response?.data?.detail || error?.message || error;
  return typeof value === "string"
    ? value
    : Array.isArray(value)
      ? value.map((item) => item.msg || item.error).join("; ")
      : "The profile could not be saved. Check the fields and try again.";
}

function ProfileField({
  spec,
  value,
  editing,
  patch,
  approval,
  values,
}: {
  spec: Spec;
  value: any;
  editing: boolean;
  patch: (key: string, value: any) => void;
  approval: boolean;
  values: Values;
}) {
  const id = useId();
  const [key, label, kind] = spec;
  return (
    <div className="up-field" data-profile-kind={kind}>
      <label htmlFor={id}>
        {label}
        {approval && editing && <small>HR review</small>}
      </label>
      {!editing ? (
        <p>
          {kind === "phone" ? <PhoneActions value={value} record={values} field={key} /> : text(value)}
        </p>
      ) : kind === "phone" ? (
        <PhoneInput
          id={id}
          label={label}
          value={value || ""}
          countryCode={values[key + "_country_code"] || ""}
          onChange={(number) => patch(key, number || null)}
          onCountryCodeChange={(code) => patch(key + "_country_code", code)}
        />
      ) : kind === "textarea" ? (
        <textarea
          id={id}
          rows={3}
          value={value || ""}
          maxLength={4000}
          onChange={(e) => patch(key, e.target.value || null)}
        />
      ) : kind === "skills" ? (
        <input
          id={id}
          defaultValue={(value || []).join(", ")}
          placeholder="Python, React, Communication"
          maxLength={3000}
          onChange={(e) =>
            patch(
              key,
              e.target.value
                .split(",")
                .map((name) => name.trim())
                .filter(Boolean),
            )
          }
        />
      ) : (
        <input
          id={id}
          type={
            kind === "number"
              ? "number"
              : kind === "date"
                ? "date"
                : kind === "email"
                  ? "email"
                  : kind === "url"
                    ? "url"
                    : "text"
          }
          value={value ?? ""}
          maxLength={kind === "email" ? 150 : 200}
          step={
            key.endsWith("_marks") || key === "percentage_cgpa" ? "0.01" : "1"
          }
          onChange={(e) =>
            patch(
              key,
              kind === "number"
                ? e.target.value === ""
                  ? null
                  : Number(e.target.value)
                : e.target.value || null,
            )
          }
        />
      )}
    </div>
  );
}

function CollectionEditor({
  kind,
  rows,
  editing,
  patch,
}: {
  kind: "education" | "experience";
  rows: Values[];
  editing: boolean;
  patch: (key: string, value: any) => void;
}) {
  const fields: Spec[] =
    kind === "education"
      ? [
          ["degree", "Qualification"],
          ["institution", "Institution"],
          ["specialization", "Specialization"],
          ["board_university", "Board / university"],
          ["pass_year", "Pass-out year", "number"],
          ["percentage_cgpa", "Marks / CGPA", "number"],
        ]
      : [
          ["company_name", "Company"],
          ["designation", "Job title"],
          ["from_date", "Start date", "date"],
          ["to_date", "End date", "date"],
          ["responsibilities", "Responsibilities", "textarea"],
        ];
  return (
    <section className="up-collection">
      <h2>{kind === "education" ? "Education records" : "Work experience"}</h2>
      {!rows.length && <p className="up-muted">No {kind} records yet.</p>}
      {rows.map((row, index) => (
        <article key={row.id || `new-${index}`}>
          <header>
            <h3>
              {kind === "education"
                ? row.degree || "New qualification"
                : row.company_name || "New experience"}
            </h3>
            {editing && (
              <button
                type="button"
                onClick={() =>
                  patch(
                    kind,
                    rows.filter((_, i) => i !== index),
                  )
                }
              >
                Remove
              </button>
            )}
          </header>
          <div className="up-grid">
            {fields.map((spec) => (
              <ProfileField
                key={spec[0]}
                spec={spec}
                value={row[spec[0]]}
                values={row}
                editing={editing}
                approval={false}
                patch={(key, value) =>
                  patch(
                    kind,
                    rows.map((item, i) =>
                      i === index ? { ...item, [key]: value } : item,
                    ),
                  )
                }
              />
            ))}
            {kind === "experience" && editing && (
              <label className="up-check">
                <input
                  type="checkbox"
                  checked={!!row.is_current}
                  onChange={(e) =>
                    patch(
                      kind,
                      rows.map((item, i) =>
                        i === index
                          ? {
                              ...item,
                              is_current: e.target.checked,
                              ...(e.target.checked ? { to_date: null } : {}),
                            }
                          : item,
                      ),
                    )
                  }
                />
                I currently work here
              </label>
            )}
          </div>
        </article>
      ))}
      {editing && (
        <button
          type="button"
          className="up-button"
          onClick={() =>
            patch(kind, [
              ...rows,
              kind === "education"
                ? { degree: "", institution: "" }
                : { company_name: "", designation: "", is_current: false },
            ])
          }
        >
          Add {kind === "education" ? "qualification" : "experience"}
        </button>
      )}
    </section>
  );
}

function ConnectDialog({
  preview,
  confirm,
  close,
  busy,
  mobile = false,
  error = "",
  returnFocus,
}: {
  preview: Values;
  confirm: (id: number) => void;
  close: () => void;
  busy: boolean;
  mobile?: boolean;
  error?: string;
  returnFocus?: HTMLElement | null;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState(
    String(preview.candidates[0]?.employeeId || ""),
  );
  useEffect(() => {
    if (!mobile) ref.current?.showModal();
  }, [mobile]);
  useEffect(() => {
    if (mobile && error) errorRef.current?.focus();
  }, [mobile, error]);
  const content = <>
      {!mobile && <h2>Connect profile by email</h2>}
      <p>{preview.email}</p>
      <p>{preview.message}</p>
      {mobile && error && <div className="up-error" role="alert" ref={errorRef} tabIndex={-1}>{error}</div>}
      {preview.candidates.length ? (
        <>
          <label>
            Matching employee
            <NativeSelect
              disabled={mobile && busy}
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
            >
              {preview.candidates.map((item: Values) => (
                <option key={item.employeeId} value={item.employeeId}>
                  {item.name} ({item.employeeCode})
                  {item.linked ? " · already connected" : ""}
                </option>
              ))}
            </NativeSelect>
          </label>
          <button
            className="up-button up-primary"
            disabled={busy || !selected}
            onClick={() => confirm(Number(selected))}
          >
            Confirm employee connection
          </button>
        </>
      ) : (
        <p>
          No available employee matches this login email in your organization.
          Pending applications still require HR approval.
        </p>
      )}
      <button className="up-button" disabled={busy} onClick={close}>
        Close
      </button>
    </>;
  if (mobile) return <MobileSheet open onClose={() => { if (!busy) close(); }} title="Connect profile by email" onClosed={() => { if (returnFocus?.isConnected && !ref.current?.open) returnFocus.focus(); }}><div className="up-root up-management-connect" aria-busy={busy}>{content}</div></MobileSheet>;
  return <dialog className="up-connect-dialog" ref={ref} onCancel={event => { event.preventDefault(); if (!busy) close(); }}>{content}</dialog>;
}

export function UnifiedProfile({
  request,
  userId,
  employeeId,
  onSaved,
  onDirtyChange,
  onBusyChange,
  renderLoadError,
  mobileManagement = false,
}: {
  request: ProfileRequest;
  userId?: number;
  employeeId?: number;
  onSaved?: () => void;
  onDirtyChange?: (dirty: boolean) => void;
  onBusyChange?: (busy: boolean) => void;
  renderLoadError?: (message: string) => React.ReactNode;
  mobileManagement?: boolean;
}) {
  const path = employeeId
    ? `/profiles/employees/${employeeId}`
    : userId
      ? `/profiles/users/${userId}`
      : "/profiles/me";
  const [profile, setProfile] = useState<Profile>();
  const [draft, setDraft] = useState<Values>({});
  const [editing, setEditing] = useState(false);
  const [tab, setTab] = useState("Overview");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [reload, setReload] = useState(0);
  const [preview, setPreview] = useState<Values>();
  const [photoFailed, setPhotoFailed] = useState(false);
  useAuthStore(state => state.user);
  const [photoSelection, setPhotoSelection] = useState<{file:File;scope:string;error?:string;retryable?:boolean}>();
  const [, refreshPhotoScope] = useState(0);
  const photoInputRef = useRef<HTMLInputElement>(null);
  const photoButtonRef = useRef<HTMLButtonElement>(null);
  const profileHeadingRef = useRef<HTMLHeadingElement>(null);
  const photoFocusPending = useRef(false);
  const photoErrorRef = useRef<HTMLDivElement>(null);
  const photoInFlight = useRef(false);
  function photoContextKey() { return JSON.stringify([syncScope(),useAuthStore.getState().user?.employee_id,path,profile?.employeeId]); }
  const currentPhotoScope = photoContextKey();
  const currentPhoto = photoSelection?.scope === currentPhotoScope ? photoSelection : undefined;
  useEffect(() => {
    if (!mobileManagement) return;
    const refresh = () => refreshPhotoScope(value => value + 1);
    const names = ["suite:organization-changed", "suite:branch-changed", "storage"];
    names.forEach(name => window.addEventListener(name, refresh));
    return () => names.forEach(name => window.removeEventListener(name, refresh));
  }, [mobileManagement]);
  useEffect(() => { if (mobileManagement && currentPhoto?.error) photoErrorRef.current?.focus(); }, [mobileManagement, currentPhoto]);
  useEffect(() => {
    if (mobileManagement && !busy && photoFocusPending.current) {
      photoFocusPending.current = false;
      (photoButtonRef.current || profileHeadingRef.current)?.focus();
    }
  }, [mobileManagement, busy, photoSelection]);
  const [reviewRemarks, setReviewRemarks] = useState<Record<string, string>>({});
  const [reviewError, setReviewError] = useState<{ id: number; message: string }>();
  const reviewErrorRef = useRef<HTMLDivElement>(null);
  const reviewHeadingRef = useRef<HTMLHeadingElement>(null);
  const reviewFocusPending = useRef(false);
  useEffect(() => {
    if (mobileManagement && profile && reviewFocusPending.current && reviewHeadingRef.current) {
      reviewFocusPending.current = false;
      reviewHeadingRef.current.focus();
    }
  }, [mobileManagement, profile, tab]);
  useEffect(() => { onBusyChange?.(busy); }, [busy, onBusyChange]);
  useEffect(() => {
    if (mobileManagement && reviewError) reviewErrorRef.current?.focus();
  }, [mobileManagement, reviewError, tab]);
  const connectButtonRef = useRef<HTMLButtonElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (mobileManagement && error && !preview) errorRef.current?.focus();
  }, [mobileManagement, error, preview]);
  useEffect(() => {
    let active = true;
    setProfile(undefined);
    setError("");
    setEditing(false);
    request(path)
      .then((result) => {
        if (active) {
          setProfile(result);
          setDraft(structuredClone(result.values));
          setPhotoFailed(false);
        }
      })
      .catch((error) => {
        if (active) setError(errorText(error));
      });
    return () => {
      active = false;
    };
  }, [request, path, reload]);
  const patch = (key: string, value: any) =>
    setDraft((values) => ({ ...values, [key]: value }));
  const dirty =
    profile &&
    Object.keys(draft).some(
      (key) =>
        JSON.stringify(draft[key]) !== JSON.stringify(profile.values[key]),
    );
  const reviewDirty = Object.values(reviewRemarks).some(value => value.length > 0);
  const photoDirty = !!currentPhoto;
  useEffect(() => {
    onDirtyChange?.(!!dirty || reviewDirty || photoDirty);
  }, [dirty, reviewDirty, photoDirty, onDirtyChange]);
  useEffect(() => {
    if (!dirty && !reviewDirty && !photoDirty) return;
    const protect = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener("beforeunload", protect);
    return () => window.removeEventListener("beforeunload", protect);
  }, [dirty, reviewDirty, photoDirty]);
  const cancel = () => {
    if (dirty && !window.confirm("Discard unsaved profile changes?")) return;
    if (profile) setDraft(structuredClone(profile.values));
    setEditing(false);
    setError("");
  };
  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!profile) return;
    const values = Object.fromEntries(
      Object.entries(draft).filter(
        ([key, value]) =>
          JSON.stringify(value) !== JSON.stringify(profile.values[key]),
      ),
    );
    setBusy(true);
    setError("");
    try {
      const result = await request(path, {
        method: "PATCH",
        body: {
          values,
          version: profile.version,
          reason: "Updated from complete profile",
        },
      });
      setProfile(result.profile);
      setDraft(structuredClone(result.profile.values));
      setEditing(false);
      setMessage(result.message);
      onSaved?.();
    } catch (error) {
      setError(errorText(error));
    } finally {
      setBusy(false);
    }
  };
  async function uploadProfilePhoto(file: File, scope?: string) {
    if (!profile) return;
    if (scope !== undefined) {
      if (busy || photoInFlight.current || dirty || !profile.canEdit) return;
      if (scope !== photoContextKey()) { refreshPhotoScope(value => value + 1); return; }
      setPhotoSelection(current => ({file,scope,retryable:current?.scope === scope && current.file === file && current.retryable}));
    }
    if (file.size > 3 * 1024 * 1024) {
      if (scope !== undefined) setPhotoSelection({file,scope,error:"Profile photos must be 3 MB or smaller"});
      else setError("Profile photos must be 3 MB or smaller");
      return;
    }
    const body = new FormData(); body.append("file", file);
    photoInFlight.current = true;
    setBusy(true); setError("");
    try {
      const result = await request(path + "/photo", {method:"POST",body});
      if (scope === undefined || scope === photoContextKey()) {
        if (scope !== undefined) photoFocusPending.current = true;
        setProfile(result); setDraft(structuredClone(result.values)); setPhotoFailed(false);
        setMessage("Profile photo updated across connected modules."); onSaved?.();
      }
      if (scope !== undefined) setPhotoSelection(current => current?.scope === scope && current.file === file ? undefined : current);
    } catch (error) {
      if (scope !== undefined) setPhotoSelection(current => current?.scope === scope && current.file === file ? {...current,error:errorText(error),retryable:true} : current);
      else setError(errorText(error));
    } finally { photoInFlight.current = false; setBusy(false); }
  }
  if (!profile)
    return (
      <section className="up-root">
        {error ? renderLoadError?.(error) || (
          <div className="up-error" role="alert" ref={errorRef} tabIndex={mobileManagement ? -1 : undefined}>
            {error}
            <button onClick={() => setReload((v) => v + 1)}>Retry</button>
          </div>
        ) : (
          <p role="status">Loading complete profile…</p>
        )}
      </section>
    );
  const tabs = [
    "Overview",
    "Personal",
    "Contact",
    "Academic",
    "Education",
    "Experience",
    "Professional",
    "Employment",
    "Documents",
    ...(profile.application ? ["Application"] : []),
    ...(profile.pendingRequests.length ? ["Pending changes"] : []),
  ];
  const completionFields = profile.completionFields || ["first_name","personal_email","phone_number","present_address","present_city","skills","education","emergency_contact_number","bio"];
  const filled = (value: unknown) => Array.isArray(value) ? value.length>0 : typeof value === "string" ? value.trim().length>0 : !!value;
  const draftMissing = completionFields.filter(key=>!filled(draft[key]));
  const displayedCompletion = editing ? Math.round(100*(completionFields.length-draftMissing.length)/completionFields.length) : profile.completeness;
  const displayedMissing = editing ? draftMissing : profile.missingFields;
  const pendingValues = Object.assign({},profile.values,...[...profile.pendingRequests].reverse().map(p=>p.values));
  const pendingCompletion = Math.round(100*completionFields.filter(key=>filled(pendingValues[key])).length/completionFields.length);
  const fieldSection = (name: string) => (
    <section className="up-section">
      <h2>
        {name === "Academic"
          ? "Academic background"
          : name === "Professional"
            ? "Skills, interests & links"
            : `${name} information`}
      </h2>
      <div className="up-grid">
        {sections[name].map((spec) => (
          <ProfileField
            key={`${profile.version}-${spec[0]}-${editing}`}
            spec={spec}
            value={draft[spec[0]]}
            values={draft}
            editing={editing}
            patch={patch}
            approval={profile.requiresApprovalFields.includes(spec[0])}
          />
        ))}
      </div>
    </section>
  );
  return (
    <section className="up-root">
      <header className="up-header">
        <div className="up-identity">
          <span className="up-avatar">
            {profile.photoUrl && !photoFailed ? (
              <img
                src={profile.photoUrl}
                alt={`${profile.displayName} profile`}
                onError={() => setPhotoFailed(true)}
              />
            ) : (
              (profile.displayName || "?").slice(0, 1).toUpperCase()
            )}
          </span>
          <div>
            <div className="up-kicker">CONNECTED PROFILE</div>
            <h1 ref={profileHeadingRef} tabIndex={mobileManagement ? -1 : undefined}>{profile.displayName || "My profile"}</h1>
            <p>{profile.loginEmail}</p>
            <div className="up-badges">
              <span>{profile.kind}</span>
              {profile.employment?.employee_id && (
                <span>{profile.employment.employee_id}</span>
              )}
              <span>
                {profile.accountActive ? "Active account" : "Inactive account"}
              </span>
            </div>
          </div>
        </div>
        <div className="up-actions">
          {profile.canEdit && (
            <>
            {mobileManagement && <button ref={photoButtonRef} type="button" className="up-button" disabled={busy || !!dirty} onClick={() => photoInputRef.current?.click()}>Change photo</button>}
            <label className="up-button up-photo-control" style={mobileManagement ? {display:"none"} : undefined}>
              Change photo
              <input
                ref={photoInputRef}
                type="file"
                accept="image/png,image/jpeg"
                aria-label="Upload profile photo"
                disabled={busy || !!dirty}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  event.target.value = "";
                  if (!file) return;
                  if (!mobileManagement) setPhotoSelection(undefined);
                  void uploadProfilePhoto(file, mobileManagement ? photoContextKey() : undefined);
                }}
              />
            </label>
            </>
          )}
          {profile.canManage && !editing && (
            <button
              ref={connectButtonRef}
              className="up-button"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  setPreview(
                    await request(
                      `/profiles/users/${profile.userId}/connect-preview`,
                    ),
                  );
                } catch (error) {
                  setError(errorText(error));
                } finally {
                  setBusy(false);
                }
              }}
            >
              Connect by email
            </button>
          )}
          {profile.canEdit && (
            <button
              className="up-button up-primary"
              disabled={busy}
              onClick={() => (editing ? cancel() : setEditing(true))}
            >
              {editing ? "Cancel editing" : "Edit profile"}
            </button>
          )}
          {mobileManagement && profile.canEdit && currentPhoto && <div className="up-photo-feedback">
            <p>Selected photo: {currentPhoto.file.name}</p>
            {busy && photoInFlight.current && <p role="status">Uploading photo…</p>}
            {currentPhoto.error && <div className="up-error" role="alert" tabIndex={-1} ref={photoErrorRef}>{currentPhoto.error}</div>}
            {currentPhoto.retryable && <button type="button" className="up-button" disabled={busy || !!dirty} onClick={() => void uploadProfilePhoto(currentPhoto.file,currentPhoto.scope)}>Retry photo upload</button>}
          </div>}
        </div>
      </header>
      <div className="up-summary">
        <div>
          <strong>{displayedCompletion}%</strong>
          <span>{editing ? "Draft profile complete" : "Saved profile complete"}</span>
        </div>
        <progress
          max={100}
          value={displayedCompletion}
          aria-label="Profile completeness"
        />
        <p>
          {displayedMissing.length
            ? "To complete: " +
              displayedMissing.map((key) => labels[key] || key).join(", ")
            : "Your main profile details are complete."}
        </p>
        {profile.pendingRequests.length>0 && <p role="status">Submitted details: {pendingCompletion}% complete. Name and employee record changes update the saved profile after HR approval; your pending changes are retained.</p>}
      </div>
      <p className="up-source-note">
        Login email connects your account. Employee and internship details come
        from HRMS; approved application details are retained below. Login email,
        role and job assignments are managed separately.
      </p>
      {profile.application && (
        <div className="up-application-note">
          Application {profile.application.reference} is connected to this
          profile. You do not need to enter the same onboarding information
          again.
        </div>
      )}
      {message && (
        <div className="up-success" role="status">
          {message}
        </div>
      )}
      {!!profile.certificationAlerts?.length && <aside role="status" className="profile-card"><h2>Certification expiry alerts</h2>{profile.certificationAlerts.map((certificate,index)=><p key={index}>{certificate.name}: {certificate.expired?"Expired":"Expires within 90 days"} · {certificate.expires}</p>)}</aside>}
      {error && !(mobileManagement && preview) && (
        <div className="up-error" role="alert" ref={errorRef} tabIndex={mobileManagement ? -1 : undefined}>
          {error}
          <button
            type="button"
            onClick={() => {
              if (
                (!dirty && !reviewDirty && !photoDirty) ||
                window.confirm(
                  "Discard this draft and reload the latest profile?",
                )
              ) {
                setReviewRemarks({}); setPhotoSelection(undefined);
                setReload((v) => v + 1);
              }
            }}
          >
            Reload latest profile
          </button>
        </div>
      )}
      <RecordSectionNav value={tab} onChange={setTab} label="Profile sections" groups={[
        {label:"Overview",sections:tabs.filter(name=>["Overview","Pending changes"].includes(name)).map(value=>({value,label:value}))},
        {label:"Personal",sections:tabs.filter(name=>["Personal","Contact"].includes(name)).map(value=>({value,label:value}))},
        {label:"Career",sections:tabs.filter(name=>["Academic","Education","Experience","Professional","Employment"].includes(name)).map(value=>({value,label:value}))},
        {label:"Documents",sections:tabs.filter(name=>["Documents","Application"].includes(name)).map(value=>({value,label:value}))},
      ]}/>

      <CompactForm onSubmit={save}>
        <fieldset className="up-fieldset" disabled={busy}>
          {tab === "Overview" && (
            <>
              <div className="up-overview">
                <div>
                  <h2>Identity & contact</h2>
                  <dl>
                    <dt>Name</dt>
                    <dd>{profile.displayName}</dd>
                    <dt>Login email</dt>
                    <dd>{profile.loginEmail}</dd>
                    <dt>Personal email</dt>
                    <dd>{text(draft.personal_email)}</dd>
                    <dt>Phone</dt>
                    <dd>
                      <PhoneActions value={draft.phone_number} record={draft} field="phone_number" />
                    </dd>
                    <dt>Location</dt>
                    <dd>
                      {[
                        draft.present_city,
                        draft.present_state,
                        draft.present_country,
                      ]
                        .filter(Boolean)
                        .join(", ") || "Not provided"}
                    </dd>
                  </dl>
                </div>
                <div>
                  <h2>About & interests</h2>
                  <p>{text(draft.bio)}</p>
                  <p>{text(draft.interests)}</p>
                  <div className="up-skill-chips">
                    {(draft.skills || []).map((skill: string) => (
                      <span key={skill}>{skill}</span>
                    ))}
                  </div>
                </div>
              </div>
              {editing && (
                <p className="up-help">
                  Choose a profile section above to edit its fields, then save
                  all changes together.
                </p>
              )}
              {profile.pendingRequests.length > 0 && (
                <button
                  type="button"
                  className="up-button"
                  onClick={() => setTab("Pending changes")}
                >
                  {profile.pendingRequests.length} changes awaiting HR approval
                </button>
              )}
            </>
          )}
          {sections[tab] && fieldSection(tab)}
          {(tab === "Education" || tab === "Experience") && (
            <>
              <p className="up-help">
                {editing &&
                profile.requiresApprovalFields.includes(tab.toLowerCase())
                  ? "Updates to these employee records require HR review before they take effect."
                  : "Qualifications and work history are shared with your employee profile."}
              </p>
              <CollectionEditor
                kind={tab.toLowerCase() as "education" | "experience"}
                rows={draft[tab.toLowerCase()] || []}
                editing={editing}
                patch={patch}
              />
            </>
          )}
          {tab === "Employment" && (
            <section className="up-section">
              <h2>
                {profile.kind === "intern"
                  ? "Internship & employment"
                  : "Employment"}
              </h2>
              <p className="up-help">
                HR manages these assignments. Profile editing cannot change
                account permissions or job status.
              </p>
              {profile.employment ? (
                <dl className="up-read-grid">
                  {Object.entries(profile.employment).map(([key, value]) => (
                    <div key={key}>
                      <dt>{key.replace(/_/g, " ")}</dt>
                      <dd>{text(value)}</dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <p>
                  No employee record is connected to this account. HR can
                  connect an existing employee after reviewing the email match.
                </p>
              )}
            </section>
          )}
          {tab === "Documents" && (
            <section className="up-section">
              <h2>Profile documents</h2>
              {profile.documents.length ? (
                <ul className="up-document-list">
                  {profile.documents.map((doc) => (
                    <li key={`${doc.source}-${doc.id}`}>
                      <strong>{doc.name}</strong>
                      <span>
                        {doc.source} · {doc.status || "Pending verification"}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>No documents are attached yet.</p>
              )}
              <p className="up-help">
                Document files and identity verification are managed through the
                existing HRMS document controls. Passwords, raw identity numbers
                and payroll details are not part of this shared profile.
              </p>
            </section>
          )}
          {tab === "Application" && profile.application && (
            <section className="up-section">
              <h2>Original application</h2>
              <p className="up-help">
                Submitted information is retained as provenance. Later profile
                edits update your current profile, not the original form.
              </p>
              <dl className="up-read-grid">
                {Object.entries({
                  Reference: profile.application.reference,
                  "Application email": profile.application.email,
                  "Submitted name": profile.application.full_name,
                  ...(profile.application.values || {}),
                  ...(profile.application.identity_last4
                    ? {
                        "Identity reference":
                          "•••• " + profile.application.identity_last4,
                      }
                    : {}),
                }).map(([key, value]) => (
                  <div key={key}>
                    <dt>{labels[key] || key.replace(/_/g, " ")}</dt>
                    <dd>{text(value)}</dd>
                  </div>
                ))}
              </dl>
            </section>
          )}
          {tab === "Pending changes" && (
            <section className="up-section">
              <h2 ref={reviewHeadingRef} tabIndex={mobileManagement ? -1 : undefined}>Changes awaiting HR review</h2>
              {mobileManagement && !profile.pendingRequests.length && <p role="status">No changes awaiting HR review.</p>}
              {profile.pendingRequests.map((change) => (
                <article className="up-pending" key={change.id}>
                  <h3>
                    Request #{change.id} · {change.status}
                  </h3>
                  <p>{change.reason}</p>
                  <dl>
                    {Object.entries(change.values).map(([key, value]) => {
                      const rendered = typeof value === "object" && value !== null ? JSON.stringify(value) : text(value);
                      return (
                      <div key={key}>
                        <dt>{labels[key] || key}</dt>
                        <dd>
                          {mobileManagement && rendered.length > 240 ? <details className="up-review-value"><summary>View full requested value</summary><div>{rendered}</div></details> : rendered}
                        </dd>
                      </div>
                    );})}
                  </dl>
                  {profile.canReview && (
                    <>
                    {mobileManagement && <>
                      {reviewError && reviewError.id === change.id && <div className="up-error" role="alert" tabIndex={-1} ref={reviewErrorRef}>{reviewError.message}</div>}
                      <label className="up-review-remarks">Review remarks (optional)<textarea rows={2} value={reviewRemarks[change.id] || ""} onChange={event => setReviewRemarks(current => ({...current, [change.id]:event.target.value}))}/></label>
                    </>}
                    <div className={`up-actions${mobileManagement ? " up-review-actions" : ""}`}>
                      {["approve", "reject"].map((action) => (
                        <button
                          key={action}
                          className="up-button"
                          type="button"
                          disabled={busy}
                          onClick={async () => {
                            if (mobileManagement && busy) return;
                            const remarks = mobileManagement ? reviewRemarks[change.id] || "" : window.prompt(
                              `${action === "approve" ? "Approve" : "Reject"} profile changes: review remarks`,
                            );
                            if (remarks === null) return;
                            if (mobileManagement) { setReviewError(undefined); setError(""); }
                            setBusy(true);
                            try {
                              await request(
                                `/hrms/profile-change-requests/${change.id}/${action}`,
                                {
                                  method: "POST",
                                  body: { remarks, applyChanges: true },
                                },
                              );
                              setReviewRemarks(current => { const next={...current}; delete next[change.id]; return next; });
                              if (mobileManagement) {
                                reviewFocusPending.current = true;
                              }
                              setReload((v) => v + 1);
                              onSaved?.();
                            } catch (error) {
                              if (mobileManagement) setReviewError({id:change.id,message:errorText(error)});
                              else setError(errorText(error));
                            } finally {
                              setBusy(false);
                            }
                          }}
                        >
                          {action === "approve"
                            ? "Approve changes"
                            : "Reject changes"}
                        </button>
                      ))}
                    </div>
                    </>
                  )}
                </article>
              ))}
            </section>
          )}
        </fieldset>
        {editing && (
          <footer className="up-save-bar">
            <div>
              <strong>{dirty ? "Unsaved changes" : "No changes yet"}</strong>
              {profile.requiresApprovalFields.length > 0 && (
                <small>
                  Fields marked HR review remain unchanged until approved.
                </small>
              )}
            </div>
            <button
              type="button"
              className="up-button"
              disabled={busy}
              onClick={cancel}
            >
              Cancel
            </button>
            <button
              className="up-button up-primary"
              type="submit"
              disabled={!dirty || busy}
            >
              {busy ? "Saving…" : "Save profile"}
            </button>
          </footer>
        )}
      </CompactForm>
      {preview && (
        <ConnectDialog
          preview={preview}
          busy={busy}
          mobile={mobileManagement}
          error={error}
          returnFocus={connectButtonRef.current}
          close={() => setPreview(undefined)}
          confirm={async (employeeId) => {
            if (mobileManagement) setError("");
            setBusy(true);
            try {
              const result = await request(
                `/profiles/users/${profile.userId}/connect-email`,
                { method: "POST", body: { employeeId } },
              );
              setProfile(result);
              setDraft(structuredClone(result.values));
              setPreview(undefined);
              setMessage("Employee and account profiles are connected.");
              onSaved?.();
            } catch (error) {
              setError(errorText(error));
            } finally {
              setBusy(false);
            }
          }}
        />
      )}
    </section>
  );
}

export function ProfileManagement({ request }: { request: ProfileRequest }) {
  const phone = useMobile(480);
  const [result, setResult] = useState<{ items: Values[]; total: number }>({items: [], total: 0});
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number>();
  const [profileDirty, setProfileDirty] = useState(false);
  const [profileBusy, setProfileBusy] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [reload, setReload] = useState(0);
  const [mobileView, setMobileView] = useState("list");
  const searchRef = useRef<HTMLInputElement>(null);
  const backRef = useRef<HTMLButtonElement>(null);
  const opener = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      setLoading(true);
      request(`/profiles/directory?search=${encodeURIComponent(search)}&page=${page}`)
        .then((data) => {
          if (active) {setResult(data);setHasLoaded(true);setError("");}
        })
        .catch((error) => {if (active) setError(errorText(error));})
        .finally(() => {if (active) setLoading(false);});
    }, 250);
    return () => {active = false;clearTimeout(timer);};
  }, [request, search, page, reload]);
  useEffect(() => {
    if(!phone || !selected)return;
    if(mobileView === "profile")backRef.current?.focus();
    else if(opener.current?.isConnected)opener.current.focus();
    else searchRef.current?.focus();
  },[phone,mobileView,selected]);
  const list = <>
    {phone && selected && <div className="up-management-resume"><button type="button" className="up-button" onClick={event => {opener.current=event.currentTarget;setMobileView("profile");}}>{profileDirty ? "Continue editing profile" : "Open selected profile"}</button></div>}
    {error && <div role="alert" className="up-error">{error}{phone && <button type="button" className="up-button" disabled={loading} onClick={()=>{if(!loading){setLoading(true);setReload(value=>value+1);}}}>Retry profiles</button>}</div>}
    {phone && error && hasLoaded && !loading && <p className="up-muted">Showing the last loaded results.</p>}
    {loading ? <p role="status">Loading profiles…</p> : (!phone || hasLoaded) && <div className="up-directory">
      {result.items.map(item => <button key={item.userId} disabled={phone && profileBusy} onClick={event => {
        if(selected === item.userId){if(phone){opener.current=event.currentTarget;setMobileView("profile");}return;}
        if(profileDirty && !window.confirm("Discard unsaved profile changes?"))return;
        if(phone)opener.current=event.currentTarget;
        setProfileDirty(false);setSelected(item.userId);setMobileView("profile");
      }} aria-pressed={selected === item.userId}>
        <span><strong>{item.displayName}</strong><small>{item.email}</small></span>
        <span>{item.employeeCode || "Account only"}</span>
        <span>{item.kind} · {item.active ? "Active" : "Inactive"}</span>
      </button>)}
      {!result.items.length && !(phone && error) && <p>No profiles match your search.</p>}
    </div>}
    <div className="up-actions up-pagination">
      <span>{phone && !hasLoaded ? "—" : result.total} profiles</span>
      <button className="up-button" disabled={page <= 1 || (phone && loading)} onClick={()=>{if(phone)setLoading(true);setPage(value=>value-1);}}>Previous</button>
      <span>Page {page}</span>
      <button className="up-button" disabled={page * 30 >= result.total || (phone && loading)} onClick={()=>{if(phone)setLoading(true);setPage(value=>value+1);}}>Next</button>
    </div>
  </>;
  return <div className="up-root up-management" data-mobile-view={mobileView}>
    <header className="up-header">
      <div><div className="up-kicker">PEOPLE</div><h1>Profile management</h1><p>Employees, interns and user accounts in your permitted scope.</p></div>
      <label className="up-field">Find a profile<input ref={searchRef} type="search" value={search} onChange={event=>{if(phone)setLoading(true);setSearch(event.target.value);setPage(1);}} placeholder="Name, email or employee code"/></label>
    </header>
    <div className="up-management-list">{list}</div>
    {phone && selected && mobileView === "profile" && <div className="up-management-profile-nav"><button ref={backRef} type="button" className="up-button" disabled={profileBusy} onClick={()=>setMobileView("list")}><ArrowLeft size={16}/>All profiles</button>{profileDirty && <span className="up-muted">Unsaved changes</span>}</div>}
    <div className="up-management-detail">{selected && <UnifiedProfile key={selected} request={request} userId={selected} onDirtyChange={setProfileDirty} onBusyChange={phone ? setProfileBusy : undefined} mobileManagement={phone}/>}</div>
  </div>;
}
