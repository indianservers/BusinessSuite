import { useAuthStore } from "@/store/authStore";
import { selectedBranch } from "@/lib/branch-context";
export type VerificationCheck = {
  id: number; check_type: string; status: string; result: string | null;
  employee_document_id: number | null; document_url: string | null;
  verified_by: string | null; verified_at: string | null; remarks: string | null;
};
export type VerificationCase = {
  id: number; employee_id: number | null; candidate_id: number | null;
  package_name: string; purpose: string | null; status: string; overall_result: string | null;
  vendor_id: number | null; vendor_reference: string | null; vendor_status: string | null;
  consent_status: string; consent_url: string | null; consent_captured_at: string | null;
  owner_name: string | null; reviewer_name: string | null;
  owner_user_id: number | null; expected_completion_date: string | null;
  initiated_at: string; completed_at: string | null; submitted_at: string | null;
  reviewed_at: string | null; reviewed_by: number | null; review_notes: string | null;
  report_url: string | null; remarks: string | null; version: number; checks: VerificationCheck[];
};
export type EmployeeFile = {
  legacy_verification: {status: string | null; date: string | null; agency: string | null} | null;
  employee: {id: number; employee_code: string; name: string; status: string; date_of_joining: string; date_of_exit: string | null; former: boolean; archived: boolean};
  background: {email: string | null; phone: string | null; address: string | null; branch: string | null; department: string | null; designation: string | null;
    education: {id: number; degree: string; institution: string | null; pass_year: number | null; document_url: string | null}[];
    experience: {id: number; company_name: string; designation: string | null; from_date: string | null; to_date: string | null; relieving_letter_url: string | null}[]};
  cases: VerificationCase[];
  documents: {id: number; document_name: string | null; document_type: string; file_url: string | null; verification_status: string}[];
  certificates: {id: number; title: string; file_url: string; verification_status: string}[];
  letters: {id: number; name: string; type: string; file_url: string | null}[];
  studio_letters: {id: number; name: string; type: string; status: string; issue_date: string}[];
  exits: {id: number; exit_type: string | null; last_working_date: string | null; resignation_date: string | null; reason: string | null; status: string; checklist: {id: number; task_name: string; is_completed: boolean; remarks: string | null; assigned_to_role: string | null}[]}[];
  settlements: {id: number; status: string; paid_at: string | null; exit_record_id: number | null}[];
  active_assets: number | null; login_active: boolean;
  restricted: {exit: boolean; payroll: boolean; assets: boolean};
  missing: string[];
  history: {id: number; event_type: string; event_date: string; from_status: string | null; to_status: string | null; reason: string | null}[];
};
export type Vendor = {id: number; name: string; status: string};
export function verificationError(error: unknown): string {
  const detail = (error as {response?: {data?: {detail?: unknown}}})?.response?.data?.detail;
  return typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map(v => v.msg || "Invalid value").join("; ") : "Could not save. Please retry.";
}

export function verificationPhoneScope(employeeId: number) {
  const actor = useAuthStore.getState().user;
  let context: unknown[] = [];
  try { context = [sessionStorage.getItem("suite-tenant"), sessionStorage.getItem("suite-organization"), selectedBranch()]; } catch { /* Current in-memory identity still scopes the editor. */ }
  return JSON.stringify([employeeId, actor?.id, actor?.employee_id, actor?.role, actor?.is_superuser, actor?.access, ...context]);
}
