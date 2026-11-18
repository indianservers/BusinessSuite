import { api } from "@/services/api";
import type { Resource, Environment } from "../../registry";
import type {
  Analysis,
  AIProposal,
  AuthoringServices,
  AutomationTemplate,
  NodeDefinition,
  PreviewResult,
  ValidationResult,
  VersionSnapshot,
  WorkflowDocument,
  WorkflowGraph,
} from "./builder/types";
const root = "/power-apps/automations";
export const studioApi = {
  rename: (environment: Environment, row: Resource, name: string) =>
    api
      .put<Resource>(
        `${root}/${row.id}`,
        {
          name,
          description: row.description,
          definition: row.definition,
          expected_version: row.version,
        },
        { params: { environment } },
      )
      .then((r) => r.data),
  nodes: () =>
    api
      .get<{ version: number; nodes: NodeDefinition[] }>(`${root}/node-catalog`)
      .then((r) => r.data.nodes),
  templates: () =>
    api
      .get<{ items: AutomationTemplate[] }>(`${root}/templates`)
      .then((r) => r.data.items || []),
  list: (environment: Environment, view = "all", search = "", offset = 0) =>
    api
      .get<{
        items: Resource[];
        total: number;
      }>(root, { params: { environment, view, search, offset, limit: 50 } })
      .then((r) => r.data),
  save: (
    environment: Environment,
    document: WorkflowDocument,
    expected_version: number,
    id?: number,
  ) =>
    (id
      ? api.put<Resource>(
          `${root}/${id}`,
          { ...document, expected_version },
          { params: { environment }, progress: false },
        )
      : api.post<Resource>(root, document, {
          params: { environment },
          progress: false,
        })
    ).then((r) => r.data),
  duplicate: (environment: Environment, id: number) =>
    api
      .post<Resource>(
        `${root}/${id}/duplicate`,
        {},
        { params: { environment } },
      )
      .then((r) => r.data),
  lifecycle: (environment: Environment, row: Resource, archived: boolean) =>
    api
      .post<Resource>(
        `${root}/${row.id}/${archived ? "archive" : "unarchive"}`,
        { expected_version: row.version },
        { params: { environment } },
      )
      .then((r) => r.data),
  versions: (environment: Environment, id: number) =>
    api
      .get<{
        items: VersionSnapshot[];
      }>(`${root}/${id}/versions`, { params: { environment }, progress: false })
      .then((r) => r.data.items),
  restore: (environment: Environment, id: number, version: number) =>
    api
      .post<Resource>(
        `${root}/${id}/restore`,
        { version },
        { params: { environment } },
      )
      .then((r) => r.data),
  useTemplate: (environment: Environment, id: string) =>
    api
      .post<Resource>(
        `${root}/templates/${id}/use`,
        {},
        { params: { environment } },
      )
      .then((r) => r.data),
  validate: (environment: Environment, definition: WorkflowGraph) =>
    api
      .post<ValidationResult>(
        `${root}/validate`,
        { definition },
        { params: { environment }, progress: false },
      )
      .then((r) => r.data),
  preview: (
    environment: Environment,
    definition: WorkflowGraph,
    test_input: Record<string, unknown>,
  ) =>
    api
      .post<PreviewResult>(
        `${root}/preview`,
        { definition, test_input },
        { params: { environment }, progress: false },
      )
      .then((r) => r.data),
};
export function environmentFromSearch(search: string): Environment {
  const value = new URLSearchParams(search).get("environment");
  return (
    ["development", "testing", "production"].includes(value || "")
      ? value
      : "development"
  ) as Environment;
}
export function studioPath(path: string, environment: Environment) {
  return `${path}${path.includes("?") ? "&" : "?"}environment=${environment}`;
}

export function authoringServices(
  environment: Environment,
  workflowId?: number,
): AuthoringServices {
  const post = <T>(path: string, data: unknown) =>
    api
      .post<T>(root + path, data, { params: { environment }, progress: false })
      .then((r) => r.data);
  return {
    review: (definition) => post("/intelligence/review", { definition }),
    analyze: (document, version) =>
      post<Analysis>("/intelligence/analyze", {
        ...document,
        version,
        workflow_id: workflowId,
      }),
    propose: (prompt, mode, provider, definition) =>
      post<AIProposal>("/ai/propose", { prompt, mode, provider, definition }),
    mapping: (mapping, context, node_type, field) =>
      post("/mapping/preview", { mapping, context, node_type, field }),
    portable: (definition) => post("/portable/prepare", { definition }),
    templates: studioApi.templates,
    blocks: () =>
      api
        .get<{
          items: Resource[];
        }>(root + "/blocks", { params: { environment }, progress: false })
        .then((r) => r.data.items),
    saveBlock: (document, id, expected_version = 0) =>
      (id
        ? api.put<Resource>(
            root + "/blocks/" + id,
            { ...document, expected_version },
            { params: { environment } },
          )
        : api.post<Resource>(
            root + "/blocks",
            { ...document, expected_version },
            { params: { environment } },
          )
      ).then((r) => r.data),
    blockVersions: (id) =>
      api
        .get<{
          items: VersionSnapshot[];
        }>(root + `/blocks/${id}/versions`, {
          params: { environment },
          progress: false,
        })
        .then((r) => r.data.items),
    blockUsage: (id) =>
      api
        .get<{
          items: { id: number; name: string; version: number }[];
        }>(root + `/blocks/${id}/usage`, {
          params: { environment },
          progress: false,
        })
        .then((r) => r.data.items),
    archiveBlock: (row) =>
      post(`/blocks/${row.id}/archive`, { expected_version: row.version }),
    simulate: (definition, test_input, synthetic_outputs, injected_errors) =>
      post("/preview", {
        definition,
        test_input,
        synthetic_outputs,
        injected_errors,
      }),
  };
}
