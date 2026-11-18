import { api } from "@/services/api";
import type {
  Activity,
  Catalog,
  Environment,
  Overview,
  Resource,
} from "./registry";
const root = "/power-apps";
export const powerApi = {
  catalog: () => api.get<Catalog>(`${root}/catalog`).then((r) => r.data),
  environments: () =>
    api
      .get<{
        items: { key: Environment; enabled: boolean }[];
      }>(`${root}/environments`)
      .then((r) => r.data.items),
  configure: (key: Environment, enabled: boolean) =>
    api.put(`${root}/environments/${key}`, { enabled }),
  overview: (environment: Environment) =>
    api
      .get<Overview>(`${root}/overview`, { params: { environment } })
      .then((r) => r.data),
  activity: (environment: Environment) =>
    api
      .get<{
        items: Activity[];
      }>(`${root}/activity`, { params: { environment } })
      .then((r) => r.data.items),
  drafts: (environment: Environment, offset = 0) =>
    api
      .get<{
        items: Resource[];
        total: number;
      }>(`${root}/automations`, { params: { environment, offset } })
      .then((r) => r.data),
  read: (environment: Environment, id: number) =>
    api
      .get<Resource>(`${root}/automations/${id}`, { params: { environment } })
      .then((r) => r.data),
  save: (
    environment: Environment,
    body: {
      name: string;
      description: string;
      definition: Record<string, unknown>;
      expected_version?: number;
    },
    id?: number,
  ) =>
    (id
      ? api.put<Resource>(`${root}/automations/${id}`, body, {
          params: { environment },
        })
      : api.post<Resource>(`${root}/automations`, body, {
          params: { environment },
        })
    ).then((r) => r.data),
  remove: (environment: Environment, row: Resource) =>
    api.delete(`${root}/automations/${row.id}`, {
      params: { environment, expected_version: row.version },
    }),
};
export function errorMessage(error: unknown) {
  const detail = (error as { response?: { data?: { detail?: unknown } } })
    ?.response?.data?.detail;
  return typeof detail === "string"
    ? detail
    : Array.isArray(detail)
      ? "The definition is invalid. Check the workflow schema and field limits."
      : "Could not load Power Apps. Please try again.";
}
