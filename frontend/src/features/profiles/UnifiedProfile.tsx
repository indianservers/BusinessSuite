import React, { useEffect, useId, useRef, useState } from "react";
import { PhoneInput } from "../../lib/validation/PhoneInput";
import "./profiles.css";

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
  missingFields: string[];
  canEdit: boolean;
  canManage: boolean;
  canReview?: boolean;
  requiresApprovalFields: string[];
  employment?: Values;
  application?: Values;
  documents: Values[];
  pendingRequests: Values[];
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
    <div className="up-field">
      <label htmlFor={id}>
        {label}
        {approval && editing && <small>HR review</small>}
      </label>
      {!editing ? (
        <p>
          {kind === "phone"
            ? values[key + "_country_code"]
              ? `${values[key + "_country_code"]} ${text(value)}`
              : text(value)
            : text(value)}
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
}: {
  preview: Values;
  confirm: (id: number) => void;
  close: () => void;
  busy: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [selected, setSelected] = useState(
    String(preview.candidates[0]?.employeeId || ""),
  );
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return (
    <dialog
      className="up-connect-dialog"
      ref={ref}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) close();
      }}
    >
      <h2>Connect profile by email</h2>
      <p>{preview.email}</p>
      <p>{preview.message}</p>
      {preview.candidates.length ? (
        <>
          <label>
            Matching employee
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
            >
              {preview.candidates.map((item: Values) => (
                <option key={item.employeeId} value={item.employeeId}>
                  {item.name} ({item.employeeCode})
                  {item.linked ? " · already connected" : ""}
                </option>
              ))}
            </select>
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
    </dialog>
  );
}

