import { Link } from "react-router-dom";
import { FormEvent, useEffect, useState } from "react";
import { Github, Gitlab, Settings, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { devIntegrationsAPI, projectsAPI } from "../services/api";
import type { PMSDevIntegration, PMSProject } from "../types";

const settings = [
  { label: "AI task operator", href: "/pms/operator", description: "Execute reviewed multi-step task commands through voice or text." },
  { label: "OpenAI / ChatGPT API", href: "/pms/settings/ai/openai", description: "Configure encrypted API credentials, model, usage analytics and logs." },
  { label: "Google Gemini API", href: "/pms/settings/ai/gemini", description: "Configure Gemini credentials, model and API usage." },
  { label: "Anthropic Claude API", href: "/pms/settings/ai/claude", description: "Configure Claude credentials, model and API usage." },
  { label: "Docs", href: "/pms/docs", description: "Project documents, task links, Markdown editing and revision history." },
  { label: "Task Types", href: "/pms/task-types", description: "Configure work types, categories, icons, defaults and practice presets." },
  { label: "Tag Manager", href: "/pms/tags", description: "Search tags, review accessible usage, edit colors and remove unwanted tags." },
  { label: "Plans and capabilities", href: "/pms/plans", description: "Core, Business, Business Plus and Enterprise feature status and remaining work." },
  { label: "Custom Field Manager", href: "/pms/custom-fields", description: "Search, group, create and edit typed fields across your projects." },
  { label: "Direct messages", href: "/pms/messages", description: "Private conversations with workspace collaborators." },
  { label: "Audit logs", href: "/pms/audit-logs", description: "Admin-only user, task, role and request diagnostics." },
  { label: "Teams", href: "/pms/teams", description: "Create named collaborator groups and manage team membership." },
  { label: "Workspace people and invitations", href: "/pms/workspaces", description: "Open People in your workspace to manage members and invitation links." },
  { label: "Task views", href: "/pms/tasks", description: "Save filters and choose visible columns." },
  { label: "Templates and intake", href: "/pms/workspace-tools", description: "Manage saved templates, goals and authenticated intake." },
  { label: "Task automation", href: "/pms/automation", description: "Create and manage workspace automation rules." },
  { label: "Task recovery", href: "/pms/trash", description: "Find and restore deleted tasks." },
];

export default function SettingsPage() {
  const [projects, setProjects] = useState<PMSProject[]>([]);
  const [integrations, setIntegrations] = useState<PMSDevIntegration[]>([]);
  const [provider, setProvider] = useState<"github" | "gitlab">("github");
  const [projectId, setProjectId] = useState("");
  const [repoOwner, setRepoOwner] = useState("");
  const [repoName, setRepoName] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    Promise.all([
      projectsAPI.list().catch(() => []),
      devIntegrationsAPI.list().catch(() => []),
    ]).then(([projectItems, integrationItems]) => {
      setProjects(projectItems);
      setIntegrations(integrationItems);
      if (!projectId && projectItems[0]) setProjectId(String(projectItems[0].id));
    });
  };

  useEffect(load, []);

  const submitIntegration = async (event: FormEvent) => {
    event.preventDefault();
    if (!projectId || !repoOwner.trim() || !repoName.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const item = await devIntegrationsAPI.create({
        provider,
        project_id: Number(projectId),
        repo_owner: repoOwner.trim(),
        repo_name: repoName.trim(),
        access_token: accessToken.trim() || undefined,
        webhook_secret: webhookSecret.trim() || undefined,
        is_active: true,
      });
      setIntegrations((current) => [item, ...current.filter((existing) => existing.id !== item.id)]);
      setRepoOwner("");
      setRepoName("");
      setAccessToken("");
      setWebhookSecret("");
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to save development integration.");
    } finally {
      setSaving(false);
    }
  };

  const deleteIntegration = async (integrationId: number) => {
    await devIntegrationsAPI.delete(integrationId);
    setIntegrations((current) => current.filter((item) => item.id !== integrationId));
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Settings</h1>
        <p className="page-description">Workspace-level preferences, repository mappings, and module configuration.</p>
      </div>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Settings className="h-5 w-5" />KaryaFlow settings</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          {settings.map(item => <Link key={item.href} to={item.href} className="rounded-lg border p-4 hover:bg-muted/40"><strong className="text-sm">{item.label}</strong><p className="mt-1 text-xs text-muted-foreground">{item.description}</p></Link>)}
          <p className="text-sm text-muted-foreground md:col-span-2">Custom fields are configured from task details and apply to the task's project. Workspace-wide preference controls will appear here as their saved behavior is implemented.</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Github className="h-5 w-5" />Development integrations</CardTitle></CardHeader>
        <CardContent className="space-y-5">
          <form className="grid gap-3 lg:grid-cols-6" onSubmit={submitIntegration}>
            <label className="space-y-1 text-sm">
              <span className="font-medium text-muted-foreground">Provider</span>
              <select className="input" value={provider} onChange={(event) => setProvider(event.target.value as "github" | "gitlab")}>
                <option value="github">GitHub</option>
                <option value="gitlab">GitLab</option>
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-medium text-muted-foreground">Project</span>
              <select className="input" value={projectId} onChange={(event) => setProjectId(event.target.value)}>
                {projects.map((project) => <option key={project.id} value={project.id}>{project.project_key} - {project.name}</option>)}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-medium text-muted-foreground">Owner / group</span>
              <Input value={repoOwner} onChange={(event) => setRepoOwner(event.target.value)} placeholder="acme or group/subgroup" />
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-medium text-muted-foreground">Repository</span>
              <Input value={repoName} onChange={(event) => setRepoName(event.target.value)} placeholder="web-app" />
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-medium text-muted-foreground">Access token</span>
              <Input type="password" value={accessToken} onChange={(event) => setAccessToken(event.target.value)} placeholder="Optional" />
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-medium text-muted-foreground">Webhook secret</span>
              <Input type="password" value={webhookSecret} onChange={(event) => setWebhookSecret(event.target.value)} placeholder="Required for webhooks" />
            </label>
            <div className="lg:col-span-6">
              <Button disabled={saving || !projectId}>{saving ? "Saving..." : "Link repository"}</Button>
            </div>
          </form>
          {error ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}

          <div className="space-y-3">
            {integrations.map((item) => (
              <div key={item.id} className="flex flex-col gap-3 rounded-md border p-3 md:flex-row md:items-center md:justify-between">
                <div className="flex items-start gap-3">
                  {item.provider === "github" ? <Github className="mt-1 h-5 w-5" /> : <Gitlab className="mt-1 h-5 w-5" />}
                  <div>
                    <p className="font-semibold">{item.repo_owner}/{item.repo_name}</p>
                    <p className="text-xs text-muted-foreground">{item.project_name || `Project ${item.project_id}`}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Badge variant="outline">{item.provider}</Badge>
                      <Badge variant={item.has_access_token ? "default" : "outline"}>{item.has_access_token ? "Token stored" : "No token"}</Badge>
                      <Badge variant={item.has_webhook_secret ? "default" : "outline"}>{item.has_webhook_secret ? "Webhook secured" : "No webhook secret"}</Badge>
                    </div>
                  </div>
                </div>
                <Button type="button" variant="outline" size="icon" onClick={() => deleteIntegration(item.id)}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
            {!integrations.length ? <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">No repositories linked yet.</p> : null}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
