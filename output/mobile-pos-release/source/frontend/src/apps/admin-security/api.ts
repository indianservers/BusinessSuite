import { api } from "@/services/api";

export type AdminSecurityRecord = Record<string, any>;
export type AdminSecurityList = { items: AdminSecurityRecord[]; total?: number };

const list = (path: string) => api.get<AdminSecurityList>(path).then((response) => response.data);
const post = (path: string, data: AdminSecurityRecord) => api.post<AdminSecurityRecord>(path, data).then((response) => response.data);

export const adminSecurityApi = {
  overview: () => api.get<AdminSecurityRecord>("/admin/security").then((response) => response.data),
  profiles: () => list("/admin/profiles"),
  createProfile: (data: AdminSecurityRecord) => post("/admin/profiles", data),
  setProfilePermissions: (id: number, permissions: string[]) => post(`/admin/profiles/${id}/permissions`, { permissions }),
  roles: () => list("/admin/roles"),
  createRole: (data: AdminSecurityRecord) => post("/admin/roles", data),
  createRoleHierarchy: (data: AdminSecurityRecord) => post("/admin/roles/hierarchy", data),
  fieldSecurity: () => list("/admin/field-security"),
  createFieldSecurity: (data: AdminSecurityRecord) => post("/admin/field-security", data),
  validateFieldUpdate: (data: AdminSecurityRecord) => post("/admin/security/validate-field-update", data),
  applyFieldSecurity: (data: AdminSecurityRecord) => post("/admin/security/apply-field-security", data),
  recordSharingRules: () => list("/admin/record-sharing-rules"),
  createRecordSharingRule: (data: AdminSecurityRecord) => post("/admin/record-sharing-rules", data),
  shareRecord: (data: AdminSecurityRecord) => post("/admin/records/share", data),
  unshareRecord: (data: AdminSecurityRecord) => post("/admin/records/unshare", data),
  dataSharingRules: () => list("/admin/data-sharing-rules"),
  createDataSharingRule: (data: AdminSecurityRecord) => post("/admin/data-sharing-rules", data),
  ipRestrictions: () => list("/admin/ip-restrictions"),
  createIpRestriction: (data: AdminSecurityRecord) => post("/admin/ip-restrictions", data),
  auditLogs: () => list("/admin/audit-logs"),
  importsUpload: (data: AdminSecurityRecord) => post("/admin/imports/upload", data),
  importsMap: (id: number, data: AdminSecurityRecord) => post(`/admin/imports/${id}/map-fields`, data),
  importsRun: (id: number) => post(`/admin/imports/${id}/run`, {}),
  importErrors: (id: number) => list(`/admin/imports/${id}/errors`),
  duplicateRules: () => list("/admin/duplicate-rules"),
  createDuplicateRule: (data: AdminSecurityRecord) => post("/admin/duplicate-rules", data),
  scanDuplicates: (data: AdminSecurityRecord) => post("/admin/duplicates/scan", data),
  duplicateCandidates: () => list("/admin/duplicates/candidates"),
  mergeDuplicates: (data: AdminSecurityRecord) => post("/admin/duplicates/merge", data),
  exportControls: () => list("/admin/export-controls"),
  createExportControl: (data: AdminSecurityRecord) => post("/admin/export-controls", data),
  backups: () => list("/admin/backups"),
  requestBackup: (data: AdminSecurityRecord) => post("/admin/backups/request", data),
  compliance: () => list("/admin/compliance"),
  upsertCompliance: (data: AdminSecurityRecord) => post("/admin/compliance", data),
  retention: () => list("/admin/data-retention"),
  createRetention: (data: AdminSecurityRecord) => post("/admin/data-retention", data),
};
