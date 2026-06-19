import axios, { AxiosError, AxiosResponse } from "axios";
import { useAuthStore } from "@/store/authStore";
import { getApiBaseUrl } from "@/config/runtime";

const BASE_URL = getApiBaseUrl();
type RefreshResponse = { access_token: string; refresh_token: string };
let refreshPromise: Promise<RefreshResponse> | null = null;

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
});

// Request interceptor: attach access token
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: handle token refresh
api.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError) => {
    const original = error.config as (typeof error.config & { _retry?: boolean }) | undefined;

    if (error.response?.status === 401 && original && !original._retry) {
      original._retry = true;
      const { refreshToken, setTokens, logout } = useAuthStore.getState();

      if (refreshToken) {
        try {
          if (!refreshPromise) {
            refreshPromise = axios
              .post<RefreshResponse>(`${BASE_URL}/auth/refresh`, {
                refresh_token: refreshToken,
              })
              .then((res) => res.data)
              .finally(() => {
                refreshPromise = null;
              });
          }
          const { access_token, refresh_token } = await refreshPromise;
          setTokens(access_token, refresh_token);
          original.headers = original.headers || {};
          original.headers.Authorization = `Bearer ${access_token}`;
          return api(original);
        } catch {
          if (useAuthStore.getState().refreshToken === refreshToken) {
            logout();
          }
        }
      } else {
        logout();
      }
    }

    return Promise.reject(error);
  }
);

// API service functions
export const authApi = {
  login: (email: string, password: string, module?: string, trustedDeviceToken?: string) =>
    api.post("/auth/login", { email, password, module, trusted_device_token: trustedDeviceToken }),
  refresh: (refreshToken: string) =>
    api.post("/auth/refresh", { refresh_token: refreshToken }),
  forgotPassword: (email: string) => api.post("/auth/forgot-password", { email }),
  resetPassword: (token: string, newPassword: string) =>
    api.post("/auth/reset-password", { token, new_password: newPassword }),
  me: () => api.get("/auth/me"),
  changePassword: (currentPassword: string, newPassword: string) =>
    api.post("/auth/change-password", {
      current_password: currentPassword,
      new_password: newPassword,
    }),
  logout: () => api.post("/auth/logout"),
  mfaSetup: () => api.post("/auth/mfa/setup"),
  mfaConfirm: (data: unknown) => api.post("/auth/mfa/confirm", data),
  mfaVerify: (data: unknown) => api.post("/auth/mfa/verify", data),
  mfaDisable: (data: unknown) => api.delete("/auth/mfa/disable", { data }),
  mfaStatus: () => api.get("/auth/mfa/status"),
  regenerateRecoveryCodes: (data: unknown) => api.post("/auth/mfa/regenerate-recovery-codes", data),
  permissions: () => api.get("/auth/permissions"),
  users: () => api.get("/auth/users"),
  createUser: (data: unknown) => api.post("/auth/users", data),
  roles: () => api.get("/auth/roles"),
  createRole: (data: unknown) => api.post("/auth/roles", data),
  updateRole: (id: number, data: unknown) => api.put(`/auth/roles/${id}`, data),
  deleteRole: (id: number) => api.delete(`/auth/roles/${id}`),
  sessions: (params?: Record<string, unknown>) => api.get("/auth/sessions", { params }),
  mySessions: () => api.get("/auth/sessions/me"),
  createSession: (data: unknown) => api.post("/auth/sessions", data),
  revokeSession: (id: number) => api.put(`/auth/sessions/${id}/revoke`),
  revokeMySession: (id: number) => api.put(`/auth/sessions/me/${id}/revoke`),
  revokeOtherSessions: () => api.put("/auth/sessions/me/revoke-others"),
  mfaMethods: (params?: Record<string, unknown>) => api.get("/auth/mfa-methods", { params }),
  createMfaMethod: (data: unknown) => api.post("/auth/mfa-methods", data),
  verifyMfaMethod: (id: number) => api.put(`/auth/mfa-methods/${id}/verify`),
  passwordPolicies: () => api.get("/auth/password-policies"),
  createPasswordPolicy: (data: unknown) => api.post("/auth/password-policies", data),
  updatePasswordPolicy: (id: number, data: unknown) => api.put(`/auth/password-policies/${id}`, data),
  enforceMfaPolicy: (id: number) => api.post(`/auth/password-policies/${id}/enforce-mfa`),
  loginAttempts: (params?: Record<string, unknown>) => api.get("/auth/login-attempts", { params }),
  ipPolicies: () => api.get("/auth/ip-policies"),
  createIpPolicy: (data: unknown) => api.post("/auth/ip-policies", data),
  updateIpPolicy: (id: number, data: unknown) => api.put(`/auth/ip-policies/${id}`, data),
  ssoProviders: () => api.get("/auth/sso/providers/active"),
  ssoAdminProviders: () => api.get("/auth/sso/providers"),
  createSsoProvider: (data: unknown) => api.post("/auth/sso/providers", data),
  updateSsoProvider: (id: number, data: unknown) => api.put(`/auth/sso/providers/${id}`, data),
  deleteSsoProvider: (id: number) => api.delete(`/auth/sso/providers/${id}`),
  testSsoProvider: (id: number) => api.get(`/auth/sso/providers/${id}/test`),
  ssoMetadata: (id: number) => api.get(`/auth/sso/providers/${id}/sp-metadata`, { responseType: "blob" }),
};

