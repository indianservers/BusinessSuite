import { api } from "@/services/api";

export type CustomizationRecord = Record<string, unknown> & { id?: number; name?: string; module_name?: string };

const list = (path: string) => api.get<{ items: CustomizationRecord[]; total: number }>(path).then((res) => res.data);
const create = (path: string, data: unknown) => api.post(path, data).then((res) => res.data);

export const customizationApi = {
  modules: () => list("/customization/modules"),
  createModule: (data: unknown) => create("/customization/modules", data),
  fields: () => list("/customization/fields"),
  createField: (data: unknown) => create("/customization/fields", data),
  validateField: (id: number, data: unknown) => create(`/customization/fields/${id}/validate`, data),
  layouts: () => list("/customization/layouts"),
  createLayout: (data: unknown) => create("/customization/layouts", data),
  addLayoutSection: (id: number, data: unknown) => create(`/customization/layouts/${id}/sections`, data),
  reorderLayoutFields: (id: number, data: unknown) => create(`/customization/layouts/${id}/fields/reorder`, data),
  views: () => list("/customization/views"),
  createView: (data: unknown) => create("/customization/views", data),
  kanban: () => list("/customization/kanban"),
  createKanban: (data: unknown) => create("/customization/kanban", data),
  validationRules: () => list("/customization/validation-rules"),
  createValidationRule: (data: unknown) => create("/customization/validation-rules", data),
  testValidationRule: (id: number, data: unknown) => create(`/customization/validation-rules/${id}/test`, data),
  buttons: () => list("/customization/buttons"),
  createButton: (data: unknown) => create("/customization/buttons", data),
  executeButton: (id: number, data: unknown) => create(`/customization/buttons/${id}/execute`, data),
  picklists: () => list("/customization/picklists"),
  createPicklist: (data: unknown) => create("/customization/picklists", data),
  formulas: () => list("/customization/formulas"),
  createFormula: (data: unknown) => create("/customization/formulas", data),
  testFormula: (data: unknown) => create("/customization/formulas/test", data),
  rollups: () => list("/customization/rollups"),
  createRollup: (data: unknown) => create("/customization/rollups", data),
  audit: () => list("/customization/audit-logs"),
  dynamicRecords: (module: string) => list(`/custom/${module}`),
  createDynamicRecord: (module: string, data: unknown) => create(`/custom/${module}`, data),
};

