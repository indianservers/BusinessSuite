import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Layers3, RefreshCw } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { powerApi, errorMessage } from "../../api";
import type { Catalog, Resource } from "../../registry";
import { AutomationBuilder } from "./builder/AutomationBuilder";
import { asVisualGraph, emptyGraph } from "./builder/graph";
import type {
  NodeDefinition,
  VersionSnapshot,
  WorkflowDocument,
} from "./builder/types";
import {
  environmentFromSearch,
  studioApi,
  studioPath,
  authoringServices,
} from "./studioApi";
type Bootstrap = {
  catalog: Catalog;
  nodes: NodeDefinition[];
  row?: Resource;
  initial: WorkflowDocument;
  key: string;
};
export default function AutomationEditorPage() {
  const { resourceId } = useParams();
  const location = useLocation(),
    navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const environment = environmentFromSearch(location.search),
    id = resourceId ? Number(resourceId) : undefined;
  const mode = location.pathname.endsWith("/versions")
    ? "versions"
    : location.pathname.endsWith("/settings")
      ? "settings"
      : null;
  const [bootstrap, setBootstrap] = useState<Bootstrap>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);
  const [retry, setRetry] = useState(0);
  const [workflowTrail, setWorkflowTrail] = useState<
    { id: number; name: string }[]
  >([]);
  const [versions, setVersions] = useState<VersionSnapshot[]>([]);
  const currentRow = useRef<Resource>();
  const currentEnvironment = useRef(environment);
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  useEffect(() => {
    if (
      bootstrap &&
      currentRow.current?.id === id &&
      bootstrap.row?.id === id &&
      currentEnvironment.current === environment
    ) {
      setBusy(false);
      return;
    }
    let live = true;
    setBusy(true);
    setError("");
    (async () => {
      const [catalog, nodes, environments, row] = await Promise.all([
        powerApi.catalog(),
        studioApi.nodes(),
        powerApi.environments(),
        id ? powerApi.read(environment, id) : Promise.resolve(undefined),
      ]);
      if (!environments.some((e) => e.key === environment && e.enabled))
        throw new Error(
          "The selected environment is not enabled for this organization",
        );
      if (!Array.isArray(nodes) || !nodes.length)
        throw new Error("The editor node catalog is unavailable");
      if (!row && !catalog.permissions.includes("power_apps_create"))
        throw new Error("Create permission is required for a new automation");
      if (!live) return;
      currentRow.current = row;
      currentEnvironment.current = environment;
      setBootstrap({
        catalog,
        nodes,
        row,
        initial: row
          ? {
              name: row.name,
              description: row.description,
              definition: asVisualGraph(row.definition, nodes),
            }
          : {
              name: "Untitled automation",
              description: "",
              definition: emptyGraph(),
            },
        key: `${environment}:${id || "new"}:${retry}`,
      });
      setBusy(false);
    })().catch((e) => {
      if (live) {
        setError(
          (e as { response?: unknown }).response
            ? errorMessage(e)
            : (e as Error).message,
        );
        setBusy(false);
      }
    });
    return () => {
      live = false;
    };
  }, [id, environment, retry]);
  useEffect(() => {
    if (mode !== "versions" || !bootstrap?.row?.id) return;
    let live = true;
    studioApi
      .versions(environment, bootstrap.row.id)
      .then((rows) => {
        if (live) setVersions(rows || []);
      })
      .catch((e) => {
        if (live) setError(errorMessage(e));
      });
    return () => {
      live = false;
    };
  }, [mode, environment, bootstrap?.row?.id, bootstrap?.row?.version]);
  const openRow = (row: Resource) => {
    currentRow.current = undefined;
    setBootstrap(undefined);
    navigate(studioPath(`/power-apps/automations/${row.id}/edit`, environment));
  };
  if (busy || !bootstrap)
    return (
      <div className="as-editor-loading">
        <Layers3 size={35} />
        <h1>{busy ? "Opening Automation Studio" : "Studio unavailable"}</h1>
        {error && <p role="alert">{error}</p>}
        {!busy && (
          <button onClick={() => setRetry((v) => v + 1)}>
            <RefreshCw size={15} />
            Retry
          </button>
        )}
        <button
          onClick={() =>
            navigate(studioPath("/power-apps/automations", environment))
          }
        >
          <ArrowLeft size={15} />
          Back to Automations
        </button>
      </div>
    );
  const can = (permission: string) =>
    bootstrap.catalog.permissions.includes(`power_apps_${permission}`);
  return (
    <>
      {bootstrap.row && bootstrap.row.definition.schema_version !== 2 && (
        <p className="as-legacy-notice" role="status">
          Imported schema v1 for review. Original definitions remain in version
          history; review the visual configuration before saving.
        </p>
      )}
      {error && (
        <div className="as-page-error" role="alert">
          {error}
          <button onClick={() => setError("")}>Dismiss</button>
        </div>
      )}
      <AutomationBuilder
        authoring={authoringServices(environment, id)}
        key={bootstrap.key}
        workflowId={bootstrap.row?.id}
        environmentId={environment}
        mode={
          bootstrap.row?.archived_at ||
          (bootstrap.row ? !can("edit") : !can("create"))
            ? "read-only"
            : "edit"
        }
        initialDocument={bootstrap.initial}
        version={bootstrap.row?.version || 0}
        savedAt={bootstrap.row?.updated_at}
        recoveryKey={`power-apps-recovery:${user?.id}:${sessionStorage.getItem("suite-organization") || user?.access?.companyId || "current"}:${environment}:${bootstrap.row?.id || "new"}`}
        nodeCatalog={bootstrap.nodes}
        permissions={{
          create: can("create"),
          edit: can("edit"),
          delete: can("delete"),
          publish: can("publish"),
          execute: can("execute"),
          manageCredentials: can("manage_credentials"),
        }}
        onSave={async (document, expectedVersion) => {
          const wasNew = !currentRow.current;
          const row = await studioApi.save(
            environment,
            document,
            expectedVersion,
            currentRow.current?.id,
          );
          if (active.current) {
            currentRow.current = row;
            setBootstrap((previous) =>
              previous ? { ...previous, row } : previous,
            );
            if (wasNew)
              navigate(
                studioPath(
                  `/power-apps/automations/${row.id}/edit`,
                  environment,
                ),
                { replace: true },
              );
          }
          return row;
        }}
        referenceProviders={{
          user: async (query) =>
            user &&
            `${user.id} ${user.name} ${user.email}`
              .toLowerCase()
              .includes(query.toLowerCase())
              ? [{ value: String(user.id), label: user.name || user.email }]
              : [],
          "sub_workflow.workflow_id": async (query) =>
            (await studioApi.list(environment, "all", query)).items
              .filter((row) => row.id !== currentRow.current?.id)
              .map((row) => ({ value: String(row.id), label: row.name })),
        }}
        onValidate={(definition) => studioApi.validate(environment, definition)}
        onPreview={(definition, input) =>
          studioApi.preview(environment, definition, input)
        }
        breadcrumbs={workflowTrail
          .filter((item) => item.id !== id)
          .map((item, index) => ({
            id: String(item.id),
            label: item.name,
            onNavigate: () => {
              void powerApi
                .read(environment, item.id)
                .then((target) => {
                  setWorkflowTrail((current) => current.slice(0, index));
                  openRow(target);
                })
                .catch((e) => setError(errorMessage(e)));
            },
          }))}
        onOpenWorkflow={async (workflowId) => {
          const target = await powerApi.read(environment, Number(workflowId));
          if (target.application_id !== "automations")
            throw new Error("Referenced automation is unavailable");
          const source = currentRow.current;
          if (source)
            setWorkflowTrail((current) =>
              [
                ...current.filter(
                  (item) => item.id !== target.id && item.id !== source.id,
                ),
                { id: source.id, name: source.name },
              ].slice(-10),
            );
          openRow(target);
        }}
        onRuntime={id ? () => navigate(studioPath(`/power-apps/automations/${id}/runtime`, environment)) : undefined}
        onBack={() =>
          navigate(studioPath("/power-apps/automations", environment))
        }
        onDuplicate={async () => {
          if (currentRow.current)
            openRow(
              await studioApi.duplicate(environment, currentRow.current.id),
            );
        }}
        onSaveCopy={async (document) => {
          openRow(
            await studioApi.save(
              environment,
              { ...document, name: document.name.slice(0, 170) + " (copy)" },
              0,
            ),
          );
        }}
        onVersionHistory={() => {
          if (currentRow.current)
            navigate(
              studioPath(
                `/power-apps/automations/${currentRow.current.id}/versions`,
                environment,
              ),
            );
        }}
        onSettings={() => {
          if (currentRow.current)
            navigate(
              studioPath(
                `/power-apps/automations/${currentRow.current.id}/settings`,
                environment,
              ),
            );
        }}
        externalPanel={mode}
        versions={versions}
        onRestoreVersion={async (version) => {
          if (currentRow.current)
            openRow(
              await studioApi.restore(
                environment,
                currentRow.current.id,
                version,
              ),
            );
        }}
      />
    </>
  );
}
