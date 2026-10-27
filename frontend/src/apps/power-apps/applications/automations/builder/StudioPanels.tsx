import { useMemo, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  CircleAlert,
  Clock3,
  Play,
  ShieldCheck,
  X,
} from "lucide-react";
import { compareVersions } from "./graph";
import type {
  PreviewResult,
  ValidationResult,
  VersionSnapshot,
  WorkflowDocument,
  WorkflowSettings,
} from "./types";
export function ValidationPanel({
  result,
  onClose,
  onSelect,
}: {
  result: ValidationResult;
  onClose: () => void;
  onSelect: (id: string) => void;
}) {
  const errors = result.issues.filter((i) => i.severity === "error");
  return (
    <aside className="as-aux-panel" aria-label="Workflow validation">
      <header>
        <ShieldCheck size={19} />
        <h2>Workflow validation</h2>
        <button aria-label="Close validation" onClick={onClose}>
          <X size={17} />
        </button>
      </header>
      <div
        className={`as-validation-summary ${errors.length ? "has-errors" : ""}`}
      >
        {errors.length ? <CircleAlert size={22} /> : <CheckCircle2 size={22} />}
        <strong>
          {errors.length
            ? `${errors.length} things to resolve`
            : "Structure is valid"}
        </strong>
        <p>
          {result.node_count} nodes / {result.edge_count} connections
        </p>
      </div>
      <p className="as-info-banner">
        All node runtimes remain unavailable. A valid graph cannot publish or
        execute in Phase 2.
      </p>
      <div className="as-aux-scroll">
        {errors.map((issue, index) => (
          <button
            className="as-validation-issue"
            key={index}
            onClick={() => issue.node_id && onSelect(issue.node_id)}
          >
            <CircleAlert size={15} />
            <span>
              <strong>{issue.message}</strong>
              <small>
                {issue.node_id || "Workflow"}
                {issue.field ? ` / ${issue.field}` : ""}
              </small>
            </span>
            <ArrowRight size={14} />
          </button>
        ))}
        {!errors.length && (
          <p className="as-config-note">
            The editor found no structural errors. Connections, required
            settings, expressions and reachable nodes were checked.
          </p>
        )}
      </div>
    </aside>
  );
}
export function PreviewPanel({
  result,
  input,
  setInput,
  busy,
  error,
  onRun,
  onClose,
  onInspect,
}: {
  result?: PreviewResult;
  input: string;
  setInput: (value: string) => void;
  busy: boolean;
  error: string;
  onRun: () => void;
  onClose: () => void;
  onInspect: (id: string) => void;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected =
    result?.timeline.find((e) => e.node_id === selectedId) ||
    result?.timeline[0];
  return (
    <section className="as-preview" aria-label="Design-time testing">
      <header>
        <div>
          <Play size={16} />
          <h2>Design-time test</h2>
          <span>No live integrations</span>
        </div>
        <button aria-label="Close testing panel" onClick={onClose}>
          <X size={17} />
        </button>
      </header>
      <div className="as-preview-body">
        <div className="as-test-input">
          <label htmlFor="test-input">Test input / JSON</label>
          <textarea
            id="test-input"
            spellCheck={false}
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <div>
            <button
              onClick={() =>
                setInput(
                  JSON.stringify(
                    {
                      record: {
                        id: "example-100",
                        status: "Open",
                        title: "Design-time sample",
                        priority: "High",
                      },
                    },
                    null,
                    2,
                  ),
                )
              }
            >
              Insert labeled sample data
            </button>
            <button
              className="as-button-primary"
              disabled={busy}
              onClick={onRun}
            >
              <Play size={13} />
              {busy ? "Validating..." : "Preview locally"}
            </button>
          </div>
          <p>
            Pure nodes only. No emails, external requests, task changes, waits
            or AI calls.
          </p>
          {error && (
            <p role="alert" className="as-field-error">
              {error}
            </p>
          )}
        </div>
        <div className="as-preview-timeline">
          <h3>Preview timeline</h3>
          {result?.timeline.length ? (
            result.timeline.map((entry, index) => (
              <button
                key={entry.node_id}
                className={
                  selected?.node_id === entry.node_id ? "selected" : ""
                }
                onClick={() => {
                  setSelectedId(entry.node_id);
                  onInspect(entry.node_id);
                }}
              >
                <span>{index + 1}</span>
                <span>
                  <strong>{entry.label}</strong>
                  <small>
                    {entry.status === "previewed"
                      ? "Local preview only"
                      : entry.status.replace(/_/g, " ")}
                  </small>
                </span>
                {entry.status === "error" ? (
                  <CircleAlert size={14} />
                ) : (
                  <Clock3 size={14} />
                )}
              </button>
            ))
          ) : (
            <p className="as-config-note">
              {result && !result.validation.valid
                ? "Resolve validation errors before previewing."
                : "Run a local preview to inspect deterministic transformations. No execution history will be created."}
            </p>
          )}
        </div>
        <div className="as-preview-inspect">
          <h3>Node input / output</h3>
          {selected ? (
            <>
              <strong>{selected.label}</strong>
              {selected.error && (
                <p className="as-field-error">{selected.error}</p>
              )}
              <details open>
                <summary>Resolved inputs</summary>
                <pre>{JSON.stringify(selected.input, null, 2)}</pre>
              </details>
              <details open>
                <summary>Local output</summary>
                <pre>{JSON.stringify(selected.output, null, 2)}</pre>
              </details>
            </>
          ) : (
            <p className="as-config-note">
              Choose a preview step to inspect it.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
export function VersionsPanel({
  versions,
  current,
  readOnly,
  onRestore,
  onClose,
}: {
  versions: VersionSnapshot[];
  current: WorkflowDocument;
  readOnly: boolean;
  onRestore?: (version: number) => Promise<void>;
  onClose: () => void;
}) {
  const [left, setLeft] = useState(
      versions[1]?.version || versions[0]?.version || 0,
    ),
    [right, setRight] = useState(versions[0]?.version || 0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const a = versions.find((v) => v.version === left),
    b = versions.find((v) => v.version === right);
  const diff = useMemo(
    () => (a && b ? compareVersions(a.snapshot, b.snapshot) : null),
    [a, b],
  );
  return (
    <aside className="as-aux-panel" aria-label="Version history">
      <header>
        <Clock3 size={19} />
        <h2>Version history</h2>
        <button aria-label="Close version history" onClick={onClose}>
          <X size={17} />
        </button>
      </header>
      <div className="as-aux-scroll">
        <p className="as-config-note">
          Saved snapshots are preserved. Restoring creates a separate draft and
          leaves this automation unchanged. Showing up to 100 recent snapshots.
        </p>
        <div className="as-version-comparison">
          <label>
            Compare version
            <select
              aria-label="Compare version"
              value={left}
              onChange={(e) => setLeft(Number(e.target.value))}
            >
              {versions.map((v) => (
                <option value={v.version} key={v.id}>
                  Version {v.version}
                </option>
              ))}
            </select>
          </label>
          <label>
            With version
            <select
              aria-label="With version"
              value={right}
              onChange={(e) => setRight(Number(e.target.value))}
            >
              {versions.map((v) => (
                <option value={v.version} key={v.id}>
                  Version {v.version}
                </option>
              ))}
            </select>
          </label>
        </div>
        {diff && (
          <div className="as-diff">
            <h3>Changes between snapshots</h3>
            <p>
              {diff.added.length} added / {diff.removed.length} removed /{" "}
              {diff.changed.length} changed nodes
            </p>
            {diff.added.map((n, i) => (
              <p key={`a${i}`} className="added">
                + {n}
              </p>
            ))}
            {diff.removed.map((n, i) => (
              <p key={`r${i}`} className="removed">
                - {n}
              </p>
            ))}
            {diff.changed.map((n, i) => (
              <p key={`c${i}`}>~ {n}</p>
            ))}
            {diff.connectionsChanged && <p>Connections changed</p>}
            {diff.settingsChanged && <p>Workflow settings changed</p>}
            {diff.organizationChanged && (
              <p>
                Groups, notes, tags, variables or canvas preferences changed
              </p>
            )}
            {diff.nameChanged && <p>Automation name changed</p>}
            {diff.descriptionChanged && <p>Description changed</p>}
          </div>
        )}
        {error && (
          <p className="as-field-error" role="alert">
            {error}
          </p>
        )}
        {versions.map((v) => (
          <article className="as-version-item" key={v.id}>
            <div>
              <strong>Version {v.version}</strong>
              <time>{new Date(v.created_at).toLocaleString()}</time>
            </div>
            <p>{v.snapshot.name}</p>
            <button
              disabled={readOnly || busy || !onRestore}
              onClick={async () => {
                if (
                  !window.confirm(
                    `Restore version ${v.version} as a separate draft?`,
                  )
                )
                  return;
                setBusy(true);
                try {
                  await onRestore?.(v.version);
                } catch {
                  setError(
                    "Could not restore this version. Check access and retry.",
                  );
                } finally {
                  setBusy(false);
                }
              }}
            >
              Restore as new draft
            </button>
            <details>
              <summary>View snapshot definition</summary>
              <pre>{JSON.stringify(v.snapshot.definition, null, 2)}</pre>
            </details>
          </article>
        ))}
        {!versions.length && (
          <p className="as-config-note">
            Save your draft to create its first version snapshot.
          </p>
        )}
      </div>
    </aside>
  );
}
export function SettingsPanel({
  metadata,
  settings,
  description,
  readOnly,
  onChange,
  onDescription,
  onClose,
}: {
  metadata?: React.ReactNode;
  settings: WorkflowSettings;
  description: string;
  readOnly: boolean;
  onChange: (value: WorkflowSettings) => void;
  onDescription: (value: string) => void;
  onClose: () => void;
}) {
  return (
    <aside className="as-aux-panel" aria-label="Workflow settings">
      <header>
        <ShieldCheck size={19} />
        <h2>Workflow settings</h2>
        <button aria-label="Close settings" onClick={onClose}>
          <X size={17} />
        </button>
      </header>
      <div className="as-aux-scroll">
        {metadata}
        <p className="as-info-banner">
          Draft settings are saved with this version. They do not enable runtime
          execution.
        </p>
        <label className="as-basic-field">
          Automation description
          <textarea
            aria-label="Automation description"
            readOnly={readOnly}
            maxLength={2000}
            rows={3}
            value={description}
            onChange={(e) => onDescription(e.target.value)}
          />
        </label>
        <label className="as-basic-field">
          Maximum attempts
          <input
            readOnly={readOnly}
            type="number"
            min={1}
            max={10}
            value={settings.max_attempts}
            onChange={(e) =>
              onChange({ ...settings, max_attempts: Number(e.target.value) })
            }
          />
        </label>
        <label className="as-basic-field">
          Retry backoff (seconds)
          <input
            readOnly={readOnly}
            type="number"
            min={1}
            max={86400}
            value={settings.retry_backoff_seconds}
            onChange={(e) =>
              onChange({
                ...settings,
                retry_backoff_seconds: Number(e.target.value),
              })
            }
          />
        </label>
        <label className="as-basic-field">
          Idempotency source
          <select
            disabled={readOnly}
            value={settings.idempotency}
            onChange={(e) =>
              onChange({
                ...settings,
                idempotency: e.target.value as "event_id" | "request_id",
              })
            }
          >
            <option value="request_id">Request ID</option>
            <option value="event_id">Event ID</option>
          </select>
        </label>
        <label className="as-basic-field">
          Timezone
          <input
            readOnly={readOnly}
            value={settings.timezone}
            maxLength={80}
            onChange={(e) =>
              onChange({ ...settings, timezone: e.target.value })
            }
          />
        </label>
        <label className="as-basic-field">
          History retention (days)
          <input
            readOnly={readOnly}
            type="number"
            min={1}
            max={365}
            value={settings.retention_days}
            onChange={(e) =>
              onChange({ ...settings, retention_days: Number(e.target.value) })
            }
          />
        </label>
        <p className="as-config-note">
          Execution identity: resource owner. The future worker must recheck the
          owner's active permissions and environment access on every run.
        </p>
      </div>
    </aside>
  );
}
