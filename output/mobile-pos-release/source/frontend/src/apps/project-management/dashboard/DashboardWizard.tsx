import { RichTextField, RichTextContent, richTextPlainText } from "@/components/rich-text/LazyRichText";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BarChart3, Check, Layers3 } from "lucide-react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Panel, Choice, FilterFields } from "./Panels";
import {
  copy,
  emptyFilters,
  type Catalog,
  type Configuration,
  type Dashboard,
  type Scope,
} from "./model";
export default function DashboardWizard({
  catalog,
  workspaces,
  onClose,
  onCreate,
}: {
  catalog: Catalog;
  workspaces: { id: number; name: string; role: string }[];
  onClose: () => void;
  onCreate: (payload: Record<string, unknown>) => Promise<void>;
}) {
  const [step, setStep] = useState(1),
    [name, setName] = useState(""),
    [description, setDescription] = useState(""),
    [workspace, setWorkspace] = useState(
      String(workspaces.find((w) => w.role !== "Guest")?.id || ""),
    ),
    [visibility, setVisibility] = useState("private"),
    [category, setCategory] = useState(""),
    [icon, setIcon] = useState("dashboard"),
    [accent, setAccent] = useState("#6d3df5"),
    [template, setTemplate] = useState("project_overview"),
    [config, setConfig] = useState<Configuration>(() => {
      const value = copy(catalog.templates[0].configuration);
      value.filters = emptyFilters();
      return value;
    }),
    [pending, setPending] = useState(false),
    [error, setError] = useState(""),
    [shares, setShares] = useState<
      { user_id: number; role: "viewer" | "editor" }[]
    >([]);
  const members = useQuery({
    queryKey: ["dashboard-create-members", workspace],
    enabled: !!workspace,
    queryFn: async () =>
      (await api.get(`/project-management/workspaces/${workspace}/members`))
        .data as { user_id: number; email: string; role: string }[],
  });
  const projects = useQuery({
    queryKey: ["dashboard-create-projects"],
    queryFn: async () =>
      (await api.get("/project-management/projects")).data as {
        id: number;
        name: string;
        workspace_id: number;
        status: string;
      }[],
  });
  const scope: Scope = {
    projects: (projects.data || []).filter(
      (p) => p.workspace_id === Number(workspace),
    ),
    people: (members.data || []).map((m) => ({ id: m.user_id, name: m.email })),
    sprints: [],
    teams: [],
    tags: [],
    custom_fields: [],
  };
  const create = async () => {
    setPending(true);
    setError("");
    try {
      await onCreate({
        name: name.trim(),
        description,
        workspace_id: Number(workspace),
        visibility,
        category,
        icon,
        accent,
        shared_users: shares,
        configuration: config,
      });
    } catch (e: any) {
      setError(
        typeof e?.response?.data?.detail === "string"
          ? e.response.data.detail
          : "Dashboard could not be created. Check the name, workspace and filter configuration.",
      );
    } finally {
      setPending(false);
    }
  };
  return (
    <Panel
      open
      wide
      title="New dashboard"
      description="Start with a template or a blank canvas. Every widget queries your authorized records."
      onClose={() => {
        if (!pending) onClose();
      }}
    >
      <ol className="db-wizard-steps">
        {["Basics", "Template", "Data scope", "Create"].map((label, i) => (
          <li key={label} data-active={step === i + 1}>
            <span>{step > i + 1 ? <Check size={13} /> : i + 1}</span>
            {label}
          </li>
        ))}
      </ol>
      {error && (
        <p className="db-error" role="alert">
          {error}
        </p>
      )}
      {step === 1 && (
        <div className="db-wizard-fields">
          <label className="db-field">
            <span>Dashboard name *</span>
            <input
              autoFocus
              maxLength={120}
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Product delivery overview"
            />
          </label>
          <label className="db-field">
            <span>Description</span>
            <RichTextField data-legacy-format="markdown"
              maxLength={2000}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What should your team learn from this dashboard?"
            />
          </label>
          <div className="db-field-pair">
            <Choice
              label="Dashboard icon"
              value={icon}
              onChange={setIcon}
              options={[
                "dashboard",
                "projects",
                "team",
                "chart",
                "calendar",
                "target",
                "briefcase",
              ].map((v) => ({ value: v, label: v }))}
            />
            <label className="db-field">
              <span>Accent color</span>
              <input
                type="color"
                value={accent}
                onChange={(e) => setAccent(e.target.value)}
              />
            </label>
          </div>
          <Choice
            label="Workspace"
            value={workspace}
            onChange={(v) => {
              setWorkspace(v);
              setShares([]);
              setConfig((c) => ({ ...c, filters: emptyFilters() }));
            }}
            options={workspaces
              .filter((w) => w.role !== "Guest")
              .map((w) => ({ value: String(w.id), label: w.name }))}
          />
          <label className="db-field">
            <span>Folder or category</span>
            <input
              maxLength={80}
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="e.g. Leadership"
            />
          </label>
          <Choice
            label="Visibility"
            value={visibility}
            onChange={setVisibility}
            options={[
              { value: "private", label: "Private — only you" },
              { value: "selected", label: "Selected workspace members" },
              { value: "workspace", label: "Workspace members" },
              {
                value: "organization",
                label: "Organization members — organization account required",
              },
            ]}
          />
          {visibility === "selected" && (
            <div className="db-share-members">
              {members.isError && (
                <p role="alert">
                  Members could not load. Choose the workspace again to retry.
                </p>
              )}
              {members.data?.map((m) => (
                <div key={m.user_id}>
                  <label>
                    <input
                      type="checkbox"
                      checked={shares.some((s) => s.user_id === m.user_id)}
                      onChange={(e) =>
                        setShares((v) =>
                          e.target.checked
                            ? [...v, { user_id: m.user_id, role: "viewer" }]
                            : v.filter((s) => s.user_id !== m.user_id),
                        )
                      }
                    />
                    {m.email}
                  </label>
                  {shares.some((s) => s.user_id === m.user_id) && (
                    <Choice
                      label={`Access for ${m.email}`}
                      value={shares.find((s) => s.user_id === m.user_id)!.role}
                      onChange={(role) =>
                        setShares((v) =>
                          v.map((s) =>
                            s.user_id === m.user_id
                              ? { ...s, role: role as "viewer" | "editor" }
                              : s,
                          ),
                        )
                      }
                      options={[
                        { value: "viewer", label: "Viewer" },
                        ...(m.role !== "Guest"
                          ? [{ value: "editor", label: "Editor" }]
                          : []),
                      ]}
                    />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      {step === 2 && (
        <div className="db-template-grid">
          {catalog.templates.map((t) => (
            <button
              key={t.id}
              className={template === t.id ? "selected" : ""}
              onClick={() => {
                setTemplate(t.id);
                setConfig({
                  ...copy(t.configuration),
                  filters: config.filters,
                });
              }}
            >
              <span className="db-template-symbol">
                <BarChart3 size={23} />
                {template === t.id && <Check size={15} />}
              </span>
              <strong>{t.name}</strong>
              <small>
                {t.configuration.widgets.length} widgets · real workspace data
              </small>
              <span className="db-template-lines">
                {t.configuration.widgets.slice(0, 5).map((w) => (
                  <i key={w.id} style={{ width: `${(w.w / 12) * 100}%` }} />
                ))}
              </span>
            </button>
          ))}
        </div>
      )}
      {step === 3 && (
        <>
          <p className="db-info">
            Only records you can access will appear. Teams, sprints, tags and
            custom fields can be refined in the full editor after creation.
          </p>
          <FilterFields
            value={config.filters}
            onChange={(filters) => setConfig({ ...config, filters })}
            scope={scope}
          />
        </>
      )}
      {step === 4 && (
        <div className="db-create-review">
          <Layers3 size={42} />
          <h3>{name}</h3>
          <p>{description || "Ready to customize your dashboard."}</p>
          <dl>
            <div>
              <dt>Template</dt>
              <dd>{catalog.templates.find((t) => t.id === template)?.name}</dd>
            </div>
            <div>
              <dt>Workspace</dt>
              <dd>
                {workspaces.find((w) => String(w.id) === workspace)?.name}
              </dd>
            </div>
            <div>
              <dt>Visibility</dt>
              <dd>{visibility}</dd>
            </div>
            <div>
              <dt>Widgets</dt>
              <dd>{config.widgets.length}</dd>
            </div>
          </dl>
          <small>
            Dashboard permissions do not grant access to additional project
            records.
          </small>
        </div>
      )}
      <footer className="db-panel-actions">
        <Button
          variant="outline"
          disabled={pending}
          onClick={() => (step > 1 ? setStep((s) => s - 1) : onClose())}
        >
          {step > 1 ? "Back" : "Cancel"}
        </Button>
        {step < 4 ? (
          <Button
            disabled={pending || (step === 1 && (!name.trim() || !workspace))}
            onClick={() => setStep((s) => s + 1)}
          >
            Continue
            <ArrowRight size={15} />
          </Button>
        ) : (
          <Button disabled={pending} onClick={() => void create()}>
            {pending ? "Creating…" : "Create dashboard"}
          </Button>
        )}
      </footer>
    </Panel>
  );
}