export function UnifiedProfile({
  request,
  userId,
  employeeId,
  onSaved,
  onDirtyChange,
}: {
  request: ProfileRequest;
  userId?: number;
  employeeId?: number;
  onSaved?: () => void;
  onDirtyChange?: (dirty: boolean) => void;
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
  useEffect(() => {
    let active = true;
    setProfile(undefined);
    setError("");
    setEditing(false);
    request(path)
      .then((result) => {
        if (active) {
          setProfile(result);
          setDraft(result.values);
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
  useEffect(() => {
    onDirtyChange?.(!!dirty);
  }, [dirty, onDirtyChange]);
  useEffect(() => {
    if (!dirty) return;
    const protect = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener("beforeunload", protect);
    return () => window.removeEventListener("beforeunload", protect);
  }, [dirty]);
  const cancel = () => {
    if (dirty && !window.confirm("Discard unsaved profile changes?")) return;
    if (profile) setDraft(profile.values);
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
      setDraft(result.profile.values);
      setEditing(false);
      setMessage(result.message);
      onSaved?.();
    } catch (error) {
      setError(errorText(error));
    } finally {
      setBusy(false);
    }
  };
  if (!profile)
    return (
      <section className="up-root">
        {error ? (
          <div className="up-error" role="alert">
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
            <h1>{profile.displayName || "My profile"}</h1>
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
            <label className="up-button up-photo-control">
              Change photo
              <input
                type="file"
                accept="image/png,image/jpeg"
                aria-label="Upload profile photo"
                disabled={busy || !!dirty}
                onChange={async (event) => {
                  const file = event.target.files?.[0];
                  event.target.value = "";
                  if (!file) return;
                  if (file.size > 3 * 1024 * 1024) {
                    setError("Profile photos must be 3 MB or smaller");
                    return;
                  }
                  const body = new FormData();
                  body.append("file", file);
                  setBusy(true);
                  setError("");
                  try {
                    const result = await request(path + "/photo", {
                      method: "POST",
                      body,
                    });
                    setProfile(result);
                    setDraft(result.values);
                    setPhotoFailed(false);
                    setMessage(
                      "Profile photo updated across connected modules.",
                    );
                    onSaved?.();
                  } catch (error) {
                    setError(errorText(error));
                  } finally {
                    setBusy(false);
                  }
                }}
              />
            </label>
          )}
          {profile.canManage && !editing && (
            <button
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
        </div>
      </header>
      <div className="up-summary">
        <div>
          <strong>{profile.completeness}%</strong>
          <span>Profile complete</span>
        </div>
        <progress
          max={100}
          value={profile.completeness}
          aria-label="Profile completeness"
        />
        <p>
          {profile.missingFields.length
            ? "To complete: " +
              profile.missingFields.map((key) => labels[key] || key).join(", ")
            : "Your main profile details are complete."}
        </p>
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
      {error && (
        <div className="up-error" role="alert">
          {error}
          <button
            type="button"
            onClick={() => {
              if (
                !dirty ||
                window.confirm(
                  "Discard this draft and reload the latest profile?",
                )
              )
                setReload((v) => v + 1);
            }}
          >
            Reload latest profile
          </button>
        </div>
      )}
      <nav className="up-tabs" aria-label="Profile sections">
        {tabs.map((name) => (
          <button
            key={name}
            type="button"
            aria-pressed={tab === name}
            className={tab === name ? "active" : ""}
            onClick={() => setTab(name)}
          >
            {name}
          </button>
        ))}
      </nav>
      <form onSubmit={save}>
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
                      {draft.phone_number_country_code || ""}{" "}
                      {text(draft.phone_number)}
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
              <h2>Changes awaiting HR review</h2>
              {profile.pendingRequests.map((change) => (
                <article className="up-pending" key={change.id}>
                  <h3>
                    Request #{change.id} · {change.status}
                  </h3>
                  <p>{change.reason}</p>
                  <dl>
                    {Object.entries(change.values).map(([key, value]) => (
                      <div key={key}>
                        <dt>{labels[key] || key}</dt>
                        <dd>
                          {typeof value === "object" && value !== null
                            ? JSON.stringify(value)
                            : text(value)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                  {profile.canReview && (
                    <div className="up-actions">
                      {["approve", "reject"].map((action) => (
                        <button
                          key={action}
                          className="up-button"
                          type="button"
                          disabled={busy}
                          onClick={async () => {
                            const remarks = window.prompt(
                              `${action === "approve" ? "Approve" : "Reject"} profile changes: review remarks`,
                            );
                            if (remarks === null) return;
                            setBusy(true);
                            try {
                              await request(
                                `/hrms/profile-change-requests/${change.id}/${action}`,
                                {
                                  method: "POST",
                                  body: { remarks, applyChanges: true },
                                },
                              );
                              setReload((v) => v + 1);
                              onSaved?.();
                            } catch (error) {
                              setError(errorText(error));
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
      </form>
      {preview && (
        <ConnectDialog
          preview={preview}
          busy={busy}
          close={() => setPreview(undefined)}
          confirm={async (employeeId) => {
            setBusy(true);
            try {
              const result = await request(
                `/profiles/users/${profile.userId}/connect-email`,
                { method: "POST", body: { employeeId } },
              );
              setProfile(result);
              setDraft(result.values);
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
  const [result, setResult] = useState<{ items: Values[]; total: number }>({
    items: [],
    total: 0,
  });
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number>();
  const [profileDirty, setProfileDirty] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      setLoading(true);
      request(
        `/profiles/directory?search=${encodeURIComponent(search)}&page=${page}`,
      )
        .then((data) => {
          if (active) {
            setResult(data);
            setError("");
          }
        })
        .catch((error) => {
          if (active) setError(errorText(error));
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }, 250);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [request, search, page]);
  return (
    <div className="up-root">
      <header className="up-header">
        <div>
          <div className="up-kicker">PEOPLE</div>
          <h1>Profile management</h1>
          <p>Employees, interns and user accounts in your permitted scope.</p>
        </div>
        <label className="up-field">
          Find a profile
          <input
            type="search"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Name, email or employee code"
          />
        </label>
      </header>
      {error && (
        <div role="alert" className="up-error">
          {error}
        </div>
      )}
      {loading ? (
        <p role="status">Loading profiles…</p>
      ) : (
        <div className="up-directory">
          {result.items.map((item) => (
            <button
              key={item.userId}
              onClick={() => {
                if (selected === item.userId) return;
                if (
                  profileDirty &&
                  !window.confirm("Discard unsaved profile changes?")
                )
                  return;
                setProfileDirty(false);
                setSelected(item.userId);
              }}
              aria-pressed={selected === item.userId}
            >
              <span>
                <strong>{item.displayName}</strong>
                <small>{item.email}</small>
              </span>
              <span>{item.employeeCode || "Account only"}</span>
              <span>
                {item.kind} · {item.active ? "Active" : "Inactive"}
              </span>
            </button>
          ))}
          {!result.items.length && <p>No profiles match your search.</p>}
        </div>
      )}
      <div className="up-actions up-pagination">
        <span>{result.total} profiles</span>
        <button
          className="up-button"
          disabled={page <= 1}
          onClick={() => setPage((v) => v - 1)}
        >
          Previous
        </button>
        <span>Page {page}</span>
        <button
          className="up-button"
          disabled={page * 30 >= result.total}
          onClick={() => setPage((v) => v + 1)}
        >
          Next
        </button>
      </div>
      {selected && (
        <UnifiedProfile
          key={selected}
          request={request}
          userId={selected}
          onDirtyChange={setProfileDirty}
        />
      )}
    </div>
  );
}
