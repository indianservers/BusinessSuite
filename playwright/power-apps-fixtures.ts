import type { Page } from "../frontend/node_modules/playwright/test";
import catalogFile from "../backend/app/apps/power_apps/node_catalog.json";
import templateFile from "../backend/app/apps/power_apps/automation_templates.json";
import { validateGraph } from "../frontend/src/apps/power-apps/applications/automations/builder/graph";
import type {
  NodeDefinition,
  WorkflowGraph,
} from "../frontend/src/apps/power-apps/applications/automations/builder/types";
export const nodeCatalog = catalogFile.nodes as NodeDefinition[];
export const permissions = [
  "view",
  "create",
  "edit",
  "delete",
  "publish",
  "execute",
  "manage_credentials",
  "manage_environment",
  "activity_view",
].map((p) => "power_apps_" + p);
export const ids = [
  "automations",
  "approvals",
  "forms",
  "tables",
  "app-builder",
  "notifications",
  "search",
  "dashboards",
  "connectors",
  "documents",
  "ai-agents",
  "activity",
];
export const names = [
  "Automations",
  "Approvals",
  "Forms",
  "Tables & Databases",
  "App Builder",
  "Notifications",
  "Universal Search",
  "Dashboards & Reports",
  "Connectors",
  "Documents & Templates",
  "AI Agents",
  "Activity & Audit Center",
];
const icons = [
  "Workflow",
  "BadgeCheck",
  "ClipboardList",
  "Database",
  "PanelsTopLeft",
  "BellRing",
  "Search",
  "ChartNoAxesCombined",
  "Plug",
  "Files",
  "Bot",
  "History",
];
export function makeGraph(count = 4): WorkflowGraph {
  const nodes = Array.from({ length: count }, (_, i) => ({
    id: i === 0 ? "trigger" : `step_${i}`,
    type: i === 0 ? "manual_trigger" : "set_variable",
    label: i === 0 ? "Manual Trigger" : `Transform ${i}`,
    description: "",
    position: { x: 80 + i * 320, y: 240 },
    config: i === 0 ? {} : { value: `Value ${i}` },
    credential_reference: null,
    advanced: {
      retry_attempts: 3,
      error_strategy: "stop" as const,
      timeout_seconds: 60,
    },
  }));
  return {
    schema_version: 2,
    catalog_version: 1,
    nodes,
    edges: nodes
      .slice(1)
      .map((n, i) => ({
        id: `edge_${i}`,
        source: nodes[i].id,
        target: n.id,
        source_port: "out",
        target_port: "in",
        label: "",
      })),
    groups: [],
    viewport: { x: 0, y: 0, zoom: 1 },
    settings: {
      max_attempts: 3,
      retry_backoff_seconds: 60,
      idempotency: "request_id",
      execution_identity: "owner",
      timezone: "Asia/Kolkata",
      retention_days: 30,
    },
  };
}
export function fixtureRow(id = 41, graph = makeGraph()) {
  return {
    id,
    name: "Customer onboarding",
    description: "Explicit browser test fixture",
    definition: graph,
    environment: "development",
    application_id: "automations",
    owner_user_id: 1,
    status: "draft",
    version: 1,
    archived_at: null,
    updated_at: new Date().toISOString(),
  };
}
export async function setupPowerApps(
  page: Page,
  options: {
    allowed?: boolean;
    readOnly?: boolean;
    records?: ReturnType<typeof fixtureRow>[];
  } = {},
) {
  const effective = options.readOnly
    ? ["power_apps_view", "power_apps_activity_view"]
    : permissions;
  const access = {
    managed: true,
    companyId: 1,
    grants: {
      power_apps: {
        enabled: options.allowed !== false,
        role: options.readOnly ? "viewer" : "admin",
        scope: "organization",
        permissions: effective,
        actions: ["view", "create", "edit", "delete"],
      },
    },
    modules: [{ key: "power_apps", route: "/power-apps", label: "Power Apps" }],
    isAccessAdmin: false,
    isGlobalAdmin: false,
    memberships: [1],
  };
  const user = {
    id: 1,
    email: "builder@example.com",
    name: "Alex Builder",
    role: "admin",
    primary_role: "admin",
    is_superuser: false,
    access,
  };
  await page.addInitScript(
    ({ user }) => {
      window.__AI_HRMS_CONFIG__ = { apiBaseUrl: "/api/v1" };
      const token =
        btoa(JSON.stringify({ alg: "HS256" })) +
        "." +
        btoa(
          JSON.stringify({
            sub: "1",
            exp: Math.floor(Date.now() / 1000) + 7200,
          }),
        ) +
        ".test";
      if (!sessionStorage.getItem("hrms-auth"))
        sessionStorage.setItem(
          "hrms-auth",
          JSON.stringify({
            state: {
              accessToken: token,
              refreshToken: "test-refresh",
              user,
              isAuthenticated: true,
            },
            version: 0,
          }),
        );
    },
    { user },
  );
  let records: any[] = structuredClone(options.records || []),
    nextId = Math.max(40, ...records.map((r) => r.id)) + 1,
    nextSaveFailure = 0;
  const snapshots: Record<number, any[]> = {},
    writes: { path: string; method: string; body: any }[] = [];
  const snapshot = (row: any) => {
    (snapshots[row.id] ||= []).unshift({
      id: row.id * 1000 + row.version,
      version: row.version,
      created_at: new Date().toISOString(),
      created_by: 1,
      snapshot: structuredClone({
        name: row.name,
        description: row.description,
        definition: row.definition,
        status: "draft",
      }),
    });
  };
  records.forEach(snapshot);
  await page.route("**/api/v1/**", async (route) => {
    const req = route.request(),
      url = new URL(req.url()),
      path = url.pathname,
      method = req.method(),
      environment = url.searchParams.get("environment") || "development";
    const body =
      method === "GET" || method === "DELETE" ? {} : req.postDataJSON();
    if (path.endsWith("/access/me")) return route.fulfill({ json: access });
    if (path.endsWith("/business-os/modules"))
      return route.fulfill({
        json: {
          enabled_modules: [
            "hrms",
            "crm",
            "project_management",
            "srm",
            "fam",
            "power_apps",
          ],
        },
      });
    if (!path.includes("/power-apps/")) return route.fulfill({ json: {} });
    if (path.endsWith("/catalog"))
      return route.fulfill({
        json: {
          applications: ids.map((id, i) => ({
            id,
            name: names[i],
            icon: icons[i],
            route: "/power-apps/" + id,
            description: "A focused workspace for your business.",
            status: i === 0 ? "drafts" : i === 11 ? "available" : "planned",
            required_permissions: ["power_apps_view"],
            environments: ["development", "testing", "production"],
            feature_flags: [],
          })),
          permissions: effective,
          execution_enabled: false,
          templates: [],
        },
      });
    if (path.endsWith("/node-catalog"))
      return route.fulfill({ json: catalogFile });
    if (path.endsWith("/templates"))
      return route.fulfill({ json: { items: templateFile.templates } });
    if (path.endsWith("/environments"))
      return route.fulfill({
        json: {
          items: [
            { key: "development", enabled: true },
            { key: "testing", enabled: true },
          ],
        },
      });
    if (path.endsWith("/overview"))
      return route.fulfill({
        json: {
          counts: {
            total_apps: 0,
            active_automations: 0,
            pending_approvals: 0,
            form_submissions: 0,
            workflow_executions: 0,
            failed_runs: 0,
          },
          recent: records
            .filter((r) => r.environment === environment && !r.archived_at)
            .slice(0, 8),
          unsupported_metrics: [
            "active_automations",
            "pending_approvals",
            "form_submissions",
          ],
        },
      });
    if (path.endsWith("/activity"))
      return route.fulfill({ json: { items: [] } });
    if (path.endsWith("/validate"))
      return route.fulfill({
        json: validateGraph(body.definition, nodeCatalog),
      });
    if (path.endsWith("/preview")) {
      const validation = validateGraph(body.definition, nodeCatalog);
      return route.fulfill({
        json: {
          design_time_only: true,
          integration_execution: false,
          validation,
          timeline: validation.valid
            ? body.definition.nodes.map((n: any) => ({
                node_id: n.id,
                label: n.label,
                status: nodeCatalog.find((d) => d.id === n.type)
                  ?.preview_supported
                  ? "previewed"
                  : "not_executable",
                input: n.config,
                output: null,
                error: null,
              }))
            : [],
        },
      });
    }
    const match = /automations\/(\d+)(?:\/(.*))?$/.exec(path),
      id = match ? Number(match[1]) : undefined,
      action = match?.[2],
      row = records.find((r) => r.id === id && r.environment === environment);
    if (method !== "GET") writes.push({ path, method, body });
    if (method === "GET" && action === "versions")
      return route.fulfill({ json: { items: snapshots[id!] || [] } });
    if (method === "GET" && id)
      return row
        ? route.fulfill({ json: row })
        : route.fulfill({ status: 404, json: { detail: "Draft not found" } });
    if (method === "GET" && path.endsWith("/automations")) {
      const view = url.searchParams.get("view"),
        search = (url.searchParams.get("search") || "").toLowerCase(),
        filtered = records.filter(
          (r) =>
            r.environment === environment &&
            (view === "disabled" ? r.archived_at : !r.archived_at) &&
            (view !== "shared" || r.owner_user_id !== 1) &&
            view !== "published" &&
            r.name.toLowerCase().includes(search),
        ),
        offset = Number(url.searchParams.get("offset") || 0);
      return route.fulfill({
        json: {
          items: filtered.slice(offset, offset + 50),
          total: filtered.length,
        },
      });
    }
    if (method === "PUT" && nextSaveFailure) {
      const status = nextSaveFailure;
      nextSaveFailure = 0;
      return route.fulfill({
        status,
        json: {
          detail:
            status === 409
              ? "Draft changed since you opened it; reload before saving"
              : "Connection unavailable",
        },
      });
    }
    if (method === "DELETE") {
      records = records.filter((r) => r.id !== id);
      return route.fulfill({ status: 204 });
    }
    if (action === "archive" || action === "unarchive") {
      if (row) {
        row.archived_at =
          action === "archive" ? new Date().toISOString() : null;
        row.version++;
        snapshot(row);
      }
      return route.fulfill({ json: row });
    }
    if (action === "duplicate" || action === "restore") {
      const original =
        action === "restore"
          ? snapshots[id!]?.find((r) => r.version === body.version)?.snapshot
          : row;
      const copied = {
        ...structuredClone(original),
        id: nextId++,
        name:
          original.name + (action === "restore" ? " (restored)" : " (copy)"),
        environment,
        owner_user_id: 1,
        archived_at: null,
        version: 1,
        updated_at: new Date().toISOString(),
      };
      records.push(copied);
      snapshot(copied);
      return route.fulfill({ status: 201, json: copied });
    }
    if (path.includes("/templates/") && path.endsWith("/use")) {
      const template = templateFile.templates.find((t) =>
          path.includes("/" + t.id + "/"),
        )!,
        created = {
          ...fixtureRow(nextId++, template.definition as WorkflowGraph),
          environment,
          name: template.name,
        };
      records.push(created);
      snapshot(created);
      return route.fulfill({ status: 201, json: created });
    }
    if (method === "POST" || method === "PUT") {
      if (id && row && row.version !== body.expected_version)
        return route.fulfill({
          status: 409,
          json: {
            detail: "Draft changed since you opened it; reload before saving",
          },
        });
      const record = {
        ...body,
        id: id || nextId++,
        environment,
        owner_user_id: 1,
        application_id: "automations",
        status: "draft",
        archived_at: null,
        version: method === "POST" ? 1 : body.expected_version + 1,
        updated_at: new Date().toISOString(),
      };
      records = [...records.filter((r) => r.id !== record.id), record];
      snapshot(record);
      return route.fulfill({
        status: method === "POST" ? 201 : 200,
        json: record,
      });
    }
    return route.fulfill({ json: {} });
  });
  return {
    writes,
    records: () => records,
    snapshots,
    failNextSave: (status = 409) => {
      nextSaveFailure = status;
    },
    bumpVersion: (id: number) => {
      const r = records.find((r) => r.id === id);
      if (r) {
        r.version++;
        r.name = "Updated by another user";
        snapshot(r);
      }
    },
  };
}
