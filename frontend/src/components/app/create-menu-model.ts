export type CreateGroup = "Work" | "Sales" | "People & requests" | "Content" | "Collaboration" | "Configuration";
export function createGroup(label: string, module: string): CreateGroup {
  if (/field|tag|dashboard|view list|whiteboard|asset|form/i.test(label)) return "Configuration";
  if (/conversation|invitation|workspace|space/i.test(label)) return "Collaboration";
  if (/document|page|note|sheet|artifact|clip|folder|letter/i.test(label)) return "Content";
  return module === "hrms" ? "People & requests" : module === "crm" ? "Sales" : "Work";
}
export function createPriority(label: string, module: string, employee = false) {
  const order = module === "pms" ? ["Task", "Quick task", "Subtask", "Project", "Document"] : module === "crm" ? ["Add Lead", "Contact", "Company", "Add Customer", "Deal", "Reminder"] : employee ? ["Apply for leave", "Submit expense", "Support ticket", "Correct attendance"] : ["Add employee", "Bulk add employees", "Correct attendance", "Generate letter", "Apply for leave"];
  const index = order.indexOf(label);
  return index < 0 ? 100 : index;
}
export const createDescriptions: Record<string, string> = {
  "Add Lead": "A potential buyer to qualify · quick capture",
  Contact: "An individual person you communicate with",
  Company: "An organization linked to contacts and deals",
  "Add Customer": "A person or company that buys from you",
  Deal: "A sales opportunity with a value and pipeline stage",
};
