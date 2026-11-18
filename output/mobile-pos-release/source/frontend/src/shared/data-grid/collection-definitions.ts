/** Default display columns are defined even for empty datasets. Optional fields appear when supplied by the owning API. */
export function collectionDefinition(scope: string): { entity: string; columns: string[] } {
  const definitions: [RegExp,string,string[]][] = [
    [/benefits.*records-1/i,"Benefit plan",["name","plan_type","provider","employer_contribution","employee_contribution"]],
    [/benefits.*records-2/i,"Claim",["claim_type","employee_id","claim_amount","status"]],
    [/onboarding.*records/i,"Onboarding",["employee_id","status","start","expected_end"]],
    [/exit.*records/i,"Exit record",["employee_id","exit_type","status","resignation_date","last_working_date"]],
    [/recruitment/i,"Job title",["name","department","type","status","created"]],
    [/assets.*custody/i,"Asset",["name","code","employee_id","status","assigned_date","returned_date"]],
    [/assets/i,"Asset",["name","code","category","status"]],
    [/lms.*records-1|courses/i,"Course",["name","code","category","delivery_mode","duration"]],
    [/lms/i,"Course",["name","course","employee_id","status"]],
    [/expenses/i,"Expense claim",["claim_type","amount","approved_amount","currency","status","expense_date"]],
    [/developer.*logs/i,"API request",["method","path","response_code","duration_ms","created"]],
    [/sentmessages|delivery-logs|deliveries/i,"Message",["channel","template","status","created"]],
    [/action-log|audit|activity.*records/i,"Event",["event","module","status","created"]],
    [/tasks/i,"Task",["name","status","priority","owner","start","due"]],
    [/approvals/i,"Request",["name","request_type","requested_by","status","created"]],
    [/reports|analytics/i,"Report",["name","module","status","next_run","updated"]],
    [/integrations|ConnectorCatalog/i,"Connector",["name","type","status","updated"]],
    [/workflow/i,"Workflow",["name","status","version","updated"]],
    [/automations/i,"Automation",["name","status","version","updated"]],
    [/templates/i,"Template",["name","type","status","updated"]],
    [/certificat/i,"Certificate",["name","employee_id","status","created"]],
    [/marketplace/i,"Application",["name","type","status","version"]],
    [/notifications/i,"Notification",["name","type","status","created"]],
    [/business-os.*modules/i,"Module",["name","module","status","version"]],
    [/campaign/i,"Campaign",["name","channel","status","start","due"]],
    [/forms/i,"Form",["name","status","version","updated"]],
    [/ai-agent/i,"Agent",["name","status","type","updated"]],
  ];
  const found=definitions.find(([pattern])=>pattern.test(scope));
  return found?{entity:found[1],columns:found[2]}:{entity:"Name",columns:["name","status","updated"]};
}
