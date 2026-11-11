import { fresh, question, type Definition, type Kind } from "./formsTypes";

export const formTemplates = [
  { id: "feedback", name: "Feedback Form", description: "Survey and collect feedback", color: "#0d9488", icon: "☆" },
  { id: "project", name: "Project Intake", description: "Streamline new project requests", color: "#db2777", icon: "▤" },
  { id: "order", name: "Order Form", description: "Capture and process client orders", color: "#7c3aed", icon: "▱" },
  { id: "job", name: "Job Application", description: "Accept and review applications for open roles", color: "#ea580c", icon: "♙" },
  { id: "it", name: "IT Requests", description: "Triage and prioritize IT service requests", color: "#4f46e5", icon: "≡" },
  { id: "blank", name: "Start from scratch", description: "Bring your own ideas to a blank canvas", color: "#64748b", icon: "+" },
];
type Field = [Kind, string, string[]?];
const fields: Record<string, Field[]> = {
  feedback: [["text", "Your name"], ["email", "Email address"], ["rating", "How was your experience?"], ["radio", "Would you recommend us?", ["Yes", "Maybe", "No"]], ["textarea", "What could we improve?"]],
  project: [["text", "Project name"], ["text", "Your name"], ["email", "Work email"], ["textarea", "Tell us about your project"], ["select", "Budget range", ["Under 1,000", "1,000–5,000", "5,000–20,000", "20,000+"]], ["date", "Target launch date"], ["file", "Supporting documents"]],
  order: [["text", "Order reference"], ["text", "Customer name"], ["email", "Email address"], ["phone", "Phone number"], ["textarea", "Products or services requested"], ["number", "Quantity"], ["textarea", "Delivery address"], ["date", "Preferred delivery date"]],
  job: [["text", "Full name"], ["email", "Email address"], ["phone", "Phone number"], ["text", "Position you are applying for"], ["url", "Portfolio or LinkedIn URL"], ["file", "Upload your resume"], ["textarea", "Why would you be a great fit?"], ["checkbox", "I consent to being contacted about my application"]],
  it: [["text", "Request subject"], ["email", "Work email"], ["select", "Request category", ["Hardware", "Software", "Account access", "Network", "Other"]], ["radio", "Urgency", ["Low", "Normal", "High", "Critical"]], ["textarea", "Describe the issue"], ["file", "Screenshot or attachment"]],
};
export function createFormTemplate(id: string): Definition {
  const d = fresh();
  const template = formTemplates.find(t => t.id === id);
  if (!template || id === "blank") return { ...d, description: "", fields: [], workflow: { ...d.workflow, title_field: "" } };
  d.name = template.name;
  d.description = template.description + ". Fill in the details below to get started.";
  d.accent = template.color;
  d.submit_label = id === "job" ? "Submit application" : id === "order" ? "Submit order" : "Send response";
  d.settings = { ...d.settings!, columns: 1, surface: "minimal" };
  d.fields = fields[id].map(([type, label, options], i) => ({ ...question(type, label), required: i < 2, ...(options ? { options } : {}), ...(type === "number" ? { min: 1 } : {}) }));
  d.workflow.title_field = d.fields[0].id;
  return d;
}
