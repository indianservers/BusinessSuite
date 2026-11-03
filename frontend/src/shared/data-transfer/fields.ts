import type { TransferField } from "./transfer";
export const employeeImportFields: TransferField[] = [
  { key: "first_name", required: true },
  { key: "last_name" },
  { key: "date_of_joining", type: "date", required: true },
  { key: "employee_id", hint: "Optional; generated when empty" },
  { key: "personal_email", type: "email" },
  { key: "phone_number" },
  { key: "phone_number_country_code", hint: "For example +91" },
  { key: "date_of_confirmation", type: "date" },
  { key: "employment_type", hint: "Full-time, Part-time, Contract or Intern" },
  { key: "status", hint: "Active or Inactive" },
  { key: "work_location" },
  ...[
    "branch_id",
    "department_id",
    "designation_id",
    "reporting_manager_id",
  ].map((key) => ({
    key,
    type: "number" as const,
    hint: "Existing record ID",
  })),
];
export const catalogImportFields: TransferField[] = [
  { key: "name", required: true },
  { key: "code", label: "SKU / Code", required: true },
  {
    key: "kind",
    required: true,
    default: "product",
    hint: "product or service",
  },
  { key: "category" },
  { key: "description" },
  { key: "price", type: "number" },
  { key: "currency", hint: "Three-letter currency, e.g. INR" },
  { key: "tax", type: "number" },
  { key: "unit" },
  { key: "status", hint: "Active or Archived" },
  { key: "workspace_id", type: "number" },
  { key: "images", hint: "JSON array of image URLs" },
  { key: "custom_fields", hint: "JSON object" },
  { key: "pricing_options", hint: "JSON array of pricing options" },
];
export const bankStatementFields: TransferField[] = [
  { key: "transaction_date", type: "date", required: true },
  { key: "description", required: true },
  { key: "reference_number" },
  { key: "debit_amount", type: "number" },
  { key: "credit_amount", type: "number" },
  { key: "balance", type: "number" },
];
export const bankResultFields: TransferField[] = [
  { key: "payroll_record_id", type: "number", hint: "Map this or Employee ID" },
  { key: "employee_id", type: "number", hint: "Existing internal employee ID" },
  {
    key: "status",
    required: true,
    hint: "Paid or Failed",
    aliases: ["payment_status"],
  },
  {
    key: "reference",
    hint: "Required for Paid",
    aliases: ["utr_number", "transaction reference"],
  },
  { key: "failure_reason", hint: "Required for Failed" },
];
export const certificateImportFields: TransferField[] = [
  { key: "title", required: true },
  { key: "employee_id", type: "number" },
  { key: "certificate_number" },
  { key: "issue_date", type: "date" },
  { key: "expiry_date", type: "date" },
  { key: "issuer" },
  { key: "remarks" },
];
