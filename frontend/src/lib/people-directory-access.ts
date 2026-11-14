// Keep directory visibility aligned with the API's can_explore_directory policy.
const directoryRoles = new Set([
  "super_admin", "admin", "hr", "hr_admin", "hr_manager", "hr_company_admin",
  "hr_workflow_admin", "hr_custom_field_admin", "manager", "team_lead",
  "department_head", "ceo", "founder", "director", "executive", "pms_org_admin",
]);

export function canExplorePeopleDirectory(role?: string | null, isSuperuser = false) {
  return isSuperuser || directoryRoles.has((role || "").toLowerCase().replace(/ /g, "_"));
}