export const employeeApi = {
  list: (params?: Record<string, unknown>) => api.get("/employees/", { params }),
  directory: (params?: Record<string, unknown>) => api.get("/employees/directory", { params }),
  directoryExport: (params?: Record<string, unknown>) =>
    api.get("/employees/directory/export", { params, responseType: "blob" }),
  directoryFilters: () => api.get("/employees/directory/filters"),
  recentJoiners: (params?: Record<string, unknown>) => api.get("/employees/recent-joiners", { params }),
  birthdays: (params?: Record<string, unknown>) => api.get("/employees/birthdays", { params }),
  workAnniversaries: (params?: Record<string, unknown>) => api.get("/employees/work-anniversaries", { params }),
  orgSearch: (params?: Record<string, unknown>) => api.get("/employees/org-search", { params }),
  profileCard: (id: number) => api.get(`/employees/${id}/profile-card`),
  reportDirectoryCorrection: (data: unknown) => api.post("/employees/directory/report-correction", data),
  create: (data: unknown) => api.post("/employees/", data),
  me: () => api.get("/employees/me"),
  exportCsv: (params?: Record<string, unknown>) =>
    api.get("/employees/export", { params, responseType: "blob" }),
  importCsv: (formData: FormData) =>
    api.post("/employees/import", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  get: (id: number) => api.get(`/employees/${id}`),
  update: (id: number, data: unknown) => api.put(`/employees/${id}`, data),
  delete: (id: number) => api.delete(`/employees/${id}`),
  userOptions: (params?: Record<string, unknown>) =>
    api.get("/employees/user-options", { params }),
  linkUser: (id: number, userId: number | null) =>
    api.put(`/employees/${id}/user-link`, { user_id: userId }),
  createUserAccount: (id: number, data: unknown) =>
    api.post(`/employees/${id}/user-account`, data),
  stats: () => api.get("/employees/stats"),
  count: () => api.get("/employees/count"),
  addEducation: (id: number, data: unknown) => api.post(`/employees/${id}/education`, data),
  addExperience: (id: number, data: unknown) => api.post(`/employees/${id}/experience`, data),
  addSkill: (id: number, data: unknown) => api.post(`/employees/${id}/skills`, data),
  uploadDocument: (id: number, formData: FormData) =>
    api.post(`/employees/${id}/documents`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  expiringDocuments: (params?: Record<string, unknown>) =>
    api.get("/employees/documents/expiring", { params }),
  verifyDocument: (employeeId: number, documentId: number, data: unknown) =>
    api.put(`/employees/${employeeId}/documents/${documentId}/verify`, data),
  uploadPhoto: (id: number, formData: FormData) =>
    api.post(`/employees/${id}/photo`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  profileCompleteness: () => api.get("/employees/me/completeness"),
  changeRequests: (params?: Record<string, unknown>) =>
    api.get("/hrms/profile-change-requests", { params }),
  getChangeRequest: (id: number) => api.get(`/hrms/profile-change-requests/${id}`),
  createChangeRequest: (data: unknown) => api.post("/employees/change-requests", data),
  createProfileChangeRequest: (employeeId: number, data: unknown) =>
    api.post(`/hrms/employees/${employeeId}/change-request`, data),
  reviewChangeRequest: (id: number, data: unknown) =>
    api.put(`/employees/change-requests/${id}/review`, data),
  approveProfileChangeRequest: (id: number, data: unknown) =>
    api.post(`/hrms/profile-change-requests/${id}/approve`, data),
  rejectProfileChangeRequest: (id: number, data: unknown) =>
    api.post(`/hrms/profile-change-requests/${id}/reject`, data),
};

export const companyApi = {
  listCompanies: () => api.get("/company/"),
  createCompany: (data: unknown) => api.post("/company/", data),
  updateCompany: (id: number, data: unknown) => api.put(`/company/${id}`, data),
  uploadLogo: (id: number, formData: FormData) =>
    api.post(`/company/${id}/logo`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  deleteCompany: (id: number) => api.delete(`/company/${id}`),
  listBranches: (companyId?: number) =>
    api.get("/company/branches/", { params: { company_id: companyId } }),
  createBranch: (data: unknown) => api.post("/company/branches/", data),
  updateBranch: (id: number, data: unknown) => api.put(`/company/branches/${id}`, data),
  deleteBranch: (id: number) => api.delete(`/company/branches/${id}`),
  listDepartments: (branchId?: number) =>
    api.get("/company/departments/", { params: { branch_id: branchId } }),
  createDepartment: (data: unknown) => api.post("/company/departments/", data),
  updateDepartment: (id: number, data: unknown) => api.put(`/company/departments/${id}`, data),
  deleteDepartment: (id: number) => api.delete(`/company/departments/${id}`),
  listDesignations: (deptId?: number) =>
    api.get("/company/designations/", { params: { department_id: deptId } }),
  createDesignation: (data: unknown) => api.post("/company/designations/", data),
  updateDesignation: (id: number, data: unknown) =>
    api.put(`/company/designations/${id}`, data),
  deleteDesignation: (id: number) => api.delete(`/company/designations/${id}`),
  businessUnits: () => api.get("/company/business-units"),
  createBusinessUnit: (data: unknown) => api.post("/company/business-units", data),
  costCenters: () => api.get("/company/cost-centers"),
  createCostCenter: (data: unknown) => api.post("/company/cost-centers", data),
  workLocations: () => api.get("/company/locations"),
  createWorkLocation: (data: unknown) => api.post("/company/locations", data),
  gradeBands: () => api.get("/company/grade-bands"),
  createGradeBand: (data: unknown) => api.post("/company/grade-bands", data),
  jobFamilies: () => api.get("/company/job-families"),
  createJobFamily: (data: unknown) => api.post("/company/job-families", data),
  jobProfiles: () => api.get("/company/job-profiles"),
  createJobProfile: (data: unknown) => api.post("/company/job-profiles", data),
  positions: (params?: Record<string, unknown>) => api.get("/company/positions", { params }),
  createPosition: (data: unknown) => api.post("/company/positions", data),
  orgChart: (params?: Record<string, unknown>) => api.get("/company/org-chart", { params }),
  validateManagerHierarchy: () => api.get("/company/manager-hierarchy/validate"),
  headcountPlans: (params?: Record<string, unknown>) =>
    api.get("/company/headcount-plans", { params }),
  createHeadcountPlan: (data: unknown) => api.post("/company/headcount-plans", data),
  approveHeadcountPlan: (id: number) => api.put(`/company/headcount-plans/${id}/approve`),
};

export const enterpriseApi = {
  integrationCredentials: () => api.get("/enterprise/integration-credentials"),
  createIntegrationCredential: (data: unknown) =>
    api.post("/enterprise/integration-credentials", data),
  webhooks: () => api.get("/enterprise/webhooks"),
  createWebhook: (data: unknown) => api.post("/enterprise/webhooks", data),
  integrationEvents: (params?: Record<string, unknown>) =>
    api.get("/enterprise/integration-events", { params }),
  queueIntegrationEvent: (data: unknown) => api.post("/enterprise/integration-events", data),
  consents: (params?: Record<string, unknown>) => api.get("/enterprise/consents", { params }),
  createConsent: (data: unknown) => api.post("/enterprise/consents", data),
  revokeConsent: (id: number) => api.put(`/enterprise/consents/${id}/revoke`),
  privacyRequests: (params?: Record<string, unknown>) =>
    api.get("/enterprise/privacy-requests", { params }),
  createPrivacyRequest: (data: unknown) => api.post("/enterprise/privacy-requests", data),
  reviewPrivacyRequest: (id: number, data: unknown) =>
    api.put(`/enterprise/privacy-requests/${id}`, data),
  processPrivacyRequest: (id: number) => api.post(`/enterprise/privacy-requests/${id}/process`),
  privacyExport: (id: number) => api.get(`/enterprise/privacy-requests/${id}/export`),
  retentionPolicies: () => api.get("/enterprise/retention-policies"),
  createRetentionPolicy: (data: unknown) => api.post("/enterprise/retention-policies", data),
  runRetentionPolicies: (dryRun = true) =>
    api.post("/enterprise/retention-policies/run", null, { params: { dry_run: dryRun } }),
  legalHolds: () => api.get("/enterprise/legal-holds"),
  createLegalHold: (data: unknown) => api.post("/enterprise/legal-holds", data),
  releaseLegalHold: (id: number) => api.put(`/enterprise/legal-holds/${id}/release`),
  metrics: (params?: Record<string, unknown>) => api.get("/enterprise/metrics", { params }),
  createMetric: (data: unknown) => api.post("/enterprise/metrics", data),
  domainPackCatalog: () => api.get("/enterprise/domain-packs/catalog"),
  domainPacks: (params?: Record<string, unknown>) => api.get("/enterprise/domain-packs", { params }),
  enableDomainPack: (data: unknown) => api.post("/enterprise/domain-packs/enable", data),
  disableDomainPack: (id: number) => api.put(`/enterprise/domain-packs/${id}/disable`),
  manufacturingSafetyIncidents: (params?: Record<string, unknown>) =>
    api.get("/enterprise/domain-packs/manufacturing/safety-incidents", { params }),
  createManufacturingSafetyIncident: (data: unknown) =>
    api.post("/enterprise/domain-packs/manufacturing/safety-incidents", data),
  manufacturingPpeIssuances: (params?: Record<string, unknown>) =>
    api.get("/enterprise/domain-packs/manufacturing/ppe-issuances", { params }),
  createManufacturingPpeIssuance: (data: unknown) =>
    api.post("/enterprise/domain-packs/manufacturing/ppe-issuances", data),
  manufacturingMedicalFitness: (params?: Record<string, unknown>) =>
    api.get("/enterprise/domain-packs/manufacturing/medical-fitness", { params }),
  createManufacturingMedicalFitness: (data: unknown) =>
    api.post("/enterprise/domain-packs/manufacturing/medical-fitness", data),
  manufacturingContractLaborBatches: (params?: Record<string, unknown>) =>
    api.get("/enterprise/domain-packs/manufacturing/contract-labor-batches", { params }),
  createManufacturingContractLaborBatch: (data: unknown) =>
    api.post("/enterprise/domain-packs/manufacturing/contract-labor-batches", data),
};

export const attendanceApi = {
  checkIn: (data: unknown) => api.post("/attendance/check-in", data),
  checkOut: (data: unknown) => api.post("/attendance/check-out", data),
  getToday: () => api.get("/attendance/today"),
  myAttendance: (fromDate: string, toDate: string) =>
    api.get("/attendance/my", { params: { from_date: fromDate, to_date: toDate } }),
  employeeAttendance: (empId: number, fromDate: string, toDate: string) =>
    api.get(`/attendance/employee/${empId}`, {
      params: { from_date: fromDate, to_date: toDate },
    }),
  register: (params: Record<string, unknown>) => api.get("/attendance/register", { params }),
  bulkEntry: (data: unknown) => api.post("/attendance/bulk-entry", data),
  monthlySummary: (month: number, year: number, employeeId?: number) =>
    api.get("/attendance/summary/monthly", {
      params: { month, year, employee_id: employeeId },
    }),
  listShifts: () => api.get("/attendance/shifts"),
  createShift: (data: unknown) => api.post("/attendance/shifts", data),
  updateShift: (id: number, data: unknown) => api.put(`/attendance/shifts/${id}`, data),
  deleteShift: (id: number) => api.delete(`/attendance/shifts/${id}`),
  listHolidays: (year?: number) =>
    api.get("/attendance/holidays", { params: { year } }),
  createHoliday: (data: unknown) => api.post("/attendance/holidays", data),
  updateHoliday: (id: number, data: unknown) => api.put(`/attendance/holidays/${id}`, data),
  deleteHoliday: (id: number) => api.delete(`/attendance/holidays/${id}`),
  requestRegularization: (data: unknown) => api.post("/attendance/regularize", data),
  pendingRegularizations: () => api.get("/attendance/regularize/pending"),
  approveRegularization: (id: number, data: unknown) =>
    api.put(`/attendance/regularize/${id}/approve`, data),
  biometricDevices: () => api.get("/attendance/biometric/devices"),
  createBiometricDevice: (data: unknown) => api.post("/attendance/biometric/devices", data),
  importBiometricPunches: (data: unknown) => api.post("/attendance/biometric/import", data),
  importBiometricAdapter: (data: unknown) => api.post("/attendance/biometric/import-adapter", data),
  reconcileBiometric: (data: unknown) => api.post("/attendance/biometric/reconcile", data),
  missingPunches: (params: Record<string, unknown>) => api.get("/attendance/reports/missing-punches", { params }),
  locks: (params?: Record<string, unknown>) => api.get("/attendance/locks", { params }),
  lockMonth: (data: unknown) => api.post("/attendance/locks", data),
  unlockMonth: (id: number, reason?: string) =>
    api.put(`/attendance/locks/${id}/unlock`, null, { params: { reason } }),
  weeklyOffs: (params?: Record<string, unknown>) => api.get("/attendance/weekly-offs", { params }),
  createWeeklyOff: (data: unknown) => api.post("/attendance/weekly-offs", data),
  geoPolicies: () => api.get("/attendance/geo/policies"),
  createGeoPolicy: (data: unknown) => api.post("/attendance/geo/policies", data),
  geoPunch: (data: unknown) => api.post("/attendance/geo/punch", data),
  todaySummary: () => api.get("/attendance/today-summary"),
};

export const shiftRosterApi = {
  list: (params: Record<string, unknown>) => api.get("/hrms/shift-roster", { params }),
  assign: (data: unknown) => api.post("/hrms/shift-roster/assign", data),
  bulkAssign: (data: unknown) => api.post("/hrms/shift-roster/bulk-assign", data),
  copyWeek: (data: unknown) => api.post("/hrms/shift-roster/copy-week", data),
  publish: (data: unknown) => api.post("/hrms/shift-roster/publish", data),
  delete: (id: number) => api.delete(`/hrms/shift-roster/${id}`),
};

export const customFieldsApi = {
  definitions: (params?: Record<string, unknown>) => api.get("/custom-fields/definitions", { params }),
  createDefinition: (data: unknown) => api.post("/custom-fields/definitions", data),
  values: (params: Record<string, unknown>) => api.get("/custom-fields/values", { params }),
  upsertValue: (data: unknown) => api.put("/custom-fields/values", data),
  forms: (params?: Record<string, unknown>) => api.get("/custom-fields/forms", { params }),
  createForm: (data: unknown) => api.post("/custom-fields/forms", data),
  getForm: (id: number) => api.get(`/custom-fields/forms/${id}`),
  submitForm: (id: number, data: unknown) =>
    api.post(`/custom-fields/forms/${id}/submissions`, data),
  formSubmissions: (id: number, params?: Record<string, unknown>) =>
    api.get(`/custom-fields/forms/${id}/submissions`, { params }),
  reviewSubmission: (id: number, data: unknown) =>
    api.put(`/custom-fields/forms/submissions/${id}/review`, data),
};

export const logsApi = {
  audit: (params?: Record<string, unknown>) => api.get("/logs/audit", { params }),
  fieldAudit: (params?: Record<string, unknown>) => api.get("/logs/field-audit", { params }),
  errors: (params?: Record<string, unknown>) => api.get("/logs/errors", { params }),
  analysis: (params?: Record<string, unknown>) => api.get("/logs/analysis", { params }),
};

export const leaveApi = {
  types: () => api.get("/leave/types"),
  createType: (data: unknown) => api.post("/leave/types", data),
  updateType: (id: number, data: unknown) => api.put(`/leave/types/${id}`, data),
  deleteType: (id: number) => api.delete(`/leave/types/${id}`),
  balance: (year?: number) => api.get("/leave/balance", { params: { year } }),
  employeeBalance: (employeeId: number, year?: number) => api.get(`/leave/balance/${employeeId}`, { params: { year } }),
  apply: (data: unknown) => api.post("/leave/apply", data),
  myRequests: (params?: Record<string, unknown>) =>
    api.get("/leave/my-requests", { params }),
  allRequests: (params?: Record<string, unknown>) =>
    api.get("/leave/requests", { params }),
  calendar: (params?: Record<string, unknown>) =>
    api.get("/leave/calendar", { params }),
  approve: (id: number, data: unknown) =>
    api.put(`/leave/requests/${id}/approve`, data),
  cancel: (id: number) => api.put(`/leave/requests/${id}/cancel`),
  runAccruals: (runDate?: string) =>
    api.post("/leave/accruals/run", null, { params: { run_date: runDate } }),
  runCarryForward: (fromYear?: number, toYear?: number) =>
    api.post("/leave/carry-forward/run", null, { params: { from_year: fromYear, to_year: toYear } }),
  pendingCount: () => api.get("/leave/pending-count"),
};

export const leavePayrollApi = {
  encashmentRequests: (params?: Record<string, unknown>) =>
    api.get("/hrms/leave-encashment", { params }),
  requestEncashment: (data: unknown) => api.post("/hrms/leave-encashment/request", data),
  approveEncashment: (id: number, data: unknown) =>
    api.post(`/hrms/leave-encashment/${id}/approve`, data),
  rejectEncashment: (id: number, data: unknown) =>
    api.post(`/hrms/leave-encashment/${id}/reject`, data),
  lwpFeed: (month: string) => api.get("/hrms/payroll/lwp-feed", { params: { month } }),
  lwpSync: (data: unknown) => api.post("/hrms/payroll/lwp-sync", data),
};

export type PayrollAnalyticsParams = {
  from_month?: number;
  from_year?: number;
  to_month?: number;
  to_year?: number;
  month?: number;
  year?: number;
  department_id?: number;
  cost_center_id?: number;
};

export const payrollApi = {
  components: () => api.get("/payroll/components"),
  createComponent: (data: unknown) => api.post("/payroll/components", data),
  updateComponent: (id: number, data: unknown) => api.put(`/payroll/components/${id}`, data),
  deleteComponent: (id: number) => api.delete(`/payroll/components/${id}`),
  structures: () => api.get("/payroll/structures"),
  createStructure: (data: unknown) => api.post("/payroll/structures", data),
  cloneStructure: (id: number, params: Record<string, unknown>) =>
    api.post(`/payroll/structures/${id}/clone`, null, { params }),
  previewStructure: (id: number, data: unknown) =>
    api.post(`/payroll/structures/${id}/preview`, data),
  formulaGraph: (id: number) => api.get(`/payroll/structures/${id}/formula-graph`),
  setEmployeeSalary: (data: unknown) => api.post("/payroll/salary", data),
  salaryHistory: (empId: number) => api.get(`/payroll/salary/${empId}`),
  salaryTemplates: (params?: Record<string, unknown>) => api.get("/payroll/salary-templates", { params }),
  createSalaryTemplate: (data: unknown) => api.post("/payroll/salary-templates", data),
  salaryRevisions: (params?: Record<string, unknown>) =>
    api.get("/payroll/salary-revisions", { params }),
  createSalaryRevision: (data: unknown) => api.post("/payroll/salary-revisions", data),
  reviewSalaryRevision: (id: number, data: unknown) =>
    api.put(`/payroll/salary-revisions/${id}/review`, data),
  salaryAudit: (params?: Record<string, unknown>) =>
    api.get("/payroll/salary-audit", { params }),
  runs: (params?: Record<string, unknown>) => api.get("/payroll/runs", { params }),
  lastRun: () => api.get("/payroll/last-run"),
  runPayroll: (data: unknown) => api.post("/payroll/run", data),
  getRun: (id: number) => api.get(`/payroll/runs/${id}`),
  approveRun: (id: number, data: unknown) => api.put(`/payroll/runs/${id}/approve`, data),
  runRecords: (runId: number) => api.get(`/payroll/runs/${runId}/records`),
  runVariance: (runId: number) => api.get(`/payroll/runs/${runId}/variance`),
  validateExport: (runId: number, exportType: string) =>
    api.get(`/payroll/runs/${runId}/exports/${exportType}/validate`),
  exportRun: (runId: number, exportType: string) =>
    api.post(`/payroll/runs/${runId}/exports/${exportType}`),
  runAudit: (runId: number) => api.get(`/payroll/runs/${runId}/audit`),
  preRunChecks: (runId: number) => api.get(`/payroll/runs/${runId}/pre-run-checks`),
  addPreRunCheck: (runId: number, data: unknown) =>
    api.post(`/payroll/runs/${runId}/pre-run-checks`, data),
  manualInputs: (runId: number) => api.get(`/payroll/runs/${runId}/manual-inputs`),
  createManualInput: (runId: number, data: unknown) =>
    api.post(`/payroll/runs/${runId}/manual-inputs`, data),
  reviewManualInput: (id: number, data: unknown) =>
    api.put(`/payroll/manual-inputs/${id}/review`, data),
  createUnlockRequest: (runId: number, data: unknown) =>
    api.post(`/payroll/runs/${runId}/unlock-requests`, data),
  reviewUnlockRequest: (id: number, data: unknown) =>
    api.put(`/payroll/unlock-requests/${id}/review`, data),
  publishPayslips: (runId: number, data: unknown) =>
    api.post(`/payroll/runs/${runId}/payslip-publish`, data),
  payslip: (month: number, year: number, empId?: number) =>
    api.get("/payroll/payslip", { params: { month, year, employee_id: empId } }),
  generatePayslipPdf: (recordId: number) => api.post(`/payroll/payslip/${recordId}/pdf`),
  downloadPayslipPdf: (recordId: number) =>
    api.get(`/payroll/payslip/${recordId}/pdf`, { responseType: "blob" }),
  payGroups: () => api.get("/payroll/setup/pay-groups"),
  createPayGroup: (data: unknown) => api.post("/payroll/setup/pay-groups", data),
  payrollPeriods: (params?: Record<string, unknown>) => api.get("/payroll/setup/periods", { params }),
  createPayrollPeriod: (data: unknown) => api.post("/payroll/setup/periods", data),
  payrollCalendars: (params?: Record<string, unknown>) => api.get("/payroll/setup/calendars", { params }),
  createPayrollCalendar: (data: unknown) => api.post("/payroll/setup/calendars", data),
  complianceRules: (params?: Record<string, unknown>) => api.get("/payroll/setup/compliance-rules", { params }),
  createComplianceRule: (data: unknown) => api.post("/payroll/setup/compliance-rules", data),
  setupStatutoryProfiles: (params?: Record<string, unknown>) =>
    api.get("/payroll/setup/statutory-profiles", { params }),
  createSetupStatutoryProfile: (data: unknown) =>
    api.post("/payroll/setup/statutory-profiles", data),
  bankAdviceFormats: () => api.get("/payroll/setup/bank-advice-formats"),
  createBankAdviceFormat: (data: unknown) => api.post("/payroll/setup/bank-advice-formats", data),
  pfRules: () => api.get("/payroll/statutory/pf-rules"),
  createPfRule: (data: unknown) => api.post("/payroll/statutory/pf-rules", data),
  esiRules: () => api.get("/payroll/statutory/esi-rules"),
  createEsiRule: (data: unknown) => api.post("/payroll/statutory/esi-rules", data),
  ptSlabs: (params?: Record<string, unknown>) => api.get("/payroll/statutory/pt-slabs", { params }),
  createPtSlab: (data: unknown) => api.post("/payroll/statutory/pt-slabs", data),
  lwfSlabs: (params?: Record<string, unknown>) => api.get("/payroll/statutory/lwf-slabs", { params }),
  createLwfSlab: (data: unknown) => api.post("/payroll/statutory/lwf-slabs", data),
  gratuityRules: () => api.get("/payroll/statutory/gratuity-rules"),
  createGratuityRule: (data: unknown) => api.post("/payroll/statutory/gratuity-rules", data),
  statutoryProfiles: (params?: Record<string, unknown>) => api.get("/payroll/statutory/employee-profiles", { params }),
  createStatutoryProfile: (data: unknown) => api.post("/payroll/statutory/employee-profiles", data),
  calculateStatutory: (data: unknown) => api.post("/payroll/statutory/calculate", data),
  statutoryContributionLines: (params?: Record<string, unknown>) =>
    api.get("/payroll/statutory/contribution-lines", { params }),
  payrollAttendanceInputs: (params?: Record<string, unknown>) =>
    api.get("/payroll/inputs/attendance", { params }),
  createPayrollAttendanceInput: (data: unknown) => api.post("/payroll/inputs/attendance", data),
  reconcilePayrollAttendance: (data: unknown) => api.post("/payroll/inputs/reconcile-attendance", data),
  lopAdjustments: (params?: Record<string, unknown>) => api.get("/payroll/inputs/lop-adjustments", { params }),
  createLopAdjustment: (data: unknown) => api.post("/payroll/inputs/lop-adjustments", data),
  overtimePolicies: () => api.get("/payroll/inputs/overtime-policies"),
  createOvertimePolicy: (data: unknown) => api.post("/payroll/inputs/overtime-policies", data),
  overtimeLines: (params?: Record<string, unknown>) => api.get("/payroll/inputs/overtime-lines", { params }),
  createOvertimeLine: (data: unknown) => api.post("/payroll/inputs/overtime-lines", data),
  leaveEncashmentPolicies: () => api.get("/payroll/inputs/leave-encashment-policies"),
  createLeaveEncashmentPolicy: (data: unknown) => api.post("/payroll/inputs/leave-encashment-policies", data),
  leaveEncashmentLines: (params?: Record<string, unknown>) =>
    api.get("/payroll/inputs/leave-encashment-lines", { params }),
  createLeaveEncashmentLine: (data: unknown) => api.post("/payroll/inputs/leave-encashment-lines", data),
  runWorksheet: (runId: number) => api.get(`/payroll/runs/${runId}/worksheet`),
  updateWorksheetRow: (runId: number, rowId: number, data: unknown) =>
    api.put(`/payroll/runs/${runId}/worksheet/${rowId}`, data),
  processRunWorksheet: (runId: number) => api.post(`/payroll/runs/${runId}/worksheet/process`),
  calculationSnapshots: (runId: number, params?: Record<string, unknown>) =>
    api.get(`/payroll/runs/${runId}/calculation-snapshots`, { params }),
  createArrearRun: (data: unknown) => api.post("/payroll/arrear-runs", data),
  arrearRuns: (params?: Record<string, unknown>) => api.get("/payroll/arrear-runs", { params }),
  createOffCycleRun: (data: unknown) => api.post("/payroll/off-cycle-runs", data),
  offCycleRuns: (params?: Record<string, unknown>) => api.get("/payroll/off-cycle-runs", { params }),
  createPaymentBatch: (data: unknown) => api.post("/payroll/payments/batches", data),
  paymentBatches: (params?: Record<string, unknown>) => api.get("/payroll/payments/batches", { params }),
  importPaymentStatus: (batchId: number, data: unknown) =>
    api.put(`/payroll/payments/batches/${batchId}/status-import`, data),
  bankAdvicePreview: (runId: number, params?: Record<string, unknown>) =>
    api.get(`/hrms/payroll/${runId}/bank-advice/preview`, { params }),
  generateBankAdvice: (runId: number, data: unknown) =>
    api.post(`/hrms/payroll/${runId}/bank-advice/generate`, data),
  bankAdviceExports: (runId: number) => api.get(`/hrms/payroll/${runId}/bank-exports`),
  downloadBankAdviceExport: (exportId: number) =>
    api.get(`/hrms/payroll/bank-exports/${exportId}/download`, { responseType: "blob" }),
  accountingLedgers: () => api.get("/payroll/accounting/ledgers"),
  createAccountingLedger: (data: unknown) => api.post("/payroll/accounting/ledgers", data),
  glMappings: () => api.get("/payroll/accounting/gl-mappings"),
  createGlMapping: (data: unknown) => api.post("/payroll/accounting/gl-mappings", data),
  generateAccountingJournal: (runId: number) => api.post(`/payroll/runs/${runId}/accounting-journal`),
  accountingJournals: (runId: number) => api.get(`/payroll/runs/${runId}/accounting-journals`),
  validateStatutoryFile: (data: unknown) => api.post("/payroll/statutory/file-validations", data),
  generateStatutoryTemplate: (templateType: string) => api.post(`/payroll/statutory/templates/${templateType}`),
  statutoryChallans: (params?: Record<string, unknown>) => api.get("/payroll/statutory/challans", { params }),
  generateStatutoryChallan: (data: unknown) => api.post("/payroll/statutory/challans/generate", data),
  statutoryReturnFiles: (params?: Record<string, unknown>) => api.get("/payroll/statutory/return-files", { params }),
  createStatutoryReturnFile: (data: unknown) => api.post("/payroll/statutory/return-files", data),
  taxCycles: () => api.get("/payroll/tax/cycles"),
  createTaxCycle: (data: unknown) => api.post("/payroll/tax/cycles", data),
  taxDeclarations: (params?: Record<string, unknown>) => api.get("/payroll/tax/declarations", { params }),
  createTaxDeclaration: (data: unknown) => api.post("/payroll/tax/declarations", data),
  submitTaxProof: (data: unknown) => api.post("/payroll/tax/proofs", data),
  verifyTaxProof: (id: number, data: unknown) => api.put(`/payroll/tax/proofs/${id}/verify`, data),
  taxProjection: (params: Record<string, unknown>) => api.get("/payroll/tax/projection", { params }),
  taxCompare: (params: Record<string, unknown>) => api.get("/payroll/tax/compare", { params }),
  prorationPreview: (params: Record<string, unknown>) => api.get("/payroll/proration-preview", { params }),
  simulateSalary: (data: unknown) => api.post("/payroll/simulate", data),
  healthDashboard: (params: Record<string, unknown>) => api.get("/payroll/health-dashboard", { params }),
  dispatchPayslips: (runId: number, channels: string[]) =>
    api.post(`/payroll/runs/${runId}/payslip-dispatch?${channels.map((channel) => `channels=${encodeURIComponent(channel)}`).join("&")}`),
  createPayslipQuery: (data: unknown) => api.post("/payroll/payslip-queries", data),
  payslipQueries: (params?: Record<string, unknown>) => api.get("/payroll/payslip-queries", { params }),
  resolvePayslipQuery: (id: number, data: unknown) => api.put(`/payroll/payslip-queries/${id}/resolve`, data),
  createSalaryAdvance: (data: unknown) => api.post("/payroll/salary-advances", data),
  salaryAdvances: (params?: Record<string, unknown>) => api.get("/payroll/salary-advances", { params }),
  reviewSalaryAdvance: (id: number, data: unknown) => api.put(`/payroll/salary-advances/${id}/review`, data),
  createBulkSalaryRevision: (data: unknown) => api.post("/payroll/salary-revisions/bulk", data),
  applyBulkSalaryRevision: (batchId: number) => api.put(`/payroll/salary-revisions/bulk/${batchId}/apply`),
  validateBankDetails: (params: Record<string, unknown>) => api.post("/payroll/bank/validate", null, { params }),
  taxOptimizer: (params: Record<string, unknown>) => api.get("/payroll/tax/optimizer", { params }),
  autoCalculateArrears: (payrollRunId: number) =>
    api.post("/payroll/arrear-runs/auto-calculate", null, { params: { payroll_run_id: payrollRunId } }),
  createBonusPolicy: (data: unknown) => api.post("/payroll/bonus-policies", data),
  bonusPolicies: () => api.get("/payroll/bonus-policies"),
  applyBonusPolicy: (data: unknown) => api.post("/payroll/bonus-policies/apply", data),
  generateGratuityAccruals: (runId: number) => api.post(`/payroll/runs/${runId}/gratuity-accruals`),
  generateSalaryCertificate: (data: unknown) => api.post("/payroll/salary-certificates", data),
  createPayrollBudget: (data: unknown) => api.post("/payroll/budgets", data),
  payrollBudgetVariance: (params: Record<string, unknown>) => api.get("/payroll/budgets/variance", { params }),
  validateBankFile: (params: Record<string, unknown>) => api.post("/payroll/bank-file/validate", null, { params }),
  reconcileTds26As: (data: unknown) => api.post("/payroll/tds-26as/reconcile", data),
  generateForm12BA: (data: unknown) => api.post("/payroll/form-12ba", data),
  downloadForm12BA: (id: number) => api.get(`/payroll/form-12ba/${id}/download`, { responseType: "blob" }),
  submitStatutoryPortal: (params: Record<string, unknown>) => api.post("/payroll/statutory/portal-submit", null, { params }),
  linkExpenseClaimsToReimbursements: (payrollRunId: number) =>
    api.post("/payroll/reimbursements/link-expense-claims", null, { params: { payroll_run_id: payrollRunId } }),
  autoGeneratePayrollPeriods: (params: Record<string, unknown>) =>
    api.post("/payroll/setup/periods/auto-generate", null, { params }),
  sendCutoffReminders: (params: Record<string, unknown>) => api.post("/payroll/cutoff-reminders", null, { params }),
  exchangeRates: (params?: Record<string, unknown>) => api.get("/payroll/exchange-rates", { params }),
  createExchangeRate: (data: unknown) => api.post("/payroll/exchange-rates", data),
  convertCurrency: (params: Record<string, unknown>) => api.get("/payroll/multi-currency/convert", { params }),
  payrollAnalytics: (params?: PayrollAnalyticsParams) => api.get("/payroll/analytics", { params }),
  createPayrollReport: (data: unknown) => api.post("/payroll/reports", data),
  payrollReports: (params?: Record<string, unknown>) => api.get("/payroll/reports", { params }),
  getPayrollReport: (id: number) => api.get(`/payroll/reports/${id}`),
  updatePayrollReport: (id: number, data: unknown) => api.put(`/payroll/reports/${id}`, data),
  deletePayrollReport: (id: number) => api.delete(`/payroll/reports/${id}`),
  runPayrollReport: (id: number, params?: Record<string, unknown>) => api.get(`/payroll/reports/${id}/run`, { params }),
  runPayrollReportWithFilters: (id: number, data: unknown) => api.post(`/payroll/reports/${id}/run`, data),
  exportPayrollReport: (id: number) => api.get(`/payroll/reports/${id}/export`, { responseType: "blob" }),
  reimbursements: (params?: Record<string, unknown>) =>
    api.get("/payroll/reimbursements", { params }),
  createReimbursement: (data: unknown) => api.post("/payroll/reimbursements", data),
  reviewReimbursement: (id: number, data: unknown) =>
    api.put(`/payroll/reimbursements/${id}/review`, data),
  reimbursementLedger: (id: number) => api.get(`/payroll/reimbursements/${id}/ledger`),
  loans: (params?: Record<string, unknown>) => api.get("/payroll/loans", { params }),
  createLoan: (data: unknown) => api.post("/payroll/loans", data),
  loanInstallments: (id: number) => api.get(`/payroll/loans/${id}/installments`),
  loanLedger: (id: number) => api.get(`/payroll/loans/${id}/ledger`),
  settlements: (params?: Record<string, unknown>) =>
    api.get("/payroll/settlements", { params }),
  createSettlement: (data: unknown) => api.post("/payroll/settlements", data),
  approveSettlement: (id: number, remarks?: string) =>
    api.put(`/payroll/settlements/${id}/approve`, null, { params: { remarks } }),
};

export const statutoryComplianceApi = {
  legalEntities: () => api.get("/statutory-compliance/legal-entities"),
  createLegalEntity: (data: unknown) => api.post("/statutory-compliance/legal-entities", data),
  calendar: (params?: Record<string, unknown>) => api.get("/statutory-compliance/calendar", { params }),
  createCalendarEvent: (data: unknown) => api.post("/statutory-compliance/calendar", data),
  form16: (params?: Record<string, unknown>) => api.get("/statutory-compliance/form16", { params }),
  createForm16: (data: unknown) => api.post("/statutory-compliance/form16", data),
  portalSubmissions: (params?: Record<string, unknown>) =>
    api.get("/statutory-compliance/portal-submissions", { params }),
  createPortalSubmission: (data: unknown) => api.post("/statutory-compliance/portal-submissions", data),
  updateCalendarEvent: (id: number, data: unknown) => api.put(`/statutory-compliance/calendar/${id}`, data),
};

export const statutoryApi = {
  calendar: (params?: Record<string, unknown>) => api.get("/statutory/calendar", { params }),
  markFiled: (id: number, data: unknown) => api.put(`/statutory/calendar/${id}/mark-filed`, data),
  generate: (runId: number, type: string) => api.post(`/statutory/generate/${runId}/${type}`),
  submissions: (params?: Record<string, unknown>) => api.get("/statutory/submissions", { params }),
  downloadSubmission: (id: number) =>
    api.get(`/statutory/submissions/${id}/download`, { responseType: "blob" }),
  markSubmitted: (id: number, data: unknown) =>
    api.put(`/statutory/submissions/${id}/mark-submitted`, data),
  complianceSummary: () => api.get("/statutory/compliance-summary"),
  pfEcrPreview: (payrollRunId: number) =>
    api.get("/hrms/compliance/pf-ecr/preview", { params: { payrollRunId } }),
  generatePfEcr: (payrollRunId: number) =>
    api.post("/hrms/compliance/pf-ecr/generate", { payroll_run_id: payrollRunId }),
  esiPreview: (payrollRunId: number) =>
    api.get("/hrms/compliance/esi/preview", { params: { payrollRunId } }),
  generateEsi: (payrollRunId: number) =>
    api.post("/hrms/compliance/esi/generate", { payroll_run_id: payrollRunId }),
  downloadComplianceExport: (id: number) =>
    api.get(`/hrms/compliance/exports/${id}/download`, { responseType: "blob" }),
};

export const form16Api = {
  list: (financialYear: string, employeeId?: number) =>
    api.get("/hrms/form16", { params: { financialYear, employeeId } }),
  generate: (data: unknown) => api.post("/hrms/form16/generate", data),
  uploadPartA: (id: number, formData: FormData) =>
    api.post(`/hrms/form16/${id}/upload-part-a`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  publish: (id: number) => api.post(`/hrms/form16/${id}/publish`),
  download: (id: number) => api.get(`/hrms/form16/${id}/download`, { responseType: "blob" }),
};

export const lmsApi = {
  courses: () => api.get("/lms/courses"),
  createCourse: (data: unknown) => api.post("/lms/courses", data),
  assignments: (params?: Record<string, unknown>) => api.get("/lms/assignments", { params }),
  createAssignment: (data: unknown) => api.post("/lms/assignments", data),
  updateAssignment: (id: number, data: unknown) => api.put(`/lms/assignments/${id}`, data),
  certifications: (params?: Record<string, unknown>) => api.get("/lms/certifications", { params }),
  createCertification: (data: unknown) => api.post("/lms/certifications", data),
  certificationRenewals: (params?: Record<string, unknown>) =>
    api.get("/lms/certification-renewals", { params }),
  createCertificationRenewal: (data: unknown) => api.post("/lms/certification-renewals", data),
  updateCertificationRenewal: (id: number, data: unknown) =>
    api.put(`/lms/certification-renewals/${id}`, data),
  markCertificationRenewalReminders: (dueWithinDays = 30) =>
    api.post("/lms/certification-renewals/reminders", null, { params: { due_within_days: dueWithinDays } }),
  completionCallbackPlaceholder: (assignmentId: number, data: unknown) =>
    api.post(`/lms/assignments/${assignmentId}/completion-callback`, data),
};

export const recruitmentApi = {
  jobs: (params?: Record<string, unknown>) => api.get("/recruitment/jobs", { params }),
  createJob: (data: unknown) => api.post("/recruitment/jobs", data),
  getJob: (id: number) => api.get(`/recruitment/jobs/${id}`),
  updateJob: (id: number, data: unknown) => api.put(`/recruitment/jobs/${id}`, data),
  candidates: (params?: Record<string, unknown>) =>
    api.get("/recruitment/candidates", { params }),
  createCandidate: (data: unknown) => api.post("/recruitment/candidates", data),
  getCandidate: (id: number) => api.get(`/recruitment/candidates/${id}`),
  updateCandidateStatus: (id: number, status: string) =>
    api.put(`/recruitment/candidates/${id}/status`, null, { params: { status } }),
  convertCandidate: (id: number) => api.post(`/recruitment/candidates/${id}/convert`),
  uploadResume: (id: number, formData: FormData) =>
    api.post(`/recruitment/candidates/${id}/resume`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  scheduleInterview: (data: unknown) => api.post("/recruitment/interviews", data),
  getInterviews: (candidateId: number) =>
    api.get(`/recruitment/candidates/${candidateId}/interviews`),
  addFeedback: (interviewId: number, data: unknown) =>
    api.post(`/recruitment/interviews/${interviewId}/feedback`, data),
  createOffer: (data: unknown) => api.post("/recruitment/offers", data),
  updateOfferStatus: (id: number, status: string) =>
    api.put(`/recruitment/offers/${id}/status`, null, { params: { status } }),
};

export const backgroundVerificationApi = {
  vendors: () => api.get("/background-verification/vendors"),
  createVendor: (data: unknown) => api.post("/background-verification/vendors", data),
  requests: (params?: Record<string, unknown>) =>
    api.get("/background-verification/requests", { params }),
  createRequest: (data: unknown) => api.post("/background-verification/requests", data),
  updateRequest: (id: number, data: unknown) =>
    api.put(`/background-verification/requests/${id}`, data),
  captureConsent: (id: number, data: unknown) =>
    api.put(`/background-verification/requests/${id}/consent`, data),
  submitToVendor: (id: number) =>
    api.post(`/background-verification/requests/${id}/submit`),
  updateCheck: (id: number, data: unknown) =>
    api.put(`/background-verification/checks/${id}`, data),
  events: (id: number) => api.get(`/background-verification/requests/${id}/events`),
};

export const performanceApi = {
  cycles: () => api.get("/performance/cycles"),
  createCycle: (data: unknown) => api.post("/performance/cycles", data),
  goals: (cycleId?: number) =>
    api.get("/performance/goals", { params: { cycle_id: cycleId } }),
  createGoal: (data: unknown) => api.post("/performance/goals", data),
  updateGoal: (id: number, data: unknown) => api.put(`/performance/goals/${id}`, data),
  submitReview: (data: unknown) => api.post("/performance/reviews", data),
  calibrationSessions: (params?: Record<string, unknown>) =>
    api.get("/performance/calibration/sessions", { params }),
  createCalibrationSession: (data: unknown) => api.post("/performance/calibration/sessions", data),
  updateCalibrationSession: (id: number, data: unknown) =>
    api.put(`/performance/calibration/sessions/${id}`, data),
  nineBox: (params?: Record<string, unknown>) => api.get("/performance/nine-box", { params }),
  oneOnOnes: (params?: Record<string, unknown>) => api.get("/performance/one-on-ones", { params }),
  createOneOnOne: (data: unknown) => api.post("/performance/one-on-ones", data),
  employeeReviews: (empId: number, cycleId?: number) =>
    api.get(`/performance/reviews/${empId}`, { params: { cycle_id: cycleId } }),
  createGoalCheckIn: (data: unknown) => api.post("/performance/goals/check-ins", data),
  goalCheckIns: (goalId: number) => api.get(`/performance/goals/${goalId}/check-ins`),
  reviewTemplates: (params?: Record<string, unknown>) =>
    api.get("/performance/review-templates", { params }),
  createReviewTemplate: (data: unknown) => api.post("/performance/review-templates", data),
  feedback360Requests: (params?: Record<string, unknown>) =>
    api.get("/performance/360-feedback-requests", { params }),
  createFeedback360Request: (data: unknown) => api.post("/performance/360-feedback-requests", data),
  submitFeedback360: (id: number, data: unknown) =>
    api.put(`/performance/360-feedback-requests/${id}/submit`, data),
  competencies: (params?: Record<string, unknown>) =>
    api.get("/performance/competencies", { params }),
  createCompetency: (data: unknown) => api.post("/performance/competencies", data),
  createRoleSkillRequirement: (data: unknown) =>
    api.post("/performance/role-skill-requirements", data),
  createCompetencyAssessment: (data: unknown) =>
    api.post("/performance/competency-assessments", data),
  skillGap: (employeeId: number) => api.get(`/performance/employees/${employeeId}/skill-gap`),
  criticalRoles: (params?: Record<string, unknown>) =>
    api.get("/performance/succession/critical-roles", { params }),
  createCriticalRole: (data: unknown) => api.post("/performance/succession/critical-roles", data),
  createSuccessionCandidate: (data: unknown) => api.post("/performance/succession/candidates", data),
  compensationCycles: () => api.get("/performance/compensation/cycles"),
  createCompensationCycle: (data: unknown) => api.post("/performance/compensation/cycles", data),
  payBands: () => api.get("/performance/compensation/pay-bands"),
  createPayBand: (data: unknown) => api.post("/performance/compensation/pay-bands", data),
  meritRecommendations: (params?: Record<string, unknown>) =>
    api.get("/performance/compensation/merit-recommendations", { params }),
  createMeritRecommendation: (data: unknown) =>
    api.post("/performance/compensation/merit-recommendations", data),
  reviewMeritRecommendation: (id: number, data: unknown) =>
    api.put(`/performance/compensation/merit-recommendations/${id}`, data),
  compensationWorksheet: (params?: Record<string, unknown>) =>
    api.get("/performance/compensation/worksheet", { params }),
  createCompensationWorksheetRow: (data: unknown) =>
    api.post("/performance/compensation/worksheet", data),
  updateCompensationWorksheetRow: (id: number, data: unknown) =>
    api.put(`/performance/compensation/worksheet/${id}`, data),
};

export const benefitsApi = {
  plans: (params?: Record<string, unknown>) => api.get("/benefits/plans", { params }),
  createPlan: (data: unknown) => api.post("/benefits/plans", data),
  enrollments: (params?: Record<string, unknown>) =>
    api.get("/benefits/enrollments", { params }),
  createEnrollment: (data: unknown) => api.post("/benefits/enrollments", data),
  flexiPolicies: () => api.get("/benefits/flexi-policies"),
  createFlexiPolicy: (data: unknown) => api.post("/benefits/flexi-policies", data),
  createFlexiAllocation: (data: unknown) => api.post("/benefits/flexi-allocations", data),
  createPayrollDeduction: (data: unknown) => api.post("/benefits/payroll-deductions", data),
  claims: (params?: Record<string, unknown>) => api.get("/benefits/claims", { params }),
  createClaim: (data: unknown) => api.post("/benefits/claims", data),
  reviewClaim: (id: number, data: unknown) => api.put(`/benefits/claims/${id}/review`, data),
  esopPlans: () => api.get("/benefits/esop/plans"),
  createEsopPlan: (data: unknown) => api.post("/benefits/esop/plans", data),
  esopGrants: (params?: Record<string, unknown>) => api.get("/benefits/esop/grants", { params }),
  createEsopGrant: (data: unknown) => api.post("/benefits/esop/grants", data),
  esopVesting: (grantId: number) => api.get(`/benefits/esop/grants/${grantId}/vesting`),
};

export const helpdeskApi = {
  categories: () => api.get("/helpdesk/categories"),
  tickets: (params?: Record<string, unknown>) =>
    api.get("/helpdesk/tickets", { params }),
  createTicket: (data: Record<string, unknown>) =>
    api.post("/helpdesk/tickets", null, { params: data }),
  getTicket: (id: number) => api.get(`/helpdesk/tickets/${id}`),
  updateStatus: (id: number, status: string) =>
    api.put(`/helpdesk/tickets/${id}/status`, null, { params: { status } }),
  escalate: (id: number, data: unknown) => api.put(`/helpdesk/tickets/${id}/escalate`, data),
  analytics: () => api.get("/helpdesk/analytics"),
  slaBreaches: () => api.get("/helpdesk/sla/breaches"),
  submitCsat: (id: number, rating: number) =>
    api.put(`/helpdesk/tickets/${id}/csat`, null, { params: { rating } }),
  escalationRules: () => api.get("/helpdesk/escalation-rules"),
  createEscalationRule: (data: unknown) => api.post("/helpdesk/escalation-rules", data),
  knowledge: (params?: Record<string, unknown>) => api.get("/helpdesk/knowledge", { params }),
  createKnowledge: (data: unknown) => api.post("/helpdesk/knowledge", data),
  addReply: (ticketId: number, message: string, isInternal = false) =>
    api.post(`/helpdesk/tickets/${ticketId}/reply`, null, {
      params: { message, is_internal: isInternal },
    }),
  getReplies: (ticketId: number) =>
    api.get(`/helpdesk/tickets/${ticketId}/replies`),
};

export const reportsApi = {
  dashboard: () => api.get("/reports/dashboard"),
  managerDashboard: () => api.get("/reports/manager-dashboard"),
  essSummary: () => api.get("/reports/ess-summary"),
  peopleMoments: (days = 30) => api.get("/reports/people-moments", { params: { days } }),
  globalSearch: (q: string) => api.get("/reports/global-search", { params: { q } }),
  headcountByDept: () => api.get("/reports/headcount-by-department"),
  attendanceTrend: (month?: number, year?: number) =>
    api.get("/reports/attendance-trend", { params: month && year ? { month, year } : undefined }),
  leaveTrend: (year?: number) =>
    api.get("/reports/leave-trend", { params: year ? { year } : undefined }),
  payrollSummary: (year?: number) =>
    api.get("/reports/payroll-summary", { params: year ? { year } : undefined }),
  turnover: (fromDate?: string, toDate?: string) =>
    api.get("/reports/employee-turnover", { params: fromDate && toDate ? { from_date: fromDate, to_date: toDate } : undefined }),
  deiAnalytics: (params?: Record<string, unknown>) =>
    api.get("/reports/dei-analytics", { params }),
  recruitmentFunnel: (jobId?: number) =>
    api.get("/reports/recruitment-funnel", { params: jobId ? { job_id: jobId } : undefined }),
  fieldCatalog: (params?: Record<string, unknown>) => api.get("/reports/field-catalog", { params }),
  definitions: (params?: Record<string, unknown>) => api.get("/reports/definitions", { params }),
  createDefinition: (data: unknown) => api.post("/reports/definitions", data),
  runDefinition: (id: number) => api.get(`/reports/definitions/${id}/run`),
  createSchedule: (data: unknown) => api.post("/reports/schedules", data),
  schedules: (params?: Record<string, unknown>) => api.get("/reports/schedules", { params }),
  runSchedule: (id: number) => api.post(`/reports/schedules/${id}/run`),
  governedMetrics: () => api.get("/reports/analytics/metric-definitions"),
  analyticsDrilldown: (params: Record<string, unknown>) =>
    api.get("/reports/analytics/drilldown", { params }),
};

export const engagementApi = {
  announcements: (publishedOnly = true) =>
    api.get("/engagement/announcements", { params: { published_only: publishedOnly } }),
  createAnnouncement: (data: unknown) => api.post("/engagement/announcements", data),
  surveys: (activeOnly = false) => api.get("/engagement/surveys", { params: { active_only: activeOnly } }),
  createSurvey: (data: unknown) => api.post("/engagement/surveys", data),
  submitSurveyResponse: (data: unknown) => api.post("/engagement/survey-responses", data),
  surveyResults: (id: number) => api.get(`/engagement/surveys/${id}/results`),
  recognitions: () => api.get("/engagement/recognition-wall"),
  createRecognition: (data: unknown) => api.post("/engagement/recognitions", data),
  reactToRecognition: (id: number, data: unknown) =>
    api.post(`/engagement/recognitions/${id}/reactions`, data),
};

export const timesheetsApi = {
  projects: (params?: Record<string, unknown>) =>
    api.get("/timesheets/projects", { params }),
  createProject: (data: unknown) => api.post("/timesheets/projects", data),
  list: (params?: Record<string, unknown>) =>
    api.get("/timesheets/", { params }),
  create: (data: unknown) => api.post("/timesheets/", data),
  addEntry: (timesheetId: number, data: unknown) =>
    api.post(`/timesheets/${timesheetId}/entries`, data),
  submit: (timesheetId: number) => api.put(`/timesheets/${timesheetId}/submit`),
  review: (timesheetId: number, data: unknown) =>
    api.put(`/timesheets/${timesheetId}/review`, data),
};

export const workflowApi = {
  inbox: (mine?: boolean) => api.get("/workflow/inbox", { params: { mine } }),
  definitions: () => api.get("/workflow-engine/definitions"),
  createDefinition: (data: unknown) => api.post("/workflow-engine/definitions", data),
  startInstance: (data: unknown) => api.post("/workflow-engine/instances", data),
  tasks: () => api.get("/workflow-engine/tasks"),
  decideTask: (id: number, data: unknown) =>
    api.put(`/workflow-engine/tasks/${id}/decision`, data),
  sendReminders: () => api.post("/workflow-engine/tasks/send-reminders"),
  processEscalations: () => api.post("/workflow-engine/tasks/process-escalations"),
};

export const approvalOsApi = {
  inbox: (params?: Record<string, unknown>) => api.get("/approval-os/inbox", { params }),
  summary: (params?: Record<string, unknown>) => api.get("/approval-os/summary", { params }),
  createRequest: (data: unknown) => api.post("/approval-os/requests", data),
  getRequest: (id: number) => api.get(`/approval-os/requests/${id}`),
  approve: (id: number, data: unknown) => api.put(`/approval-os/requests/${id}/approve`, data),
  reject: (id: number, data: unknown) => api.put(`/approval-os/requests/${id}/reject`, data),
  addComment: (id: number, data: unknown) => api.post(`/approval-os/requests/${id}/comments`, data),
  history: (id: number) => api.get(`/approval-os/requests/${id}/history`),
  processEscalations: () => api.post("/approval-os/process-escalations"),
};

export const workflowDefinitionsApi = {
  list: (params?: Record<string, unknown>) =>
    api.get("/workflow-engine/definitions", { params }),
  get: (id: number) => api.get(`/workflow-engine/definitions/${id}`),
  create: (data: unknown) => api.post("/workflow-engine/definitions", data),
  update: (id: number, data: unknown) => api.put(`/workflow-engine/definitions/${id}`, data),
  delete: (id: number) => api.delete(`/workflow-engine/definitions/${id}`),
  toggleActive: (id: number) => api.put(`/workflow-engine/definitions/${id}/toggle-active`),
  steps: (id: number) => api.get(`/workflow-engine/definitions/${id}/steps`),
  createStep: (id: number, data: unknown) =>
    api.post(`/workflow-engine/definitions/${id}/steps`, data),
  updateStep: (id: number, stepId: number, data: unknown) =>
    api.put(`/workflow-engine/definitions/${id}/steps/${stepId}`, data),
  deleteStep: (id: number, stepId: number) =>
    api.delete(`/workflow-engine/definitions/${id}/steps/${stepId}`),
  reorderSteps: (id: number, data: unknown) =>
    api.put(`/workflow-engine/definitions/${id}/steps/reorder`, data),
  getSteps: (id: number) => api.get(`/workflow-engine/definitions/${id}/steps`),
  addStep: (id: number, data: unknown) => api.post(`/workflow-engine/definitions/${id}/steps`, data),
  activate: (id: number) => api.put(`/workflow-engine/definitions/${id}/toggle-active`),
  deactivate: (id: number) => api.put(`/workflow-engine/definitions/${id}/toggle-active`),
};

export const notificationsApi = {
  list: (params?: Record<string, unknown>) => api.get("/notifications/", { params }),
  unreadCount: () => api.get("/notifications/unread-count"),
  markRead: (id: number) => api.put(`/notifications/${id}/read`),
  markAllRead: () => api.put("/notifications/mark-all-read"),
  create: (data: unknown) => api.post("/notifications/", data),
};

export const whatsappEssApi = {
  configs: () => api.get("/whatsapp-ess/configs"),
  createConfig: (data: unknown) => api.post("/whatsapp-ess/configs", data),
  messages: () => api.get("/whatsapp-ess/messages"),
  inboundMessage: (data: unknown) => api.post("/whatsapp-ess/messages/inbound", data),
  templates: () => api.get("/whatsapp-ess/templates"),
  createTemplate: (data: unknown) => api.post("/whatsapp-ess/templates", data),
  upsertOptIn: (data: unknown) => api.post("/whatsapp-ess/opt-ins", data),
  outboundMessage: (data: unknown) => api.post("/whatsapp-ess/messages/outbound", data),
  deliveryCallback: (data: unknown) => api.post("/whatsapp-ess/delivery-callbacks", data),
};


export const aiApi = {
  chat: (message: string, history?: unknown[]) =>
    api.post("/ai/assistant", { message, history }),
  policyQA: (question: string) =>
    api.post("/ai/policy-qa", { question }),
  parseResume: (candidateId: number) =>
    api.post(`/ai/parse-resume/${candidateId}`),
  attritionRisk: (departmentId?: number) =>
    api.get("/ai/attrition-risk", { params: { department_id: departmentId } }),
  employeeAttritionRisk: (empId: number) =>
    api.get(`/ai/attrition-risk/${empId}`),
  detectPayrollAnomalies: (runId: number) =>
    api.post(`/ai/payroll-anomaly/${runId}`),
  helpdeskReply: (ticketId: number) =>
    api.post(`/ai/helpdesk-reply/${ticketId}`),
};

export const assetApi = {
  categories: () => api.get("/assets/categories"),
  createCategory: (data: unknown) => api.post("/assets/categories", data),
  list: (params?: Record<string, unknown>) => api.get("/assets/", { params }),
  create: (data: unknown) => api.post("/assets/", data),
  update: (id: number, data: unknown) => api.put(`/assets/${id}`, data),
  assign: (data: unknown) => api.post("/assets/assignments", data),
  returnAsset: (assignmentId: number, condition?: string) =>
    api.put(`/assets/assignments/${assignmentId}/return`, null, {
      params: { condition_at_return: condition },
    }),
};

export const onboardingApi = {
  templates: () => api.get("/onboarding/templates"),
  createTemplate: (data: unknown) => api.post("/onboarding/templates", data),
  employees: () => api.get("/onboarding/employees"),
  start: (data: unknown) => api.post("/onboarding/employees", data),
  complete: (id: number) => api.put(`/onboarding/employees/${id}/complete`),
  acknowledgePolicy: (data: unknown) =>
    api.post("/onboarding/policy-acknowledgements", data),
};

export const documentsApi = {
  templates: () => api.get("/documents/templates"),
  createTemplate: (data: unknown) => api.post("/documents/templates", data),
  policies: () => api.get("/documents/policies"),
  createPolicy: (data: unknown) => api.post("/documents/policies", data),
  policyVersions: (policyId: number) => api.get(`/documents/policies/${policyId}/versions`),
  publishPolicyVersion: (policyId: number, data: unknown) =>
    api.post(`/documents/policies/${policyId}/versions`, data),
  generated: (employeeId?: number) =>
    api.get("/documents/generated", { params: { employee_id: employeeId } }),
  createGenerated: (data: unknown) => api.post("/documents/generated", data),
  certificates: (params?: Record<string, unknown>) =>
    api.get("/documents/certificates", { params }),
  uploadCertificate: (formData: FormData) =>
    api.post("/documents/certificates", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  verifyCertificate: (id: number, data: unknown) =>
    api.put(`/documents/certificates/${id}/verify`, data),
  importCertificates: (formData: FormData) =>
    api.post("/documents/certificates/imports", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  certificateBatches: (params?: Record<string, unknown>) =>
    api.get("/documents/certificates/import-export", { params }),
};

export const exitApi = {
  records: () => api.get("/exit/records"),
  createRecord: (data: unknown) => api.post("/exit/records", data),
  updateRecord: (id: number, data: unknown) => api.put(`/exit/records/${id}`, data),
  approveRecord: (id: number) => api.put(`/exit/records/${id}/approve`),
  createChecklistItem: (data: unknown) => api.post("/exit/checklist", data),
  completeChecklistItem: (id: number, remarks?: string) =>
    api.put(`/exit/checklist/${id}/complete`, null, { params: { remarks } }),
};

export const fnfApi = {
  list: (params?: Record<string, unknown>) => api.get("/hrms/fnf-settlements", { params }),
  get: (id: number) => api.get(`/hrms/fnf-settlements/${id}`),
  generate: (data: unknown) => api.post("/hrms/fnf-settlements/generate", data),
  update: (id: number, data: unknown) => api.patch(`/hrms/fnf-settlements/${id}`, data),
  submit: (id: number) => api.post(`/hrms/fnf-settlements/${id}/submit`),
  approve: (id: number, data?: unknown) => api.post(`/hrms/fnf-settlements/${id}/approve`, data ?? {}),
  reject: (id: number, data: unknown) => api.post(`/hrms/fnf-settlements/${id}/reject`, data),
  markPaid: (id: number, data?: unknown) => api.post(`/hrms/fnf-settlements/${id}/mark-paid`, data ?? {}),
  pdf: (id: number) => api.get(`/hrms/fnf-settlements/${id}/pdf`, { responseType: "blob" }),
};

export const taxDeclarationApi = {
  categories: (financialYear: string) => api.get("/hrms/tax-declaration/categories", { params: { financialYear } }),
  createCategory: (data: unknown) => api.post("/hrms/tax-declaration/categories", data),
  list: (params?: Record<string, unknown>) => api.get("/hrms/tax-declarations", { params }),
  employeeDeclarations: (employeeId: number, financialYear: string) =>
    api.get(`/hrms/employees/${employeeId}/tax-declarations`, { params: { financialYear } }),
  create: (data: unknown) => api.post("/hrms/tax-declarations", data),
  update: (id: number, data: unknown) => api.patch(`/hrms/tax-declarations/${id}`, data),
  submit: (id: number) => api.post(`/hrms/tax-declarations/${id}/submit`),
  review: (id: number, data: unknown) => api.post(`/hrms/tax-declarations/${id}/review`, data),
  uploadProof: (id: number, formData: FormData) =>
    api.post(`/hrms/tax-declarations/${id}/upload-proof`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  downloadProof: (id: number) => api.get(`/hrms/tax-proofs/${id}/download`, { responseType: "blob" }),
};

export const probationApi = {
  dashboard: () => api.get("/hrms/probation/dashboard"),
  dueList: (params?: Record<string, unknown>) => api.get("/hrms/probation/due-list", { params }),
  review: (employeeId: number, data: unknown) => api.post(`/hrms/probation/${employeeId}/review`, data),
  confirm: (employeeId: number, data: unknown) => api.post(`/hrms/probation/${employeeId}/confirm`, data),
  extend: (employeeId: number, data: unknown) => api.post(`/hrms/probation/${employeeId}/extend`, data),
  terminate: (employeeId: number, data: unknown) => api.post(`/hrms/probation/${employeeId}/terminate`, data),
  letter: (employeeId: number) => api.get(`/hrms/probation/${employeeId}/letter`, { responseType: "blob" }),
  runAlerts: () => api.post("/hrms/probation/alerts/run"),
};
