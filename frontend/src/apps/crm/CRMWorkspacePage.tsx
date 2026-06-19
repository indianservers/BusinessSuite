import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  closestCorners,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useLocation, useNavigate } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  ArrowUpDown,
  BarChart3,
  Bell,
  Building2,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock,
  Download,
  Edit3,
  FileCheck2,
  Filter,
  GitMerge,
  GripVertical,
  IndianRupee,
  LayoutGrid,
  ListFilter,
  Mail,
  Megaphone,
  Package,
  Phone,
  Plus,
  Save,
  Search,
  Sparkles,
  Target,
  Upload,
  Users,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { exportRows } from "@/lib/export";
import { formatCurrency, formatDate, statusColor } from "@/lib/utils";
import { crmApi, type CRMApiRecord, type CRMApiValue, type CRMApprovalRequest, type CRMApprovalWorkflow, type CRMCalendarEvent, type CRMDuplicateGroup, type CRMWinLossReport } from "./api";

type CRMLead = {
  id: number;
  name: string;
  company: string;
  email?: string;
  phone?: string;
  source: string;
  status: string;
  rating: string;
  leadScore: number;
  scoreLabel: string;
  owner?: string;
  value: number;
  nextFollowUp?: string;
  lastContacted?: string;
  industry?: string;
};

type CRMDeal = {
  id: number;
  name: string;
  company: string;
  contact: string;
  owner: string;
  pipelineId: number;
  stageId: number;
  stage: string;
  amount: number;
  probability: number;
  closeDate: string;
  nextStep: string;
  products: string[];
};

type CRMRecord = CRMApiRecord;

const emptyRecords: CRMRecord[] = [];
const emptyLeads: CRMLead[] = [];
const emptyDeals: CRMDeal[] = [];

type CRMPageKind =
  | "dashboard"
  | "leads"
  | "contacts"
  | "companies"
  | "deals"
  | "pipeline"
  | "pipelineSettings"
  | "activities"
  | "tasks"
  | "calendar"
  | "calendarIntegrations"
  | "webhooks"
  | "campaigns"
  | "products"
  | "services"
  | "priceBooks"
  | "quotes"
  | "quoteBuilder"
  | "quoteApprovals"
  | "cpq"
  | "guidedSelling"
  | "quotations"
  | "approvalSettings"
  | "myApprovals"
  | "duplicates"
  | "territories"
  | "tickets"
  | "files"
  | "reports"
  | "automation"
  | "leadCash"
  | "forecasting"
  | "targets"
  | "salesPerformance"
  | "funnel"
  | "lostAnalysis"
  | "customer360"
  | "importExport"
  | "settings"
  | "leadScoring"
  | "featureChecklist"
  | "admin";

const pageTitles: Record<CRMPageKind, string> = {
  dashboard: "CRM Dashboard",
  leads: "Leads",
  contacts: "Contacts",
  companies: "Accounts",
  deals: "Deals",
  pipeline: "Sales Pipeline",
  pipelineSettings: "Pipeline Settings",
  activities: "Activities",
  tasks: "CRM Tasks",
  calendar: "Calendar",
  calendarIntegrations: "Calendar Integrations",
  webhooks: "Webhooks",
  campaigns: "Campaigns",
  products: "Products",
  services: "Services",
  priceBooks: "Price Books",
  quotes: "Quotes",
  quoteBuilder: "Quote Builder",
  quoteApprovals: "Quote Approvals",
  cpq: "CPQ Rules",
  guidedSelling: "Guided Selling",
  quotations: "Quotations",
  approvalSettings: "Approval Settings",
  myApprovals: "My Approvals",
  duplicates: "Duplicate Management",
  territories: "Territory Settings",
  tickets: "Support Tickets",
  files: "Files",
  reports: "Reports",
  automation: "Automation",
  leadCash: "Lead-to-Cash",
  forecasting: "Forecasting",
  targets: "Sales Targets",
  salesPerformance: "Sales Performance",
  funnel: "Sales Funnel",
  lostAnalysis: "Lost Analysis",
  customer360: "Customer 360",
  importExport: "Import & Export",
  settings: "CRM Settings",
  leadScoring: "Lead Scoring",
  featureChecklist: "Feature Checklist",
  admin: "CRM Admin",
};

const savedViews = ["My records", "Hot pipeline", "Due this week", "No follow-up", "Recently updated"];
type CRMFilters = { owner: string; status: string; type: string; territory: string };
type SortState = { key: string; direction: "asc" | "desc" } | null;
type DashboardQuickCreateKind = "leads" | "contacts" | "companies" | "deals" | "tasks";

const dashboardQuickCreateKinds: Array<{ kind: DashboardQuickCreateKind; label: string }> = [
  { kind: "leads", label: "Lead" },
  { kind: "contacts", label: "Contact" },
  { kind: "companies", label: "Company" },
  { kind: "deals", label: "Deal" },
  { kind: "tasks", label: "Task" },
];

type CRMBusinessTemplate = {
  key: string;
  name: string;
  group: "Teams" | "Industries";
  category: string;
  accent: string;
  description?: string;
  fieldEntity?: string;
  sampleRecord?: string;
  stages: Array<{ name: string; probability: number; color: string; isWon?: boolean; isLost?: boolean }>;
  fields: string[];
  customFields?: CRMTemplateCustomField[];
  sampleDeals?: CRMTemplateSampleDeal[];
  automations: string[];
  reports: string[];
};

type CRMTemplateCustomField = {
  entityType: "leads" | "contacts" | "companies" | "deals" | "quotations" | "tasks";
  fieldName: string;
  fieldKey: string;
  fieldType: "text" | "long_text" | "number" | "currency" | "date" | "datetime" | "dropdown" | "multi_select" | "checkbox" | "email" | "phone" | "url" | "user" | "owner";
  options?: string[];
  isRequired?: boolean;
  isUnique?: boolean;
  isVisible?: boolean;
  isFilterable?: boolean;
};

type CRMTemplateSampleDeal = {
  name: string;
  company: string;
  amount: number;
  stageIndex?: number;
  closeDate: string;
  source: string;
  nextStep: string;
  customFields?: Record<string, CRMApiValue>;
};

const crmBusinessTemplates: CRMBusinessTemplate[] = [
  { key: "sales-pipeline", name: "Sales Pipeline", group: "Teams", category: "Core Sales", accent: "#2563eb", stages: [{ name: "Qualification", probability: 20, color: "#2563eb" }, { name: "Needs Analysis", probability: 35, color: "#0891b2" }, { name: "Proposal", probability: 55, color: "#7c3aed" }, { name: "Negotiation", probability: 75, color: "#d97706" }, { name: "Closed Won", probability: 100, color: "#059669", isWon: true }, { name: "Closed Lost", probability: 0, color: "#dc2626", isLost: true }], fields: ["Lead source", "Deal value", "Expected close", "Competitor", "Next step"], automations: ["Owner assignment", "No-response reminder", "Won handoff"], reports: ["Pipeline value", "Forecast", "Lost reasons"] },
  { key: "customer-support", name: "Customer Support", group: "Teams", category: "Support", accent: "#0891b2", stages: [{ name: "New Request", probability: 10, color: "#0891b2" }, { name: "Triage", probability: 25, color: "#2563eb" }, { name: "In Progress", probability: 50, color: "#7c3aed" }, { name: "Customer Review", probability: 75, color: "#d97706" }, { name: "Resolved", probability: 100, color: "#059669", isWon: true }], fields: ["Issue type", "SLA", "Priority", "Product", "Resolution"], automations: ["SLA escalation", "Customer update", "Reopen alert"], reports: ["Open cases", "SLA breaches", "Resolution time"] },
  { key: "customer-onboarding", name: "Customer Onboarding", group: "Teams", category: "Success", accent: "#0f766e", stages: [{ name: "Kickoff", probability: 15, color: "#0f766e" }, { name: "Setup", probability: 35, color: "#2563eb" }, { name: "Training", probability: 55, color: "#7c3aed" }, { name: "Go Live", probability: 85, color: "#d97706" }, { name: "Adopted", probability: 100, color: "#059669", isWon: true }], fields: ["Plan", "Stakeholders", "Launch date", "Training owner", "Adoption score"], automations: ["Kickoff task pack", "Training reminder", "CS handoff"], reports: ["Activation", "Time to value", "At-risk onboardings"] },
  { key: "customer-testimonials", name: "Customer Testimonials", group: "Teams", category: "Marketing", accent: "#be185d", stages: [{ name: "Candidate", probability: 20, color: "#be185d" }, { name: "Outreach", probability: 35, color: "#7c3aed" }, { name: "Interview", probability: 60, color: "#2563eb" }, { name: "Approval", probability: 80, color: "#d97706" }, { name: "Published", probability: 100, color: "#059669", isWon: true }], fields: ["Customer story", "Use case", "Approver", "Asset type", "Publish date"], automations: ["Consent check", "Approval reminder", "Publish handoff"], reports: ["Story pipeline", "Assets by industry", "Approval aging"] },
  { key: "project-tracker", name: "Project Tracker", group: "Teams", category: "Delivery", accent: "#7c3aed", stages: [{ name: "Intake", probability: 10, color: "#7c3aed" }, { name: "Scoped", probability: 30, color: "#2563eb" }, { name: "In Delivery", probability: 55, color: "#0891b2" }, { name: "UAT", probability: 80, color: "#d97706" }, { name: "Delivered", probability: 100, color: "#059669", isWon: true }], fields: ["Project owner", "Budget", "Milestone", "Risk", "Delivery date"], automations: ["Milestone reminder", "Risk escalation", "PMS project handoff"], reports: ["Delivery value", "Milestone health", "Budget risk"] },
  { key: "recruitment", name: "Recruitment", group: "Teams", category: "Hiring", accent: "#9333ea", stages: [{ name: "Sourced", probability: 10, color: "#9333ea" }, { name: "Screening", probability: 30, color: "#2563eb" }, { name: "Interview", probability: 55, color: "#0891b2" }, { name: "Offer", probability: 80, color: "#d97706" }, { name: "Hired", probability: 100, color: "#059669", isWon: true }, { name: "Rejected", probability: 0, color: "#dc2626", isLost: true }], fields: ["Role", "Candidate source", "Notice period", "CTC", "Hiring manager"], automations: ["Interview schedule", "Offer approval", "Candidate update"], reports: ["Hiring funnel", "Source quality", "Offer aging"] },
  { key: "refund-processing", name: "Refund Processing", group: "Teams", category: "Finance Ops", accent: "#ca8a04", stages: [{ name: "Request", probability: 10, color: "#ca8a04" }, { name: "Validation", probability: 35, color: "#2563eb" }, { name: "Approval", probability: 60, color: "#d97706" }, { name: "Payment", probability: 85, color: "#0891b2" }, { name: "Closed", probability: 100, color: "#059669", isWon: true }], fields: ["Invoice", "Reason", "Amount", "Approval owner", "Refund mode"], automations: ["Eligibility check", "Approval route", "Payment reminder"], reports: ["Refund value", "Aging", "Approval SLA"] },
  { key: "order-fulfillment", name: "Order Fulfillment", group: "Teams", category: "Operations", accent: "#ea580c", stages: [{ name: "Order Received", probability: 15, color: "#ea580c" }, { name: "Packed", probability: 35, color: "#2563eb" }, { name: "Dispatched", probability: 65, color: "#0891b2" }, { name: "Delivered", probability: 90, color: "#d97706" }, { name: "Completed", probability: 100, color: "#059669", isWon: true }], fields: ["Order ID", "Items", "Warehouse", "Courier", "Delivery SLA"], automations: ["Dispatch alert", "Delay escalation", "Delivery confirmation"], reports: ["Orders by status", "Delay reasons", "Fulfillment SLA"] },
  { key: "website-launch", name: "Website Launch", group: "Teams", category: "Marketing Ops", accent: "#0284c7", stages: [{ name: "Brief", probability: 10, color: "#0284c7" }, { name: "Design", probability: 30, color: "#7c3aed" }, { name: "Build", probability: 55, color: "#2563eb" }, { name: "QA", probability: 80, color: "#d97706" }, { name: "Launched", probability: 100, color: "#059669", isWon: true }], fields: ["Domain", "Launch date", "Content owner", "SEO checklist", "QA owner"], automations: ["Content reminder", "QA checklist", "Launch approval"], reports: ["Launch readiness", "Blocked tasks", "Post-launch issues"] },
  { key: "press-release", name: "Press Release", group: "Teams", category: "PR", accent: "#475569", stages: [{ name: "Idea", probability: 10, color: "#475569" }, { name: "Draft", probability: 35, color: "#2563eb" }, { name: "Review", probability: 60, color: "#7c3aed" }, { name: "Distribution", probability: 85, color: "#d97706" }, { name: "Published", probability: 100, color: "#059669", isWon: true }], fields: ["Announcement", "Spokesperson", "Media list", "Approval", "Publish date"], automations: ["Legal approval", "Media follow-up", "Coverage tracking"], reports: ["Release calendar", "Coverage", "Approval aging"] },
  { key: "event-sponsorship", name: "Event Sponsorship", group: "Teams", category: "Events", accent: "#16a34a", stages: [{ name: "Target Event", probability: 15, color: "#16a34a" }, { name: "Proposal", probability: 35, color: "#2563eb" }, { name: "Negotiation", probability: 65, color: "#d97706" }, { name: "Booked", probability: 90, color: "#0891b2" }, { name: "Completed", probability: 100, color: "#059669", isWon: true }], fields: ["Event date", "Package", "Audience", "Sponsor fee", "Deliverables"], automations: ["Budget approval", "Asset deadline", "Post-event follow-up"], reports: ["Event ROI", "Sponsor pipeline", "Deliverable status"] },
  { key: "content-planner", name: "Content Planner", group: "Teams", category: "Content", accent: "#db2777", stages: [{ name: "Backlog", probability: 10, color: "#db2777" }, { name: "Writing", probability: 35, color: "#2563eb" }, { name: "Design", probability: 55, color: "#7c3aed" }, { name: "Review", probability: 80, color: "#d97706" }, { name: "Published", probability: 100, color: "#059669", isWon: true }], fields: ["Topic", "Channel", "Writer", "Designer", "Publish date"], automations: ["Brief reminder", "Review approval", "Publish task"], reports: ["Content velocity", "Channel mix", "Review bottlenecks"] },
  { key: "employee-onboarding", name: "Employee Onboarding", group: "Teams", category: "People Ops", accent: "#4f46e5", stages: [{ name: "Offer Accepted", probability: 20, color: "#4f46e5" }, { name: "Documents", probability: 40, color: "#2563eb" }, { name: "Assets", probability: 60, color: "#0891b2" }, { name: "Day One", probability: 85, color: "#d97706" }, { name: "Onboarded", probability: 100, color: "#059669", isWon: true }], fields: ["Joining date", "Department", "Manager", "Asset kit", "Document status"], automations: ["Document reminder", "Asset request", "Welcome workflow"], reports: ["Joining pipeline", "Document gaps", "Onboarding SLA"] },
  { key: "real-estate", name: "Real Estate", group: "Industries", category: "Property Sales", accent: "#0f766e", stages: [{ name: "Inquiry", probability: 10, color: "#0f766e" }, { name: "Site Visit", probability: 30, color: "#2563eb" }, { name: "Shortlisted", probability: 55, color: "#7c3aed" }, { name: "Booking", probability: 80, color: "#d97706" }, { name: "Registration", probability: 100, color: "#059669", isWon: true }], fields: ["Project", "Unit type", "Budget", "Visit date", "Broker"], automations: ["Visit reminder", "Payment follow-up", "Booking approval"], reports: ["Inventory interest", "Broker performance", "Booking forecast"] },
  { key: "facility-maintenance", name: "Facility Maintenance", group: "Industries", category: "Services", accent: "#64748b", stages: [{ name: "Service Request", probability: 10, color: "#64748b" }, { name: "Inspection", probability: 30, color: "#2563eb" }, { name: "Estimate", probability: 55, color: "#d97706" }, { name: "Work Order", probability: 80, color: "#0891b2" }, { name: "Completed", probability: 100, color: "#059669", isWon: true }], fields: ["Site", "Asset", "Issue type", "Technician", "SLA"], automations: ["Technician assignment", "SLA escalation", "Completion proof"], reports: ["Open work orders", "SLA breaches", "Asset issues"] },
  { key: "interior-design", name: "Interior Design", group: "Industries", category: "Design Studio", accent: "#be123c", stages: [{ name: "Consultation", probability: 15, color: "#be123c" }, { name: "Concept", probability: 35, color: "#7c3aed" }, { name: "Estimate", probability: 55, color: "#2563eb" }, { name: "Contract", probability: 80, color: "#d97706" }, { name: "Handover", probability: 100, color: "#059669", isWon: true }], fields: ["Property type", "Room count", "Budget", "Moodboard", "Handover date"], automations: ["Design review", "Estimate approval", "Material reminder"], reports: ["Design pipeline", "Budget mix", "Handover forecast"] },
  { key: "software-consulting", name: "Software Consulting", group: "Industries", category: "IT Services", accent: "#2563eb", stages: [{ name: "Discovery", probability: 15, color: "#2563eb" }, { name: "Solution Fit", probability: 35, color: "#0891b2" }, { name: "Proposal", probability: 60, color: "#7c3aed" }, { name: "MSA/SOW", probability: 85, color: "#d97706" }, { name: "Won", probability: 100, color: "#059669", isWon: true }, { name: "Lost", probability: 0, color: "#dc2626", isLost: true }], fields: ["Stack", "Scope", "Cloud", "SOW owner", "Delivery model"], automations: ["Solution review", "SOW approval", "SRM/PMS handoff"], reports: ["Services forecast", "Tech demand", "SOW aging"] },
  { key: "freelancers", name: "Freelancers", group: "Industries", category: "Solo Business", accent: "#7c3aed", stages: [{ name: "Lead", probability: 10, color: "#7c3aed" }, { name: "Brief", probability: 30, color: "#2563eb" }, { name: "Quote Sent", probability: 55, color: "#d97706" }, { name: "In Work", probability: 80, color: "#0891b2" }, { name: "Paid", probability: 100, color: "#059669", isWon: true }], fields: ["Service", "Rate", "Deadline", "Advance", "Payment status"], automations: ["Quote follow-up", "Deadline reminder", "Payment chase"], reports: ["Cash forecast", "Workload", "Client repeat rate"] },
  { key: "brand-collaborations", name: "Brand Collaborations", group: "Industries", category: "Creator/Brand", accent: "#db2777", stages: [{ name: "Lead", probability: 10, color: "#db2777" }, { name: "Media Kit", probability: 30, color: "#7c3aed" }, { name: "Negotiation", probability: 60, color: "#d97706" }, { name: "Content Live", probability: 85, color: "#2563eb" }, { name: "Paid", probability: 100, color: "#059669", isWon: true }], fields: ["Brand", "Campaign", "Deliverables", "Usage rights", "Payout"], automations: ["Contract reminder", "Content approval", "Invoice follow-up"], reports: ["Brand revenue", "Deliverable status", "Payment aging"] },
  { key: "legal", name: "Legal", group: "Industries", category: "Legal Practice", accent: "#334155", stages: [{ name: "Consultation", probability: 15, color: "#334155" }, { name: "Conflict Check", probability: 30, color: "#2563eb" }, { name: "Engagement Letter", probability: 55, color: "#d97706" }, { name: "Matter Opened", probability: 85, color: "#0891b2" }, { name: "Closed", probability: 100, color: "#059669", isWon: true }], fields: ["Matter type", "Jurisdiction", "Conflict status", "Retainer", "Court date"], automations: ["Conflict check", "Retainer reminder", "Matter task pack"], reports: ["Matter pipeline", "Retainer aging", "Practice mix"] },
  { key: "insurance", name: "Insurance", group: "Industries", category: "Policy Sales", accent: "#0369a1", stages: [{ name: "Prospect", probability: 10, color: "#0369a1" }, { name: "Needs Analysis", probability: 30, color: "#2563eb" }, { name: "Quote", probability: 55, color: "#d97706" }, { name: "Underwriting", probability: 80, color: "#7c3aed" }, { name: "Policy Issued", probability: 100, color: "#059669", isWon: true }], fields: ["Policy type", "Premium", "Sum assured", "Nominee", "Renewal date"], automations: ["Document reminder", "Underwriting follow-up", "Renewal alert"], reports: ["Premium forecast", "Policy mix", "Renewals"] },
  { key: "startup-fundraising", name: "Startup Fundraising", group: "Industries", category: "Investor Pipeline", accent: "#9333ea", stages: [{ name: "Target Investor", probability: 10, color: "#9333ea" }, { name: "Intro", probability: 25, color: "#2563eb" }, { name: "Partner Meeting", probability: 50, color: "#7c3aed" }, { name: "Term Sheet", probability: 80, color: "#d97706" }, { name: "Committed", probability: 100, color: "#059669", isWon: true }], fields: ["Fund", "Partner", "Ticket size", "Round", "Data room"], automations: ["Intro follow-up", "Data room reminder", "Commitment update"], reports: ["Capital pipeline", "Investor stage", "Round forecast"] },
  { key: "bank-loan-processing", name: "Bank Loan Processing", group: "Industries", category: "Lending", accent: "#075985", stages: [{ name: "Application", probability: 10, color: "#075985" }, { name: "Documents", probability: 30, color: "#2563eb" }, { name: "Credit Review", probability: 55, color: "#d97706" }, { name: "Sanction", probability: 80, color: "#7c3aed" }, { name: "Disbursed", probability: 100, color: "#059669", isWon: true }], fields: ["Loan type", "Amount", "CIBIL", "Collateral", "Disbursement date"], automations: ["Document checklist", "Credit escalation", "Disbursement reminder"], reports: ["Loan funnel", "Sanction value", "Document gaps"] },
  { key: "school-admission", name: "School Admission", group: "Industries", category: "Education", accent: "#16a34a", stages: [{ name: "Inquiry", probability: 10, color: "#16a34a" }, { name: "Counselling", probability: 30, color: "#2563eb" }, { name: "Application", probability: 55, color: "#d97706" }, { name: "Fee Payment", probability: 85, color: "#7c3aed" }, { name: "Enrolled", probability: 100, color: "#059669", isWon: true }], fields: ["Grade", "Parent", "Campus", "Scholarship", "Fee status"], automations: ["Counselling reminder", "Document reminder", "Fee follow-up"], reports: ["Admissions funnel", "Campus demand", "Fee pending"] },
  { key: "education-training", name: "Education/Training", group: "Industries", category: "Training Sales", accent: "#4f46e5", stages: [{ name: "Inquiry", probability: 10, color: "#4f46e5" }, { name: "Counselling", probability: 30, color: "#2563eb" }, { name: "Demo Class", probability: 55, color: "#0891b2" }, { name: "Enrollment", probability: 85, color: "#d97706" }, { name: "Completed", probability: 100, color: "#059669", isWon: true }], fields: ["Course", "Batch", "Trainer", "Fee", "Learning goal"], automations: ["Demo reminder", "Fee reminder", "Batch onboarding"], reports: ["Course pipeline", "Batch fill", "Fee collection"] },
  { key: "used-car-sales", name: "Used Car Sales", group: "Industries", category: "Automotive", accent: "#ea580c", stages: [{ name: "Lead", probability: 10, color: "#ea580c" }, { name: "Vehicle Match", probability: 30, color: "#2563eb" }, { name: "Test Drive", probability: 55, color: "#0891b2" }, { name: "Finance", probability: 80, color: "#d97706" }, { name: "Delivered", probability: 100, color: "#059669", isWon: true }], fields: ["Model", "Budget", "Test drive", "Exchange", "Finance status"], automations: ["Test drive reminder", "Finance follow-up", "Delivery checklist"], reports: ["Vehicle demand", "Finance conversion", "Delivery forecast"] },
  { key: "automobile-sales", name: "Automobile Sales", group: "Industries", category: "Automotive", accent: "#0284c7", stages: [{ name: "Walk-in/Lead", probability: 10, color: "#0284c7" }, { name: "Model Demo", probability: 30, color: "#2563eb" }, { name: "Test Drive", probability: 55, color: "#0891b2" }, { name: "Booking", probability: 80, color: "#d97706" }, { name: "Delivered", probability: 100, color: "#059669", isWon: true }], fields: ["Model", "Variant", "Color", "Exchange", "Delivery date"], automations: ["Test drive reminder", "Booking approval", "Delivery task pack"], reports: ["Model demand", "Booking value", "Delivery SLA"] },
  { key: "automobile-service", name: "Automobile Service", group: "Industries", category: "Automotive Service", accent: "#64748b", stages: [{ name: "Service Booking", probability: 10, color: "#64748b" }, { name: "Vehicle In", probability: 30, color: "#2563eb" }, { name: "Estimate", probability: 55, color: "#d97706" }, { name: "Repair", probability: 80, color: "#0891b2" }, { name: "Delivered", probability: 100, color: "#059669", isWon: true }], fields: ["Vehicle", "Odometer", "Job card", "Parts", "Advisor"], automations: ["Service reminder", "Estimate approval", "Delivery notification"], reports: ["Service load", "Parts pending", "Advisor performance"] },
  { key: "car-accessories", name: "Car Accessories", group: "Industries", category: "Retail", accent: "#0f766e", stages: [{ name: "Inquiry", probability: 10, color: "#0f766e" }, { name: "Fitment Advice", probability: 30, color: "#2563eb" }, { name: "Quote", probability: 55, color: "#d97706" }, { name: "Installation", probability: 85, color: "#0891b2" }, { name: "Sold", probability: 100, color: "#059669", isWon: true }], fields: ["Vehicle", "Accessory", "Fitment slot", "Warranty", "Invoice"], automations: ["Stock check", "Fitment reminder", "Warranty follow-up"], reports: ["Accessory demand", "Install slots", "Revenue mix"] },
  { key: "nonprofits-donations", name: "Nonprofits Donations", group: "Industries", category: "Nonprofit", accent: "#16a34a", stages: [{ name: "Prospect", probability: 10, color: "#16a34a" }, { name: "Appeal Sent", probability: 30, color: "#2563eb" }, { name: "Pledge", probability: 60, color: "#d97706" }, { name: "Donation Received", probability: 100, color: "#059669", isWon: true }, { name: "Not Now", probability: 0, color: "#dc2626", isLost: true }], fields: ["Cause", "Donation amount", "Frequency", "Receipt", "Donor type"], automations: ["Pledge reminder", "Receipt email", "Renewal appeal"], reports: ["Donation pipeline", "Donor retention", "Campaign ROI"] },
  { key: "patient-referral", name: "Patient Referral Management", group: "Industries", category: "Healthcare", accent: "#dc2626", stages: [{ name: "Referral", probability: 10, color: "#dc2626" }, { name: "Eligibility", probability: 30, color: "#2563eb" }, { name: "Appointment", probability: 60, color: "#0891b2" }, { name: "Consulted", probability: 85, color: "#d97706" }, { name: "Care Started", probability: 100, color: "#059669", isWon: true }], fields: ["Referrer", "Department", "Insurance", "Appointment", "Consent"], automations: ["Appointment reminder", "Consent check", "Referrer update"], reports: ["Referral conversion", "Department demand", "No-show rate"] },
  { key: "patient-management", name: "Patient Management", group: "Industries", category: "Healthcare", accent: "#be123c", stages: [{ name: "Inquiry", probability: 10, color: "#be123c" }, { name: "Registration", probability: 30, color: "#2563eb" }, { name: "Consultation", probability: 60, color: "#0891b2" }, { name: "Treatment Plan", probability: 85, color: "#d97706" }, { name: "Follow-up", probability: 100, color: "#059669", isWon: true }], fields: ["Patient ID", "Doctor", "Department", "Treatment", "Follow-up date"], automations: ["Registration checklist", "Follow-up reminder", "Care plan update"], reports: ["Patient funnel", "Doctor load", "Follow-up compliance"] },
  { key: "dry-cleaning", name: "Dry Cleaning", group: "Industries", category: "Local Services", accent: "#0e7490", stages: [{ name: "Pickup Request", probability: 10, color: "#0e7490" }, { name: "Received", probability: 30, color: "#2563eb" }, { name: "Cleaning", probability: 55, color: "#7c3aed" }, { name: "Ready", probability: 85, color: "#d97706" }, { name: "Delivered", probability: 100, color: "#059669", isWon: true }], fields: ["Garments", "Pickup slot", "Service type", "Delivery slot", "Payment"], automations: ["Pickup reminder", "Ready notification", "Payment follow-up"], reports: ["Order volume", "Pickup SLA", "Revenue by service"] },
  { key: "jewellery", name: "Jewellery", group: "Industries", category: "Luxury Retail", accent: "#b45309", stages: [{ name: "Walk-in/Inquiry", probability: 10, color: "#b45309" }, { name: "Design Selection", probability: 35, color: "#7c3aed" }, { name: "Estimate", probability: 60, color: "#d97706" }, { name: "Advance Paid", probability: 85, color: "#2563eb" }, { name: "Delivered", probability: 100, color: "#059669", isWon: true }], fields: ["Occasion", "Metal", "Stone", "Budget", "Delivery date"], automations: ["Design follow-up", "Advance reminder", "Delivery appointment"], reports: ["Occasion demand", "Custom orders", "Advance aging"] },
  { key: "photography", name: "Photography", group: "Industries", category: "Creative Services", accent: "#7c3aed", stages: [{ name: "Inquiry", probability: 10, color: "#7c3aed" }, { name: "Package Sent", probability: 35, color: "#2563eb" }, { name: "Date Hold", probability: 60, color: "#d97706" }, { name: "Booked", probability: 85, color: "#0891b2" }, { name: "Delivered", probability: 100, color: "#059669", isWon: true }], fields: ["Event date", "Package", "Venue", "Advance", "Album status"], automations: ["Date hold expiry", "Advance reminder", "Delivery timeline"], reports: ["Booking calendar", "Package revenue", "Delivery backlog"] },
  { key: "telecommunications", name: "Telecommunications", group: "Industries", category: "Telecom", accent: "#2563eb", stages: [{ name: "Lead", probability: 10, color: "#2563eb" }, { name: "Feasibility", probability: 30, color: "#0891b2" }, { name: "Plan Proposal", probability: 55, color: "#7c3aed" }, { name: "Provisioning", probability: 85, color: "#d97706" }, { name: "Activated", probability: 100, color: "#059669", isWon: true }], fields: ["Plan", "Location", "Bandwidth", "Feasibility", "Activation date"], automations: ["Feasibility task", "Provisioning reminder", "Activation notice"], reports: ["Activation pipeline", "Plan demand", "Provisioning SLA"] },
  { key: "ca-firm", name: "CA Firm", group: "Industries", category: "Professional Services", accent: "#0f766e", description: "Manage compliance leads, retainers, filing work, and recurring client service pipelines for chartered accountancy firms.", fieldEntity: "Client", sampleRecord: "GST return retainer", stages: [{ name: "Client Inquiry", probability: 10, color: "#0f766e" }, { name: "Document Review", probability: 30, color: "#2563eb" }, { name: "Proposal/Retainer", probability: 55, color: "#d97706" }, { name: "Engagement Signed", probability: 85, color: "#7c3aed" }, { name: "Service Active", probability: 100, color: "#059669", isWon: true }], fields: ["Service type", "PAN/GSTIN", "Due date", "Retainer value", "Document status"], automations: ["Document checklist", "Filing due reminder", "Retainer renewal"], reports: ["Compliance pipeline", "Retainer forecast", "Filing aging"] },
  { key: "audit-firm", name: "Audit Firm", group: "Industries", category: "Assurance", accent: "#475569", description: "Track audit prospects from scoping through engagement letters, fieldwork readiness, and final sign-off.", fieldEntity: "Audit", sampleRecord: "FY audit engagement", stages: [{ name: "Audit Lead", probability: 10, color: "#475569" }, { name: "Scope Assessment", probability: 30, color: "#2563eb" }, { name: "Fee Proposal", probability: 55, color: "#d97706" }, { name: "Engagement Letter", probability: 80, color: "#7c3aed" }, { name: "Audit Scheduled", probability: 100, color: "#059669", isWon: true }], fields: ["Audit type", "Entity size", "Period", "Partner", "Risk rating"], automations: ["Independence check", "Proposal approval", "PBC list reminder"], reports: ["Audit pipeline", "Partner workload", "Risk mix"] },
  { key: "tax-practice", name: "Tax Practice", group: "Industries", category: "Tax Advisory", accent: "#b45309", description: "Handle tax advisory, notices, assessment cases, appeals, and recurring filing opportunities.", fieldEntity: "Tax case", sampleRecord: "Income tax notice response", stages: [{ name: "Tax Query", probability: 10, color: "#b45309" }, { name: "Case Review", probability: 30, color: "#2563eb" }, { name: "Fee Quote", probability: 55, color: "#d97706" }, { name: "Authority Filing", probability: 80, color: "#7c3aed" }, { name: "Closed/Filed", probability: 100, color: "#059669", isWon: true }], fields: ["Tax type", "Assessment year", "Notice date", "Filing deadline", "Fee"], automations: ["Deadline alert", "Document reminder", "Client approval"], reports: ["Tax case value", "Deadline risk", "Case outcome"] },
  { key: "it-company", name: "IT Company", group: "Industries", category: "IT Products & Services", accent: "#2563eb", description: "Run product demos, implementation proposals, support renewals, and CRM-to-SRM/PMS delivery handoffs.", fieldEntity: "Opportunity", sampleRecord: "ERP implementation", stages: [{ name: "Discovery", probability: 15, color: "#2563eb" }, { name: "Demo/POC", probability: 35, color: "#0891b2" }, { name: "Commercial Proposal", probability: 60, color: "#7c3aed" }, { name: "Security/Legal", probability: 80, color: "#d97706" }, { name: "Won - Delivery Handoff", probability: 100, color: "#059669", isWon: true }, { name: "Lost", probability: 0, color: "#dc2626", isLost: true }], fields: ["Solution", "Users", "Implementation scope", "ARR/Project value", "Delivery owner"], automations: ["Demo follow-up", "Security checklist", "SRM/PMS handoff"], reports: ["ARR forecast", "Implementation backlog", "Win rate by solution"] },
  { key: "manufacturing", name: "Manufacturing", group: "Industries", category: "B2B Manufacturing", accent: "#64748b", description: "Track enquiries, samples, quotations, purchase orders, production readiness, and dispatch commitments.", fieldEntity: "Order", sampleRecord: "Custom component order", stages: [{ name: "RFQ Received", probability: 10, color: "#64748b" }, { name: "Sample/Spec Review", probability: 30, color: "#2563eb" }, { name: "Quote Sent", probability: 55, color: "#d97706" }, { name: "PO Received", probability: 85, color: "#7c3aed" }, { name: "Production Ready", probability: 100, color: "#059669", isWon: true }], fields: ["SKU/spec", "Quantity", "Target price", "Delivery date", "Plant"], automations: ["Sample reminder", "Quote follow-up", "Production handoff"], reports: ["RFQ value", "PO conversion", "Capacity forecast"] },
  { key: "logistics", name: "Logistics", group: "Industries", category: "Transport & Freight", accent: "#ea580c", description: "Manage freight enquiries, route pricing, shipment booking, tracking, POD, and billing follow-up.", fieldEntity: "Shipment", sampleRecord: "Mumbai to Delhi FTL", stages: [{ name: "Shipment Inquiry", probability: 10, color: "#ea580c" }, { name: "Route Priced", probability: 35, color: "#2563eb" }, { name: "Booking Confirmed", probability: 65, color: "#d97706" }, { name: "In Transit", probability: 85, color: "#0891b2" }, { name: "Delivered/POD", probability: 100, color: "#059669", isWon: true }], fields: ["Origin", "Destination", "Load type", "Vehicle", "POD status"], automations: ["Rate approval", "Tracking update", "POD reminder"], reports: ["Freight pipeline", "Route margin", "Delivery SLA"] },
  { key: "restaurant-catering", name: "Restaurant & Catering", group: "Industries", category: "Hospitality", accent: "#be123c", description: "Convert event enquiries into menus, tastings, bookings, advance payments, and final delivery.", fieldEntity: "Event", sampleRecord: "Corporate lunch booking", stages: [{ name: "Event Inquiry", probability: 10, color: "#be123c" }, { name: "Menu Shared", probability: 30, color: "#d97706" }, { name: "Tasting/Review", probability: 55, color: "#7c3aed" }, { name: "Advance Paid", probability: 85, color: "#2563eb" }, { name: "Event Completed", probability: 100, color: "#059669", isWon: true }], fields: ["Event date", "Guest count", "Menu", "Venue", "Advance"], automations: ["Tasting reminder", "Advance follow-up", "Kitchen prep task"], reports: ["Event pipeline", "Menu demand", "Advance pending"] },
  { key: "travel-agency", name: "Travel Agency", group: "Industries", category: "Travel", accent: "#0284c7", description: "Track travel enquiries, itineraries, quotes, booking payments, visa steps, and departure readiness.", fieldEntity: "Trip", sampleRecord: "Dubai family package", stages: [{ name: "Travel Inquiry", probability: 10, color: "#0284c7" }, { name: "Itinerary Planned", probability: 35, color: "#2563eb" }, { name: "Quote Approved", probability: 60, color: "#d97706" }, { name: "Booked", probability: 85, color: "#7c3aed" }, { name: "Travel Completed", probability: 100, color: "#059669", isWon: true }], fields: ["Destination", "Travel dates", "Passengers", "Visa status", "Payment"], automations: ["Quote follow-up", "Visa checklist", "Departure reminder"], reports: ["Package pipeline", "Destination demand", "Payment aging"] },
];

const advancedIndustryTemplates: CRMBusinessTemplate[] = [
  {
    key: "solar-epc",
    name: "Solar EPC",
    group: "Industries",
    category: "Renewable Energy",
    accent: "#f59e0b",
    description: "Manage rooftop and commercial solar enquiries from site survey through subsidy documents, PPA approval, installation, and commissioning.",
    fieldEntity: "Project",
    sampleRecord: "Warehouse rooftop solar",
    stages: [{ name: "Energy Inquiry", probability: 10, color: "#f59e0b" }, { name: "Site Survey", probability: 30, color: "#2563eb" }, { name: "Proposal & ROI", probability: 55, color: "#7c3aed" }, { name: "PPA/Approval", probability: 80, color: "#d97706" }, { name: "Commissioned", probability: 100, color: "#059669", isWon: true }],
    fields: ["Site capacity", "Roof area", "DISCOM", "Subsidy status", "Commissioning date"],
    customFields: [
      { entityType: "deals", fieldName: "Site Capacity (kW)", fieldKey: "site_capacity_kw", fieldType: "number", isRequired: true, isFilterable: true },
      { entityType: "deals", fieldName: "DISCOM", fieldKey: "discom", fieldType: "dropdown", options: ["BESCOM", "MSEDCL", "TANGEDCO", "Torrent", "Other"], isFilterable: true },
      { entityType: "deals", fieldName: "Subsidy Status", fieldKey: "subsidy_status", fieldType: "dropdown", options: ["Not applicable", "Documents pending", "Submitted", "Approved"], isFilterable: true },
    ],
    sampleDeals: [
      { name: "250 kW rooftop EPC", company: "Sunrise Warehousing", amount: 18500000, stageIndex: 1, closeDate: "2026-07-18", source: "Energy audit", nextStep: "Complete shadow analysis and single-line diagram", customFields: { site_capacity_kw: 250, discom: "BESCOM", subsidy_status: "Submitted" } },
      { name: "Housing society solar retrofit", company: "Lakeview Residency", amount: 4200000, stageIndex: 2, closeDate: "2026-08-05", source: "Referral", nextStep: "Share ROI model and net-metering checklist", customFields: { site_capacity_kw: 60, discom: "MSEDCL", subsidy_status: "Documents pending" } },
    ],
    automations: ["Survey assignment", "ROI proposal reminder", "Subsidy document chase"],
    reports: ["Capacity pipeline", "DISCOM approval aging", "Commissioning forecast"],
  },
  {
    key: "construction-contracting",
    name: "Construction Contracting",
    group: "Industries",
    category: "Construction",
    accent: "#92400e",
    description: "Track civil contracting opportunities from BOQ receipt to site visit, tender quote, LOI, mobilization advance, and project handoff.",
    fieldEntity: "Tender",
    sampleRecord: "Commercial fit-out tender",
    stages: [{ name: "BOQ Received", probability: 10, color: "#92400e" }, { name: "Site Visit", probability: 30, color: "#2563eb" }, { name: "Tender Submitted", probability: 55, color: "#7c3aed" }, { name: "LOI/Negotiation", probability: 80, color: "#d97706" }, { name: "Mobilized", probability: 100, color: "#059669", isWon: true }, { name: "Not Awarded", probability: 0, color: "#dc2626", isLost: true }],
    fields: ["BOQ value", "Site location", "Tender due date", "EMD amount", "Mobilization advance"],
    customFields: [
      { entityType: "deals", fieldName: "BOQ Value", fieldKey: "boq_value", fieldType: "currency", isRequired: true, isFilterable: true },
      { entityType: "deals", fieldName: "Tender Due Date", fieldKey: "tender_due_date", fieldType: "date", isFilterable: true },
      { entityType: "deals", fieldName: "EMD Amount", fieldKey: "emd_amount", fieldType: "currency" },
    ],
    sampleDeals: [
      { name: "Mall interior civil package", company: "Orion Developers", amount: 32000000, stageIndex: 2, closeDate: "2026-07-02", source: "Tender portal", nextStep: "Submit final BOQ clarifications", customFields: { boq_value: 32000000, tender_due_date: "2026-06-28", emd_amount: 500000 } },
      { name: "Factory expansion work", company: "Prakash Foods", amount: 58000000, stageIndex: 1, closeDate: "2026-08-16", source: "Architect referral", nextStep: "Complete site measurements", customFields: { boq_value: 58000000, tender_due_date: "2026-07-20", emd_amount: 750000 } },
    ],
    automations: ["Tender due reminder", "Site visit checklist", "PMS mobilization handoff"],
    reports: ["Tender value", "Award ratio", "EMD exposure"],
  },
  {
    key: "diagnostic-lab",
    name: "Diagnostic Lab",
    group: "Industries",
    category: "Healthcare Diagnostics",
    accent: "#0e7490",
    description: "Manage doctor referrals, corporate health checks, home sample collections, report delivery, and repeat package sales.",
    fieldEntity: "Test booking",
    sampleRecord: "Corporate health camp",
    stages: [{ name: "Referral/Inquiry", probability: 10, color: "#0e7490" }, { name: "Package Suggested", probability: 30, color: "#2563eb" }, { name: "Sample Scheduled", probability: 55, color: "#7c3aed" }, { name: "Payment/Collection", probability: 80, color: "#d97706" }, { name: "Report Delivered", probability: 100, color: "#059669", isWon: true }],
    fields: ["Test package", "Sample type", "Collection slot", "Referring doctor", "Report SLA"],
    customFields: [
      { entityType: "deals", fieldName: "Test Package", fieldKey: "test_package", fieldType: "dropdown", options: ["Full body", "Diabetes", "Cardiac", "Pre-employment", "Custom panel"], isFilterable: true },
      { entityType: "deals", fieldName: "Collection Slot", fieldKey: "collection_slot", fieldType: "datetime", isRequired: true },
      { entityType: "deals", fieldName: "Report SLA", fieldKey: "report_sla", fieldType: "dropdown", options: ["Same day", "24 hours", "48 hours"], isFilterable: true },
    ],
    sampleDeals: [
      { name: "Pre-employment test batch", company: "TalentBridge HR", amount: 145000, stageIndex: 2, closeDate: "2026-06-22", source: "Corporate referral", nextStep: "Confirm sample collection team roster", customFields: { test_package: "Pre-employment", collection_slot: "2026-06-19T09:30", report_sla: "24 hours" } },
      { name: "Cardiac panel home collection", company: "Mehta Family", amount: 18500, stageIndex: 1, closeDate: "2026-06-14", source: "Doctor referral", nextStep: "Share fasting instructions", customFields: { test_package: "Cardiac", collection_slot: "2026-06-13T07:00", report_sla: "Same day" } },
    ],
    automations: ["Collection reminder", "Doctor report notification", "SLA escalation"],
    reports: ["Package conversion", "Collection SLA", "Referral revenue"],
  },
  {
    key: "hotel-banquet",
    name: "Hotel Banquet Sales",
    group: "Industries",
    category: "Hospitality",
    accent: "#be123c",
    description: "Convert banquet enquiries into property visits, menu negotiations, room blocks, advance payments, and event execution.",
    fieldEntity: "Event",
    sampleRecord: "Wedding reception booking",
    stages: [{ name: "Event Inquiry", probability: 10, color: "#be123c" }, { name: "Property Visit", probability: 30, color: "#2563eb" }, { name: "Menu & Package", probability: 55, color: "#7c3aed" }, { name: "Advance Paid", probability: 85, color: "#d97706" }, { name: "Event Closed", probability: 100, color: "#059669", isWon: true }],
    fields: ["Event date", "Guest count", "Hall", "Room block", "Advance amount"],
    customFields: [
      { entityType: "deals", fieldName: "Event Date", fieldKey: "event_date", fieldType: "date", isRequired: true, isFilterable: true },
      { entityType: "deals", fieldName: "Guest Count", fieldKey: "guest_count", fieldType: "number", isRequired: true },
      { entityType: "deals", fieldName: "Banquet Hall", fieldKey: "banquet_hall", fieldType: "dropdown", options: ["Grand Ballroom", "Terrace", "Boardroom", "Lawn"], isFilterable: true },
    ],
    sampleDeals: [
      { name: "Wedding reception 450 pax", company: "Rao Family", amount: 2750000, stageIndex: 2, closeDate: "2026-07-28", source: "Walk-in", nextStep: "Send revised menu and room block quote", customFields: { event_date: "2026-11-22", guest_count: 450, banquet_hall: "Grand Ballroom" } },
      { name: "Annual sales meet", company: "Vertex Pharma", amount: 940000, stageIndex: 1, closeDate: "2026-07-12", source: "Corporate account", nextStep: "Schedule AV requirement review", customFields: { event_date: "2026-08-09", guest_count: 160, banquet_hall: "Boardroom" } },
    ],
    automations: ["Visit reminder", "Advance payment follow-up", "Event ops handoff"],
    reports: ["Banquet revenue", "Hall utilization", "Advance aging"],
  },
  {
    key: "wholesale-distribution",
    name: "Wholesale Distribution",
    group: "Industries",
    category: "Distribution",
    accent: "#0f766e",
    description: "Handle dealer onboarding, price negotiation, credit terms, stock allocation, dispatch, and repeat order cycles.",
    fieldEntity: "Dealer order",
    sampleRecord: "Distributor first order",
    stages: [{ name: "Dealer Inquiry", probability: 10, color: "#0f766e" }, { name: "KYC/Credit Check", probability: 30, color: "#2563eb" }, { name: "Price Negotiation", probability: 55, color: "#d97706" }, { name: "PO Received", probability: 85, color: "#7c3aed" }, { name: "Dispatched", probability: 100, color: "#059669", isWon: true }],
    fields: ["Dealer grade", "Credit limit", "SKU mix", "Margin", "Dispatch warehouse"],
    customFields: [
      { entityType: "deals", fieldName: "Dealer Grade", fieldKey: "dealer_grade", fieldType: "dropdown", options: ["A", "B", "C", "New"], isFilterable: true },
      { entityType: "deals", fieldName: "Credit Limit", fieldKey: "credit_limit", fieldType: "currency", isFilterable: true },
      { entityType: "deals", fieldName: "Dispatch Warehouse", fieldKey: "dispatch_warehouse", fieldType: "dropdown", options: ["Bengaluru", "Mumbai", "Delhi NCR", "Chennai"], isFilterable: true },
    ],
    sampleDeals: [
      { name: "North dealer onboarding order", company: "Shree Traders", amount: 1250000, stageIndex: 1, closeDate: "2026-06-30", source: "Distributor meet", nextStep: "Complete GST and credit review", customFields: { dealer_grade: "New", credit_limit: 800000, dispatch_warehouse: "Delhi NCR" } },
      { name: "Q2 repeat bulk order", company: "Urban Retail Mart", amount: 2860000, stageIndex: 3, closeDate: "2026-07-04", source: "Account manager", nextStep: "Confirm stock allocation", customFields: { dealer_grade: "A", credit_limit: 3500000, dispatch_warehouse: "Mumbai" } },
    ],
    automations: ["KYC reminder", "Credit approval route", "Dispatch notification"],
    reports: ["Dealer pipeline", "Credit exposure", "Warehouse dispatch forecast"],
  },
  {
    key: "agriculture-equipment",
    name: "Agriculture Equipment",
    group: "Industries",
    category: "Agri Sales",
    accent: "#16a34a",
    description: "Manage farm equipment enquiries, demo visits, subsidy paperwork, finance, booking, and delivery readiness.",
    fieldEntity: "Equipment deal",
    sampleRecord: "Tractor implement sale",
    stages: [{ name: "Farmer Inquiry", probability: 10, color: "#16a34a" }, { name: "Demo Visit", probability: 30, color: "#2563eb" }, { name: "Finance/Subsidy", probability: 55, color: "#d97706" }, { name: "Booking", probability: 85, color: "#7c3aed" }, { name: "Delivered", probability: 100, color: "#059669", isWon: true }],
    fields: ["Equipment model", "Land size", "Subsidy scheme", "Finance partner", "Delivery village"],
    customFields: [
      { entityType: "deals", fieldName: "Equipment Model", fieldKey: "equipment_model", fieldType: "dropdown", options: ["Tractor", "Rotavator", "Harvester", "Sprayer", "Pump set"], isFilterable: true },
      { entityType: "deals", fieldName: "Land Size Acres", fieldKey: "land_size_acres", fieldType: "number" },
      { entityType: "deals", fieldName: "Subsidy Scheme", fieldKey: "subsidy_scheme", fieldType: "text" },
    ],
    sampleDeals: [
      { name: "Rotavator and tractor package", company: "Patil Farms", amount: 1750000, stageIndex: 2, closeDate: "2026-07-15", source: "Field demo", nextStep: "Submit subsidy documents", customFields: { equipment_model: "Tractor", land_size_acres: 18, subsidy_scheme: "State farm mechanization" } },
      { name: "Drip pump upgrade", company: "Green Acres Co-op", amount: 420000, stageIndex: 1, closeDate: "2026-06-26", source: "Dealer referral", nextStep: "Schedule village demo", customFields: { equipment_model: "Pump set", land_size_acres: 42, subsidy_scheme: "Micro irrigation support" } },
    ],
    automations: ["Demo schedule", "Finance document reminder", "Delivery checklist"],
    reports: ["Model demand", "Subsidy pending", "Dealer conversion"],
  },
  {
    key: "government-tenders",
    name: "Government Tenders",
    group: "Industries",
    category: "Public Sector Sales",
    accent: "#475569",
    description: "Track e-procurement opportunities with EMD, eligibility, bid submission, technical evaluation, financial bid, and award status.",
    fieldEntity: "Tender",
    sampleRecord: "Municipal software tender",
    stages: [{ name: "Tender Identified", probability: 10, color: "#475569" }, { name: "Eligibility Check", probability: 25, color: "#2563eb" }, { name: "Bid Submitted", probability: 50, color: "#7c3aed" }, { name: "Financial Opened", probability: 75, color: "#d97706" }, { name: "Awarded", probability: 100, color: "#059669", isWon: true }, { name: "Lost/Disqualified", probability: 0, color: "#dc2626", isLost: true }],
    fields: ["Tender ID", "Department", "EMD", "Bid due date", "L1 status"],
    customFields: [
      { entityType: "deals", fieldName: "Tender ID", fieldKey: "tender_id", fieldType: "text", isRequired: true, isUnique: true, isFilterable: true },
      { entityType: "deals", fieldName: "Bid Due Date", fieldKey: "bid_due_date", fieldType: "date", isRequired: true, isFilterable: true },
      { entityType: "deals", fieldName: "EMD Value", fieldKey: "emd_value", fieldType: "currency" },
    ],
    sampleDeals: [
      { name: "Municipal CRM tender", company: "City Corporation", amount: 9200000, stageIndex: 2, closeDate: "2026-07-09", source: "GeM portal", nextStep: "Upload financial bid attachments", customFields: { tender_id: "GEM/2026/B/CRM-1187", bid_due_date: "2026-07-03", emd_value: 250000 } },
      { name: "State training platform RFP", company: "Skill Mission Office", amount: 14800000, stageIndex: 1, closeDate: "2026-08-01", source: "E-procurement", nextStep: "Confirm turnover eligibility documents", customFields: { tender_id: "RFP-SM-2026-44", bid_due_date: "2026-07-18", emd_value: 500000 } },
    ],
    automations: ["Bid due reminder", "EMD approval", "Eligibility checklist"],
    reports: ["Tender value", "Bid aging", "Award ratio"],
  },
  {
    key: "gym-fitness",
    name: "Gym & Fitness Studio",
    group: "Industries",
    category: "Fitness",
    accent: "#dc2626",
    description: "Convert walk-ins and digital enquiries into trials, membership plans, personal training packages, and renewal follow-ups.",
    fieldEntity: "Membership",
    sampleRecord: "Annual membership enquiry",
    stages: [{ name: "Inquiry", probability: 10, color: "#dc2626" }, { name: "Trial Booked", probability: 30, color: "#2563eb" }, { name: "Plan Suggested", probability: 55, color: "#7c3aed" }, { name: "Payment Pending", probability: 80, color: "#d97706" }, { name: "Member Active", probability: 100, color: "#059669", isWon: true }],
    fields: ["Fitness goal", "Plan", "Trial date", "Trainer", "Renewal date"],
    customFields: [
      { entityType: "deals", fieldName: "Fitness Goal", fieldKey: "fitness_goal", fieldType: "dropdown", options: ["Weight loss", "Strength", "Rehab", "General fitness", "Athletic training"], isFilterable: true },
      { entityType: "deals", fieldName: "Trial Date", fieldKey: "trial_date", fieldType: "date", isFilterable: true },
      { entityType: "deals", fieldName: "Plan Type", fieldKey: "plan_type", fieldType: "dropdown", options: ["Monthly", "Quarterly", "Annual", "PT package"], isFilterable: true },
    ],
    sampleDeals: [
      { name: "Annual fitness membership", company: "Aditi Sharma", amount: 42000, stageIndex: 2, closeDate: "2026-06-20", source: "Instagram ad", nextStep: "Share annual plan and PT bundle", customFields: { fitness_goal: "Strength", trial_date: "2026-06-12", plan_type: "Annual" } },
      { name: "Personal training package", company: "Vikram Menon", amount: 36000, stageIndex: 1, closeDate: "2026-06-18", source: "Walk-in", nextStep: "Book trainer consultation", customFields: { fitness_goal: "Weight loss", trial_date: "2026-06-11", plan_type: "PT package" } },
    ],
    automations: ["Trial reminder", "Payment follow-up", "Renewal alert"],
    reports: ["Membership pipeline", "Trainer conversion", "Renewal forecast"],
  },
  {
    key: "salon-spa",
    name: "Salon & Spa",
    group: "Industries",
    category: "Beauty & Wellness",
    accent: "#db2777",
    description: "Track bridal packages, recurring memberships, appointment deposits, stylist allocation, and package completion.",
    fieldEntity: "Booking",
    sampleRecord: "Bridal package booking",
    stages: [{ name: "Inquiry", probability: 10, color: "#db2777" }, { name: "Consultation", probability: 30, color: "#7c3aed" }, { name: "Package Shared", probability: 55, color: "#2563eb" }, { name: "Deposit Paid", probability: 85, color: "#d97706" }, { name: "Service Completed", probability: 100, color: "#059669", isWon: true }],
    fields: ["Service package", "Appointment date", "Stylist", "Deposit", "Occasion"],
    customFields: [
      { entityType: "deals", fieldName: "Service Package", fieldKey: "service_package", fieldType: "dropdown", options: ["Bridal", "Hair color", "Spa day", "Membership", "Grooming"], isFilterable: true },
      { entityType: "deals", fieldName: "Appointment Date", fieldKey: "appointment_date", fieldType: "datetime", isRequired: true },
      { entityType: "deals", fieldName: "Stylist", fieldKey: "stylist", fieldType: "text" },
    ],
    sampleDeals: [
      { name: "Bridal makeup package", company: "Nisha Kapoor", amount: 85000, stageIndex: 3, closeDate: "2026-06-25", source: "Referral", nextStep: "Confirm trial makeup date", customFields: { service_package: "Bridal", appointment_date: "2026-07-10T11:00", stylist: "Rhea" } },
      { name: "Quarterly spa membership", company: "Corporate Wellness Club", amount: 240000, stageIndex: 2, closeDate: "2026-07-08", source: "Corporate lead", nextStep: "Share membership terms", customFields: { service_package: "Membership", appointment_date: "2026-07-01T16:00", stylist: "Team allocation" } },
    ],
    automations: ["Consultation reminder", "Deposit follow-up", "Stylist task"],
    reports: ["Package pipeline", "Deposit aging", "Stylist utilization"],
  },
  {
    key: "export-import",
    name: "Export / Import Trading",
    group: "Industries",
    category: "International Trade",
    accent: "#0369a1",
    description: "Manage export enquiries, proforma invoices, compliance documents, LC/payment terms, shipment booking, and collection follow-up.",
    fieldEntity: "Trade order",
    sampleRecord: "UAE export order",
    stages: [{ name: "Buyer Inquiry", probability: 10, color: "#0369a1" }, { name: "PI Shared", probability: 35, color: "#2563eb" }, { name: "Docs/LC Review", probability: 60, color: "#7c3aed" }, { name: "Shipment Booked", probability: 85, color: "#d97706" }, { name: "Documents Released", probability: 100, color: "#059669", isWon: true }],
    fields: ["Country", "Incoterm", "Port", "HS code", "Payment terms"],
    customFields: [
      { entityType: "deals", fieldName: "Destination Country", fieldKey: "destination_country", fieldType: "text", isFilterable: true },
      { entityType: "deals", fieldName: "Incoterm", fieldKey: "incoterm", fieldType: "dropdown", options: ["EXW", "FOB", "CIF", "DAP", "DDP"], isFilterable: true },
      { entityType: "deals", fieldName: "Payment Terms", fieldKey: "payment_terms", fieldType: "dropdown", options: ["Advance", "LC", "CAD", "Open credit"], isFilterable: true },
    ],
    sampleDeals: [
      { name: "Spices export to Dubai", company: "Al Noor Trading", amount: 3850000, stageIndex: 2, closeDate: "2026-07-19", source: "Trade fair", nextStep: "Review LC draft and certificate requirements", customFields: { destination_country: "UAE", incoterm: "CIF", payment_terms: "LC" } },
      { name: "Textile shipment to Kenya", company: "Nairobi Retail Group", amount: 2100000, stageIndex: 1, closeDate: "2026-07-05", source: "Buyer portal", nextStep: "Send proforma invoice", customFields: { destination_country: "Kenya", incoterm: "FOB", payment_terms: "Advance" } },
    ],
    automations: ["PI follow-up", "Document checklist", "Shipment reminder"],
    reports: ["Country pipeline", "Payment terms risk", "Shipment forecast"],
  },
  {
    key: "subscription-saas",
    name: "Subscription SaaS",
    group: "Industries",
    category: "SaaS Sales",
    accent: "#4f46e5",
    description: "Run SaaS trials, product-qualified leads, security reviews, annual subscriptions, renewals, and expansion opportunities.",
    fieldEntity: "Subscription",
    sampleRecord: "Annual SaaS subscription",
    stages: [{ name: "PQL/Lead", probability: 10, color: "#4f46e5" }, { name: "Trial Active", probability: 30, color: "#2563eb" }, { name: "Security Review", probability: 55, color: "#7c3aed" }, { name: "Commercials", probability: 80, color: "#d97706" }, { name: "Subscribed", probability: 100, color: "#059669", isWon: true }, { name: "Churned/Lost", probability: 0, color: "#dc2626", isLost: true }],
    fields: ["Plan", "Seats", "ARR", "Trial end", "Security owner"],
    customFields: [
      { entityType: "deals", fieldName: "Seat Count", fieldKey: "seat_count", fieldType: "number", isRequired: true, isFilterable: true },
      { entityType: "deals", fieldName: "ARR", fieldKey: "arr", fieldType: "currency", isFilterable: true },
      { entityType: "deals", fieldName: "Trial End Date", fieldKey: "trial_end_date", fieldType: "date", isFilterable: true },
    ],
    sampleDeals: [
      { name: "Enterprise annual plan", company: "CloudLedger", amount: 1800000, stageIndex: 2, closeDate: "2026-07-11", source: "Product signup", nextStep: "Complete security questionnaire", customFields: { seat_count: 120, arr: 1800000, trial_end_date: "2026-06-29" } },
      { name: "Mid-market team rollout", company: "Horizon Design Co", amount: 540000, stageIndex: 1, closeDate: "2026-06-27", source: "Webinar", nextStep: "Review trial usage with champion", customFields: { seat_count: 35, arr: 540000, trial_end_date: "2026-06-20" } },
    ],
    automations: ["Trial usage alert", "Security review task", "Renewal reminder"],
    reports: ["ARR forecast", "Trial conversion", "Expansion pipeline"],
  },
  {
    key: "home-services",
    name: "Home Services",
    group: "Industries",
    category: "Field Services",
    accent: "#0891b2",
    description: "Manage plumbing, electrical, appliance, and home repair jobs from inquiry to inspection, estimate, job completion, and payment.",
    fieldEntity: "Job",
    sampleRecord: "Apartment plumbing repair",
    stages: [{ name: "Service Inquiry", probability: 10, color: "#0891b2" }, { name: "Technician Assigned", probability: 30, color: "#2563eb" }, { name: "Estimate Shared", probability: 55, color: "#d97706" }, { name: "Job Scheduled", probability: 85, color: "#7c3aed" }, { name: "Paid & Closed", probability: 100, color: "#059669", isWon: true }],
    fields: ["Service type", "Address", "Technician", "Visit slot", "Warranty"],
    customFields: [
      { entityType: "deals", fieldName: "Service Type", fieldKey: "service_type", fieldType: "dropdown", options: ["Plumbing", "Electrical", "Appliance", "Painting", "Cleaning"], isFilterable: true },
      { entityType: "deals", fieldName: "Visit Slot", fieldKey: "visit_slot", fieldType: "datetime", isRequired: true },
      { entityType: "deals", fieldName: "Technician", fieldKey: "technician", fieldType: "text" },
    ],
    sampleDeals: [
      { name: "Kitchen plumbing repair", company: "Prestige Lakeside A-1204", amount: 8500, stageIndex: 1, closeDate: "2026-06-12", source: "Phone call", nextStep: "Assign technician and confirm slot", customFields: { service_type: "Plumbing", visit_slot: "2026-06-11T15:00", technician: "Mahesh" } },
      { name: "AC service annual package", company: "Kapoor Residence", amount: 28000, stageIndex: 2, closeDate: "2026-06-18", source: "Renewal", nextStep: "Share estimate and service schedule", customFields: { service_type: "Appliance", visit_slot: "2026-06-15T10:30", technician: "Ravi" } },
    ],
    automations: ["Technician assignment", "Visit reminder", "Payment collection"],
    reports: ["Service pipeline", "Technician workload", "Payment aging"],
  },
];

const allCrmBusinessTemplates = [...crmBusinessTemplates, ...advancedIndustryTemplates];

type QuickFormField = {
  key: string;
  label: string;
  type?: "text" | "email" | "number" | "date" | "textarea" | "select";
  placeholder?: string;
  options?: string[];
  required?: boolean;
  width?: "full" | "half" | "third";
};

type DealProductLine = {
  id: number;
  product: string;
  listPrice: number;
  quantity: number;
  discount: number;
};

const createDealStages = [
  { id: 1, name: "Qualification", probability: 10, tone: "border-blue-200 bg-blue-50 text-blue-800" },
  { id: 2, name: "Needs Analysis", probability: 25, tone: "border-cyan-200 bg-cyan-50 text-cyan-800" },
  { id: 3, name: "Proposal/Price Quote", probability: 50, tone: "border-amber-200 bg-amber-50 text-amber-800" },
  { id: 4, name: "Negotiation/Review", probability: 75, tone: "border-violet-200 bg-violet-50 text-violet-800" },
  { id: 5, name: "Closed Won", probability: 100, tone: "border-emerald-200 bg-emerald-50 text-emerald-800", isWon: true },
  { id: 6, name: "Closed Lost", probability: 0, tone: "border-red-200 bg-red-50 text-red-800", isLost: true },
];

const quickFormFieldsByKind: Partial<Record<CRMPageKind, QuickFormField[]>> = {
  leads: [
    { key: "name", label: "Lead name", required: true, placeholder: "Jane Shah" },
    { key: "company", label: "Company", placeholder: "Acme India" },
    { key: "email", label: "Email", type: "email", placeholder: "jane@company.com" },
    { key: "phone", label: "Phone", placeholder: "+91 98765 43210" },
    { key: "source", label: "Source", type: "select", options: ["Website", "Referral", "Event", "Partner", "Phone Call", "Manual Entry"] },
    { key: "status", label: "Status", type: "select", options: ["New", "Qualified", "Working", "Converted", "Lost"] },
    { key: "rating", label: "Rating", type: "select", options: ["Cold", "Warm", "Hot"] },
    { key: "nextFollowUp", label: "Next follow-up", type: "date" },
    { key: "owner", label: "Owner", placeholder: "Owner ID or name" },
  ],
  contacts: [
    { key: "name", label: "Contact name", required: true, placeholder: "Jane Shah" },
    { key: "company", label: "Company", placeholder: "Acme India" },
    { key: "email", label: "Email", type: "email", placeholder: "jane@company.com" },
    { key: "phone", label: "Phone", placeholder: "+91 98765 43210" },
    { key: "source", label: "Source", type: "select", options: ["Manual Entry", "Referral", "Website", "Partner"] },
    { key: "stage", label: "Lifecycle stage", type: "select", options: ["Lead", "Opportunity", "Customer"] },
    { key: "status", label: "Status", type: "select", options: ["Active", "Prospect", "Dormant"] },
    { key: "nextFollowUp", label: "Next follow-up", type: "date" },
    { key: "owner", label: "Owner", placeholder: "Owner ID or name" },
  ],
  companies: [
    { key: "name", label: "Company name", required: true, placeholder: "Acme India" },
    { key: "industry", label: "Industry", placeholder: "Software" },
    { key: "type", label: "Account type", type: "select", options: ["Prospect", "Customer", "Partner", "Vendor"] },
    { key: "revenue", label: "Annual revenue", type: "number", placeholder: "5000000" },
    { key: "status", label: "Status", type: "select", options: ["Active", "Prospect", "Inactive"] },
    { key: "owner", label: "Owner", placeholder: "Owner ID or name" },
  ],
  deals: [
    { key: "name", label: "Deal name", required: true, placeholder: "ERP rollout" },
    { key: "amount", label: "Amount", type: "number", placeholder: "500000" },
    { key: "probability", label: "Probability %", type: "number", placeholder: "10" },
    { key: "status", label: "Status", type: "select", options: ["Open", "Won", "Lost"] },
    { key: "nextFollowUp", label: "Expected close", type: "date" },
    { key: "owner", label: "Owner", placeholder: "Owner ID or name" },
  ],
  activities: [
    { key: "subject", label: "Subject", required: true, placeholder: "Follow-up call" },
    { key: "type", label: "Activity type", type: "select", options: ["Task", "Call", "Meeting", "Email"] },
    { key: "status", label: "Status", type: "select", options: ["Planned", "Open", "Completed"] },
    { key: "priority", label: "Priority", type: "select", options: ["Low", "Medium", "High"] },
    { key: "nextFollowUp", label: "Due date", type: "date" },
    { key: "owner", label: "Owner", placeholder: "Owner ID or name" },
  ],
  tasks: [
    { key: "subject", label: "Task title", required: true, placeholder: "Call lead" },
    { key: "status", label: "Status", type: "select", options: ["Open", "In Progress", "Completed"] },
    { key: "priority", label: "Priority", type: "select", options: ["Low", "Medium", "High"] },
    { key: "nextFollowUp", label: "Due date", type: "date" },
    { key: "owner", label: "Owner", placeholder: "Owner ID or name" },
  ],
  products: [
    { key: "name", label: "Product name", required: true, placeholder: "CRM Starter" },
    { key: "productCode", label: "Product code", placeholder: "CRM-STARTER" },
    { key: "category", label: "Category", placeholder: "Software" },
    { key: "price", label: "List price", type: "number", placeholder: "25000" },
    { key: "cost", label: "Cost price", type: "number", placeholder: "12000" },
    { key: "status", label: "Status", type: "select", options: ["Active", "Draft", "Inactive"] },
    { key: "owner", label: "Owner", placeholder: "Owner ID or name" },
  ],
  services: [
    { key: "serviceCode", label: "Service code", required: true, placeholder: "IMPL-STD" },
    { key: "name", label: "Service name", required: true, placeholder: "Implementation" },
    { key: "category", label: "Category", placeholder: "Professional Services" },
    { key: "billingType", label: "Billing type", type: "select", options: ["fixed", "hourly", "milestone", "recurring"] },
    { key: "price", label: "Default rate", type: "number", placeholder: "5000" },
    { key: "cost", label: "Default cost", type: "number", placeholder: "2500" },
  ],
  priceBooks: [
    { key: "name", label: "Price book", required: true, placeholder: "India Standard FY26" },
    { key: "currency", label: "Currency", placeholder: "INR" },
    { key: "region", label: "Region", placeholder: "India" },
    { key: "segment", label: "Segment", placeholder: "Mid-market" },
    { key: "status", label: "Status", type: "select", options: ["active", "draft", "inactive"] },
  ],
  quotes: [
    { key: "quote", label: "Quote number", placeholder: "QT-2026-001" },
    { key: "status", label: "Status", type: "select", options: ["Draft", "Pending Approval", "Approved", "Sent", "Accepted", "Declined"] },
    { key: "issueDate", label: "Quote date", type: "date" },
    { key: "expiryDate", label: "Valid until", type: "date" },
    { key: "total", label: "Grand total", type: "number", placeholder: "150000" },
  ],
  quotations: [
    { key: "quote", label: "Quote number", placeholder: "QT-2026-001" },
    { key: "status", label: "Status", type: "select", options: ["Draft", "Sent", "Accepted", "Rejected"] },
    { key: "issueDate", label: "Issue date", type: "date" },
    { key: "expiryDate", label: "Expiry date", type: "date" },
    { key: "total", label: "Total amount", type: "number", placeholder: "150000" },
  ],
  campaigns: [
    { key: "name", label: "Campaign name", required: true, placeholder: "Q2 Lead Nurture" },
    { key: "type", label: "Campaign type", type: "select", options: ["Email", "WhatsApp", "Event", "Ads"] },
    { key: "status", label: "Status", type: "select", options: ["Planned", "Active", "Completed"] },
    { key: "startDate", label: "Start date", type: "date" },
    { key: "endDate", label: "End date", type: "date" },
    { key: "budget", label: "Budget", type: "number", placeholder: "100000" },
    { key: "expectedRevenue", label: "Expected revenue", type: "number", placeholder: "250000" },
    { key: "owner", label: "Owner", placeholder: "Owner ID or name" },
  ],
  tickets: [
    { key: "subject", label: "Ticket subject", required: true, placeholder: "Customer issue" },
    { key: "number", label: "Ticket number", placeholder: "TCK-2026-001" },
    { key: "priority", label: "Priority", type: "select", options: ["Low", "Medium", "High", "Critical"] },
    { key: "status", label: "Status", type: "select", options: ["Open", "In Progress", "Resolved"] },
    { key: "category", label: "Category", type: "select", options: ["General", "Billing", "Technical", "Onboarding"] },
    { key: "source", label: "Source", type: "select", options: ["Manual", "Email", "Phone", "Portal"] },
    { key: "nextFollowUp", label: "Due date", type: "date" },
    { key: "owner", label: "Owner", placeholder: "Owner ID or name" },
  ],
};
type AutomationCard = [title: string, value: string, detail: string, Icon: React.ElementType];
type CRMApiState<T> = { data: T; loading: boolean; error: string | null };
type InlineFieldType = "text" | "number" | "date" | "select" | "tags";
type InlineEditConfig = { type: InlineFieldType; apiField: string; options?: string[] };

const customFieldEntities = [
  { value: "leads", label: "Leads" },
  { value: "contacts", label: "Contacts" },
  { value: "companies", label: "Accounts" },
  { value: "deals", label: "Deals" },
  { value: "quotations", label: "Quotations" },
  { value: "tasks", label: "Tasks" },
];

const customFieldTypes = [
  "text",
  "long_text",
  "number",
  "currency",
  "date",
  "datetime",
  "dropdown",
  "multi_select",
  "checkbox",
  "email",
  "phone",
  "url",
  "user",
  "owner",
];

const listInlineEditConfig: Partial<Record<CRMPageKind, Record<string, InlineEditConfig>>> = {
  leads: {
    name: { type: "text", apiField: "full_name" },
    company: { type: "text", apiField: "company_name" },
    email: { type: "text", apiField: "email" },
    phone: { type: "text", apiField: "phone" },
    source: { type: "select", apiField: "source", options: ["Website", "Referral", "Event", "Partner", "Phone Call", "Email Campaign", "Other"] },
    status: { type: "select", apiField: "status", options: ["New", "Contacted", "Qualified", "Converted", "Lost"] },
    rating: { type: "select", apiField: "rating", options: ["Hot", "Warm", "Cold"] },
    leadScore: { type: "number", apiField: "lead_score" },
    value: { type: "number", apiField: "estimated_value" },
    nextFollowUp: { type: "date", apiField: "next_follow_up_at" },
  },
  contacts: {
    name: { type: "text", apiField: "full_name" },
    email: { type: "text", apiField: "email" },
    phone: { type: "text", apiField: "phone" },
    title: { type: "text", apiField: "job_title" },
    stage: { type: "select", apiField: "lifecycle_stage", options: ["Lead", "Opportunity", "Customer", "Inactive"] },
    status: { type: "select", apiField: "status", options: ["Active", "Open", "Inactive"] },
    owner: { type: "number", apiField: "ownerId" },
    territoryId: { type: "number", apiField: "territoryId" },
  },
  companies: {
    name: { type: "text", apiField: "name" },
    industry: { type: "text", apiField: "industry" },
    type: { type: "select", apiField: "account_type", options: ["Prospect", "Customer", "Partner", "Vendor"] },
    status: { type: "select", apiField: "status", options: ["Active", "Inactive", "Prospect"] },
    revenue: { type: "number", apiField: "annual_revenue" },
    owner: { type: "number", apiField: "ownerId" },
    territoryId: { type: "number", apiField: "territoryId" },
    city: { type: "text", apiField: "city" },
    email: { type: "text", apiField: "email" },
  },
  deals: {
    name: { type: "text", apiField: "name" },
    owner: { type: "number", apiField: "ownerId" },
    territoryId: { type: "number", apiField: "territoryId" },
    stageId: { type: "number", apiField: "stage_id" },
    amount: { type: "number", apiField: "amount" },
    probability: { type: "number", apiField: "probability" },
    closeDate: { type: "date", apiField: "expected_close_date" },
    status: { type: "select", apiField: "status", options: ["Open", "Won", "Lost"] },
  },
  tasks: {
    subject: { type: "text", apiField: "title" },
    owner: { type: "number", apiField: "ownerId" },
    due: { type: "date", apiField: "due_date" },
    status: { type: "select", apiField: "status", options: ["To Do", "In Progress", "Completed", "Done"] },
    priority: { type: "select", apiField: "priority", options: ["Low", "Medium", "High", "Critical"] },
  },
};

const apiEntityForKind: Partial<Record<CRMPageKind, string>> = {
  leads: "leads",
  contacts: "contacts",
  companies: "companies",
  deals: "deals",
  pipeline: "deals",
  pipelineSettings: "pipelines",
  activities: "activities",
  tasks: "tasks",
  calendar: "meetings",
  products: "products",
  services: "services",
  priceBooks: "price-books",
  quotes: "quotes",
  quoteBuilder: "quotes",
  quoteApprovals: "quote-approvals",
  cpq: "cpq-rules",
  guidedSelling: "guided-selling-flows",
  quotations: "quotations",
  campaigns: "campaigns",
  tickets: "tickets",
  files: "files",
  settings: "custom-fields",
  leadScoring: "lead-scoring-rules",
  admin: "owners",
};

function useCrmRecords<T = CRMRecord>(entity: string | undefined, fallback: T[], params?: Record<string, unknown>): CRMApiState<T[]> {
  const [state, setState] = useState<CRMApiState<T[]>>({ data: fallback, loading: Boolean(entity), error: null });

  useEffect(() => {
    if (!entity) {
      setState({ data: fallback, loading: false, error: null });
      return;
    }
    let cancelled = false;
    setState((current) => ({ ...current, loading: true, error: null }));
    crmApi
      .list<CRMApiRecord>(entity, { per_page: 100, ...(params || {}) })
      .then((response) => {
        if (!cancelled) setState({ data: response.data.items.map((item) => normalizeApiRecord(kindlessEntity(entity), item)) as T[], loading: false, error: null });
      })
      .catch((err) => {
        if (!cancelled) setState({ data: fallback, loading: false, error: err?.response?.data?.detail || "CRM API is not reachable." });
      });
    return () => {
      cancelled = true;
    };
  }, [entity, JSON.stringify(params)]);

  return state;
}

function kindlessEntity(entity: string) {
  if (entity === "companies") return "companies";
  if (entity === "products") return "products";
  if (entity === "services") return "services";
  if (entity === "price-books") return "priceBooks";
  if (entity === "quotes") return "quotes";
  if (entity === "quote-approvals") return "quoteApprovals";
  if (entity === "cpq-rules") return "cpq";
  if (entity === "guided-selling-flows") return "guidedSelling";
  if (entity === "quotations") return "quotations";
  if (entity === "deals") return "deals";
  if (entity === "leads") return "leads";
  if (entity === "contacts") return "contacts";
  if (entity === "activities") return "activities";
  if (entity === "tasks") return "tasks";
  if (entity === "meetings") return "meetings";
  if (entity === "custom-fields") return "settings";
  if (entity === "owners") return "admin";
  return entity;
}

export default function CRMWorkspacePage({ kind }: { kind: CRMPageKind }) {
  if (kind === "pipeline") return <PipelinePage />;
  if (kind === "pipelineSettings") return <PipelineSettingsPage />;
  if (kind === "leadScoring") return <LeadScoringSettingsPage />;
  if (kind === "calendar") return <CRMCalendarPage />;
  if (kind === "calendarIntegrations") return <CalendarIntegrationsPage />;
  if (kind === "webhooks") return <WebhookSettingsPage />;
  if (kind === "approvalSettings") return <ApprovalSettingsPage />;
  if (kind === "myApprovals") return <MyApprovalsPage />;
  if (kind === "duplicates") return <DuplicateManagementPage />;
  if (kind === "territories") return <TerritorySettingsPage />;
  if (kind === "featureChecklist") return <CRMFeatureChecklistPage />;
  if (kind === "settings") return <CustomFieldsSettingsPage />;
  if (kind === "dashboard") return <CRMDashboard />;
  if (kind === "reports") return <CRMReports />;
  if (kind === "automation") return <SalesAutomationPage />;
  if (kind === "leadCash") return <LeadToCashPage />;
  if (kind === "forecasting") return <ForecastingPage />;
  if (kind === "targets") return <SalesTargetsPage />;
  if (kind === "salesPerformance") return <SalesPerformancePage />;
  if (kind === "funnel") return <FunnelAnalyticsPage />;
  if (kind === "lostAnalysis") return <LostAnalysisPage />;
  if (kind === "customer360") return <Customer360Page />;
  if (kind === "importExport") return <ImportExportPage />;
  if (kind === "products") return <ProductCatalogPage />;
  if (kind === "quoteBuilder") return <QuoteBuilderPage />;
  if (kind === "quoteApprovals") return <QuoteApprovalsPage />;
  if (kind === "cpq") return <CPQPage />;
  if (kind === "guidedSelling") return <GuidedSellingPage />;
  return <CRMListPage kind={kind} />;
}

function CRMDashboard() {
  const navigate = useNavigate();
  const leadState = useCrmRecords<CRMRecord>("leads", emptyRecords);
  const contactState = useCrmRecords<CRMRecord>("contacts", emptyRecords);
  const companyState = useCrmRecords<CRMRecord>("companies", emptyRecords);
  const dealState = useCrmRecords<CRMRecord>("deals", emptyRecords);
  const stageState = useCrmRecords<CRMRecord>("pipeline-stages", emptyRecords, { sort_by: "position", sort_order: "asc" });
  const [dashboardMode, setDashboardMode] = useState<"simple" | "advanced">("simple");
  const [quickCreateKind, setQuickCreateKind] = useState<DashboardQuickCreateKind>("leads");
  const [showQuickCreate, setShowQuickCreate] = useState(false);
  const [quickCreateSaving, setQuickCreateSaving] = useState(false);
  const [quickCreateError, setQuickCreateError] = useState<string | null>(null);
  const crmLeads = useMemo(() => leadState.data.map(recordToLead), [leadState.data]);
  const companyNames = useMemo(() => companyNameLookup(companyState.data), [companyState.data]);
  const crmDeals = useMemo(() => dealState.data.map((record) => recordToDeal(record, stageState.data, companyNames)), [dealState.data, stageState.data, companyNames]);
  const stageNames = useMemo(() => stageState.data.map((stage) => String(stage.name)).filter(Boolean), [stageState.data]);
  const openCrmDeals = crmDeals.filter(isOpenDeal);
  const wonCrmDeals = crmDeals.filter((deal) => isWonDeal(deal.stage));
  const lostCrmDeals = crmDeals.filter((deal) => isLostDeal(deal.stage));
  const wonRevenue = wonCrmDeals.reduce((sum, deal) => sum + deal.amount, 0);
  const pipelineValue = openCrmDeals.reduce((sum, deal) => sum + deal.amount, 0);
  const weighted = openCrmDeals.reduce((sum, deal) => sum + (deal.amount * deal.probability) / 100, 0);
  const overdueFollowUps = crmLeads.filter((lead) => lead.nextFollowUp && new Date(lead.nextFollowUp) < new Date() && lead.status !== "Converted").length;
  const openDeals = openCrmDeals.length;
  const wonDeals = wonCrmDeals.length;
  const lostDeals = lostCrmDeals.length;
  const contactsCreated = countRecordsThisMonth(contactState.data);
  const convertedLeads = crmLeads.filter((lead) => lead.status === "Converted").length;
  const hotLeads = crmLeads.filter((lead) => lead.rating === "Hot" || lead.scoreLabel === "Hot").length;
  const averageDealSize = crmDeals.length ? crmDeals.reduce((sum, deal) => sum + deal.amount, 0) / crmDeals.length : 0;
  const winRate = wonDeals + lostDeals ? Math.round((wonDeals / (wonDeals + lostDeals)) * 100) : 0;
  const conversionRate = crmLeads.length ? Math.round((convertedLeads / crmLeads.length) * 100) : 0;
  const weightedCoverage = pipelineValue ? Math.round((weighted / pipelineValue) * 100) : 0;
  const staleOpenDeals = openCrmDeals.filter((deal) => deal.closeDate && new Date(deal.closeDate) < new Date()).length;
  const chartStages = stageNames.length ? stageNames : Array.from(new Set(crmDeals.map((deal) => deal.stage).filter(Boolean)));
  const chartData = chartStages.map((stage) => ({
    stage,
    value: openCrmDeals.filter((deal) => deal.stage === stage).reduce((sum, deal) => sum + deal.amount, 0),
  })).filter((row) => row.value > 0 || !stageNames.length);
  const sourceData = ["Website", "Referral", "Event", "Partner", "Phone Call", "Email Campaign"].map((source) => ({
    name: source,
    value: crmLeads.filter((lead) => lead.source === source).length,
  }));
  const revenueTrend = useMemo(() => {
    const buckets = new Map<string, { month: string; revenue: number; forecast: number }>();
    dealState.data.forEach((deal) => {
      const rawDate = String(deal.closed_at || deal.wonAt || deal.won_at || deal.expected_close_date || deal.createdAt || deal.created_at || "");
      const date = rawDate ? new Date(rawDate) : null;
      if (!date || Number.isNaN(date.getTime())) return;
      const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
      const month = date.toLocaleDateString(undefined, { month: "short" });
      const current = buckets.get(key) || { month, revenue: 0, forecast: 0 };
      const amount = Number(deal.amount || 0);
      if (String(deal.status || "").toLowerCase() === "won") current.revenue += amount;
      current.forecast += (amount * Number(deal.probability || 0)) / 100;
      buckets.set(key, current);
    });
    return Array.from(buckets.entries()).sort(([a], [b]) => a.localeCompare(b)).slice(-6).map(([, value]) => value);
  }, [dealState.data]);
  const insightRows = [
    `${crmLeads.filter((lead) => lead.rating === "Hot" || lead.scoreLabel === "Hot").length} hot leads are visible from current CRM data.`,
    `${openDeals} ${pluralize("open deal", openDeals)} ${openDeals === 1 ? "carries" : "carry"} ${formatCurrency(pipelineValue)} in pipeline value.`,
    `${staleOpenDeals} ${pluralize("open deal", staleOpenDeals)} ${staleOpenDeals === 1 ? "is" : "are"} past expected close date.`,
    `${openCrmDeals.filter((deal) => deal.probability >= 70).length} high-probability ${pluralize("deal", openCrmDeals.filter((deal) => deal.probability >= 70).length)} should be reviewed for approvals and quotation follow-up.`,
  ];
  const createQuickRecord = (draft: CRMRecord, customFields?: CRMApiRecord) => {
    const apiEntity = apiEntityForKind[quickCreateKind];
    if (!apiEntity) return;
    const payload = { ...createPayloadForKind(quickCreateKind, draft), customFields: customFields || {} };
    setQuickCreateSaving(true);
    setQuickCreateError(null);
    crmApi
      .create<CRMApiRecord>(apiEntity, payload)
      .then((response) => {
        setShowQuickCreate(false);
        const detailPath = detailPathFor(quickCreateKind);
        if (detailPath && response.data?.id) {
          navigate(`${detailPath}/${response.data.id}`);
          return;
        }
        navigate(`/crm/${quickCreateKind}`);
      })
      .catch((err) => setQuickCreateError(err?.response?.data?.detail || "CRM record could not be created."))
      .finally(() => setQuickCreateSaving(false));
  };

  return (
    <div className="min-h-[calc(100vh-5rem)] max-w-full overflow-hidden bg-slate-50/70">
      <div className="border-b bg-white px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <select className="h-10 rounded-full border bg-white px-4 text-sm font-semibold text-slate-950" defaultValue="overview" aria-label="Dashboard view">
                <option value="overview">Overview</option>
                <option value="sales">Sales performance</option>
                <option value="activity">Activity performance</option>
                <option value="forecast">Forecast</option>
              </select>
              <div className="flex rounded-full border bg-slate-50 p-1" aria-label="Dashboard mode">
                {(["simple", "advanced"] as const).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    className={`rounded-full px-4 py-1.5 text-sm font-semibold transition ${dashboardMode === mode ? "bg-white text-emerald-700 shadow-sm" : "text-slate-600 hover:text-slate-950"}`}
                    onClick={() => setDashboardMode(mode)}
                  >
                    {mode === "simple" ? "Simple" : "Advanced"}
                  </button>
                ))}
              </div>
              <Badge variant="outline">Live CRM</Badge>
              <Badge className="bg-emerald-50 text-emerald-700 hover:bg-emerald-50">{dashboardMode === "simple" ? "Simple dashboard" : "Executive dashboard"}</Badge>
            </div>
            <h1 className="mt-3 text-2xl font-semibold tracking-tight text-slate-950">VyaparaCRM</h1>
            <p className="max-w-3xl text-sm text-slate-600">Sales command center for leads, accounts, deals, pipeline, activities, quotations, support, automation, and analytics.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => navigate("/crm/reports")}><BarChart3 className="h-4 w-4" />Reports</Button>
            <Button variant="outline" onClick={() => navigate("/crm/templates")}><LayoutGrid className="h-4 w-4" />Templates</Button>
            <Button onClick={() => setShowQuickCreate(true)}><Plus className="h-4 w-4" />Quick create</Button>
          </div>
        </div>
      </div>
      <main className="space-y-5 px-4 py-4 sm:px-6 lg:px-8">
      {leadState.error || contactState.error || companyState.error || dealState.error || stageState.error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{leadState.error || contactState.error || companyState.error || dealState.error || stageState.error}</div> : null}
      {leadState.loading || contactState.loading || companyState.loading || dealState.loading || stageState.loading ? <div className="rounded-md border bg-white px-4 py-3 text-sm text-slate-500">Loading CRM dashboard...</div> : null}
      {dashboardMode === "simple" ? (
        <SimpleDashboardView
          chartData={chartData}
          contactsCreated={contactsCreated}
          crmDeals={crmDeals}
          crmLeads={crmLeads}
          lostDeals={lostDeals}
          openDeals={openDeals}
          overdueFollowUps={overdueFollowUps}
          pipelineValue={pipelineValue}
          weighted={weighted}
          wonDeals={wonDeals}
          wonRevenue={wonRevenue}
          onOpenPipeline={() => navigate("/crm/pipeline")}
          onQuickCreate={() => setShowQuickCreate(true)}
        />
      ) : (
      <>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
        <DashboardKpiCard title="Contacts created" value={contactsCreated} previous={`${contactState.data.length} total contacts`} delta={conversionRate || 0} />
        <DashboardKpiCard title="Deals won" value={wonDeals} previous={formatCurrency(wonRevenue)} delta={winRate} tone="emerald" />
        <DashboardKpiCard title="Deals lost" value={lostDeals} previous="This month" delta={lostDeals ? -100 : 0} tone="red" />
        <DashboardKpiCard title="Tasks closed" value={Math.max(0, crmLeads.length - overdueFollowUps)} previous={`${overdueFollowUps} overdue`} delta={overdueFollowUps ? -overdueFollowUps : 0} tone="amber" />
        <DashboardKpiCard title="Open pipeline" value={openDeals} previous={formatCurrency(pipelineValue)} delta={weightedCoverage} tone="blue" />
        <DashboardKpiCard title="Forecast" value={formatCurrency(weighted)} previous="Weighted revenue" delta={weightedCoverage} tone="violet" />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_26rem]">
        <div className="space-y-4">
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <div>
                <CardTitle>Open deals by stage - This Month</CardTitle>
                <p className="text-sm text-muted-foreground">Stage-wise pipeline value from current CRM data.</p>
              </div>
              <Button variant="ghost" size="icon" onClick={() => navigate("/crm/pipeline")} aria-label="Open pipeline"><RefreshIcon /></Button>
            </CardHeader>
            <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} layout="vertical" margin={{ left: 24 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis type="number" tickFormatter={formatChartCurrency} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="stage" tickLine={false} axisLine={false} width={110} />
                <Tooltip formatter={(value) => formatCurrency(Number(value))} />
                <Bar dataKey="value" fill="#38bdf8" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
            </CardContent>
          </Card>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader><CardTitle>Revenue trend and forecast</CardTitle></CardHeader>
              <CardContent className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={revenueTrend}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="month" tickLine={false} axisLine={false} />
                    <YAxis tickFormatter={formatChartCurrency} tickLine={false} axisLine={false} />
                    <Tooltip formatter={(value) => formatCurrency(Number(value))} />
                    <Line type="monotone" dataKey="revenue" stroke="#16a34a" strokeWidth={3} dot={false} />
                    <Line type="monotone" dataKey="forecast" stroke="#2563eb" strokeWidth={3} strokeDasharray="4 4" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Leads by source</CardTitle></CardHeader>
              <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={sourceData} dataKey="value" nameKey="name" innerRadius={58} outerRadius={104}>
                  {sourceData.map((_, index) => <Cell key={index} fill={["#2563eb", "#16a34a", "#f59e0b", "#7c3aed", "#dc2626", "#0891b2"][index]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
        </div>
        <div className="space-y-4">
          <DashboardTopCompanies deals={crmDeals} />
          <Card>
          <CardHeader><CardTitle>AI Insights</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {insightRows.map((text) => <Insight key={text} text={text} />)}
          </CardContent>
          </Card>
          <DashboardActionPanel onQuickCreate={() => setShowQuickCreate(true)} onPipeline={() => navigate("/crm/pipeline")} onReports={() => navigate("/crm/reports")} />
        </div>
      </div>

      <DashboardStatistics
        leads={crmLeads.length}
        hotLeads={hotLeads}
        convertedLeads={convertedLeads}
        openDeals={openDeals}
        wonDeals={wonDeals}
        lostDeals={lostDeals}
        pipelineValue={pipelineValue}
        weighted={weighted}
        wonRevenue={wonRevenue}
        averageDealSize={averageDealSize}
        conversionRate={conversionRate}
        winRate={winRate}
        weightedCoverage={weightedCoverage}
        overdueFollowUps={overdueFollowUps}
        staleOpenDeals={staleOpenDeals}
      />
      </>
      )}
      {showQuickCreate ? (
        <DashboardQuickCreateDialog
          kind={quickCreateKind}
          saving={quickCreateSaving}
          error={quickCreateError}
          onKindChange={(kind) => {
            setQuickCreateKind(kind);
            setQuickCreateError(null);
          }}
          onClose={() => setShowQuickCreate(false)}
        onCreate={createQuickRecord}
      />
      ) : null}
      </main>
    </div>
  );
}

function DashboardStatistics({
  leads,
  hotLeads,
  convertedLeads,
  openDeals,
  wonDeals,
  lostDeals,
  pipelineValue,
  weighted,
  wonRevenue,
  averageDealSize,
  conversionRate,
  winRate,
  weightedCoverage,
  overdueFollowUps,
  staleOpenDeals,
}: {
  leads: number;
  hotLeads: number;
  convertedLeads: number;
  openDeals: number;
  wonDeals: number;
  lostDeals: number;
  pipelineValue: number;
  weighted: number;
  wonRevenue: number;
  averageDealSize: number;
  conversionRate: number;
  winRate: number;
  weightedCoverage: number;
  overdueFollowUps: number;
  staleOpenDeals: number;
}) {
  const funnelRows = [
    { label: "Total leads", value: leads, max: Math.max(leads, 1), tone: "bg-emerald-500" },
    { label: "Hot leads", value: hotLeads, max: Math.max(leads, 1), tone: "bg-amber-500" },
    { label: "Converted leads", value: convertedLeads, max: Math.max(leads, 1), tone: "bg-blue-500" },
    { label: "Open deals", value: openDeals, max: Math.max(openDeals + wonDeals + lostDeals, 1), tone: "bg-violet-500" },
  ];
  const cards = [
    { label: "Lead conversion", value: `${conversionRate}%`, detail: `${convertedLeads} converted from ${leads}`, Icon: Target },
    { label: "Win rate", value: `${winRate}%`, detail: `${wonDeals} won / ${lostDeals} lost`, Icon: CheckCircle2 },
    { label: "Weighted coverage", value: `${weightedCoverage}%`, detail: `${formatCurrency(weighted)} weighted`, Icon: BarChart3 },
    { label: "Average deal size", value: formatCurrency(averageDealSize), detail: `${formatCurrency(wonRevenue)} won revenue`, Icon: IndianRupee },
  ];
  const hygieneRows = [
    { label: "Overdue follow-ups", value: overdueFollowUps, note: "Leads needing action" },
    { label: "Past close date", value: staleOpenDeals, note: "Open deals to review" },
    { label: "Active pipeline", value: formatCurrency(pipelineValue), note: "Open deal value" },
  ];

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-1">
        <h2 className="text-lg font-semibold tracking-tight">Dashboard Statistics</h2>
        <p className="text-sm text-muted-foreground">Live CRM performance calculated from leads, deals, stage movement, and follow-up data.</p>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {cards.map(({ label, value, detail, Icon }) => (
          <Card key={label}>
            <CardContent className="flex items-center gap-3 p-4">
              <div className="rounded-lg bg-emerald-500/10 p-2 text-emerald-700">
                <Icon className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <p className="text-2xl font-semibold">{value}</p>
                <p className="text-sm font-medium">{label}</p>
                <p className="text-xs text-muted-foreground">{detail}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle>Lead-to-revenue funnel</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {funnelRows.map((row) => {
              const width = row.value > 0 ? Math.max(6, Math.round((row.value / row.max) * 100)) : 0;
              return (
                <div key={row.label} className="space-y-2">
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <span className="font-medium">{row.label}</span>
                    <span className="text-muted-foreground">{row.value}</span>
                  </div>
                  <div className="h-2.5 overflow-hidden rounded-full bg-muted">
                    <div className={`h-full rounded-full ${row.tone}`} style={{ width: `${width}%` }} />
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Pipeline hygiene</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3">
            {hygieneRows.map((row) => (
              <div key={row.label} className="rounded-md border bg-muted/20 p-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-medium">{row.label}</span>
                  <span className="text-lg font-semibold">{row.value}</span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{row.note}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </section>
  );
}

function SimpleDashboardView({
  chartData,
  contactsCreated,
  crmDeals,
  crmLeads,
  lostDeals,
  openDeals,
  overdueFollowUps,
  pipelineValue,
  weighted,
  wonDeals,
  wonRevenue,
  onOpenPipeline,
  onQuickCreate,
}: {
  chartData: Array<{ stage: string; value: number }>;
  contactsCreated: number;
  crmDeals: CRMDeal[];
  crmLeads: CRMLead[];
  lostDeals: number;
  openDeals: number;
  overdueFollowUps: number;
  pipelineValue: number;
  weighted: number;
  wonDeals: number;
  wonRevenue: number;
  onOpenPipeline: () => void;
  onQuickCreate: () => void;
}) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <SimpleDashboardCard title="Contacts Created - This Month" value={contactsCreated} detail={`${crmLeads.length} leads tracked`} tone="emerald" />
        <SimpleDashboardCard title="Deals Won - This Month" value={wonDeals} detail={wonDeals ? formatCurrency(wonRevenue) : "No closed-won deals yet"} tone="emerald" />
        <SimpleDashboardCard title="Deals Lost - This Month" value={lostDeals} detail={lostDeals ? "Review lost reasons" : "No lost deals yet"} tone="red" />
        <SimpleDashboardCard title="Open Pipeline" value={formatCurrency(pipelineValue)} detail={`${openDeals} active deals`} tone="blue" />
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_26rem]">
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle>Open Deals by Stage - This Month</CardTitle>
              <p className="text-sm text-muted-foreground">Simple stage overview for daily sales reviews.</p>
            </div>
            <Button variant="outline" size="sm" onClick={onOpenPipeline}><LayoutGrid className="h-4 w-4" />Pipeline</Button>
          </CardHeader>
          <CardContent className="h-[26rem]">
            {chartData.some((item) => item.value > 0) ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} layout="vertical" margin={{ left: 24 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis type="number" tickFormatter={formatChartCurrency} tickLine={false} axisLine={false} />
                  <YAxis type="category" dataKey="stage" tickLine={false} axisLine={false} width={110} />
                  <Tooltip formatter={(value) => formatCurrency(Number(value))} />
                  <Bar dataKey="value" fill="#38bdf8" radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <DashboardNoData label="No open deal stage data yet" />
            )}
          </CardContent>
        </Card>
        <div className="space-y-4">
          <DashboardTopCompanies deals={crmDeals} />
          <Card>
            <CardHeader><CardTitle>Today&apos;s focus</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <SimpleFocusRow label="Overdue follow-ups" value={overdueFollowUps} />
              <SimpleFocusRow label="Weighted forecast" value={formatCurrency(weighted)} />
              <SimpleFocusRow label="Open deals" value={openDeals} />
              <Button className="w-full justify-start" onClick={onQuickCreate}><Plus className="h-4 w-4" />Add lead, deal, or task</Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function SimpleDashboardCard({ title, value, detail, tone }: { title: string; value: string | number; detail: string; tone: "emerald" | "red" | "blue" }) {
  const toneClass = tone === "emerald" ? "text-emerald-600" : tone === "red" ? "text-red-600" : "text-sky-600";
  return (
    <Card>
      <CardContent className="p-5">
        <p className="font-semibold text-slate-950">{title}</p>
        <p className={`mt-5 text-4xl font-semibold tracking-tight ${toneClass}`}>{value}</p>
        <p className="mt-2 text-sm text-slate-500">{detail}</p>
      </CardContent>
    </Card>
  );
}

function SimpleFocusRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border bg-slate-50/70 px-3 py-2 text-sm">
      <span className="text-slate-600">{label}</span>
      <span className="font-semibold text-slate-950">{value}</span>
    </div>
  );
}

function DashboardKpiCard({ title, value, previous, delta, tone = "emerald" }: { title: string; value: string | number; previous: string; delta: number; tone?: "emerald" | "red" | "amber" | "blue" | "violet" }) {
  const toneClasses = {
    emerald: "text-emerald-600 bg-emerald-50",
    red: "text-red-600 bg-red-50",
    amber: "text-amber-600 bg-amber-50",
    blue: "text-sky-600 bg-sky-50",
    violet: "text-violet-600 bg-violet-50",
  };
  const deltaLabel = delta > 0 ? `+${delta}%` : delta < 0 ? `${delta}%` : "0%";
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-sm font-semibold text-slate-950">{title}</p>
        <div className="mt-4 flex items-end gap-2">
          <p className="text-3xl font-semibold tracking-tight text-slate-950">{value}</p>
          <span className={`mb-1 rounded-full px-2 py-0.5 text-xs font-semibold ${toneClasses[tone]}`}>{deltaLabel}</span>
        </div>
        <p className="mt-2 text-sm text-slate-500">{previous}</p>
      </CardContent>
    </Card>
  );
}

function DashboardTopCompanies({ deals }: { deals: CRMDeal[] }) {
  const companies = Array.from(deals.reduce((map, deal) => {
    const key = deal.company || "Unassigned";
    const current = map.get(key) || { company: key, amount: 0, count: 0 };
    current.amount += deal.amount;
    current.count += 1;
    map.set(key, current);
    return map;
  }, new Map<string, { company: string; amount: number; count: number }>()).values()).sort((a, b) => b.amount - a.amount).slice(0, 5);
  return (
    <Card>
      <CardHeader><CardTitle>Top 5 Company</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {companies.length ? companies.map((company, index) => (
          <div key={company.company} className="flex items-center justify-between gap-3 rounded-md border bg-slate-50/70 p-3">
            <div className="flex items-center gap-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-100 text-sm font-semibold text-emerald-700">{index + 1}</span>
              <div>
                <p className="font-medium text-slate-950">{company.company}</p>
                <p className="text-xs text-slate-500">{company.count} deal(s)</p>
              </div>
            </div>
            <p className="font-semibold text-slate-950">{formatCurrency(company.amount)}</p>
          </div>
        )) : <DashboardNoData label="No company data yet" />}
      </CardContent>
    </Card>
  );
}

function DashboardActionPanel({ onQuickCreate, onPipeline, onReports }: { onQuickCreate: () => void; onPipeline: () => void; onReports: () => void }) {
  return (
    <Card>
      <CardHeader><CardTitle>Dashboard actions</CardTitle></CardHeader>
      <CardContent className="grid gap-2">
        <Button className="justify-start" onClick={onQuickCreate}><Plus className="h-4 w-4" />Create CRM record</Button>
        <Button variant="outline" className="justify-start" onClick={onPipeline}><LayoutGrid className="h-4 w-4" />Open pipeline board</Button>
        <Button variant="outline" className="justify-start" onClick={onReports}><BarChart3 className="h-4 w-4" />Open detailed reports</Button>
      </CardContent>
    </Card>
  );
}

function DashboardNoData({ label }: { label: string }) {
  return <div className="rounded-md border border-dashed bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">{label}</div>;
}

function RefreshIcon() {
  return <Clock className="h-4 w-4" />;
}

function isWonDeal(stage: string) {
  return ["won", "closed won", "service active", "delivered", "paid"].includes(stage.trim().toLowerCase());
}

function isLostDeal(stage: string) {
  return ["lost", "closed lost", "rejected"].includes(stage.trim().toLowerCase());
}

function isOpenDeal(deal: CRMDeal) {
  return !isWonDeal(deal.stage) && !isLostDeal(deal.stage);
}

function formatChartCurrency(value: number | string) {
  const amount = Number(value || 0);
  if (Math.abs(amount) >= 100000) return `₹${Math.round(amount / 100000)}L`;
  if (Math.abs(amount) >= 1000) return `₹${Math.round(amount / 1000)}K`;
  return `₹${amount}`;
}

function countRecordsThisMonth(records: CRMRecord[]) {
  const now = new Date();
  const dated = records.filter((record) => {
    const raw = String(record.createdAt || record.created_at || record.createdDate || record.created_date || "");
    if (!raw) return false;
    const date = new Date(raw);
    return !Number.isNaN(date.getTime()) && date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth();
  });
  return dated.length || records.length;
}

function companyNameLookup(companies: CRMRecord[]) {
  const entries: Array<[number, string]> = companies
    .map((company) => [Number(company.id || 0), String(company.name || company.companyName || company.company_name || "")] as [number, string])
    .filter(([id, name]) => Boolean(id && name));
  return new Map<number, string>(entries);
}

function pluralize(label: string, count: number) {
  return count === 1 ? label : `${label}s`;
}

function PipelinePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const dealState = useCrmRecords<CRMRecord>("deals", emptyRecords);
  const pipelineState = useCrmRecords<CRMRecord>("pipelines", emptyRecords, { sort_by: "created_at", sort_order: "asc" });
  const stageState = useCrmRecords<CRMRecord>("pipeline-stages", emptyRecords, { sort_by: "position", sort_order: "asc" });
  const [selectedPipelineId, setSelectedPipelineId] = useState<number | null>(null);
  const [activeTemplateKey, setActiveTemplateKey] = useState("sales-pipeline");
  const [templateSearch, setTemplateSearch] = useState("");
  const [templateGroup, setTemplateGroup] = useState<"All" | "Teams" | "Industries">("All");
  const [applyingTemplate, setApplyingTemplate] = useState(false);
  const [templateMessage, setTemplateMessage] = useState<string | null>(null);
  const activePipelineId = selectedPipelineId || Number(pipelineState.data.find((pipeline) => pipeline.is_default)?.id || pipelineState.data[0]?.id || 0);
  const pipelineStages = useMemo(() => stageState.data.filter((stage) => Number(stage.pipeline_id || stage.pipelineId || 0) === activePipelineId), [stageState.data, activePipelineId]);
  const stageByName = useMemo(() => new Map(pipelineStages.map((stage) => [String(stage.name), stage])), [pipelineStages]);
  const initialDeals = useMemo<CRMDeal[]>(() => dealState.data.filter((record) => Number(record.pipelineId || record.pipeline_id || 0) === activePipelineId).map((record) => recordToDeal(record, pipelineStages)), [dealState.data, pipelineStages, activePipelineId]);
  const [deals, setDeals] = useState<CRMDeal[]>(initialDeals);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [filter, setFilter] = useState("");
  const [transitioningDealId, setTransitioningDealId] = useState<number | null>(null);
  const [transitionMessage, setTransitionMessage] = useState<string | null>(null);
  const isTemplateLibrary = location.pathname.includes("/crm/templates");
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));
  const activeDeal = deals.find((deal) => deal.id === activeId);
  const visibleDeals = deals.filter((deal) => [deal.name, deal.company, deal.owner].join(" ").toLowerCase().includes(filter.toLowerCase()));
  const selectedTemplate = allCrmBusinessTemplates.find((template) => template.key === activeTemplateKey) || allCrmBusinessTemplates[0];
  const filteredTemplates = allCrmBusinessTemplates.filter((template) => {
    const matchesGroup = templateGroup === "All" || template.group === templateGroup;
    const text = [template.name, template.category, template.fields.join(" "), template.reports.join(" ")].join(" ").toLowerCase();
    return matchesGroup && text.includes(templateSearch.toLowerCase());
  });
  const openDeals = visibleDeals.filter((deal) => !["Won", "Lost", "Closed Won", "Closed Lost"].includes(deal.stage));
  const pipelineValue = openDeals.reduce((sum, deal) => sum + deal.amount, 0);
  const weightedValue = openDeals.reduce((sum, deal) => sum + (deal.amount * deal.probability) / 100, 0);
  const dueSoon = visibleDeals.filter((deal) => {
    if (!deal.closeDate || ["Won", "Lost", "Closed Won", "Closed Lost"].includes(deal.stage)) return false;
    const close = new Date(deal.closeDate);
    const now = new Date();
    const nextWeek = new Date();
    nextWeek.setDate(now.getDate() + 7);
    return close >= now && close <= nextWeek;
  }).length;

  useEffect(() => {
    setDeals(initialDeals);
  }, [initialDeals]);

  const applyTemplate = async () => {
    setApplyingTemplate(true);
    setTemplateMessage(null);
    try {
      const pipelineResponse = await crmApi.create<CRMApiRecord>("pipelines", {
        name: selectedTemplate.name,
        description: `${selectedTemplate.category} CRM template`,
      });
      const pipeline = normalizeApiRecord("pipelines", pipelineResponse.data) as CRMRecord;
      const pipelineId = Number(pipeline.id);
      const createdStages: CRMRecord[] = [];
      for (const [index, stage] of selectedTemplate.stages.entries()) {
        const stageResponse = await crmApi.createPipelineStage<CRMApiRecord>(pipelineId, {
          name: stage.name,
          probability: stage.probability,
          color: stage.color,
          position: index + 1,
          is_won: Boolean(stage.isWon),
          is_lost: Boolean(stage.isLost),
        });
        createdStages.push(normalizeApiRecord("pipeline-stages", stageResponse.data) as CRMRecord);
      }
      let fieldCount = 0;
      for (const field of selectedTemplate.customFields || []) {
        try {
          await crmApi.create<CRMApiRecord>("custom-fields", { ...field, displayOrder: fieldCount + 1 });
          fieldCount += 1;
        } catch (fieldError: any) {
          if (fieldError?.response?.status !== 409) throw fieldError;
        }
      }
      let dealCount = 0;
      for (const deal of templateSampleDeals(selectedTemplate)) {
        const stage = createdStages[Math.min(Math.max(deal.stageIndex || 0, 0), createdStages.length - 1)] || createdStages[0];
        if (!stage) continue;
        const isWon = Boolean(stage.isWon ?? stage.is_won);
        const isLost = Boolean(stage.isLost ?? stage.is_lost);
        await crmApi.create<CRMApiRecord>("deals", {
          name: deal.name,
          pipeline_id: pipelineId,
          stage_id: Number(stage.id),
          amount: deal.amount,
          probability: Number(stage.probability || 0),
          status: isWon ? "Won" : isLost ? "Lost" : "Open",
          expected_close_date: deal.closeDate,
          description: deal.nextStep,
          lead_source: deal.source,
          source: deal.source,
          customFields: deal.customFields || {},
        });
        dealCount += 1;
      }
      setSelectedPipelineId(pipelineId);
      setTemplateMessage(`${selectedTemplate.name} pipeline created with ${createdStages.length} stages, ${fieldCount} custom fields, and ${dealCount} sample deals. Refresh to load persisted board data if it does not appear immediately.`);
    } catch (error: any) {
      setTemplateMessage(error?.response?.data?.detail || "Template could not be applied.");
    } finally {
      setApplyingTemplate(false);
    }
  };

  const onDragStart = (event: DragStartEvent) => setActiveId(event.active.id as number);
  const transitionDealToStage = (dealId: number, targetStageRecord: CRMRecord) => {
    const targetStage = String(targetStageRecord.name || "");
    if (!targetStage || !activePipelineId) return;
    const probability = Number(targetStageRecord.probability ?? stageProbability(targetStage));
    const { status } = stageStatusFor(targetStageRecord);
    const previousDeals = deals;
    const dealName = deals.find((deal) => deal.id === dealId)?.name || "Deal";
    setTransitioningDealId(dealId);
    setTransitionMessage(null);
    setDeals((items) => items.map((deal) => (deal.id === dealId ? { ...deal, stage: targetStage, stageId: Number(targetStageRecord.id), pipelineId: activePipelineId, probability, status } : deal)));
    crmApi
      .update("deals", dealId, { pipeline_id: activePipelineId, stage_id: Number(targetStageRecord.id), probability, status })
      .then(() => setTransitionMessage(`${dealName} moved to ${targetStage}.`))
      .catch((error) => {
        setDeals(previousDeals);
        setTransitionMessage(error?.response?.data?.detail || `Could not move ${dealName}.`);
      })
      .finally(() => setTransitioningDealId(null));
  };
  const onDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveId(null);
    if (!over) return;
    const targetStage = String(over.id).startsWith("stage-") ? String(over.id).replace("stage-", "") : deals.find((deal) => deal.id === over.id)?.stage;
    if (!targetStage) return;
    const targetStageRecord = stageByName.get(targetStage);
    if (!targetStageRecord) return;
    transitionDealToStage(Number(active.id), targetStageRecord);
  };

  return (
    <div className="min-h-[calc(100vh-5rem)] bg-slate-50/70">
      <div className="border-b bg-white px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">VyaparaCRM</Badge>
              <Badge className="bg-emerald-50 text-emerald-700 hover:bg-emerald-50">{isTemplateLibrary ? "Organization templates" : "Template-ready"}</Badge>
            </div>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">{isTemplateLibrary ? "Customized CRM templates" : "Sales command pipeline"}</h1>
            <p className="max-w-3xl text-sm text-slate-600">
              {isTemplateLibrary
                ? "Clone a ready-made CRM workspace for sales, service, finance, professional firms, retail, healthcare, education, automotive, IT, and local businesses."
                : "A faster CRM board with industry templates, weighted forecast, deal hygiene, and CRM-to-SRM handoff readiness in one workspace."}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => navigate("/crm/deals")}><ListFilter className="h-4 w-4" />Deal list</Button>
            <Button variant={isTemplateLibrary ? "default" : "outline"} onClick={() => navigate("/crm/templates")}><LayoutGrid className="h-4 w-4" />Templates</Button>
            <Button variant="outline" onClick={() => navigate("/crm/reports")}><BarChart3 className="h-4 w-4" />Reports</Button>
            <Button onClick={() => navigate("/crm/pipeline-settings")}><Plus className="h-4 w-4" />Pipeline settings</Button>
          </div>
        </div>
      </div>
      <div className="grid min-w-0 gap-0 xl:grid-cols-[21rem_minmax(0,1fr)]">
        <aside className="border-r bg-white px-4 py-4 xl:h-[calc(100vh-9rem)] xl:overflow-y-auto">
          <div className="space-y-4">
            <div>
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-950">Business templates</h2>
                <Badge variant="outline">{allCrmBusinessTemplates.length}</Badge>
              </div>
              <div className="mt-3 flex gap-2">
                {(["All", "Teams", "Industries"] as const).map((group) => (
                  <Button key={group} variant={templateGroup === group ? "default" : "outline"} size="sm" onClick={() => setTemplateGroup(group)}>{group}</Button>
                ))}
              </div>
              <div className="relative mt-3">
                <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <Input className="pl-9" value={templateSearch} onChange={(event) => setTemplateSearch(event.target.value)} placeholder="Search templates" />
              </div>
            </div>
            <div className="space-y-2">
              {filteredTemplates.map((template) => (
                <button
                  key={template.key}
                  type="button"
                  className={`w-full rounded-md border px-3 py-2 text-left transition hover:border-slate-300 hover:bg-slate-50 ${template.key === activeTemplateKey ? "border-slate-900 bg-slate-50 shadow-sm" : "border-transparent bg-white"}`}
                  onClick={() => setActiveTemplateKey(template.key)}
                >
                  <div className="flex items-center gap-3">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-xs font-semibold text-white" style={{ backgroundColor: template.accent }}>{template.name.slice(0, 2).toUpperCase()}</span>
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-slate-950">{template.name}</span>
                      <span className="block truncate text-xs text-slate-500">{template.category}</span>
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </aside>
        <main className="min-w-0 space-y-4 px-4 py-4 sm:px-6 lg:px-8">
          {dealState.error || stageState.error || pipelineState.error ? <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">{dealState.error || stageState.error || pipelineState.error}</div> : null}
          {templateMessage ? <div className="rounded-md border bg-white px-4 py-2 text-sm text-slate-700">{templateMessage}</div> : null}
          {transitionMessage ? <div className="rounded-md border bg-white px-4 py-2 text-sm text-slate-700">{transitionMessage}</div> : null}
          {dealState.loading || stageState.loading || pipelineState.loading ? <div className="rounded-md border bg-white px-4 py-3 text-sm text-slate-500">Loading CRM pipeline...</div> : null}
          <div className="grid gap-3 md:grid-cols-4">
            <PipelineMetric label={isTemplateLibrary ? "Templates" : "Open pipeline"} value={isTemplateLibrary ? allCrmBusinessTemplates.length : formatCurrency(pipelineValue)} detail={isTemplateLibrary ? "Ready to clone" : `${openDeals.length} active deals`} />
            <PipelineMetric label={isTemplateLibrary ? "Industries" : "Weighted forecast"} value={isTemplateLibrary ? allCrmBusinessTemplates.filter((template) => template.group === "Industries").length : formatCurrency(weightedValue)} detail={isTemplateLibrary ? "Vertical pipelines" : "Probability adjusted"} />
            <PipelineMetric label={isTemplateLibrary ? "Teams" : "Due in 7 days"} value={isTemplateLibrary ? allCrmBusinessTemplates.filter((template) => template.group === "Teams").length : dueSoon} detail={isTemplateLibrary ? "Department workflows" : "Close-date watchlist"} />
            <PipelineMetric label="Template stages" value={selectedTemplate.stages.length} detail={selectedTemplate.name} />
          </div>
          <section className="grid min-w-0 gap-4 min-[1800px]:grid-cols-[minmax(0,1fr)_23rem]">
            <div className="space-y-3">
              <div className="flex flex-col gap-3 rounded-md border bg-white p-3 lg:flex-row lg:items-center lg:justify-between">
                {isTemplateLibrary ? (
                  <div>
                    <p className="text-sm font-semibold text-slate-950">Previewing {selectedTemplate.name}</p>
                    <p className="text-xs text-slate-500">{selectedTemplate.category} / {selectedTemplate.group} template</p>
                  </div>
                ) : (
                  <label className="min-w-64 space-y-1 text-sm">
                    <span className="font-medium text-slate-700">Active pipeline</span>
                    <select className="h-10 w-full rounded-md border bg-background px-3" value={activePipelineId || ""} onChange={(event) => setSelectedPipelineId(Number(event.target.value))}>
                      {pipelineState.data.map((pipeline) => <option key={String(pipeline.id)} value={Number(pipeline.id)}>{String(pipeline.name)}</option>)}
                    </select>
                  </label>
                )}
                <div className="w-full lg:max-w-xl">
                  {isTemplateLibrary ? (
                    <Button variant="outline" className="w-full justify-start" onClick={() => setTemplateSearch(selectedTemplate.name)}>
                      <Search className="h-4 w-4" />Search similar templates
                    </Button>
                  ) : (
                    <Toolbar search={filter} onSearch={setFilter} />
                  )}
                </div>
              </div>
              {isTemplateLibrary ? (
                <TemplatePreviewBoard template={selectedTemplate} onApply={applyTemplate} applying={applyingTemplate} />
              ) : (
                <DndContext sensors={sensors} collisionDetection={closestCorners} onDragStart={onDragStart} onDragEnd={onDragEnd}>
                  <div className="grid auto-cols-[18rem] grid-flow-col gap-4 overflow-x-auto pb-4">
                    {pipelineStages.map((stageRecord) => {
                      const stage = String(stageRecord.name);
                      const stageDeals = visibleDeals.filter((deal) => deal.stageId === Number(stageRecord.id) || deal.stage === stage);
                      return <PipelineColumn key={stageRecord.id as string | number} stage={stage} stageRecord={stageRecord} deals={stageDeals} stages={pipelineStages} transitioningDealId={transitioningDealId} onTransition={transitionDealToStage} />;
                    })}
                    {!pipelineStages.length ? <TemplatePreviewBoard template={selectedTemplate} onApply={applyTemplate} applying={applyingTemplate} /> : null}
                  </div>
                  <DragOverlay>{activeDeal ? <DealCard deal={activeDeal} overlay /> : null}</DragOverlay>
                </DndContext>
              )}
            </div>
            <TemplateDetailPanel template={selectedTemplate} applying={applyingTemplate} onApply={applyTemplate} />
          </section>
        </main>
      </div>
    </div>
  );
}

function PipelineMetric({ label, value, detail }: { label: string; value: string | number; detail: string }) {
  return (
    <div className="rounded-md border bg-white p-4">
      <p className="text-xs font-medium uppercase text-slate-500">{label}</p>
      <p className="mt-2 text-xl font-semibold text-slate-950">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{detail}</p>
    </div>
  );
}

function TemplateDetailPanel({ template, applying, onApply }: { template: CRMBusinessTemplate; applying: boolean; onApply: () => void }) {
  return (
    <aside className="rounded-md border bg-white p-4">
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md text-sm font-semibold text-white" style={{ backgroundColor: template.accent }}>{template.name.slice(0, 2).toUpperCase()}</span>
        <div>
          <p className="text-sm font-semibold text-slate-950">{template.name}</p>
          <p className="text-xs text-slate-500">{template.group} / {template.category}</p>
        </div>
      </div>
      <p className="mt-4 text-sm leading-6 text-slate-600">{template.description || defaultTemplateDescription(template)}</p>
      <Button className="mt-4 w-full" onClick={onApply} disabled={applying}>{applying ? "Creating pipeline..." : "Use this template"}</Button>
      <div className="mt-5 space-y-4">
        <TemplateList title="Stages" items={template.stages.map((stage) => `${stage.name} (${stage.probability}%)`)} />
        <TemplateList title="Fields" items={template.fields} />
        {template.customFields?.length ? (
          <TemplateList title="Custom field specs" items={template.customFields.map((field) => `${field.fieldName} / ${labelFor(field.fieldType)} / ${labelFor(field.entityType)}`)} />
        ) : null}
        <TemplateList title="Automations" items={template.automations} />
        <TemplateList title="Dashboards" items={template.reports} />
      </div>
    </aside>
  );
}

function TemplateList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase text-slate-500">{title}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {items.map((item) => <Badge key={item} variant="outline" className="bg-slate-50">{item}</Badge>)}
      </div>
    </div>
  );
}

function TemplatePreviewBoard({ template, applying, onApply }: { template: CRMBusinessTemplate; applying: boolean; onApply: () => void }) {
  const sampleDeals = templateSampleDeals(template);
  const fieldEntity = template.fieldEntity || templateFieldEntity(template);
  return (
    <div className="relative overflow-hidden rounded-md border bg-white">
      <div className="grid auto-cols-[17rem] grid-flow-col gap-3 overflow-x-auto bg-slate-100/70 p-3 pb-40">
        {template.stages.map((stage, index) => {
          const stageDeals = sampleDeals.filter((deal) => (deal.stageIndex || 0) === index);
          return (
            <section key={stage.name} className="flex min-h-[18rem] flex-col rounded-md border bg-white shadow-sm">
              <header className="border-t-4 p-3" style={{ borderTopColor: stage.color }}>
                <div className="flex items-center justify-between gap-2">
                  <h2 className="truncate text-sm font-semibold text-slate-950">{stage.name}</h2>
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{stageDeals.length || (stage.isWon || stage.isLost ? "1" : "0")}</span>
                </div>
                <p className="mt-1 text-xs text-slate-500">{stage.probability}% probability</p>
              </header>
              <div className="space-y-2 p-3">
                {stageDeals.map((deal) => <TemplateSampleCard key={deal.name} template={template} sampleDeal={deal} />)}
                <TemplateSkeletonCard strong={index === 1} />
                <TemplateSkeletonCard />
              </div>
            </section>
          );
        })}
      </div>
      <div className="absolute inset-x-0 bottom-0 border-t bg-white/95 px-4 py-8 text-center backdrop-blur">
        <div className="mx-auto max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{template.group} / {template.category}</p>
          <h2 className="mt-2 text-2xl font-semibold text-slate-950">{template.name}</h2>
          <p className="mt-3 text-sm leading-6 text-slate-600">{template.description || defaultTemplateDescription(template)}</p>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
            <Button onClick={onApply} disabled={applying}>{applying ? "Creating pipeline..." : "Use this template"}</Button>
            <Button variant="outline" type="button"><FileCheck2 className="h-4 w-4" />View {fieldEntity} fields</Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function TemplateSampleCard({ template, sampleDeal }: { template: CRMBusinessTemplate; sampleDeal: CRMTemplateSampleDeal }) {
  const fieldTags = Object.entries(sampleDeal.customFields || {}).slice(0, 2);
  return (
    <div className="rounded-md border bg-white p-3 shadow-sm">
      <p className="text-sm font-semibold text-slate-950">{sampleDeal.name}</p>
      <p className="mt-1 text-xs text-slate-500">{sampleDeal.company} / {template.category}</p>
      <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
        <span className="font-semibold text-slate-900">{formatCurrency(sampleDeal.amount)}</span>
        <span className="h-1 w-1 rounded-full bg-slate-300" />
        <span>{formatDate(sampleDeal.closeDate)}</span>
      </div>
      {fieldTags.length ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {fieldTags.map(([key, value]) => <Badge key={key} variant="outline" className="bg-slate-50 text-[10px]">{labelFor(key)}: {String(value)}</Badge>)}
        </div>
      ) : null}
    </div>
  );
}

function TemplateSkeletonCard({ strong = false }: { strong?: boolean }) {
  return (
    <div className="rounded-md border bg-white p-3">
      <div className={`h-3 rounded bg-slate-200 ${strong ? "w-4/5" : "w-3/4"}`} />
      <div className="mt-3 h-3 w-2/3 rounded bg-slate-100" />
      <div className="mt-3 flex gap-2">
        <div className="h-3 w-16 rounded bg-slate-100" />
        <div className="h-3 w-12 rounded bg-slate-100" />
      </div>
    </div>
  );
}

function defaultTemplateDescription(template: CRMBusinessTemplate) {
  return `${template.name} organizations can use this template to manage their ${template.category.toLowerCase()} workflow from first inquiry to completion.`;
}

function templateFieldEntity(template: CRMBusinessTemplate) {
  if (template.name.includes("Donation")) return "Donation";
  if (template.name.includes("Patient")) return "Patient";
  if (template.name.includes("Car") || template.name.includes("Automobile")) return "Deal";
  if (template.name.includes("Recruitment")) return "Candidate";
  if (template.name.includes("School") || template.name.includes("Education")) return "Admission";
  if (template.name.includes("Tax")) return "Tax case";
  if (template.name.includes("Audit")) return "Audit";
  if (template.name.includes("CA Firm")) return "Client";
  return "Deal";
}

function sampleTemplateRecord(template: CRMBusinessTemplate) {
  if (template.name.includes("Donation")) return "New donation pledge";
  if (template.name.includes("Used Car")) return "New buyer request";
  if (template.name.includes("Startup")) return "Investor intro";
  if (template.name.includes("Testimonials")) return "New testimonial";
  if (template.name.includes("Recruitment")) return "Senior developer candidate";
  if (template.name.includes("CA Firm")) return "GST return retainer";
  if (template.name.includes("Audit")) return "FY audit engagement";
  if (template.name.includes("IT Company")) return "ERP rollout opportunity";
  return `New ${templateFieldEntity(template).toLowerCase()}`;
}

function templateSampleDeals(template: CRMBusinessTemplate): CRMTemplateSampleDeal[] {
  if (template.sampleDeals?.length) return template.sampleDeals;
  const entity = template.fieldEntity || templateFieldEntity(template);
  const baseName = template.sampleRecord || sampleTemplateRecord(template);
  return [
    {
      name: baseName,
      company: `${template.name} customer`,
      amount: 240000,
      stageIndex: 0,
      closeDate: "2026-07-15",
      source: "Template demo",
      nextStep: `Qualify ${entity.toLowerCase()} requirements`,
    },
    {
      name: `${template.name} expansion opportunity`,
      company: `${template.category} account`,
      amount: 640000,
      stageIndex: Math.min(2, template.stages.length - 1),
      closeDate: "2026-08-05",
      source: "Referral",
      nextStep: "Prepare proposal and stakeholder review",
    },
  ];
}

function PipelineColumn({
  stage,
  stageRecord,
  deals,
  stages,
  transitioningDealId,
  onTransition,
}: {
  stage: string;
  stageRecord: CRMRecord;
  deals: CRMDeal[];
  stages: CRMRecord[];
  transitioningDealId: number | null;
  onTransition: (dealId: number, stage: CRMRecord) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: `stage-${stage}` });
  const value = deals.reduce((sum, deal) => sum + deal.amount, 0);
  const weighted = deals.reduce((sum, deal) => sum + (deal.amount * deal.probability) / 100, 0);
  const color = String(stageRecord.color || "#2563eb");
  return (
    <section ref={setNodeRef} className={`flex h-[calc(100vh-21rem)] min-w-[17rem] flex-col rounded-md border bg-white shadow-sm ${isOver ? "ring-2 ring-slate-900/20" : ""}`}>
      <header className="border-t-4 p-3" style={{ borderTopColor: color }}>
        <div className="flex items-center justify-between gap-2">
          <h2 className="truncate text-sm font-semibold text-slate-950">{stage}</h2>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{deals.length}</span>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          <div className="rounded bg-slate-50 p-2">
            <p className="text-slate-500">Value</p>
            <p className="font-semibold text-slate-950">{formatCurrency(value)}</p>
          </div>
          <div className="rounded bg-slate-50 p-2">
            <p className="text-slate-500">Weighted</p>
            <p className="font-semibold text-slate-950">{formatCurrency(weighted)}</p>
          </div>
        </div>
      </header>
      <SortableContext items={deals.map((deal) => deal.id)} strategy={verticalListSortingStrategy}>
        <div className="flex-1 space-y-3 overflow-y-auto p-3">
          {deals.map((deal) => <DealCard key={deal.id} deal={deal} stages={stages} transitioning={transitioningDealId === deal.id} onTransition={onTransition} />)}
          {!deals.length ? <div className="flex h-28 items-center justify-center rounded-md border border-dashed bg-slate-50 text-sm text-slate-500">Drop deal here</div> : null}
        </div>
      </SortableContext>
    </section>
  );
}

function DealCard({
  deal,
  stages = [],
  transitioning = false,
  overlay = false,
  onTransition,
}: {
  deal: CRMDeal;
  stages?: CRMRecord[];
  transitioning?: boolean;
  overlay?: boolean;
  onTransition?: (dealId: number, stage: CRMRecord) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: deal.id });
  const sortedStages = useMemo(() => [...stages].sort((a, b) => Number(a.position || 0) - Number(b.position || 0)), [stages]);
  const currentIndex = sortedStages.findIndex((stage) => Number(stage.id) === Number(deal.stageId) || String(stage.name) === deal.stage);
  const previousStage = currentIndex > 0 ? sortedStages[currentIndex - 1] : null;
  const nextStage = currentIndex >= 0 && currentIndex < sortedStages.length - 1 ? sortedStages[currentIndex + 1] : null;
  const wonStage = sortedStages.find((stage) => stageStatusFor(stage).status === "Won") || null;
  const lostStage = sortedStages.find((stage) => stageStatusFor(stage).status === "Lost") || null;
  const canMoveWon = wonStage && Number(wonStage.id) !== Number(deal.stageId);
  const canMoveLost = lostStage && Number(lostStage.id) !== Number(deal.stageId);
  const move = (stage: CRMRecord | null) => {
    if (!stage || !onTransition || transitioning) return;
    onTransition(deal.id, stage);
  };
  return (
    <article
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`rounded-md border bg-white p-3 shadow-sm transition hover:border-slate-300 hover:shadow-md ${isDragging ? "opacity-50" : ""} ${overlay ? "w-72 shadow-xl" : ""}`}
    >
      <div className="flex items-start gap-2">
        <button type="button" className="rounded p-1 text-slate-400 hover:bg-slate-100" {...attributes} {...listeners} aria-label="Drag deal">
          <GripVertical className="h-4 w-4" />
        </button>
        <div className="min-w-0 flex-1">
          <h3 className="line-clamp-2 text-sm font-semibold text-slate-950">{deal.name}</h3>
          <p className="mt-1 truncate text-xs text-slate-500">{deal.company || "No company"} / {deal.contact || "No contact"}</p>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between text-xs">
        <span className="font-semibold text-slate-950">{formatCurrency(deal.amount)}</span>
        <Badge variant="outline">{deal.probability}%</Badge>
      </div>
      <div className="mt-3 flex items-center justify-between rounded bg-slate-50 px-2 py-1 text-xs text-slate-600">
        <span>Close {formatDate(deal.closeDate)}</span>
        <span>{deal.owner || "Unassigned"}</span>
      </div>
      <p className="mt-2 line-clamp-2 text-xs text-slate-500">Next: {deal.nextStep || "No next step captured"}</p>
      {!overlay && onTransition && sortedStages.length ? (
        <div className="mt-3 grid grid-cols-2 gap-2">
          <Button type="button" size="sm" variant="outline" className="h-8 justify-start text-xs" disabled={!previousStage || transitioning} onClick={() => move(previousStage)}>
            <ChevronLeft className="h-3.5 w-3.5" />Prev
          </Button>
          <Button type="button" size="sm" variant="outline" className="h-8 justify-start text-xs" disabled={!nextStage || transitioning} onClick={() => move(nextStage)}>
            <ChevronRight className="h-3.5 w-3.5" />Next
          </Button>
          <Button type="button" size="sm" variant="outline" className="h-8 justify-start text-xs text-emerald-700" disabled={!canMoveWon || transitioning} onClick={() => move(wonStage)}>
            <CheckCircle2 className="h-3.5 w-3.5" />Won
          </Button>
          <Button type="button" size="sm" variant="outline" className="h-8 justify-start text-xs text-red-700" disabled={!canMoveLost || transitioning} onClick={() => move(lostStage)}>
            <X className="h-3.5 w-3.5" />Lost
          </Button>
        </div>
      ) : null}
      {transitioning ? <p className="mt-2 text-xs text-slate-500">Saving stage...</p> : null}
    </article>
  );
}

function stageStatusFor(stage: CRMRecord) {
  const isWon = Boolean(stage.is_won ?? stage.isWon);
  const isLost = Boolean(stage.is_lost ?? stage.isLost);
  return { status: isWon ? "Won" : isLost ? "Lost" : "Open" };
}

function CustomFieldsSettingsPageLegacy() {
  const [fields, setFields] = useState<CRMRecord[]>([]);
  const [draft, setDraft] = useState<CRMRecord>({ entity: "leads", fieldKey: "", label: "", fieldType: "text", isActive: true });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    crmApi
      .list<CRMRecord>("custom-fields", { per_page: 100, sort_by: "position", sort_order: "asc" })
      .then((response) => setFields(response.data.items || []))
      .catch((err) => setError(err?.response?.data?.detail || "Custom fields could not be loaded."))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const createField = () => {
    if (!draft.fieldKey || !draft.label) return;
    setLoading(true);
    setError(null);
    crmApi
      .create<CRMRecord>("custom-fields", draft)
      .then(() => {
        setDraft({ entity: draft.entity || "leads", fieldKey: "", label: "", fieldType: draft.fieldType || "text", isActive: true });
        load();
      })
      .catch((err) => setError(err?.response?.data?.detail || "Custom field could not be created."))
      .finally(() => setLoading(false));
  };

  return (
    <div className="space-y-5">
      <PageHeader title="CRM Settings" description={descriptionFor("settings")} action="Create field" onAction={createField} />
      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div> : null}
      <Card>
        <CardHeader><CardTitle>Custom Fields</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-4">
            <label className="space-y-1 text-sm"><span className="font-medium">Entity</span><select className="h-10 w-full rounded-md border bg-background px-3" value={String(draft.entity || "leads")} onChange={(event) => setDraft((current) => ({ ...current, entity: event.target.value }))}><option value="leads">Leads</option><option value="contacts">Contacts</option><option value="companies">Accounts</option><option value="deals">Deals</option><option value="quotations">Quotations</option><option value="tasks">Tasks</option></select></label>
            <label className="space-y-1 text-sm"><span className="font-medium">Field key</span><Input value={String(draft.fieldKey || "")} onChange={(event) => setDraft((current) => ({ ...current, fieldKey: event.target.value }))} /></label>
            <label className="space-y-1 text-sm"><span className="font-medium">Label</span><Input value={String(draft.label || "")} onChange={(event) => setDraft((current) => ({ ...current, label: event.target.value }))} /></label>
            <label className="space-y-1 text-sm"><span className="font-medium">Type</span><select className="h-10 w-full rounded-md border bg-background px-3" value={String(draft.fieldType || "text")} onChange={(event) => setDraft((current) => ({ ...current, fieldType: event.target.value }))}><option value="text">Text</option><option value="number">Number</option><option value="date">Date</option><option value="boolean">Boolean</option><option value="select">Select</option></select></label>
          </div>
          <div className="overflow-hidden rounded-md border">
            <table className="crm-desktop-table">
              <thead className="bg-muted/60 text-left"><tr><th className="px-3 py-2">Entity</th><th className="px-3 py-2">Label</th><th className="px-3 py-2">Key</th><th className="px-3 py-2">Type</th><th className="px-3 py-2">Status</th></tr></thead>
              <tbody>
                {fields.map((field) => (
                  <tr key={String(field.id)} className="border-t">
                    <td className="px-3 py-2">{labelFor(String(field.entity || ""))}</td>
                    <td className="px-3 py-2 font-medium">{String(field.label || "")}</td>
                    <td className="px-3 py-2 text-muted-foreground">{String(field.fieldKey || field.field_key || "")}</td>
                    <td className="px-3 py-2">{labelFor(String(field.fieldType || field.field_type || "text"))}</td>
                    <td className="px-3 py-2"><Badge className={statusColor(field.isActive === false ? "inactive" : "active")}>{field.isActive === false ? "Inactive" : "Active"}</Badge></td>
                  </tr>
                ))}
                {!fields.length ? <tr><td colSpan={5} className="px-3 py-6 text-center text-muted-foreground">{loading ? "Loading custom fields..." : "No custom fields configured."}</td></tr> : null}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function PipelineSettingsPage() {
  const pipelineState = useCrmRecords<CRMRecord>("pipelines", emptyRecords, { sort_by: "created_at", sort_order: "asc" });
  const stageState = useCrmRecords<CRMRecord>("pipeline-stages", emptyRecords, { sort_by: "position", sort_order: "asc" });
  const dealState = useCrmRecords<CRMRecord>("deals", emptyRecords);
  const [pipelines, setPipelines] = useState<CRMRecord[]>([]);
  const [stages, setStages] = useState<CRMRecord[]>([]);
  const [selectedPipelineId, setSelectedPipelineId] = useState<number | null>(null);
  const [pipelineName, setPipelineName] = useState("");
  const [stageDraft, setStageDraft] = useState<CRMRecord>({ name: "", probability: 10, color: "#2563eb", is_won: false, is_lost: false });
  const [error, setError] = useState<string | null>(null);
  const activePipelineId = selectedPipelineId || Number(pipelines.find((pipeline) => pipeline.is_default)?.id || pipelines[0]?.id || 0);
  const activeStages = stages.filter((stage) => Number(stage.pipeline_id || stage.pipelineId || 0) === activePipelineId).sort((a, b) => Number(a.position || 0) - Number(b.position || 0));
  const stageDealCounts = useMemo(() => {
    const counts = new Map<number, number>();
    dealState.data.forEach((deal) => counts.set(Number(deal.stageId || deal.stage_id || 0), (counts.get(Number(deal.stageId || deal.stage_id || 0)) || 0) + 1));
    return counts;
  }, [dealState.data]);

  useEffect(() => setPipelines(pipelineState.data), [pipelineState.data]);
  useEffect(() => setStages(stageState.data), [stageState.data]);

  const createPipeline = () => {
    const name = pipelineName.trim();
    if (!name) return;
    crmApi.create<CRMApiRecord>("pipelines", { name, description: "Custom sales pipeline" }).then((response) => {
      setPipelines((items) => [...items, normalizeApiRecord("pipelines", response.data) as CRMRecord]);
      setSelectedPipelineId(Number(response.data.id));
      setPipelineName("");
    }).catch((err) => setError(err?.response?.data?.detail || "Could not create pipeline."));
  };

  const createStage = () => {
    if (!activePipelineId || !String(stageDraft.name || "").trim()) return;
    const position = activeStages.length + 1;
    crmApi.createPipelineStage<CRMApiRecord>(activePipelineId, { ...stageDraft, position }).then((response) => {
      setStages((items) => [...items, normalizeApiRecord("pipeline-stages", response.data) as CRMRecord]);
      setStageDraft({ name: "", probability: 10, color: "#2563eb", is_won: false, is_lost: false });
    }).catch((err) => setError(err?.response?.data?.detail || "Could not create stage."));
  };

  const updateStage = (stage: CRMRecord, patch: CRMApiRecord) => {
    const stageId = Number(stage.id);
    const previous = stages;
    setStages((items) => items.map((item) => Number(item.id) === stageId ? ({ ...item, ...patch } as CRMRecord) : item));
    crmApi.update("pipeline-stages", stageId, patch).catch((err) => {
      setStages(previous);
      setError(err?.response?.data?.detail || "Could not update stage.");
    });
  };

  const deleteStage = (stage: CRMRecord, remapStageId?: number) => {
    crmApi.delete("pipeline-stages", Number(stage.id), remapStageId ? { remapStageId } : undefined).then(() => {
      setStages((items) => items.filter((item) => Number(item.id) !== Number(stage.id)));
    }).catch((err) => setError(err?.response?.data?.detail || "Could not delete stage."));
  };

  const onStageDragEnd = (event: DragEndEvent) => {
    const activeId = Number(event.active.id);
    const overId = Number(event.over?.id);
    if (!activeId || !overId || activeId === overId) return;
    const oldIndex = activeStages.findIndex((stage) => Number(stage.id) === activeId);
    const newIndex = activeStages.findIndex((stage) => Number(stage.id) === overId);
    if (oldIndex < 0 || newIndex < 0) return;
    const reordered = [...activeStages];
    const [moved] = reordered.splice(oldIndex, 1);
    reordered.splice(newIndex, 0, moved);
    const withPositions: CRMRecord[] = reordered.map((stage, index) => ({ ...stage, position: index + 1 }));
    setStages((items) => items.map((stage) => withPositions.find((item) => Number(item.id) === Number(stage.id)) || stage));
    withPositions.forEach((stage) => crmApi.update("pipeline-stages", Number(stage.id), { position: Number(stage.position) }).catch(() => undefined));
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Pipeline Settings" description="Create multiple deal pipelines and maintain each pipeline's custom stages." action="Back to board" onAction={() => window.history.back()} />
      {error || pipelineState.error || stageState.error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error || pipelineState.error || stageState.error}</div> : null}
      <div className="grid gap-4 xl:grid-cols-[20rem_1fr]">
        <Card>
          <CardHeader><CardTitle>Pipelines</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <Input value={pipelineName} onChange={(event) => setPipelineName(event.target.value)} placeholder="New pipeline name" />
              <Button onClick={createPipeline}><Plus className="h-4 w-4" /></Button>
            </div>
            <div className="space-y-2">
              {pipelines.map((pipeline) => (
                <button key={String(pipeline.id)} type="button" className={`w-full rounded-md border px-3 py-2 text-left text-sm ${Number(pipeline.id) === activePipelineId ? "border-primary bg-primary/10" : "bg-card"}`} onClick={() => setSelectedPipelineId(Number(pipeline.id))}>
                  <span className="block font-medium">{String(pipeline.name)}</span>
                  <span className="text-xs text-muted-foreground">{pipeline.is_default ? "Default pipeline" : "Custom pipeline"}</span>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Stages</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-[1fr_7rem_6rem_7rem_7rem_auto] md:items-end">
              <label className="space-y-1 text-sm"><span className="font-medium">Name</span><Input value={String(stageDraft.name || "")} onChange={(event) => setStageDraft((current) => ({ ...current, name: event.target.value }))} /></label>
              <label className="space-y-1 text-sm"><span className="font-medium">Probability</span><Input type="number" value={Number(stageDraft.probability || 0)} onChange={(event) => setStageDraft((current) => ({ ...current, probability: Number(event.target.value) }))} /></label>
              <label className="space-y-1 text-sm"><span className="font-medium">Color</span><Input type="color" value={String(stageDraft.color || "#2563eb")} onChange={(event) => setStageDraft((current) => ({ ...current, color: event.target.value }))} /></label>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(stageDraft.is_won)} onChange={(event) => setStageDraft((current) => ({ ...current, is_won: event.target.checked, is_lost: event.target.checked ? false : current.is_lost }))} />Won</label>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(stageDraft.is_lost)} onChange={(event) => setStageDraft((current) => ({ ...current, is_lost: event.target.checked, is_won: event.target.checked ? false : current.is_won }))} />Lost</label>
              <Button onClick={createStage}>Add</Button>
            </div>
            <DndContext collisionDetection={closestCorners} onDragEnd={onStageDragEnd}>
              <SortableContext items={activeStages.map((stage) => Number(stage.id))} strategy={verticalListSortingStrategy}>
                <div className="space-y-2">
                  {activeStages.map((stage) => (
                    <PipelineStageSettingsRow
                      key={String(stage.id)}
                      stage={stage}
                      stages={activeStages}
                      dealCount={stageDealCounts.get(Number(stage.id)) || 0}
                      onUpdate={updateStage}
                      onDelete={deleteStage}
                    />
                  ))}
                </div>
              </SortableContext>
            </DndContext>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function PipelineStageSettingsRow({ stage, stages, dealCount, onUpdate, onDelete }: { stage: CRMRecord; stages: CRMRecord[]; dealCount: number; onUpdate: (stage: CRMRecord, patch: CRMApiRecord) => void; onDelete: (stage: CRMRecord, remapStageId?: number) => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: Number(stage.id) });
  const [remapStageId, setRemapStageId] = useState("");
  return (
    <div ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition }} className={`grid gap-2 rounded-md border bg-card p-3 md:grid-cols-[2rem_1fr_7rem_6rem_5rem_5rem_8rem_auto] md:items-center ${isDragging ? "opacity-60" : ""}`}>
      <button type="button" className="rounded p-1 text-muted-foreground hover:bg-muted" {...attributes} {...listeners} aria-label="Reorder stage"><GripVertical className="h-4 w-4" /></button>
      <Input value={String(stage.name || "")} onChange={(event) => onUpdate(stage, { name: event.target.value })} />
      <Input type="number" value={Number(stage.probability || 0)} onChange={(event) => onUpdate(stage, { probability: Number(event.target.value) })} />
      <Input type="color" value={String(stage.color || "#2563eb")} onChange={(event) => onUpdate(stage, { color: event.target.value })} />
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(stage.is_won)} onChange={(event) => onUpdate(stage, { is_won: event.target.checked, is_lost: event.target.checked ? false : Boolean(stage.is_lost) })} />Won</label>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(stage.is_lost)} onChange={(event) => onUpdate(stage, { is_lost: event.target.checked, is_won: event.target.checked ? false : Boolean(stage.is_won) })} />Lost</label>
      {dealCount ? (
        <select className="h-10 rounded-md border bg-background px-2 text-sm" value={remapStageId} onChange={(event) => setRemapStageId(event.target.value)}>
          <option value="">Remap {dealCount}</option>
          {stages.filter((item) => Number(item.id) !== Number(stage.id)).map((item) => <option key={String(item.id)} value={Number(item.id)}>{String(item.name)}</option>)}
        </select>
      ) : <span className="text-sm text-muted-foreground">No deals</span>}
      <Button variant="outline" size="sm" onClick={() => onDelete(stage, remapStageId ? Number(remapStageId) : undefined)}>Delete</Button>
    </div>
  );
}

function CustomFieldsSettingsPage() {
  const [entity, setEntity] = useState("leads");
  const [fields, setFields] = useState<CRMApiRecord[]>([]);
  const [draft, setDraft] = useState<CRMApiRecord>({ entityType: "leads", fieldName: "", fieldKey: "", fieldType: "text", options: "", isRequired: false, isUnique: false, isVisible: true, isFilterable: false, displayOrder: 1 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = () => {
    setLoading(true);
    setError(null);
    crmApi.list<CRMApiRecord>("custom-fields", { entityType: entity, sort_by: "position", sort_order: "asc", per_page: 100 })
      .then((response) => setFields(response.data.items || []))
      .catch((err) => setError(err?.response?.data?.detail || "Custom fields could not be loaded."))
      .finally(() => setLoading(false));
  };
  useEffect(load, [entity]);
  useEffect(() => setDraft((current) => ({ ...current, entityType: entity, displayOrder: fields.length + 1 })), [entity, fields.length]);
  const patchDraft = (key: string, value: CRMApiRecord[string]) => setDraft((current) => ({ ...current, [key]: value }));
  const payloadForField = (field: CRMApiRecord) => ({
    entityType: field.entityType || field.entity || entity,
    fieldName: field.fieldName || field.label || field.field_name,
    fieldKey: field.fieldKey || field.field_key,
    fieldType: field.fieldType || field.field_type || "text",
    options: parseOptions(field.options ?? field.options_json),
    isRequired: Boolean(field.isRequired ?? field.is_required),
    isUnique: Boolean(field.isUnique ?? field.is_unique),
    isVisible: Boolean(field.isVisible ?? field.is_visible ?? true),
    isFilterable: Boolean(field.isFilterable ?? field.is_filterable),
    displayOrder: Number(field.displayOrder || field.position || 0),
  });
  const createField = () => {
    setError(null);
    const payload = payloadForField(draft);
    if (!payload.fieldName || !payload.fieldKey) {
      setError("Field name and key are required.");
      return;
    }
    crmApi.create<CRMApiRecord>("custom-fields", payload)
      .then((response) => {
        setFields((items) => [...items, response.data]);
        setDraft({ entityType: entity, fieldName: "", fieldKey: "", fieldType: "text", options: "", isRequired: false, isUnique: false, isVisible: true, isFilterable: false, displayOrder: fields.length + 2 });
      })
      .catch((err) => setError(err?.response?.data?.detail || "Could not create custom field."));
  };
  const updateField = (field: CRMApiRecord, patch: CRMApiRecord) => {
    const id = Number(field.id);
    const previous = fields;
    const next = { ...field, ...patch };
    setFields((items) => items.map((item) => Number(item.id) === id ? next : item));
    crmApi.update("custom-fields", id, payloadForField(next)).catch((err) => {
      setFields(previous);
      setError(err?.response?.data?.detail || "Could not update custom field.");
    });
  };
  const deleteField = (field: CRMApiRecord) => {
    crmApi.delete("custom-fields", Number(field.id)).then(() => {
      setFields((items) => items.filter((item) => Number(item.id) !== Number(field.id)));
    }).catch((err) => setError(err?.response?.data?.detail || "Could not delete custom field."));
  };
  const moveField = (field: CRMApiRecord, direction: -1 | 1) => {
    const sorted = [...fields].sort((a, b) => Number(a.displayOrder || a.position || 0) - Number(b.displayOrder || b.position || 0));
    const index = sorted.findIndex((item) => Number(item.id) === Number(field.id));
    const target = index + direction;
    if (target < 0 || target >= sorted.length) return;
    [sorted[index], sorted[target]] = [sorted[target], sorted[index]];
    const reordered: CRMApiRecord[] = sorted.map((item, itemIndex) => ({ ...(item as CRMApiRecord), displayOrder: itemIndex + 1, position: itemIndex + 1 }));
    setFields(reordered);
    reordered.forEach((item) => crmApi.update("custom-fields", Number(item.id), { displayOrder: Number(item.displayOrder) }).catch(() => undefined));
  };
  return (
    <div className="space-y-6">
      <PageHeader title="Custom Fields" description="Admin configuration for CRM custom fields, validation, visibility, and filterable columns." action="Add field" onAction={createField} />
      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div> : null}
      <Card>
        <CardContent className="grid gap-3 p-4 lg:grid-cols-[12rem_1fr_10rem_1.2fr_7rem_6rem_6rem_6rem_auto] lg:items-end">
          <Field label="Entity"><select className="h-10 rounded-md border bg-background px-3 text-sm" value={entity} onChange={(event) => setEntity(event.target.value)}>{customFieldEntities.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
          <Field label="Field name"><Input value={String(draft.fieldName || "")} onChange={(event) => patchDraft("fieldName", event.target.value)} onBlur={() => !draft.fieldKey && patchDraft("fieldKey", slugifyKey(String(draft.fieldName || "")))} /></Field>
          <Field label="Field key"><Input value={String(draft.fieldKey || "")} onChange={(event) => patchDraft("fieldKey", slugifyKey(event.target.value))} /></Field>
          <Field label="Type"><select className="h-10 rounded-md border bg-background px-3 text-sm" value={String(draft.fieldType || "text")} onChange={(event) => patchDraft("fieldType", event.target.value)}>{customFieldTypes.map((type) => <option key={type} value={type}>{labelFor(type)}</option>)}</select></Field>
          <Field label="Required"><ToggleBox checked={Boolean(draft.isRequired)} onChange={(checked) => patchDraft("isRequired", checked)} /></Field>
          <Field label="Unique"><ToggleBox checked={Boolean(draft.isUnique)} onChange={(checked) => patchDraft("isUnique", checked)} /></Field>
          <Field label="Visible"><ToggleBox checked={Boolean(draft.isVisible ?? true)} onChange={(checked) => patchDraft("isVisible", checked)} /></Field>
          <Field label="Filterable"><ToggleBox checked={Boolean(draft.isFilterable)} onChange={(checked) => patchDraft("isFilterable", checked)} /></Field>
          <Button onClick={createField}>Create</Button>
          {["dropdown", "multi_select"].includes(String(draft.fieldType)) ? <div className="lg:col-span-9"><Field label="Options"><Input value={String(draft.options || "")} onChange={(event) => patchDraft("options", event.target.value)} placeholder="Comma separated options" /></Field></div> : null}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>{customFieldEntities.find((item) => item.value === entity)?.label} Fields</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {loading ? <p className="text-sm text-muted-foreground">Loading custom fields...</p> : null}
          {fields.map((field) => (
            <div key={String(field.id)} className="grid gap-2 rounded-md border p-3 xl:grid-cols-[5rem_1fr_10rem_10rem_1fr_6rem_6rem_6rem_6rem_auto] xl:items-center">
              <div className="flex gap-1"><Button variant="ghost" size="sm" onClick={() => moveField(field, -1)}><ChevronLeft className="h-4 w-4" /></Button><Button variant="ghost" size="sm" onClick={() => moveField(field, 1)}><ChevronRight className="h-4 w-4" /></Button></div>
              <Input value={String(field.fieldName || field.label || "")} onChange={(event) => updateField(field, { fieldName: event.target.value })} />
              <Input value={String(field.fieldKey || field.field_key || "")} onChange={(event) => updateField(field, { fieldKey: slugifyKey(event.target.value) })} />
              <select className="h-10 rounded-md border bg-background px-3 text-sm" value={String(field.fieldType || field.field_type || "text")} onChange={(event) => updateField(field, { fieldType: event.target.value })}>{customFieldTypes.map((type) => <option key={type} value={type}>{labelFor(type)}</option>)}</select>
              <Input value={optionsText(field.options ?? field.options_json)} onChange={(event) => updateField(field, { options: event.target.value })} placeholder="Options" />
              <ToggleBox checked={Boolean(field.isRequired ?? field.is_required)} onChange={(checked) => updateField(field, { isRequired: checked })} />
              <ToggleBox checked={Boolean(field.isUnique ?? field.is_unique)} onChange={(checked) => updateField(field, { isUnique: checked })} />
              <ToggleBox checked={Boolean(field.isVisible ?? field.is_visible ?? true)} onChange={(checked) => updateField(field, { isVisible: checked })} />
              <ToggleBox checked={Boolean(field.isFilterable ?? field.is_filterable)} onChange={(checked) => updateField(field, { isFilterable: checked })} />
              <Button variant="outline" size="sm" onClick={() => deleteField(field)}>Delete</Button>
            </div>
          ))}
          {!loading && !fields.length ? <p className="text-sm text-muted-foreground">No custom fields configured for this entity yet.</p> : null}
        </CardContent>
      </Card>
    </div>
  );
}

function ToggleBox({ checked, onChange }: { checked: boolean; onChange: (checked: boolean) => void }) {
  return <input className="h-5 w-5" type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />;
}

function parseOptions(value: unknown) {
  if (Array.isArray(value)) return value.map(String);
  return String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
}

function optionsText(value: unknown) {
  return Array.isArray(value) ? value.join(", ") : String(value || "");
}

function slugifyKey(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

function LeadScoringSettingsPage() {
  const ruleState = useCrmRecords<CRMRecord>("lead-scoring-rules", emptyRecords);
  const [rules, setRules] = useState<CRMRecord[]>([]);
  const [draft, setDraft] = useState<CRMRecord>({ name: "", field: "email", operator: "exists", value: "", points: 10, is_active: true });
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setRules(ruleState.data), [ruleState.data]);

  const createRule = () => {
    if (!String(draft.name || "").trim()) return;
    crmApi.create<CRMApiRecord>("lead-scoring-rules", draft).then((response) => {
      setRules((items) => [...items, normalizeApiRecord("lead-scoring-rules", response.data) as CRMRecord]);
      setDraft({ name: "", field: "email", operator: "exists", value: "", points: 10, is_active: true });
    }).catch((err) => setError(err?.response?.data?.detail || "Could not create scoring rule."));
  };

  const updateRule = (rule: CRMRecord, patch: CRMApiRecord) => {
    const previous = rules;
    setRules((items) => items.map((item) => Number(item.id) === Number(rule.id) ? ({ ...item, ...patch } as CRMRecord) : item));
    crmApi.update("lead-scoring-rules", Number(rule.id), patch).catch((err) => {
      setRules(previous);
      setError(err?.response?.data?.detail || "Could not update scoring rule.");
    });
  };

  const deleteRule = (rule: CRMRecord) => {
    crmApi.delete("lead-scoring-rules", Number(rule.id)).then(() => setRules((items) => items.filter((item) => Number(item.id) !== Number(rule.id)))).catch((err) => setError(err?.response?.data?.detail || "Could not delete scoring rule."));
  };

  const recalculateAll = () => {
    setMessage("");
    setError(null);
    crmApi.recalculateLeadScores().then((response) => setMessage(`Recalculated ${response.data.updated} automatic leads.`)).catch((err) => setError(err?.response?.data?.detail || "Could not recalculate lead scores."));
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Lead Scoring" description="Configure automatic 0-100 CRM lead scoring rules and keep manual overrides when needed." action="Recalculate all" onAction={recalculateAll} />
      {error || ruleState.error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error || ruleState.error}</div> : null}
      {message ? <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800">{message}</div> : null}
      <div className="grid gap-4 xl:grid-cols-[1fr_22rem]">
        <Card>
          <CardHeader><CardTitle>Scoring Rules</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {ruleState.loading ? <p className="text-sm text-muted-foreground">Loading scoring rules...</p> : null}
            {rules.map((rule) => (
              <div key={String(rule.id)} className="grid gap-2 rounded-md border p-3 md:grid-cols-[1fr_9rem_8rem_8rem_6rem_6rem_auto] md:items-center">
                <Input value={String(rule.name || "")} onChange={(event) => updateRule(rule, { name: event.target.value })} />
                <Input value={String(rule.field || "")} onChange={(event) => updateRule(rule, { field: event.target.value })} />
                <RuleOperatorSelect value={String(rule.operator || "exists")} onChange={(operator) => updateRule(rule, { operator })} />
                <Input value={String(rule.value || "")} onChange={(event) => updateRule(rule, { value: event.target.value })} />
                <Input type="number" value={Number(rule.points || 0)} onChange={(event) => updateRule(rule, { points: Number(event.target.value) })} />
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(rule.is_active ?? rule.isActive ?? true)} onChange={(event) => updateRule(rule, { is_active: event.target.checked })} />Active</label>
                <Button variant="outline" size="sm" onClick={() => deleteRule(rule)}>Delete</Button>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Add Rule</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <Field label="Name"><Input value={String(draft.name || "")} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} /></Field>
            <Field label="Field"><Input value={String(draft.field || "")} onChange={(event) => setDraft((current) => ({ ...current, field: event.target.value }))} /></Field>
            <Field label="Operator"><RuleOperatorSelect value={String(draft.operator || "exists")} onChange={(operator) => setDraft((current) => ({ ...current, operator }))} /></Field>
            <Field label="Value"><Input value={String(draft.value || "")} onChange={(event) => setDraft((current) => ({ ...current, value: event.target.value }))} /></Field>
            <Field label="Points"><Input type="number" value={Number(draft.points || 0)} onChange={(event) => setDraft((current) => ({ ...current, points: Number(event.target.value) }))} /></Field>
            <Button className="w-full" onClick={createRule}>Add scoring rule</Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function RuleOperatorSelect({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <select className="h-10 rounded-md border bg-background px-2 text-sm" value={value} onChange={(event) => onChange(event.target.value)}>
      {["exists", "not_exists", "equals", "not_equals", "contains", "gt", "gte", "lt", "lte", "older_than_days"].map((operator) => <option key={operator} value={operator}>{operator}</option>)}
    </select>
  );
}

type CalendarView = "month" | "week" | "day" | "agenda";
type CalendarFilters = { ownerId: string; type: string; status: string };

function CRMCalendarPage() {
  const navigate = useNavigate();
  const [view, setView] = useState<CalendarView>("month");
  const [cursor, setCursor] = useState(() => new Date());
  const [events, setEvents] = useState<CRMCalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<CalendarFilters>({ ownerId: "all", type: "all", status: "all" });
  const [selected, setSelected] = useState<CRMCalendarEvent | null>(null);
  const [createDate, setCreateDate] = useState<Date | null>(null);
  const range = useMemo(() => calendarRange(cursor, view), [cursor, view]);

  const loadCalendar = () => {
    setLoading(true);
    setError(null);
    crmApi
      .calendar({
        startDate: range.start.toISOString(),
        endDate: range.end.toISOString(),
        ownerId: filters.ownerId === "all" ? undefined : Number(filters.ownerId),
        type: filters.type === "all" ? undefined : filters.type,
      })
      .then((response) => setEvents(response.data.items))
      .catch((err) => setError(err?.response?.data?.detail || "CRM calendar is not reachable."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadCalendar();
  }, [range.start.toISOString(), range.end.toISOString(), filters.ownerId, filters.type]);

  const visibleEvents = useMemo(() => {
    return events.filter((event) => filters.status === "all" || String(event.status || "").toLowerCase() === filters.status.toLowerCase());
  }, [events, filters.status]);
  const ownerIds = useMemo(() => uniqueCalendarValues(events.map((event) => event.ownerId).filter(Boolean).map(String)), [events]);
  const statuses = useMemo(() => uniqueCalendarValues(events.map((event) => String(event.status || "")).filter(Boolean)), [events]);
  const calendarStats = useMemo(() => {
    const dueToday = visibleEvents.filter((event) => dateKey(new Date(event.start)) === dateKey(new Date())).length;
    const synced = visibleEvents.filter((event) => event.source === "meetings" && event.syncStatus && event.syncStatus !== "not_synced").length;
    return {
      tasks: visibleEvents.filter((event) => event.source === "tasks" || event.type === "task").length,
      meetings: visibleEvents.filter((event) => event.source === "meetings" || event.type === "meeting").length,
      calls: visibleEvents.filter((event) => event.source === "calls" || event.type === "call").length,
      dueToday,
      synced,
    };
  }, [visibleEvents]);

  const moveCursor = (direction: number) => {
    setCursor((date) => {
      const next = new Date(date);
      if (view === "month") next.setMonth(next.getMonth() + direction);
      if (view === "week") next.setDate(next.getDate() + direction * 7);
      if (view === "day" || view === "agenda") next.setDate(next.getDate() + direction);
      return next;
    });
  };

  const rescheduleEvent = (event: CRMCalendarEvent, targetDate: Date) => {
    const originalStart = new Date(event.start);
    const originalEnd = new Date(event.end || event.start);
    const nextStart = new Date(targetDate);
    nextStart.setHours(originalStart.getHours(), originalStart.getMinutes(), 0, 0);
    const duration = Math.max(originalEnd.getTime() - originalStart.getTime(), 30 * 60 * 1000);
    const nextEnd = new Date(nextStart.getTime() + duration);
    const patch = calendarPatchFor(event, nextStart, nextEnd);
    setEvents((items) => items.map((item) => (item.id === event.id ? { ...item, start: nextStart.toISOString(), end: nextEnd.toISOString() } : item)));
    crmApi.update(event.source, event.recordId, patch).catch(() => {
      setError("Could not reschedule the calendar event.");
      loadCalendar();
    });
  };

  const onDragEnd = (event: DragEndEvent) => {
    if (!event.over) return;
    const calendarEvent = visibleEvents.find((item) => item.id === event.active.id);
    const targetDate = parseLocalDateKey(String(event.over.id).replace("day-", ""));
    if (calendarEvent && !Number.isNaN(targetDate.getTime())) rescheduleEvent(calendarEvent, targetDate);
  };

  return (
    <div className="min-h-[calc(100vh-5rem)] bg-slate-50/70">
      <div className="border-b bg-white px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">CRM Activities</Badge>
              <Badge className="bg-emerald-50 text-emerald-700 hover:bg-emerald-50">Calendar command center</Badge>
            </div>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">CRM calendar</h1>
            <p className="max-w-3xl text-sm text-slate-600">Plan follow-ups, tasks, events, calls, quote expiries, and deal closes in a sales-ready schedule with sync visibility.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => navigate("/crm/tasks")}><CheckCircle2 className="h-4 w-4" />Tasks</Button>
            <Button variant="outline" onClick={() => navigate("/crm/calendar-integrations")}><CalendarDays className="h-4 w-4" />Sync setup</Button>
            <Button onClick={() => setCreateDate(new Date())}><Plus className="h-4 w-4" />Create activity</Button>
          </div>
        </div>
      </div>
      <div className="border-b bg-white px-4 sm:px-6 lg:px-8">
        <div className="flex flex-wrap gap-1">
          {[
            { label: "Calendar", value: "all", icon: CalendarDays },
            { label: "Tasks", value: "task", icon: CheckCircle2 },
            { label: "Events", value: "meeting", icon: Bell },
            { label: "Calls", value: "call", icon: Phone },
          ].map((item) => {
            const Icon = item.icon;
            const active = filters.type === item.value || (item.value === "all" && filters.type === "all");
            return (
              <button key={item.value} type="button" onClick={() => setFilters((current) => ({ ...current, type: item.value }))} className={`flex h-12 items-center gap-2 border-b-2 px-4 text-sm font-medium transition ${active ? "border-emerald-600 text-emerald-700" : "border-transparent text-slate-600 hover:text-slate-950"}`}>
                <Icon className="h-4 w-4" />{item.label}
              </button>
            );
          })}
        </div>
      </div>
      <div className="grid gap-0 xl:grid-cols-[1fr_22rem]">
        <main className="min-w-0 space-y-4 px-4 py-4 sm:px-6 lg:px-8">
          <div className="rounded-md border bg-white p-3">
            <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="outline" onClick={() => setCursor(new Date())}>Today</Button>
                <Button variant="ghost" size="icon" onClick={() => moveCursor(-1)} aria-label="Previous period"><ChevronLeft className="h-4 w-4" /></Button>
                <Button variant="ghost" size="icon" onClick={() => moveCursor(1)} aria-label="Next period"><ChevronRight className="h-4 w-4" /></Button>
                <h2 className="px-2 text-lg font-semibold text-slate-950">{calendarTitle(cursor, view)}</h2>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="outline" size="sm" onClick={() => navigate("/crm/calendar-integrations")}><CalendarDays className="h-4 w-4" />Booking pages</Button>
                <div className="flex rounded-full border bg-slate-50 p-1">
                  {(["month", "week", "day", "agenda"] as CalendarView[]).map((item) => (
                    <button key={item} type="button" className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${view === item ? "bg-white text-emerald-700 shadow-sm" : "text-slate-600 hover:text-slate-950"}`} onClick={() => setView(item)}>{item[0].toUpperCase() + item.slice(1)}</button>
                  ))}
                </div>
              </div>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-4">
              <CalendarStat label="Due today" value={calendarStats.dueToday} />
              <CalendarStat label="Tasks" value={calendarStats.tasks} tone="amber" />
              <CalendarStat label="Events" value={calendarStats.meetings} tone="blue" />
              <CalendarStat label="Calls" value={calendarStats.calls} tone="violet" />
            </div>
          </div>
          {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div> : null}
          {loading ? <div className="rounded-md border bg-white px-4 py-3 text-sm text-slate-500">Loading CRM calendar...</div> : null}
          <DndContext onDragEnd={onDragEnd}>
            {view === "agenda" ? (
              <CalendarAgenda events={visibleEvents} onOpen={setSelected} />
            ) : view === "month" ? (
              <CalendarMonth cursor={cursor} events={visibleEvents} onCreate={setCreateDate} onOpen={setSelected} />
            ) : (
              <CalendarTimeGrid cursor={cursor} view={view} events={visibleEvents} onCreate={setCreateDate} onOpen={setSelected} />
            )}
          </DndContext>
        </main>
        <CalendarSidebar
          cursor={cursor}
          events={visibleEvents}
          filters={filters}
          ownerIds={ownerIds}
          statuses={statuses}
          stats={calendarStats}
          onCursorChange={setCursor}
          onFiltersChange={setFilters}
          onIntegrations={() => navigate("/crm/calendar-integrations")}
        />
      </div>
      {selected ? <CalendarEventDialog event={selected} onClose={() => setSelected(null)} onOpenRecord={(path) => navigate(path)} onComplete={() => markCalendarTaskComplete(selected, setEvents, setError)} onSynced={loadCalendar} /> : null}
      {createDate ? <CalendarCreateDialog date={createDate} onClose={() => setCreateDate(null)} onCreated={() => { setCreateDate(null); loadCalendar(); }} /> : null}
    </div>
  );
}

function CalendarStat({ label, value, tone = "emerald" }: { label: string; value: number; tone?: "emerald" | "amber" | "blue" | "violet" }) {
  const tones = {
    emerald: "bg-emerald-50 text-emerald-700",
    amber: "bg-amber-50 text-amber-700",
    blue: "bg-sky-50 text-sky-700",
    violet: "bg-violet-50 text-violet-700",
  };
  return (
    <div className="rounded-md border bg-slate-50/70 p-3">
      <p className="text-xs font-medium uppercase text-slate-500">{label}</p>
      <p className={`mt-2 inline-flex rounded-full px-2.5 py-1 text-lg font-semibold ${tones[tone]}`}>{value}</p>
    </div>
  );
}

function CalendarMonth({ cursor, events, onCreate, onOpen }: { cursor: Date; events: CRMCalendarEvent[]; onCreate: (date: Date) => void; onOpen: (event: CRMCalendarEvent) => void }) {
  const days = monthDays(cursor);
  return (
    <div className="overflow-hidden rounded-md border bg-white shadow-sm">
      <div className="grid grid-cols-7 border-b bg-slate-50 text-center text-xs font-semibold uppercase text-slate-500">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => <div key={day} className="px-3 py-3">{day}</div>)}
      </div>
      <div className="grid grid-cols-7">
        {days.map((day) => (
          <CalendarDayCell key={day.toISOString()} date={day} muted={day.getMonth() !== cursor.getMonth()} events={eventsForDay(events, day)} onCreate={onCreate} onOpen={onOpen} />
        ))}
      </div>
    </div>
  );
}

function CalendarTimeGrid({ cursor, view, events, onCreate, onOpen }: { cursor: Date; view: "week" | "day"; events: CRMCalendarEvent[]; onCreate: (date: Date) => void; onOpen: (event: CRMCalendarEvent) => void }) {
  const days = view === "day" ? [startOfDay(cursor)] : weekDays(cursor);
  return (
    <div className={`grid gap-3 ${view === "day" ? "md:grid-cols-1" : "md:grid-cols-7"}`}>
      {days.map((day) => (
        <CalendarDayCell key={day.toISOString()} date={day} events={eventsForDay(events, day)} onCreate={onCreate} onOpen={onOpen} tall />
      ))}
    </div>
  );
}

function CalendarDayCell({ date, events, muted = false, tall = false, onCreate, onOpen }: { date: Date; events: CRMCalendarEvent[]; muted?: boolean; tall?: boolean; onCreate: (date: Date) => void; onOpen: (event: CRMCalendarEvent) => void }) {
  const { setNodeRef, isOver } = useDroppable({ id: `day-${dateKey(date)}` });
  const today = dateKey(date) === dateKey(new Date());
  const weekend = [0, 6].includes(date.getDay());
  return (
    <section ref={setNodeRef} className={`min-h-36 border-r border-b p-2 last:border-r-0 ${tall ? "min-h-[28rem] rounded-md border bg-white" : ""} ${muted ? "bg-slate-50/70 text-slate-400" : weekend ? "bg-slate-50/60" : "bg-white"} ${isOver ? "ring-2 ring-emerald-500/50" : ""}`}>
      <button type="button" className="mb-2 flex w-full items-center justify-between rounded px-1 py-0.5 text-left text-xs hover:bg-slate-100" onClick={() => onCreate(date)}>
        <span className={`flex h-7 min-w-7 items-center justify-center rounded-full px-2 font-semibold ${today ? "bg-emerald-600 text-white" : "text-slate-700"}`}>{date.toLocaleDateString(undefined, { weekday: tall ? "short" : undefined, month: tall ? "short" : undefined, day: "numeric" })}</span>
        <Plus className="h-3.5 w-3.5 text-slate-400" />
      </button>
      <div className="space-y-1">
        {events.map((event) => <CalendarEventPill key={event.id} event={event} onOpen={onOpen} />)}
      </div>
    </section>
  );
}

function CalendarEventPill({ event, onOpen }: { event: CRMCalendarEvent; onOpen: (event: CRMCalendarEvent) => void }) {
  const { attributes, listeners, setNodeRef, transform } = useDraggable({ id: event.id });
  const tone = calendarEventTone(event);
  return (
    <button
      ref={setNodeRef}
      type="button"
      style={{ borderLeftColor: event.color || tone.border, transform: CSS.Transform.toString(transform) }}
      className={`w-full rounded border border-l-4 px-2 py-1.5 text-left text-xs shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${tone.className}`}
      onClick={() => onOpen(event)}
      {...attributes}
      {...listeners}
    >
      <span className="block truncate font-medium">{event.title}</span>
      <span className="block truncate opacity-80">{timeLabel(event.start)} / {event.category || event.type}</span>
      {event.source === "meetings" && event.syncStatus ? <span className="mt-1 inline-flex rounded border px-1.5 py-0.5 text-[10px] text-muted-foreground">{labelFor(event.syncStatus)}</span> : null}
    </button>
  );
}

function CalendarSidebar({ cursor, events, filters, ownerIds, statuses, stats, onCursorChange, onFiltersChange, onIntegrations }: { cursor: Date; events: CRMCalendarEvent[]; filters: CalendarFilters; ownerIds: string[]; statuses: string[]; stats: { tasks: number; meetings: number; calls: number; dueToday: number; synced: number }; onCursorChange: (date: Date) => void; onFiltersChange: React.Dispatch<React.SetStateAction<CalendarFilters>>; onIntegrations: () => void }) {
  return (
    <aside className="border-l bg-white px-4 py-4 xl:h-[calc(100vh-13rem)] xl:overflow-y-auto">
      <MiniCalendar cursor={cursor} events={events} onSelect={onCursorChange} />
      <div className="mt-5 space-y-4">
        <div>
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-950">My preferences</h3>
            <Button variant="ghost" size="sm" onClick={() => onFiltersChange({ ownerId: "all", type: "all", status: "all" })}>Reset</Button>
          </div>
          <div className="mt-3 grid gap-3">
            <FilterSelect label="Owner" value={filters.ownerId} values={ownerIds} onChange={(ownerId) => onFiltersChange((current) => ({ ...current, ownerId }))} allLabel="All owners" />
            <FilterSelect label="Status" value={filters.status} values={statuses} onChange={(status) => onFiltersChange((current) => ({ ...current, status }))} allLabel="All statuses" />
          </div>
        </div>
        <div className="rounded-md border p-3">
          <h3 className="text-sm font-semibold text-slate-950">Activity types</h3>
          <div className="mt-3 space-y-2">
            <CalendarTypeToggle label="Tasks" color="bg-amber-500" active={filters.type === "all" || filters.type === "task"} onClick={() => onFiltersChange((current) => ({ ...current, type: current.type === "task" ? "all" : "task" }))} />
            <CalendarTypeToggle label="Events" color="bg-sky-500" active={filters.type === "all" || filters.type === "meeting"} onClick={() => onFiltersChange((current) => ({ ...current, type: current.type === "meeting" ? "all" : "meeting" }))} />
            <CalendarTypeToggle label="Calls" color="bg-violet-500" active={filters.type === "all" || filters.type === "call"} onClick={() => onFiltersChange((current) => ({ ...current, type: current.type === "call" ? "all" : "call" }))} />
          </div>
        </div>
        <div className="rounded-md border p-3">
          <h3 className="text-sm font-semibold text-slate-950">Sync options</h3>
          <div className="mt-3 grid gap-2 text-sm">
            <div className="flex items-center justify-between rounded bg-slate-50 px-3 py-2"><span>Synced meetings</span><Badge variant="outline">{stats.synced}</Badge></div>
            <div className="flex items-center justify-between rounded bg-slate-50 px-3 py-2"><span>Visible activities</span><Badge variant="outline">{events.length}</Badge></div>
          </div>
          <Button variant="outline" className="mt-3 w-full" onClick={onIntegrations}><CalendarDays className="h-4 w-4" />Google / Microsoft setup</Button>
        </div>
        <div className="rounded-md border bg-emerald-50/60 p-3">
          <h3 className="text-sm font-semibold text-emerald-950">Sales day focus</h3>
          <p className="mt-2 text-sm text-emerald-800">{stats.dueToday} items are due today. Keep calls, meetings, and deal follow-ups visible before closing the day.</p>
        </div>
      </div>
    </aside>
  );
}

function MiniCalendar({ cursor, events, onSelect }: { cursor: Date; events: CRMCalendarEvent[]; onSelect: (date: Date) => void }) {
  const days = monthDays(cursor).filter((day) => day.getMonth() === cursor.getMonth());
  return (
    <div>
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-slate-950">{cursor.toLocaleDateString(undefined, { month: "long", year: "numeric" })}</h3>
        <div className="flex gap-1">
          <Button variant="ghost" size="icon" onClick={() => { const next = new Date(cursor); next.setMonth(next.getMonth() - 1); onSelect(next); }}><ChevronLeft className="h-4 w-4" /></Button>
          <Button variant="ghost" size="icon" onClick={() => { const next = new Date(cursor); next.setMonth(next.getMonth() + 1); onSelect(next); }}><ChevronRight className="h-4 w-4" /></Button>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-7 gap-1 text-center text-xs font-medium text-slate-500">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => <span key={day}>{day}</span>)}
      </div>
      <div className="mt-2 grid grid-cols-7 gap-1 text-center text-sm">
        {Array.from({ length: mondayIndex(new Date(cursor.getFullYear(), cursor.getMonth(), 1)) }).map((_, index) => <span key={`blank-${index}`} />)}
        {days.map((day) => {
          const hasEvent = eventsForDay(events, day).length > 0;
          const active = dateKey(day) === dateKey(cursor);
          const today = dateKey(day) === dateKey(new Date());
          return (
            <button key={day.toISOString()} type="button" onClick={() => onSelect(day)} className={`relative h-9 rounded-full font-medium transition ${active ? "bg-emerald-600 text-white" : today ? "bg-emerald-50 text-emerald-700" : "hover:bg-slate-100"}`}>
              {day.getDate()}
              {hasEvent ? <span className={`absolute bottom-1 left-1/2 h-1 w-1 -translate-x-1/2 rounded-full ${active ? "bg-white" : "bg-amber-500"}`} /> : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function CalendarTypeToggle({ label, color, active, onClick }: { label: string; color: string; active: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className={`flex w-full items-center gap-3 rounded-md px-2 py-2 text-left text-sm transition ${active ? "bg-slate-50 text-slate-950" : "text-slate-400"}`}>
      <span className={`h-4 w-4 rounded ${color} ${active ? "opacity-100" : "opacity-30"}`} />
      <span>{label}</span>
    </button>
  );
}

function CalendarAgenda({ events, onOpen }: { events: CRMCalendarEvent[]; onOpen: (event: CRMCalendarEvent) => void }) {
  if (!events.length) return <div className="rounded-lg border border-dashed py-12 text-center text-sm text-muted-foreground">No CRM calendar items in this range.</div>;
  return (
    <div className="divide-y rounded-lg border">
      {events.map((event) => (
        <button key={event.id} type="button" className="grid w-full gap-3 p-4 text-left hover:bg-muted/50 md:grid-cols-[9rem_1fr_8rem_8rem_8rem]" onClick={() => onOpen(event)}>
          <span className="text-sm font-medium">{formatDate(event.start)}</span>
          <span><span className="block font-medium">{event.title}</span><span className="text-sm text-muted-foreground">{timeLabel(event.start)} / {event.category}</span></span>
          <Badge className={statusColor(String(event.status || event.type))}>{event.status || event.type}</Badge>
          <Badge variant="outline">{event.source === "meetings" ? labelFor(event.syncStatus || "not_synced") : "-"}</Badge>
          <span className="text-sm text-muted-foreground">Owner {event.ownerId || "-"}</span>
        </button>
      ))}
    </div>
  );
}

function CalendarEventDialog({ event, onClose, onOpenRecord, onComplete, onSynced }: { event: CRMCalendarEvent; onClose: () => void; onOpenRecord: (path: string) => void; onComplete: () => void; onSynced: () => void }) {
  const path = relatedCalendarPath(event);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const syncMeeting = () => {
    setSyncing(true);
    setError(null);
    crmApi.syncMeeting(event.recordId).then(() => onSynced()).catch((err) => setError(err?.response?.data?.detail || "Meeting could not be synced.")).finally(() => setSyncing(false));
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm">
      <Card className="w-full max-w-lg">
        <CardHeader className="flex-row items-start justify-between gap-3">
          <div><CardTitle>{event.title}</CardTitle><p className="text-sm text-muted-foreground">{formatDate(event.start)} at {timeLabel(event.start)}</p></div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div> : null}
          <div className="grid gap-3 md:grid-cols-3">
            <InfoTile label="Type" value={event.category || event.type} />
            <InfoTile label="Status" value={event.status || "-"} />
            <InfoTile label="Owner" value={String(event.ownerId || "-")} />
          </div>
          {event.source === "meetings" ? (
            <div className="grid gap-3 md:grid-cols-3">
              <InfoTile label="Calendar sync" value={event.syncStatus || "not_synced"} />
              <InfoTile label="Provider" value={event.externalProvider || "-"} />
              <InfoTile label="External event" value={event.externalEventId || "-"} />
            </div>
          ) : null}
          <div className="flex flex-wrap gap-2">
            {event.source === "tasks" ? <Button onClick={onComplete}><CheckCircle2 className="h-4 w-4" />Mark complete</Button> : null}
            {event.source === "meetings" ? <Button onClick={syncMeeting} disabled={syncing}><CalendarDays className="h-4 w-4" />{syncing ? "Syncing..." : "Sync to calendar"}</Button> : null}
            {path ? <Button variant="outline" onClick={() => onOpenRecord(path)}>Open related record</Button> : null}
            <Button variant="outline" onClick={onClose}>Close</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function CalendarCreateDialog({ date, onClose, onCreated }: { date: Date; onClose: () => void; onCreated: () => void }) {
  const [kind, setKind] = useState<"tasks" | "meetings">("tasks");
  const [title, setTitle] = useState("");
  const [status, setStatus] = useState("To Do");
  const [time, setTime] = useState("10:00");
  const [syncToCalendar, setSyncToCalendar] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = () => {
    const start = dateWithTime(date, time);
    const end = new Date(start.getTime() + 60 * 60 * 1000);
    const payload = kind === "tasks"
      ? { title: title || "New task", due_date: start.toISOString(), status }
      : { title: title || "New meeting", start_time: start.toISOString(), end_time: end.toISOString(), status: "Scheduled", syncToCalendar };
    setSaving(true);
    setError(null);
    crmApi.create(kind, payload).then(onCreated).catch((err) => setError(err?.response?.data?.detail || "Could not create calendar item.")).finally(() => setSaving(false));
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm">
      <Card className="w-full max-w-lg">
        <CardHeader><CardTitle>Create calendar item</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div> : null}
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1 text-sm"><span className="font-medium">Type</span><select className="h-10 w-full rounded-md border bg-background px-3" value={kind} onChange={(event) => setKind(event.target.value as "tasks" | "meetings")}><option value="tasks">Task</option><option value="meetings">Meeting</option></select></label>
            <label className="space-y-1 text-sm"><span className="font-medium">Time</span><Input type="time" value={time} onChange={(event) => setTime(event.target.value)} /></label>
          </div>
          <label className="space-y-1 text-sm"><span className="font-medium">Title</span><Input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Follow up with customer" /></label>
          {kind === "tasks" ? <label className="space-y-1 text-sm"><span className="font-medium">Status</span><Input value={status} onChange={(event) => setStatus(event.target.value)} /></label> : null}
          {kind === "meetings" ? <label className="flex items-center gap-2 rounded-md border bg-muted/25 p-3 text-sm"><input type="checkbox" checked={syncToCalendar} onChange={(event) => setSyncToCalendar(event.target.checked)} />Sync to connected calendar</label> : null}
          <div className="flex justify-end gap-2"><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={submit} disabled={saving}>{saving ? "Saving..." : "Create"}</Button></div>
        </CardContent>
      </Card>
    </div>
  );
}

function CRMListPage({ kind }: { kind: CRMPageKind }) {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [selectedView, setSelectedView] = useState(savedViews[0]);
  const [filters, setFilters] = useState<CRMFilters>({ owner: "all", status: "all", type: "all", territory: "all" });
  const [showFilters, setShowFilters] = useState(kind === "calendar");
  const [selectedRecord, setSelectedRecord] = useState<CRMRecord | null>(null);
  const apiEntity = apiEntityForKind[kind];
  const apiParams = filters.territory !== "all" ? { territoryId: Number(filters.territory) } : undefined;
  const { data: apiRows, loading, error } = useCrmRecords(apiEntity, emptyRecords, apiParams);
  const [localRows, setLocalRows] = useState<CRMRecord[]>([]);
  const [contacts, setContacts] = useState<CRMRecord[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [createSaving, setCreateSaving] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [importExportError, setImportExportError] = useState<string | null>(null);
  const records = localRows.length ? localRows : apiRows;
  const rows = useMemo(() => filterRecords(records, search, selectedView, filters), [records, search, selectedView, filters]);
  const owners = useMemo(() => uniqueValues(records, "owner"), [records]);
  const statuses = useMemo(() => uniqueValues(records, "status"), [records]);
  const types = useMemo(() => uniqueValues(records, "type"), [records]);
  const territories = useMemo(() => uniqueValues(records, "territoryId"), [records]);

  useEffect(() => {
    setLocalRows([]);
    setSelectedRecord(null);
  }, [kind]);

  const createRecord = (draft: CRMRecord, customFields?: CRMApiRecord) => {
    const nextId = records.length + 1;
    const title = pageTitles[kind].replace("CRM ", "").replace(/s$/, "");
    const record = { id: nextId, ...defaultRecordFor(kind, nextId, title), ...draft };
    if (apiEntity) {
      setCreateSaving(true);
      setCreateError(null);
      crmApi
        .create<CRMApiRecord>(apiEntity, { ...createPayloadForKind(kind, record), customFields: customFields || {} })
        .then((response) => {
          const created = normalizeApiRecord(kindlessEntity(apiEntity), response.data);
          setLocalRows((items) => [created, ...items.filter((item) => Number(item.id) !== Number(created.id)), ...apiRows.filter((item) => Number(item.id) !== Number(created.id))]);
          setSelectedRecord(created);
          setShowCreate(false);
        })
        .catch((err) => setCreateError(err?.response?.data?.detail || "CRM record could not be created."))
        .finally(() => setCreateSaving(false));
      return;
    }
    setLocalRows((items) => [record, ...records, ...items]);
    setSelectedRecord(record);
    setShowCreate(false);
  };

  const saveInlineCell = (row: CRMRecord, key: string, value: string | number | boolean | null) => {
    if (!apiEntity || !row.id) return Promise.resolve();
    const config = listInlineEditConfig[kind]?.[key];
    if (!config) return Promise.resolve();
    const previous = records;
    const nextRows = records.map((item) => (Number(item.id) === Number(row.id) ? { ...item, [key]: value } : item));
    setLocalRows(nextRows);
    setSelectedRecord((current) => (current && Number(current.id) === Number(row.id) ? { ...current, [key]: value } : current));
    const payloadValue = normalizeInlineValue(config, value);
    return crmApi.update(apiEntity, Number(row.id), { [config.apiField]: payloadValue }).catch((err) => {
      setLocalRows(previous);
      setSelectedRecord((current) => (current && Number(current.id) === Number(row.id) ? row : current));
      throw new Error(err?.response?.data?.detail || "Inline update failed.");
    });
  };

  const importRows = (items: CRMRecord[]) => {
    if (!apiEntity) {
      setLocalRows(items);
      return;
    }
    setImportExportError(null);
    crmApi
      .importRows<{ created: number; items?: CRMApiRecord[]; errors?: Array<{ row: number; error: string }> }>(apiEntity, items as CRMApiRecord[])
      .then((response) => {
        if (response.data.errors?.length) {
          setImportExportError(response.data.errors.map((item) => `Row ${item.row}: ${item.error}`).join("; "));
          return;
        }
        const imported = (response.data.items || []).map((item) => normalizeApiRecord(kindlessEntity(apiEntity), item));
        setLocalRows([...imported, ...records]);
      })
      .catch((err) => setImportExportError(err?.response?.data?.detail || "CRM import failed."));
  };

  const exportServerRows = () => {
    if (!apiEntity) {
      exportRows(`${pageTitles[kind].toLowerCase().replace(/\s+/g, "-")}.csv`, rows);
      return;
    }
    setImportExportError(null);
    crmApi
      .exportEntity(apiEntity)
      .then((response) => {
        const url = URL.createObjectURL(response.data);
        const link = document.createElement("a");
        link.href = url;
        link.download = `${apiEntity}.csv`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      })
      .catch((err) => setImportExportError(err?.response?.data?.detail || "CRM export failed."));
  };

  return (
    <div className="space-y-6">
      <PageHeader title={pageTitles[kind]} description={descriptionFor(kind)} action={actionFor(kind)} onAction={() => setShowCreate(true)} />
      <Toolbar
        search={search}
        onSearch={setSearch}
        selectedView={selectedView}
        onViewChange={setSelectedView}
        onToggleFilters={() => setShowFilters((value) => !value)}
        contacts={contacts}
        onImportContacts={importRows}
        onExportServer={exportServerRows}
        importLabel={`Import ${pageTitles[kind].replace("CRM ", "")}`}
        exportLabel={`Export ${pageTitles[kind].replace("CRM ", "")}`}
      />
      {importExportError ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{importExportError}</div> : null}
      {showFilters ? (
        <FilterPanel
          filters={filters}
          onChange={setFilters}
          owners={owners}
          statuses={statuses}
          types={types}
          territories={territories}
          onClear={() => setFilters({ owner: "all", status: "all", type: "all", territory: "all" })}
        />
      ) : null}
      <div className="grid gap-4 xl:grid-cols-[1fr_22rem]">
        <SmartCRMTable rows={rows} title={pageTitles[kind]} kind={kind} onSelect={setSelectedRecord} onOpen={detailPathFor(kind) ? (row) => navigate(`${detailPathFor(kind)}/${row.id}`) : undefined} onInlineSave={saveInlineCell} onBulkDelete={apiEntity ? (selectedRows) => Promise.all(selectedRows.map((row) => crmApi.delete(apiEntity, Number(row.id)))).then(() => {
          const selectedIds = new Set(selectedRows.map((row) => Number(row.id)));
          setLocalRows(records.filter((row) => !selectedIds.has(Number(row.id))));
          setSelectedRecord(null);
        }) : undefined} loading={loading} error={error} />
        <RecordPanel record={selectedRecord || rows[0] || null} kind={kind} />
      </div>
      {showCreate ? <CreateRecordDialog kind={kind} saving={createSaving} error={createError} onClose={() => setShowCreate(false)} onCreate={createRecord} /> : null}
    </div>
  );
}

function ProductCatalogPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [selectedView, setSelectedView] = useState(savedViews[0]);
  const [filters, setFilters] = useState<CRMFilters>({ owner: "all", status: "all", type: "all", territory: "all" });
  const [showFilters, setShowFilters] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState<CRMRecord | null>(null);
  const [localRows, setLocalRows] = useState<CRMRecord[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [createSaving, setCreateSaving] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [importExportError, setImportExportError] = useState<string | null>(null);
  const { data: apiRows, loading, error } = useCrmRecords<CRMRecord>("products", emptyRecords);
  const records = localRows.length ? localRows : apiRows;
  const rows = useMemo(() => filterRecords(records, search, selectedView, filters), [records, search, selectedView, filters]);
  const owners = useMemo(() => uniqueValues(records, "owner"), [records]);
  const statuses = useMemo(() => uniqueValues(records, "status"), [records]);
  const types = useMemo(() => uniqueValues(records, "type"), [records]);
  const territories = useMemo(() => uniqueValues(records, "territoryId"), [records]);
  const metrics = useMemo(() => productCatalogMetrics(rows), [rows]);

  const createProduct = (draft: CRMRecord, customFields?: CRMApiRecord) => {
    setCreateSaving(true);
    setCreateError(null);
    crmApi
      .create<CRMApiRecord>("products", { ...createPayloadForKind("products", draft), customFields: customFields || {} })
      .then((response) => {
        const created = normalizeApiRecord("products", response.data);
        setLocalRows((items) => [created, ...items.filter((item) => Number(item.id) !== Number(created.id)), ...apiRows.filter((item) => Number(item.id) !== Number(created.id))]);
        setSelectedRecord(created);
        setShowCreate(false);
      })
      .catch((err) => setCreateError(err?.response?.data?.detail || "Product could not be created."))
      .finally(() => setCreateSaving(false));
  };

  const importRows = (items: CRMRecord[]) => {
    setImportExportError(null);
    crmApi
      .importRows<{ created: number; items?: CRMApiRecord[]; errors?: Array<{ row: number; error: string }> }>("products", items as CRMApiRecord[])
      .then((response) => {
        if (response.data.errors?.length) {
          setImportExportError(response.data.errors.map((item) => `Row ${item.row}: ${item.error}`).join("; "));
          return;
        }
        const imported = (response.data.items || []).map((item) => normalizeApiRecord("products", item));
        setLocalRows([...imported, ...records]);
      })
      .catch((err) => setImportExportError(err?.response?.data?.detail || "Product import failed."));
  };

  const exportProducts = () => {
    setImportExportError(null);
    crmApi
      .exportEntity("products")
      .then((response) => {
        const url = URL.createObjectURL(response.data);
        const link = document.createElement("a");
        link.href = url;
        link.download = "products.csv";
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      })
      .catch((err) => setImportExportError(err?.response?.data?.detail || "Product export failed."));
  };

  const saveInlineCell = (row: CRMRecord, key: string, value: string | number | boolean | null) => {
    const config = listInlineEditConfig.products?.[key];
    if (!config || !row.id) return Promise.resolve();
    const previous = records;
    const nextRows = records.map((item) => (Number(item.id) === Number(row.id) ? { ...item, [key]: value } : item));
    setLocalRows(nextRows);
    setSelectedRecord((current) => (current && Number(current.id) === Number(row.id) ? { ...current, [key]: value } : current));
    return crmApi.update("products", Number(row.id), { [config.apiField]: normalizeInlineValue(config, value) }).catch((err) => {
      setLocalRows(previous);
      setSelectedRecord((current) => (current && Number(current.id) === Number(row.id) ? row : current));
      throw new Error(err?.response?.data?.detail || "Product update failed.");
    });
  };

  return (
    <div className="min-h-[calc(100vh-5rem)] bg-slate-50/70">
      <div className="border-b bg-white px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">CRM Catalog</Badge>
              <Badge className="bg-emerald-50 text-emerald-700 hover:bg-emerald-50">Quote-ready products</Badge>
            </div>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">Products</h1>
            <p className="max-w-3xl text-sm text-slate-600">Manage sellable products, SKUs, pricing, margins, categories, and quote/SRM handoff readiness from one catalog.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => navigate("/crm/price-books")}><IndianRupee className="h-4 w-4" />Price books</Button>
            <Button variant="outline" onClick={exportProducts}><Download className="h-4 w-4" />Export</Button>
            <Button onClick={() => setShowCreate(true)}><Plus className="h-4 w-4" />Add product</Button>
          </div>
        </div>
      </div>
      <main className="space-y-5 px-4 py-4 sm:px-6 lg:px-8">
        <Toolbar
          search={search}
          onSearch={setSearch}
          selectedView={selectedView}
          onViewChange={setSelectedView}
          onToggleFilters={() => setShowFilters((value) => !value)}
          contacts={[]}
          onImportContacts={importRows}
          onExportServer={exportProducts}
          importLabel="Import Products"
          exportLabel="Export Products"
        />
        {importExportError ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{importExportError}</div> : null}
        {showFilters ? (
          <FilterPanel
            filters={filters}
            onChange={setFilters}
            owners={owners}
            statuses={statuses}
            types={types}
            territories={territories}
            onClear={() => setFilters({ owner: "all", status: "all", type: "all", territory: "all" })}
          />
        ) : null}
        {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div> : null}
        {loading ? <div className="rounded-md border bg-white px-4 py-3 text-sm text-slate-500">Loading product catalog...</div> : null}
        <div className="grid gap-3 md:grid-cols-4">
          <ProductCatalogMetric label="Products" value={rows.length} detail={`${metrics.active} active`} />
          <ProductCatalogMetric label="Catalog value" value={formatCurrency(metrics.catalogValue)} detail="List price total" />
          <ProductCatalogMetric label="Avg margin" value={`${metrics.averageMargin}%`} detail="List price vs cost" />
          <ProductCatalogMetric label="Categories" value={metrics.categories} detail="Selling groups" />
        </div>
        {rows.length ? (
          <div className="grid gap-4 xl:grid-cols-[1fr_22rem]">
            <div className="space-y-4">
              <div className="grid gap-3 lg:grid-cols-3">
                {rows.slice(0, 6).map((product) => <ProductCatalogCard key={String(product.id || product.name)} product={product} onOpen={() => product.id ? navigate(`/crm/products/${product.id}`) : setSelectedRecord(product)} onSelect={() => setSelectedRecord(product)} />)}
              </div>
              <SmartCRMTable rows={rows} title="Products" kind="products" onSelect={setSelectedRecord} onOpen={(row) => navigate(`/crm/products/${row.id}`)} onInlineSave={saveInlineCell} loading={loading} error={error} />
            </div>
            <ProductCatalogSidePanel record={selectedRecord || rows[0]} />
          </div>
        ) : (
          <ProductCatalogEmptyState onCreate={() => setShowCreate(true)} onImport={() => document.querySelector<HTMLInputElement>('input[type="file"]')?.click()} />
        )}
      </main>
      {showCreate ? <CreateRecordDialog kind="products" saving={createSaving} error={createError} onClose={() => setShowCreate(false)} onCreate={createProduct} /> : null}
    </div>
  );
}

function ProductCatalogMetric({ label, value, detail }: { label: string; value: string | number; detail: string }) {
  return (
    <div className="rounded-md border bg-white p-4">
      <p className="text-xs font-medium uppercase text-slate-500">{label}</p>
      <p className="mt-2 text-xl font-semibold text-slate-950">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{detail}</p>
    </div>
  );
}

function productCatalogMetrics(rows: CRMRecord[]) {
  const active = rows.filter((row) => String(row.status || "Active").toLowerCase() === "active").length;
  const catalogValue = rows.reduce((sum, row) => sum + Number(row.price || row.listPrice || row.list_price || row.unit_price || 0), 0);
  const margins = rows
    .map((row) => {
      const price = Number(row.price || row.listPrice || row.list_price || row.unit_price || 0);
      const cost = Number(row.cost || row.costPrice || row.cost_price || 0);
      return price ? Math.round(((price - cost) / price) * 100) : 0;
    })
    .filter((margin) => margin > 0);
  const averageMargin = margins.length ? Math.round(margins.reduce((sum, margin) => sum + margin, 0) / margins.length) : 0;
  const categories = new Set(rows.map((row) => String(row.category || "")).filter(Boolean)).size;
  return { active, catalogValue, averageMargin, categories };
}

function ProductCatalogCard({ product, onOpen, onSelect }: { product: CRMRecord; onOpen: () => void; onSelect: () => void }) {
  const price = Number(product.price || product.listPrice || product.list_price || product.unit_price || 0);
  const cost = Number(product.cost || product.costPrice || product.cost_price || 0);
  const margin = price ? Math.round(((price - cost) / price) * 100) : 0;
  return (
    <button type="button" className="rounded-md border bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-emerald-300 hover:shadow-md" onClick={onSelect} onDoubleClick={onOpen}>
      <div className="flex items-start justify-between gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-emerald-50 text-emerald-700"><PackageIcon /></span>
        <Badge className={statusColor(String(product.status || "Active"))}>{String(product.status || "Active")}</Badge>
      </div>
      <h3 className="mt-4 line-clamp-2 text-base font-semibold text-slate-950">{String(product.name || "Untitled product")}</h3>
      <p className="mt-1 text-sm text-slate-500">{String(product.productCode || product.product_code || product.sku || "No SKU")}</p>
      <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
        <div className="rounded bg-slate-50 p-2">
          <p className="text-xs text-slate-500">List price</p>
          <p className="font-semibold text-slate-950">{formatCurrency(price)}</p>
        </div>
        <div className="rounded bg-slate-50 p-2">
          <p className="text-xs text-slate-500">Margin</p>
          <p className="font-semibold text-slate-950">{margin}%</p>
        </div>
      </div>
      <p className="mt-3 truncate text-xs text-slate-500">{String(product.category || "Uncategorized")} / Quote and SRM ready</p>
    </button>
  );
}

function ProductCatalogSidePanel({ record }: { record: CRMRecord }) {
  const price = Number(record.price || record.listPrice || record.list_price || record.unit_price || 0);
  const cost = Number(record.cost || record.costPrice || record.cost_price || 0);
  const margin = price ? Math.round(((price - cost) / price) * 100) : 0;
  const readiness = [
    { label: "SKU configured", done: Boolean(record.productCode || record.product_code || record.sku) },
    { label: "Price available", done: price > 0 },
    { label: "Cost captured", done: cost > 0 },
    { label: "Active for quoting", done: String(record.status || "Active").toLowerCase() === "active" },
  ];
  return (
    <aside className="rounded-md border bg-white p-4">
      <div className="flex items-start gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-emerald-50 text-emerald-700"><PackageIcon /></span>
        <div className="min-w-0">
          <p className="truncate font-semibold text-slate-950">{String(record.name || "Product")}</p>
          <p className="text-sm text-slate-500">{String(record.category || "Catalog item")}</p>
        </div>
      </div>
      <div className="mt-4 grid gap-3">
        <InfoTile label="List price" value={formatCurrency(price)} />
        <InfoTile label="Cost" value={formatCurrency(cost)} />
        <InfoTile label="Margin" value={`${margin}%`} />
      </div>
      <div className="mt-5">
        <p className="text-xs font-semibold uppercase text-slate-500">Quote readiness</p>
        <div className="mt-3 space-y-2">
          {readiness.map((item) => (
            <div key={item.label} className="flex items-center justify-between rounded bg-slate-50 px-3 py-2 text-sm">
              <span>{item.label}</span>
              {item.done ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <AlertTriangle className="h-4 w-4 text-amber-600" />}
            </div>
          ))}
        </div>
      </div>
      <div className="mt-5 rounded-md border bg-emerald-50/60 p-3">
        <p className="text-sm font-semibold text-emerald-950">Sales usage</p>
        <p className="mt-1 text-sm text-emerald-800">Use products inside deals, quotes, price books, approvals, and SRM commercial handoff.</p>
      </div>
    </aside>
  );
}

function ProductCatalogEmptyState({ onCreate, onImport }: { onCreate: () => void; onImport: () => void }) {
  return (
    <section className="rounded-md border bg-white px-6 py-12 text-center shadow-sm">
      <div className="mx-auto flex h-28 w-28 items-center justify-center rounded-full bg-emerald-50 text-emerald-700">
        <PackageIcon large />
      </div>
      <h2 className="mt-6 text-2xl font-semibold text-slate-950">Build your sellable catalog</h2>
      <p className="mx-auto mt-3 max-w-2xl text-sm leading-6 text-slate-600">Products are the items your team sells, quotes, discounts, bundles, and hands off to SRM for billing. Start with one product or import your full SKU catalog.</p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <Button onClick={onCreate}><Plus className="h-4 w-4" />Add product</Button>
        <Button variant="outline" onClick={onImport}><Upload className="h-4 w-4" />Import from file</Button>
      </div>
      <div className="mx-auto mt-8 grid max-w-4xl gap-3 text-left md:grid-cols-3">
        {[
          ["Quote faster", "Reusable prices, tax-ready line items, and approval thresholds."],
          ["Control margins", "Capture list price and cost before proposals go out."],
          ["Handoff cleanly", "Products can flow into quotes, SRM orders, invoices, and revenue reports."],
        ].map(([title, text]) => (
          <div key={title} className="rounded-md border bg-slate-50/70 p-4">
            <p className="font-semibold text-slate-950">{title}</p>
            <p className="mt-1 text-sm text-slate-600">{text}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function PackageIcon({ large = false }: { large?: boolean }) {
  return <Package className={large ? "h-14 w-14" : "h-5 w-5"} />;
}

function quoteIdFromPath() {
  const match = window.location.pathname.match(/\/crm\/quotes\/(\d+)/);
  return Number(match?.[1] || 1);
}

function QuoteBuilderPage() {
  const quoteId = quoteIdFromPath();
  const [quote, setQuote] = useState<CRMRecord | null>(null);
  const [line, setLine] = useState<CRMRecord>({ item_type: "service", name: "Implementation", quantity: 1, unit_price: 50000, discount_type: "amount", discount_value: 0, tax_rate: 18, estimated_cost: 25000, billing_type: "fixed" });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const load = () => {
    setError(null);
    crmApi.get<CRMApiRecord>("quotes", quoteId).then((response) => setQuote(response.data)).catch((err) => setError(err?.response?.data?.detail || "Quote could not be loaded."));
  };
  useEffect(load, [quoteId]);
  const run = (label: string, action: () => Promise<{ data: CRMApiRecord }>) => {
    setSaving(true);
    setError(null);
    action().then((response) => setQuote(response.data.quote && typeof response.data.quote === "object" ? response.data.quote as CRMRecord : response.data)).catch((err) => setError(err?.response?.data?.detail || `${label} failed.`)).finally(() => setSaving(false));
  };
  const addLine = () => run("Add line", () => crmApi.addQuoteLine(quoteId, line));
  const lines = Array.isArray(quote?.lines) ? quote?.lines as CRMRecord[] : [];
  return (
    <div className="space-y-6">
      <PageHeader title="Quote Builder" description={descriptionFor("quoteBuilder")} action="Recalculate" onAction={() => run("Calculate", () => crmApi.calculateQuote(quoteId))} />
      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div> : null}
      <div className="grid gap-4 xl:grid-cols-[1fr_22rem]">
        <div className="space-y-4">
          <Card>
            <CardContent className="grid gap-3 p-4 md:grid-cols-4">
              <InfoTile label="Quote" value={String(quote?.quoteNumber || quote?.quote_number || `#${quoteId}`)} />
              <InfoTile label="Status" value={String(quote?.status || "Draft")} />
              <InfoTile label="Grand total" value={formatCurrency(Number(quote?.grandTotal || quote?.grand_total || quote?.total_amount || 0))} />
              <InfoTile label="Margin" value={formatCurrency(Number(quote?.expectedMargin || quote?.expected_margin || 0))} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Quote Lines</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className="grid gap-2 md:grid-cols-6">
                <Input value={String(line.name || "")} onChange={(event) => setLine((current) => ({ ...current, name: event.target.value }))} placeholder="Line item" />
                <Input type="number" value={Number(line.quantity || 1)} onChange={(event) => setLine((current) => ({ ...current, quantity: Number(event.target.value) }))} />
                <Input type="number" value={Number(line.unit_price || 0)} onChange={(event) => setLine((current) => ({ ...current, unit_price: Number(event.target.value) }))} />
                <Input type="number" value={Number(line.discount_value || 0)} onChange={(event) => setLine((current) => ({ ...current, discount_value: Number(event.target.value) }))} />
                <Input type="number" value={Number(line.tax_rate || 0)} onChange={(event) => setLine((current) => ({ ...current, tax_rate: Number(event.target.value) }))} />
                <Button onClick={addLine} disabled={saving}><Plus className="h-4 w-4" />Add</Button>
              </div>
              <SmartCRMTable rows={lines.map((item) => normalizeApiRecord("quoteBuilder", item))} title="Quote lines" kind="quoteBuilder" onSelect={() => undefined} />
            </CardContent>
          </Card>
        </div>
        <Card>
          <CardHeader><CardTitle>Quote Actions</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <Button className="w-full justify-start" variant="outline" onClick={() => run("Submit", () => crmApi.submitQuote(quoteId))}>Submit for approval</Button>
            <Button className="w-full justify-start" variant="outline" onClick={() => run("Approve", () => crmApi.approveQuote(quoteId))}>Approve</Button>
            <Button className="w-full justify-start" variant="outline" onClick={() => run("Send", () => crmApi.sendQuote(quoteId))}>Send</Button>
            <Button className="w-full justify-start" variant="outline" onClick={() => run("Accept", () => crmApi.acceptQuote(quoteId))}>Accept and convert to SRM</Button>
            <Button className="w-full justify-start" variant="outline" onClick={() => run("New version", () => crmApi.newQuoteVersion(quoteId))}>Create new version</Button>
            <Button className="w-full justify-start" variant="outline" onClick={() => crmApi.quotePdf(quoteId, true)}>Generate PDF</Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function QuoteApprovalsPage() {
  const { data, loading, error } = useCrmRecords<CRMRecord>("quote-approvals", emptyRecords);
  return (
    <div className="space-y-6">
      <PageHeader title="Quote Approvals" description={descriptionFor("quoteApprovals")} />
      <SmartCRMTable rows={data} title="Quote approvals" kind="quoteApprovals" onSelect={() => undefined} loading={loading} error={error} />
    </div>
  );
}

function CPQPage() {
  const { data, loading, error } = useCrmRecords<CRMRecord>("cpq-rules", emptyRecords);
  const [amount, setAmount] = useState(250000);
  const [discount, setDiscount] = useState(0);
  const [result, setResult] = useState<CRMRecord | null>(null);
  return (
    <div className="space-y-6">
      <PageHeader title="CPQ Rules" description={descriptionFor("cpq")} action="Evaluate" onAction={() => crmApi.evaluateCpq({ amount, discount }).then((response) => setResult(response.data))} />
      <Card><CardContent className="grid gap-3 p-4 md:grid-cols-[1fr_1fr_auto]"><Input type="number" value={amount} onChange={(event) => setAmount(Number(event.target.value))} /><Input type="number" value={discount} onChange={(event) => setDiscount(Number(event.target.value))} /><Button onClick={() => crmApi.evaluateCpq({ amount, discount }).then((response) => setResult(response.data))}><Sparkles className="h-4 w-4" />Evaluate</Button></CardContent></Card>
      {result ? <Card><CardContent className="grid gap-3 p-4 md:grid-cols-3"><InfoTile label="Rules checked" value={String(result.ruleCount || 0)} /><InfoTile label="Warnings" value={String((result.warnings as CRMRecord[] | undefined)?.length || 0)} /><InfoTile label="Recommendations" value={String((result.recommendations as CRMRecord[] | undefined)?.length || 0)} /></CardContent></Card> : null}
      <SmartCRMTable rows={data} title="CPQ rules" kind="cpq" onSelect={() => undefined} loading={loading} error={error} />
    </div>
  );
}

function GuidedSellingPage() {
  const { data, loading, error } = useCrmRecords<CRMRecord>("guided-selling-flows", emptyRecords);
  return (
    <div className="space-y-6">
      <PageHeader title="Guided Selling" description={descriptionFor("guidedSelling")} action="Create flow" />
      <SmartCRMTable rows={data} title="Guided selling flows" kind="guidedSelling" onSelect={() => undefined} loading={loading} error={error} />
    </div>
  );
}

function ApprovalSettingsPage() {
  const [workflows, setWorkflows] = useState<CRMApprovalWorkflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const load = () => {
    setLoading(true);
    setError(null);
    crmApi.approvalWorkflows().then((response) => setWorkflows(response.data.items || [])).catch((err) => setError(err?.response?.data?.detail || "Approval workflows could not be loaded.")).finally(() => setLoading(false));
  };
  useEffect(load, []);
  const toggleWorkflow = (workflow: CRMApprovalWorkflow) => {
    crmApi.updateApprovalWorkflow(Number(workflow.id), { isActive: !workflow.isActive }).then((response) => {
      setWorkflows((items) => items.map((item) => (Number(item.id) === Number(workflow.id) ? response.data : item)));
    }).catch((err) => setError(err?.response?.data?.detail || "Workflow could not be updated."));
  };
  return (
    <div className="space-y-6">
      <PageHeader title="Approval Settings" description={descriptionFor("approvalSettings")} action="Create workflow" onAction={() => setShowCreate(true)} />
      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div> : null}
      {loading ? <div className="rounded-md border bg-card px-4 py-3 text-sm text-muted-foreground">Loading approval workflows...</div> : null}
      <div className="grid gap-4">
        {workflows.map((workflow) => (
          <Card key={workflow.id}>
            <CardContent className="grid gap-4 p-4 lg:grid-cols-[1fr_11rem_10rem_9rem] lg:items-center">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-semibold">{workflow.name}</p>
                  <Badge className={workflow.isActive ? statusColor("Active") : statusColor("Inactive")}>{workflow.isActive ? "Active" : "Inactive"}</Badge>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{labelFor(String(workflow.entityType))} / {labelFor(String(workflow.triggerType))} / {(workflow.steps || []).length} step(s)</p>
                <p className="mt-1 text-xs text-muted-foreground">Conditions {JSON.stringify(workflow.conditions || {})}</p>
              </div>
              <Badge variant="outline">{labelFor(String(workflow.entityType))}</Badge>
              <span className="text-sm text-muted-foreground">{labelFor(String(workflow.triggerType))}</span>
              <Button variant="outline" onClick={() => toggleWorkflow(workflow)}>{workflow.isActive ? "Deactivate" : "Activate"}</Button>
            </CardContent>
          </Card>
        ))}
        {!loading && !workflows.length ? <Card><CardContent className="p-5 text-sm text-muted-foreground">No approval workflows configured yet.</CardContent></Card> : null}
      </div>
      {showCreate ? <ApprovalWorkflowDialog onClose={() => setShowCreate(false)} onCreated={(workflow) => { setWorkflows((items) => [workflow, ...items]); setShowCreate(false); }} /> : null}
    </div>
  );
}

function ApprovalWorkflowDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (workflow: CRMApprovalWorkflow) => void }) {
  const [draft, setDraft] = useState({
    name: "High value deal approval",
    entityType: "deal",
    triggerType: "manual",
    conditions: "{\"minAmount\":1000000}",
    approverType: "user",
    approverId: "1",
    actionOnReject: "stop",
  });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const patch = (key: string, value: string) => setDraft((current) => ({ ...current, [key]: value }));
  const submit = () => {
    setSaving(true);
    setError(null);
    let conditions: CRMApiRecord = {};
    try {
      conditions = draft.conditions.trim() ? JSON.parse(draft.conditions) : {};
    } catch {
      setSaving(false);
      setError("Conditions must be valid JSON.");
      return;
    }
    crmApi.createApprovalWorkflow({
      name: draft.name,
      entityType: draft.entityType,
      triggerType: draft.triggerType,
      conditions,
      isActive: true,
      steps: [{ stepOrder: 1, approverType: draft.approverType, approverId: draft.approverType === "manager" ? null : Number(draft.approverId || 0), actionOnReject: draft.actionOnReject }],
    }).then((response) => onCreated(response.data)).catch((err) => setError(err?.response?.data?.detail || "Workflow could not be created.")).finally(() => setSaving(false));
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <Card className="w-full max-w-2xl">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Create Approval Workflow</CardTitle>
          <Button variant="ghost" size="sm" onClick={onClose}><X className="h-4 w-4" /></Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div> : null}
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1 text-sm"><span className="font-medium">Name</span><Input value={draft.name} onChange={(event) => patch("name", event.target.value)} /></label>
            <label className="space-y-1 text-sm"><span className="font-medium">Entity</span><select className="h-10 w-full rounded-md border bg-background px-3" value={draft.entityType} onChange={(event) => patch("entityType", event.target.value)}><option value="deal">Deal</option><option value="quotation">Quotation</option></select></label>
            <label className="space-y-1 text-sm"><span className="font-medium">Trigger</span><select className="h-10 w-full rounded-md border bg-background px-3" value={draft.triggerType} onChange={(event) => patch("triggerType", event.target.value)}><option value="manual">Manual submit</option><option value="discount">Discount approval</option><option value="stage">Stage approval</option><option value="high-value">High-value deal</option><option value="contract-price">Contract/price approval</option></select></label>
            <label className="space-y-1 text-sm"><span className="font-medium">Approver type</span><select className="h-10 w-full rounded-md border bg-background px-3" value={draft.approverType} onChange={(event) => patch("approverType", event.target.value)}><option value="user">User</option><option value="role">Role</option><option value="manager">Manager</option></select></label>
            <label className="space-y-1 text-sm"><span className="font-medium">Approver ID</span><Input type="number" value={draft.approverId} disabled={draft.approverType === "manager"} onChange={(event) => patch("approverId", event.target.value)} /></label>
            <label className="space-y-1 text-sm"><span className="font-medium">Reject action</span><select className="h-10 w-full rounded-md border bg-background px-3" value={draft.actionOnReject} onChange={(event) => patch("actionOnReject", event.target.value)}><option value="stop">Stop</option><option value="send_back">Send back</option></select></label>
          </div>
          <label className="space-y-1 text-sm"><span className="font-medium">Conditions JSON</span><textarea className="min-h-24 w-full rounded-md border bg-background px-3 py-2 text-sm" value={draft.conditions} onChange={(event) => patch("conditions", event.target.value)} /></label>
          <div className="flex justify-end gap-2"><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={submit} disabled={saving}>{saving ? "Creating..." : "Create"}</Button></div>
        </CardContent>
      </Card>
    </div>
  );
}

function MyApprovalsPage() {
  const [approvals, setApprovals] = useState<CRMApprovalRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = () => {
    setLoading(true);
    setError(null);
    crmApi.myPendingApprovals().then((response) => setApprovals(response.data.items || [])).catch((err) => setError(err?.response?.data?.detail || "Pending approvals could not be loaded.")).finally(() => setLoading(false));
  };
  useEffect(load, []);
  const decide = (approval: CRMApprovalRequest, approve: boolean) => {
    const comments = window.prompt(approve ? "Approval comments" : "Rejection comments") || "";
    const action = approve ? crmApi.approve : crmApi.reject;
    action(Number(approval.id), { comments }).then(load).catch((err) => setError(err?.response?.data?.detail || "Approval decision could not be saved."));
  };
  return (
    <div className="space-y-6">
      <PageHeader title="My Approvals" description={descriptionFor("myApprovals")} />
      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div> : null}
      {loading ? <div className="rounded-md border bg-card px-4 py-3 text-sm text-muted-foreground">Loading pending approvals...</div> : null}
      <div className="grid gap-4">
        {approvals.map((approval) => (
          <Card key={approval.id}>
            <CardContent className="grid gap-4 p-4 lg:grid-cols-[1fr_9rem_9rem_12rem] lg:items-center">
              <div>
                <p className="font-semibold">{approval.workflow?.name || "CRM approval"}</p>
                <p className="text-sm text-muted-foreground">{labelFor(approval.entityType)} #{approval.entityId} submitted {formatDate(approval.submittedAt || "")}</p>
              </div>
              <Badge className={statusColor(approval.status)}>{approval.status}</Badge>
              <Badge variant="outline">{labelFor(approval.entityType)}</Badge>
              <div className="flex gap-2">
                <Button size="sm" onClick={() => decide(approval, true)}><CheckCircle2 className="h-4 w-4" />Approve</Button>
                <Button size="sm" variant="outline" onClick={() => decide(approval, false)}><X className="h-4 w-4" />Reject</Button>
              </div>
            </CardContent>
          </Card>
        ))}
        {!loading && !approvals.length ? <Card><CardContent className="p-5 text-sm text-muted-foreground">No approvals are waiting on you.</CardContent></Card> : null}
      </div>
    </div>
  );
}

function DuplicateManagementPage() {
  const [entityType, setEntityType] = useState("contact");
  const [groups, setGroups] = useState<CRMDuplicateGroup[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<CRMDuplicateGroup | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = () => {
    setLoading(true);
    setError(null);
    crmApi.duplicates({ entityType }).then((response) => setGroups(response.data.items || [])).catch((err) => setError(err?.response?.data?.detail || "Duplicate scan could not be loaded.")).finally(() => setLoading(false));
  };
  useEffect(load, [entityType]);
  const scanAll = () => {
    setLoading(true);
    setError(null);
    crmApi.scanDuplicates().then((response) => setGroups(response.data.items || [])).catch((err) => setError(err?.response?.data?.detail || "Duplicate scan failed.")).finally(() => setLoading(false));
  };
  return (
    <div className="space-y-6">
      <PageHeader title="Duplicate Management" description={descriptionFor("duplicates")} action="Scan all" onAction={scanAll} />
      <Card>
        <CardContent className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
          <div className="flex gap-2">
            {["lead", "contact", "account"].map((type) => (
              <Button key={type} type="button" variant={entityType === type ? "default" : "outline"} onClick={() => setEntityType(type)}>{labelFor(type)}</Button>
            ))}
          </div>
          <Badge variant="outline">{groups.length} duplicate group(s)</Badge>
        </CardContent>
      </Card>
      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div> : null}
      {loading ? <div className="rounded-md border bg-card px-4 py-3 text-sm text-muted-foreground">Scanning CRM records...</div> : null}
      <div className="grid gap-4">
        {groups.map((group) => (
          <Card key={String(group.id)}>
            <CardContent className="grid gap-4 p-4 lg:grid-cols-[1fr_8rem_12rem] lg:items-center">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-semibold">{group.records.map((record) => duplicateRecordTitle(record, group.entityType)).join(" / ")}</p>
                  <Badge className={group.score >= 90 ? statusColor("High") : statusColor("Medium")}>{group.score}% match</Badge>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{group.reasons.join(", ") || "Possible duplicate"}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {group.matchingFields.map((field) => <Badge key={field} variant="outline">{labelFor(field)}</Badge>)}
                </div>
              </div>
              <Badge variant="outline">{labelFor(group.entityType)}</Badge>
              <Button onClick={() => setSelectedGroup(group)}><GitMerge className="h-4 w-4" />Merge</Button>
            </CardContent>
          </Card>
        ))}
        {!loading && !groups.length ? <Card><CardContent className="p-5 text-sm text-muted-foreground">No duplicate groups found for this scope.</CardContent></Card> : null}
      </div>
      {selectedGroup ? <MergeWizardModal group={selectedGroup} onClose={() => setSelectedGroup(null)} onMerged={() => { setSelectedGroup(null); load(); }} /> : null}
    </div>
  );
}

function CalendarIntegrationsPage() {
  const [items, setItems] = useState<CRMApiRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = () => {
    setLoading(true);
    setError(null);
    crmApi.calendarIntegrations().then((response) => setItems(response.data.items || [])).catch((err) => setError(err?.response?.data?.detail || "Calendar integrations could not be loaded.")).finally(() => setLoading(false));
  };
  useEffect(load, []);
  const connect = (provider: "google" | "outlook" | "mock") => {
    setMessage(null);
    setError(null);
    crmApi
      .connectCalendarIntegration({ provider, mock: true })
      .then(() => {
        setMessage(`${provider === "mock" ? "Development" : labelFor(provider)} calendar connected with placeholder OAuth settings.`);
        load();
      })
      .catch((err) => setError(err?.response?.data?.detail || "Calendar could not be connected."));
  };
  const disconnect = (id: number) => {
    crmApi.disconnectCalendarIntegration(id).then(() => { setMessage("Calendar integration disconnected."); load(); }).catch((err) => setError(err?.response?.data?.detail || "Calendar could not be disconnected."));
  };
  return (
    <div className="space-y-6">
      <PageHeader title="Calendar Integrations" description="Connect CRM meetings to external calendars. OAuth adapters are isolated behind provider settings and tokens are never returned to the browser." action="Connect Mock" onAction={() => connect("mock")} />
      {message ? <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">{message}</div> : null}
      {error ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader><CardTitle>Google Calendar</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">Uses minimal calendar event scopes once OAuth client settings are configured.</p>
            <Button className="w-full" onClick={() => connect("google")}><CalendarDays className="h-4 w-4" />Connect Google Calendar</Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Outlook Calendar</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">Ready for Microsoft OAuth token exchange and Graph Calendar events.</p>
            <Button className="w-full" onClick={() => connect("outlook")}><CalendarDays className="h-4 w-4" />Connect Outlook</Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Development Provider</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">Creates local external event IDs for testing sync flows without third-party credentials.</p>
            <Button className="w-full" variant="outline" onClick={() => connect("mock")}><CalendarDays className="h-4 w-4" />Connect Mock</Button>
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader><CardTitle>Connected Calendars</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {loading ? <p className="text-sm text-muted-foreground">Loading integrations...</p> : null}
          {items.map((item) => (
            <div key={String(item.id)} className="grid gap-3 rounded-md border p-4 md:grid-cols-[1fr_8rem_12rem_auto] md:items-center">
              <div><p className="font-medium">{labelFor(String(item.provider || "calendar"))}</p><p className="text-sm text-muted-foreground">User {String(item.userId || item.user_id || "-")} / scopes {(Array.isArray(item.scopes) ? item.scopes.join(", ") : "calendar.events")}</p></div>
              <Badge className={statusColor(item.isActive === false ? "Inactive" : "Active")}>{item.isActive === false ? "Inactive" : "Active"}</Badge>
              <span className="text-sm text-muted-foreground">Expires {formatDate(String(item.expiresAt || "")) || "not set"}</span>
              <Button variant="outline" size="sm" onClick={() => disconnect(Number(item.id))}>Disconnect</Button>
            </div>
          ))}
          {!loading && !items.length ? <p className="text-sm text-muted-foreground">No calendar integrations connected yet.</p> : null}
        </CardContent>
      </Card>
    </div>
  );
}

function WebhookSettingsPage() {
  const [webhooks, setWebhooks] = useState<CRMApiRecord[]>([]);
  const [events, setEvents] = useState<string[]>([]);
  const [selected, setSelected] = useState<CRMApiRecord | null>(null);
  const [deliveries, setDeliveries] = useState<CRMApiRecord[]>([]);
  const [draft, setDraft] = useState({ name: "", url: "", secret: "", events: ["lead.created"] as string[], isActive: true });
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const load = () => {
    setLoading(true);
    setError(null);
    crmApi.webhooks().then((response) => { setWebhooks(response.data.items || []); setEvents(response.data.events || []); }).catch((err) => setError(err?.response?.data?.detail || "Webhooks could not be loaded.")).finally(() => setLoading(false));
  };
  useEffect(load, []);
  useEffect(() => {
    if (!selected?.id) {
      setDeliveries([]);
      return;
    }
    crmApi.webhookDeliveries(Number(selected.id)).then((response) => setDeliveries(response.data.items || [])).catch(() => setDeliveries([]));
  }, [selected?.id]);
  const toggleEvent = (event: string) => {
    setDraft((current) => ({ ...current, events: current.events.includes(event) ? current.events.filter((item) => item !== event) : [...current.events, event].sort() }));
  };
  const resetDraft = () => setDraft({ name: "", url: "", secret: "", events: ["lead.created"], isActive: true });
  const create = () => {
    if (!draft.name.trim() || !draft.url.trim()) return;
    setError(null);
    crmApi.createWebhook(draft).then((response) => { setMessage("Webhook created. Secret is masked after creation."); setSelected(response.data); resetDraft(); load(); }).catch((err) => setError(err?.response?.data?.detail || "Webhook could not be created."));
  };
  const toggleActive = (webhook: CRMApiRecord) => {
    crmApi.updateWebhook(Number(webhook.id), { isActive: !(webhook.isActive ?? webhook.is_active) }).then(load).catch((err) => setError(err?.response?.data?.detail || "Webhook could not be updated."));
  };
  const test = (webhook: CRMApiRecord) => {
    setError(null);
    crmApi.testWebhook(Number(webhook.id)).then((response) => { setMessage(`Test delivery ${String(response.data.status || "queued")}.`); setSelected(webhook); crmApi.webhookDeliveries(Number(webhook.id)).then((res) => setDeliveries(res.data.items || [])); }).catch((err) => setError(err?.response?.data?.detail || "Webhook test failed."));
  };
  return (
    <div className="space-y-6">
      <PageHeader title="Webhook Settings" description="Send signed CRM automation events to Zapier, n8n, and integration endpoints." action="Create webhook" onAction={create} />
      {message ? <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">{message}</div> : null}
      {error ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
      <div className="grid gap-4 xl:grid-cols-[26rem_1fr]">
        <Card>
          <CardHeader><CardTitle>Create Webhook</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <Field label="Name"><Input value={draft.name} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} /></Field>
            <Field label="Endpoint URL"><Input value={draft.url} onChange={(event) => setDraft((current) => ({ ...current, url: event.target.value }))} placeholder="https://hooks.example.com/crm" /></Field>
            <Field label="Secret">
              <Input value={draft.secret} onChange={(event) => setDraft((current) => ({ ...current, secret: event.target.value }))} placeholder="Leave blank to generate" />
            </Field>
            <label className="flex items-center gap-2 rounded-md border bg-muted/25 p-3 text-sm"><input type="checkbox" checked={draft.isActive} onChange={(event) => setDraft((current) => ({ ...current, isActive: event.target.checked }))} />Active</label>
            <div className="space-y-2">
              <Label>Events</Label>
              <div className="grid max-h-72 gap-2 overflow-y-auto rounded-md border p-3">
                {events.map((event) => (
                  <label key={event} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.events.includes(event)} onChange={() => toggleEvent(event)} />{event}</label>
                ))}
              </div>
            </div>
            <div className="flex gap-2"><Button className="flex-1" onClick={create}><Plus className="h-4 w-4" />Create</Button><Button variant="outline" onClick={resetDraft}>Reset</Button></div>
          </CardContent>
        </Card>
        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle>Configured Webhooks</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {loading ? <p className="text-sm text-muted-foreground">Loading webhooks...</p> : null}
              {webhooks.map((webhook) => (
                <div key={String(webhook.id)} className="grid gap-3 rounded-md border p-4 lg:grid-cols-[1fr_8rem_9rem_14rem] lg:items-center">
                  <div className="min-w-0">
                    <p className="font-medium">{String(webhook.name || "")}</p>
                    <p className="truncate text-sm text-muted-foreground">{String(webhook.url || "")}</p>
                    <div className="mt-2 flex flex-wrap gap-1">{(Array.isArray(webhook.events) ? webhook.events : []).slice(0, 4).map((event) => <Badge key={String(event)} variant="outline">{String(event)}</Badge>)}</div>
                  </div>
                  <Badge className={statusColor((webhook.isActive ?? webhook.is_active) ? "Active" : "Inactive")}>{(webhook.isActive ?? webhook.is_active) ? "Active" : "Inactive"}</Badge>
                  <span className="text-sm text-muted-foreground">Secret {String(webhook.secret || "masked")}</span>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" size="sm" onClick={() => setSelected(webhook)}>Logs</Button>
                    <Button variant="outline" size="sm" onClick={() => test(webhook)}>Test</Button>
                    <Button variant="outline" size="sm" onClick={() => toggleActive(webhook)}>{(webhook.isActive ?? webhook.is_active) ? "Disable" : "Enable"}</Button>
                    <Button variant="outline" size="sm" onClick={() => crmApi.deleteWebhook(Number(webhook.id)).then(load)}>Delete</Button>
                  </div>
                </div>
              ))}
              {!loading && !webhooks.length ? <p className="text-sm text-muted-foreground">No webhooks configured yet.</p> : null}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Delivery Log{selected ? ` / ${String(selected.name || selected.id)}` : ""}</CardTitle></CardHeader>
            <CardContent className="overflow-x-auto">
              {!selected ? <p className="text-sm text-muted-foreground">Select a webhook to view deliveries.</p> : null}
              {selected ? <ReportTable title="" rows={deliveries} columns={["eventType", "status", "responseCode", "attemptCount", "nextRetryAt", "createdAt"]} /> : null}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

const crmFeatureChecklist = [
  { feature: "CRM list pages", status: "Ready", api: "GET /api/v1/crm/{entity}", frontend: "Workspace lists", notes: "Leads, contacts, companies/accounts, deals, activities, tasks, campaigns, products, quotations, tickets, files, owners, and custom fields use backend APIs." },
  { feature: "Record detail pages", status: "Ready", api: "GET/PATCH/DELETE /api/v1/crm/{entity}/{id}", frontend: "Lead/contact/account/deal/quotation detail", notes: "Detail payload includes related records, custom fields, duplicate summary, approval state, and timeline." },
  { feature: "Activity timeline", status: "Ready", api: "Related timeline in detail payload", frontend: "Timeline cards on detail pages", notes: "Notes, tasks, calls, emails, meetings, approvals, PDF generation, enrichment, and duplicate merge events are surfaced." },
  { feature: "Pipeline management", status: "Ready", api: "Pipelines, stages, deal updates", frontend: "Pipeline board and settings", notes: "Multiple pipelines and organization-scoped stages are supported." },
  { feature: "Custom fields", status: "Ready", api: "Custom fields and values", frontend: "Settings, create forms, list columns, detail fields", notes: "Visible fields render in lists; values can be edited on detail pages." },
  { feature: "Duplicate detection and merge", status: "Ready", api: "Duplicates scan and merge", frontend: "Duplicate management", notes: "Lead, contact, and account matching is organization-scoped." },
  { feature: "Approvals", status: "Ready", api: "Approval workflows and requests", frontend: "Settings, my approvals, deal/quote detail", notes: "Deal and quotation final actions are blocked while approval is pending or rejected." },
  { feature: "Quotation PDF", status: "Ready", api: "GET quotation PDF, send PDF email", frontend: "Quotation detail actions", notes: "Generated PDF uses persisted quotation, account, contact, line item, and company data." },
  { feature: "Calendar", status: "Ready", api: "GET /api/v1/crm/calendar", frontend: "Calendar page", notes: "Tasks, meetings, calls, activities, quotation expiries, and deal close dates render from DB records." },
  { feature: "Reports", status: "Ready", api: "Win/loss, funnel, revenue, territory reports", frontend: "Reports page", notes: "Charts and tables are backed by organization-scoped deal data." },
  { feature: "Territories", status: "Ready", api: "Territory CRUD and auto-assign", frontend: "Territory settings", notes: "Lead, account, and deal assignment follows territory rules with manual override support." },
  { feature: "Enrichment", status: "Ready", api: "Preview, apply, history", frontend: "Lead/contact detail modal", notes: "Provider abstraction supports manual, CSV/import, and future third-party providers." },
  { feature: "WhatsApp/SMS", status: "Ready", api: "Messages and templates", frontend: "Lead/contact/deal detail compose", notes: "Provider credentials remain server-side; mock provider supports local testing." },
  { feature: "Calendar integrations", status: "Ready", api: "Integration connect, disconnect, sync", frontend: "Calendar integrations page", notes: "Mock provider is available; Google/Outlook adapters have isolated TODO configuration points." },
  { feature: "Outbound webhooks", status: "Ready", api: "Webhook CRUD, test, deliveries", frontend: "Webhook settings", notes: "Signed deliveries are logged and retried with backoff." },
  { feature: "Organization isolation", status: "Ready", api: "Organization-scoped queries", frontend: "Route-level API usage", notes: "Direct record URLs use the same backend organization filter as list pages." },
];

function CRMFeatureChecklistPage() {
  const statusCounts = crmFeatureChecklist.reduce<Record<string, number>>((counts, row) => {
    counts[row.status] = (counts[row.status] || 0) + 1;
    return counts;
  }, {});
  return (
    <div className="space-y-6">
      <PageHeader title="CRM Feature Checklist" description={descriptionFor("featureChecklist")} />
      <div className="grid gap-3 md:grid-cols-3">
        {Object.entries(statusCounts).map(([status, count]) => (
          <Metric key={status} icon={CheckCircle2} label={status} value={count} tone={status === "Ready" ? "emerald" : "amber"} />
        ))}
        <Metric icon={FileCheck2} label="Tracked features" value={crmFeatureChecklist.length} tone="blue" />
      </div>
      <Card>
        <CardHeader><CardTitle>Integration Readiness</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto">
            <table className="crm-desktop-table">
            <thead className="text-left text-xs uppercase text-muted-foreground">
              <tr className="border-b">
                <th className="px-3 py-2">Feature</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">API availability</th>
                <th className="px-3 py-2">Frontend availability</th>
                <th className="px-3 py-2">Notes</th>
              </tr>
            </thead>
            <tbody>
              {crmFeatureChecklist.map((row) => (
                <tr key={row.feature} className="border-b align-top">
                  <td className="px-3 py-3 font-medium">{row.feature}</td>
                  <td className="px-3 py-3"><Badge className={statusColor(row.status)}>{row.status}</Badge></td>
                  <td className="px-3 py-3 text-muted-foreground">{row.api}</td>
                  <td className="px-3 py-3 text-muted-foreground">{row.frontend}</td>
                  <td className="px-3 py-3 text-muted-foreground">{row.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}

function TerritorySettingsPage() {
  const [territories, setTerritories] = useState<CRMApiRecord[]>([]);
  const [reportRows, setReportRows] = useState<CRMApiRecord[]>([]);
  const [users, setUsers] = useState<CRMApiRecord[]>([]);
  const [draft, setDraft] = useState({ name: "", country: "India", state: "", city: "", industry: "", companySize: "", priority: "100", userId: "" });
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const load = () => {
    setLoading(true);
    crmApi.territories().then((response) => setTerritories(response.data.items || [])).catch((err) => setError(err?.response?.data?.detail || "Territories could not be loaded.")).finally(() => setLoading(false));
    crmApi.territoryReport().then((response) => setReportRows(response.data.items || [])).catch(() => setReportRows([]));
    crmApi.searchUsers({ q: "", limit: 25 }).then((response) => setUsers(response.data.items || [])).catch(() => setUsers([]));
  };
  useEffect(load, []);
  const create = () => {
    if (!draft.name.trim()) return;
    const rules = { country: draft.country || undefined, state: draft.state || undefined, city: draft.city || undefined, industry: draft.industry || undefined, companySize: draft.companySize || undefined };
    crmApi.createTerritory({ name: draft.name, country: draft.country, state: draft.state, city: draft.city, priority: Number(draft.priority || 100), rules, isActive: true })
      .then((response) => (draft.userId ? crmApi.addTerritoryUser(Number(response.data.id), { userId: Number(draft.userId) }).then(() => undefined) : Promise.resolve(undefined)))
      .then(() => {
        setDraft({ name: "", country: "India", state: "", city: "", industry: "", companySize: "", priority: "100", userId: "" });
        setMessage("Territory created.");
        load();
      })
      .catch((err) => setError(err?.response?.data?.detail || "Territory could not be created."));
  };
  const toggle = (territory: CRMApiRecord) => {
    crmApi.updateTerritory(Number(territory.id), { isActive: !(territory.isActive ?? territory.is_active) }).then(load).catch((err) => setError(err?.response?.data?.detail || "Territory could not be updated."));
  };
  const autoAssign = (overrideManual = false) => {
    crmApi.autoAssignTerritories({ overrideManual }).then((response) => setMessage(`Assigned ${response.data.updated} CRM records.`)).then(load).catch((err) => setError(err?.response?.data?.detail || "Auto-assignment failed."));
  };
  return (
    <div className="space-y-6">
      <PageHeader title="Territory Settings" description="Create organization-scoped routing territories, assign users, and auto-assign leads, accounts, and deals by rule priority." action="Run Auto-Assign" onAction={() => autoAssign(false)} />
      {message ? <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">{message}</div> : null}
      {error ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
      <div className="grid gap-4 xl:grid-cols-[22rem_1fr]">
        <Card>
          <CardHeader><CardTitle>Create Territory</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <Field label="Name"><Input value={draft.name} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} /></Field>
            <Field label="Country"><Input value={draft.country} onChange={(event) => setDraft((current) => ({ ...current, country: event.target.value }))} /></Field>
            <Field label="State"><Input value={draft.state} onChange={(event) => setDraft((current) => ({ ...current, state: event.target.value }))} /></Field>
            <Field label="City"><Input value={draft.city} onChange={(event) => setDraft((current) => ({ ...current, city: event.target.value }))} /></Field>
            <Field label="Industry"><Input value={draft.industry} onChange={(event) => setDraft((current) => ({ ...current, industry: event.target.value }))} /></Field>
            <Field label="Company size">
              <select className="h-10 rounded-md border bg-background px-3 text-sm" value={draft.companySize} onChange={(event) => setDraft((current) => ({ ...current, companySize: event.target.value }))}>
                <option value="">Any size</option><option value="small">Small</option><option value="mid_market">Mid market</option><option value="enterprise">Enterprise</option><option value="strategic">Strategic</option>
              </select>
            </Field>
            <Field label="Priority"><Input type="number" value={draft.priority} onChange={(event) => setDraft((current) => ({ ...current, priority: event.target.value }))} /></Field>
            <Field label="Assigned user">
              <select className="h-10 rounded-md border bg-background px-3 text-sm" value={draft.userId} onChange={(event) => setDraft((current) => ({ ...current, userId: event.target.value }))}>
                <option value="">No default user</option>
                {users.map((user) => <option key={String(user.id)} value={String(user.id)}>{String(user.displayName || user.email || user.id)}</option>)}
              </select>
            </Field>
            <Button className="w-full" onClick={create}><Plus className="h-4 w-4" />Create territory</Button>
            <Button className="w-full" variant="outline" onClick={() => autoAssign(true)}>Reassign including manual overrides</Button>
          </CardContent>
        </Card>
        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle>Territory Rules</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {loading ? <p className="text-sm text-muted-foreground">Loading territories...</p> : null}
              {territories.map((territory) => (
                <div key={String(territory.id)} className="grid gap-3 rounded-md border p-4 md:grid-cols-[1fr_8rem_9rem_auto] md:items-center">
                  <div><p className="font-medium">{String(territory.name || "")}</p><p className="text-sm text-muted-foreground">{String(territory.city || territory.state || territory.country || "Custom rule")} / priority {String(territory.priority || 100)}</p></div>
                  <Badge className={statusColor((territory.isActive ?? territory.is_active) ? "Active" : "Inactive")}>{(territory.isActive ?? territory.is_active) ? "Active" : "Inactive"}</Badge>
                  <span className="text-sm text-muted-foreground">{Array.isArray(territory.users) ? territory.users.length : 0} user(s)</span>
                  <div className="flex gap-2"><Button variant="outline" size="sm" onClick={() => toggle(territory)}>{(territory.isActive ?? territory.is_active) ? "Deactivate" : "Activate"}</Button><Button variant="outline" size="sm" onClick={() => crmApi.deleteTerritory(Number(territory.id)).then(load)}>Delete</Button></div>
                </div>
              ))}
            </CardContent>
          </Card>
          <ReportTable title="Territory-wise Report" rows={reportRows} columns={["territory", "users", "leads", "accounts", "deals", "wonRevenue"]} />
        </div>
      </div>
    </div>
  );
}

function MergeWizardModal({ group, onClose, onMerged }: { group: CRMDuplicateGroup; onClose: () => void; onMerged: () => void }) {
  const records = group.records || [];
  const [winnerId, setWinnerId] = useState<number>(() => Number(records[0]?.id || 0));
  const [fieldValues, setFieldValues] = useState<CRMApiRecord>(() => mergeDefaultFieldValues(records, group.entityType));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const fields = mergeFieldsFor(group.entityType);
  const submit = () => {
    setSaving(true);
    setError(null);
    crmApi.mergeDuplicates({
      entityType: group.entityType,
      winnerId,
      loserIds: records.map((record) => Number(record.id)).filter((id) => id !== winnerId),
      fieldValues,
    }).then(onMerged).catch((err) => setError(err?.response?.data?.detail || "Records could not be merged.")).finally(() => setSaving(false));
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <Card className="max-h-[92vh] w-full max-w-5xl overflow-hidden">
        <CardHeader className="flex-row items-center justify-between">
          <div><CardTitle>Merge Duplicate Records</CardTitle><p className="text-sm text-muted-foreground">{group.reasons.join(", ")}</p></div>
          <Button variant="ghost" size="sm" onClick={onClose}><X className="h-4 w-4" /></Button>
        </CardHeader>
        <CardContent className="space-y-4 overflow-y-auto">
          {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div> : null}
          <div className="grid gap-3 md:grid-cols-3">
            {records.map((record) => (
              <button key={String(record.id)} type="button" onClick={() => setWinnerId(Number(record.id))} className={`rounded-md border p-3 text-left ${winnerId === Number(record.id) ? "border-primary bg-primary/5" : "bg-card"}`}>
                <div className="flex items-center justify-between gap-2">
                  <p className="font-semibold">{duplicateRecordTitle(record, group.entityType)}</p>
                  <Badge variant={winnerId === Number(record.id) ? "default" : "outline"}>{winnerId === Number(record.id) ? "Winner" : `#${record.id}`}</Badge>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{valueText(record.email || record.phone || record.website || record.company_name)}</p>
              </button>
            ))}
          </div>
          <div className="overflow-x-auto rounded-md border">
            <table className="crm-desktop-table">
              <thead className="bg-muted/60">
                <tr>
                  <th className="px-3 py-2 text-left">Field</th>
                  {records.map((record) => <th key={String(record.id)} className="px-3 py-2 text-left">{duplicateRecordTitle(record, group.entityType)}</th>)}
                  <th className="px-3 py-2 text-left">Selected value</th>
                </tr>
              </thead>
              <tbody>
                {fields.map((field) => (
                  <tr key={field} className="border-t">
                    <td className="px-3 py-2 font-medium">{labelFor(field)}</td>
                    {records.map((record) => (
                      <td key={String(record.id)} className="px-3 py-2">
                        <Button type="button" size="sm" variant="outline" onClick={() => setFieldValues((current) => ({ ...current, [field]: record[field] as CRMApiRecord[string] }))}>{valueText(record[field]) || "-"}</Button>
                      </td>
                    ))}
                    <td className="px-3 py-2">{valueText(fieldValues[field]) || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">Merge will relink activities, notes, tasks, deals, and quotations to the winning record, then soft-delete the losing record(s).</div>
          <div className="flex justify-end gap-2"><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={submit} disabled={saving || records.length < 2}>{saving ? "Merging..." : "Merge records"}</Button></div>
        </CardContent>
      </Card>
    </div>
  );
}

function CRMReports() {
  const defaultEnd = new Date().toISOString().slice(0, 10);
  const defaultStart = new Date(new Date().getFullYear(), new Date().getMonth() - 11, 1).toISOString().slice(0, 10);
  const [filters, setFilters] = useState({ startDate: defaultStart, endDate: defaultEnd, ownerId: "all", pipelineId: "all" });
  const [report, setReport] = useState<CRMWinLossReport | null>(null);
  const [funnel, setFunnel] = useState<CRMApiRecord[]>([]);
  const [revenueTrend, setRevenueTrend] = useState<CRMApiRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pipelineState = useCrmRecords<CRMRecord>("pipelines", emptyRecords, { sort_by: "created_at", sort_order: "asc", per_page: 100 });
  const dealState = useCrmRecords<CRMRecord>("deals", emptyRecords, { per_page: 100 });
  const ownerOptions = useMemo(() => {
    const ids = Array.from(new Set(dealState.data.map((deal) => Number(deal.ownerId || deal.owner_user_id || 0)).filter(Boolean)));
    return ids.map((id) => ({ id, label: `User ${id}` }));
  }, [dealState.data]);
  const queryParams = useMemo(() => {
    const params: Record<string, unknown> = { startDate: filters.startDate, endDate: filters.endDate };
    if (filters.ownerId !== "all") params.ownerId = Number(filters.ownerId);
    if (filters.pipelineId !== "all") params.pipelineId = Number(filters.pipelineId);
    return params;
  }, [filters]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      crmApi.winLossReport(queryParams),
      crmApi.salesFunnelReport(queryParams),
      crmApi.revenueTrendReport(queryParams),
    ])
      .then(([winLossResponse, funnelResponse, trendResponse]) => {
        setReport(winLossResponse.data);
        setFunnel(funnelResponse.data.items || []);
        setRevenueTrend(trendResponse.data.items || winLossResponse.data.revenueWonTrend || []);
      })
      .catch((err) => setError(err?.response?.data?.detail || "Win/loss analysis could not be loaded."))
      .finally(() => setLoading(false));
  }, [queryParams]);

  const summary = report?.summary;
  const exportData = () => {
    if (!report) return;
    exportRows("crm-win-loss-analysis.csv", [
      ...(report.winRateByMonth || []).map((row) => ({ section: "Win rate by month", ...row })),
      ...(report.winRateByOwner || []).map((row) => ({ section: "Win rate by owner", ...row })),
      ...(report.winRateByPipeline || []).map((row) => ({ section: "Win rate by pipeline", ...row })),
      ...(report.winLossBySource || []).map((row) => ({ section: "Win/loss by source", ...row })),
      ...(report.lostReasonBreakdown || []).map((row) => ({ section: "Lost reasons", ...row })),
      ...funnel.map((row) => ({ section: "Sales funnel", ...row })),
    ]);
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Win/Loss Analysis" description="Monthly win rate, owner and pipeline performance, source quality, lost reasons, sales cycle, revenue trend, and stage conversion." action="Export CSV" onAction={exportData} />
      <Card>
        <CardContent className="grid gap-3 p-4 md:grid-cols-5 md:items-end">
          <div className="space-y-1">
            <Label>Start date</Label>
            <Input type="date" value={filters.startDate} onChange={(event) => setFilters((current) => ({ ...current, startDate: event.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label>End date</Label>
            <Input type="date" value={filters.endDate} onChange={(event) => setFilters((current) => ({ ...current, endDate: event.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label>Owner</Label>
            <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={filters.ownerId} onChange={(event) => setFilters((current) => ({ ...current, ownerId: event.target.value }))}>
              <option value="all">All owners</option>
              {ownerOptions.map((owner) => <option key={owner.id} value={owner.id}>{owner.label}</option>)}
            </select>
          </div>
          <div className="space-y-1">
            <Label>Pipeline</Label>
            <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={filters.pipelineId} onChange={(event) => setFilters((current) => ({ ...current, pipelineId: event.target.value }))}>
              <option value="all">All pipelines</option>
              {pipelineState.data.map((pipeline) => <option key={String(pipeline.id)} value={String(pipeline.id)}>{String(pipeline.name || `Pipeline ${pipeline.id}`)}</option>)}
            </select>
          </div>
          <Button variant="outline" onClick={exportData} disabled={!report}><Download className="h-4 w-4" />CSV</Button>
        </CardContent>
      </Card>
      {error ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
      <div className="grid gap-4 md:grid-cols-4">
        <Metric icon={CheckCircle2} label="Win rate" value={loading ? "..." : `${summary?.winRate ?? 0}%`} tone="emerald" />
        <Metric icon={IndianRupee} label="Revenue won" value={loading ? "..." : formatCurrency(summary?.wonRevenue || 0)} tone="blue" />
        <Metric icon={Target} label="Avg won deal" value={loading ? "..." : formatCurrency(summary?.averageWonDealSize || 0)} tone="violet" />
        <Metric icon={Clock} label="Avg sales cycle" value={loading ? "..." : `${summary?.averageSalesCycleDays ?? 0} days`} tone="amber" />
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Win Rate by Month</CardTitle></CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={report?.winRateByMonth || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" />
                <YAxis />
                <Tooltip formatter={(value) => [`${Number(value).toFixed(1)}%`, "Win rate"]} />
                <Line type="monotone" dataKey="winRate" stroke="#059669" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Revenue Won Trend</CardTitle></CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={revenueTrend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" />
                <YAxis />
                <Tooltip formatter={(value) => formatCurrency(Number(value))} />
                <Bar dataKey="revenue" fill="#2563eb" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Win/Loss by Source</CardTitle></CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={report?.winLossBySource || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="key" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="won" stackId="source" fill="#16a34a" />
                <Bar dataKey="lost" stackId="source" fill="#dc2626" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Conversion Funnel by Stage</CardTitle></CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={funnel} layout="vertical" margin={{ left: 24 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" />
                <YAxis type="category" dataKey="stage" width={110} />
                <Tooltip formatter={(value, name) => name === "amount" ? formatCurrency(Number(value)) : value} />
                <Bar dataKey="count" fill="#7c3aed" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <ReportTable title="By Owner" rows={report?.winRateByOwner || []} columns={["key", "won", "lost", "winRate", "wonRevenue"]} />
        <ReportTable title="By Pipeline" rows={report?.winRateByPipeline || []} columns={["key", "won", "lost", "winRate", "wonRevenue"]} />
        <ReportTable title="Lost Reasons" rows={report?.lostReasonBreakdown || []} columns={["reason", "count", "amount"]} />
      </div>
      <Card>
        <CardHeader><CardTitle>Closed Deals</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto p-0">
          <table className="crm-desktop-table">
            <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
              <tr>{["Deal", "Status", "Source", "Owner", "Pipeline", "Amount", "Closed"].map((heading) => <th key={heading} className="px-4 py-3">{heading}</th>)}</tr>
            </thead>
            <tbody>
              {(report?.deals || []).slice(0, 10).map((deal) => (
                <tr key={String(deal.id)} className="border-t">
                  <td className="px-4 py-3 font-medium">{String(deal.name || "")}</td>
                  <td className="px-4 py-3"><Badge className={statusColor(String(deal.status || ""))}>{String(deal.status || "")}</Badge></td>
                  <td className="px-4 py-3">{String(deal.source || "-")}</td>
                  <td className="px-4 py-3">{String(deal.owner || "-")}</td>
                  <td className="px-4 py-3">{String(deal.pipeline || "-")}</td>
                  <td className="px-4 py-3">{formatCurrency(Number(deal.amount || 0))}</td>
                  <td className="px-4 py-3">{deal.closedAt ? formatDate(String(deal.closedAt)) : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}

function ReportTable({ title, rows, columns }: { title: string; rows: CRMApiRecord[]; columns: string[] }) {
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent className="overflow-x-auto p-0">
        <table className="crm-desktop-table">
          <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
            <tr>{columns.map((column) => <th key={column} className="px-3 py-2">{labelFor(column)}</th>)}</tr>
          </thead>
          <tbody>
            {rows.length ? rows.slice(0, 8).map((row, index) => (
              <tr key={`${title}-${index}`} className="border-t">
                {columns.map((column) => {
                  const value = row[column];
                  const isCurrency = ["amount", "wonRevenue", "lostAmount", "pipelineAmount", "weightedAmount", "committedAmount", "bestCaseAmount", "upsideAmount", "closedWonAmount", "invoicedAmount", "collectedAmount", "targetAmount", "achievedAmount"].includes(column);
                  const isRate = column.toLowerCase().includes("rate");
                  return <td key={column} className="px-3 py-2">{isCurrency ? formatCurrency(Number(value || 0)) : isRate ? `${Number(value || 0).toFixed(1)}%` : String(value ?? "-")}</td>;
                })}
              </tr>
            )) : (
              <tr><td className="px-3 py-4 text-sm text-muted-foreground" colSpan={columns.length}>No report rows for the selected filters.</td></tr>
            )}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function LeadToCashPage() {
  const leadState = useCrmRecords<CRMRecord>("leads", emptyRecords);
  const companyState = useCrmRecords<CRMRecord>("companies", emptyRecords);
  const dealState = useCrmRecords<CRMRecord>("deals", emptyRecords);
  const quoteState = useCrmRecords<CRMRecord>("quotations", emptyRecords);
  const crmLeads = useMemo(() => leadState.data.map(recordToLead), [leadState.data]);
  const crmDeals = useMemo(() => dealState.data.map((record) => recordToDeal(record, emptyRecords)), [dealState.data]);
  const crmCompanies = companyState.data;
  const crmQuotations = quoteState.data;
  const flow = [
    ["Lead", "Qualified", `${crmLeads.filter((lead) => lead.status === "Qualified").length} qualified leads`, "/crm/leads"],
    ["Contact", "Created", `${crmLeads.filter((lead) => lead.status === "Converted").length} converted contacts`, "/crm/contacts"],
    ["Company", "Linked", `${crmCompanies.length} accounts`, "/crm/companies"],
    ["Deal", "Open", `${crmDeals.filter((deal) => !["Won", "Lost"].includes(deal.stage)).length} active deals`, "/crm/deals"],
    ["Quotation", "Sent", `${crmQuotations.filter((quote) => quote.status === "Sent").length} sent quotes`, "/crm/quotations"],
    ["Order/Invoice", "Handoff", "Ready for finance handoff", "/crm/lead-to-cash"],
  ];
  const handoffRows = [
    ...crmQuotations.filter((quote) => ["Accepted", "Approved", "Sent"].includes(String(quote.status))).slice(0, 3).map((quote) => ({
      item: String(quote.quote || quote.quote_number || `Quote #${quote.id}`),
      customer: String(quote.companyId || quote.company_id || "Linked account"),
      amount: Number(quote.total || quote.total_amount || 0),
      status: String(quote.status || "Draft"),
      next: String(quote.status) === "Accepted" ? "Create order and invoice draft" : "Follow up quotation approval or customer confirmation",
    })),
    ...crmDeals.filter((deal) => deal.stage === "Won").slice(0, 2).map((deal) => ({
      item: deal.name,
      customer: deal.company || "Linked account",
      amount: deal.amount,
      status: "Won",
      next: "Send order confirmation",
    })),
  ].slice(0, 5);

  return (
    <div className="space-y-6">
      <PageHeader title="Lead-to-Cash" description="Convert leads into contacts, companies, deals, quotations, and order/invoice handoff without leaving CRM." action="Convert lead" />
      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
        {flow.map(([label, status, detail, path], index) => (
          <Card key={label}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between gap-2">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">{index + 1}</div>
                <Badge variant="outline">{status}</Badge>
              </div>
              <p className="mt-3 font-semibold">{label}</p>
              <p className="mt-1 text-sm text-muted-foreground">{detail}</p>
              <a className="mt-3 inline-flex text-xs font-medium text-primary" href={path}>Open stage</a>
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_22rem]">
        <Card>
          <CardHeader><CardTitle>Conversion Workbench</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {crmLeads.slice(0, 5).map((lead) => (
              <div key={lead.id} className="grid gap-3 rounded-lg border p-4 md:grid-cols-[1fr_9rem_9rem_auto] md:items-center">
                <div><p className="font-medium">{lead.name}</p><p className="text-sm text-muted-foreground">{lead.company} / {lead.source}</p></div>
                <Badge className={statusColor(lead.rating)}>{lead.rating}</Badge>
                <span className="text-sm font-medium">{formatCurrency(lead.value)}</span>
                <Button size="sm">Convert</Button>
              </div>
            ))}
            {!crmLeads.length ? <p className="rounded-md border border-dashed py-8 text-center text-sm text-muted-foreground">No leads available for conversion.</p> : null}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Invoice Handoff Queue</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {handoffRows.map((row) => (
              <div key={row.item} className="rounded-lg border p-3">
                <div className="flex items-start justify-between gap-3">
                  <div><p className="font-medium">{row.item}</p><p className="text-sm text-muted-foreground">{row.customer}</p></div>
                  <Badge>{row.status}</Badge>
                </div>
                <p className="mt-2 text-sm font-semibold">{formatCurrency(row.amount)}</p>
                <p className="mt-1 text-xs text-muted-foreground">{row.next}</p>
              </div>
            ))}
            {!handoffRows.length ? <p className="rounded-md border border-dashed py-8 text-center text-sm text-muted-foreground">No quotes or won deals are ready for handoff.</p> : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function SalesAutomationPage() {
  const automationCards: AutomationCard[] = [
    ["Reminders", "18 active", "Follow-up reminders from leads, deals, quotations, and tickets.", Bell],
    ["SLA follow-ups", "4 at risk", "Escalate customer replies and support-linked sales tasks before breach.", Clock],
    ["Stale deal alerts", "3 stale", "Detect opportunities without activity or next step updates.", AlertTriangle],
    ["Auto-assignment", "Round robin", "Route website, campaign, and partner leads to available owners.", Users],
    ["Email sequences", "6 live", "Drip campaigns for nurture, proposal follow-up, and renewal.", Mail],
    ["WhatsApp sequences", "5 live", "Message templates for demo reminders and quote expiry nudges.", Phone],
  ];
  const rules = [
    { rule: "Qualified lead follow-up", trigger: "Status = Qualified", action: "Create task + WhatsApp reminder", owner: "Sales Ops" },
    { rule: "Stale negotiation", trigger: "No activity for 5 days", action: "Alert owner and manager", owner: "Sales Manager" },
    { rule: "Quote expiry", trigger: "Expiry in 2 days", action: "Email sequence + task", owner: "Revenue Ops" },
    { rule: "Critical customer ticket", trigger: "Priority = Critical", action: "Pause renewal ask and notify owner", owner: "Support Lead" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Sales Automation" description="Reminders, SLA follow-ups, stale deal alerts, auto-assignment, email sequences, and WhatsApp sequences." action="Create rule" />
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {automationCards.map(([title, value, detail, Icon]) => (
          <Card key={String(title)}>
            <CardContent className="flex gap-3 p-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"><Icon className="h-5 w-5" /></div>
              <div><p className="font-semibold">{title}</p><p className="text-2xl font-semibold">{value}</p><p className="text-sm text-muted-foreground">{detail}</p></div>
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader><CardTitle>Automation Rules</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {rules.map((row) => (
            <div key={row.rule} className="grid gap-3 rounded-lg border p-4 md:grid-cols-[1fr_13rem_15rem_9rem] md:items-center">
              <p className="font-medium">{row.rule}</p>
              <span className="text-sm text-muted-foreground">{row.trigger}</span>
              <span className="text-sm">{row.action}</span>
              <Badge variant="outline">{row.owner}</Badge>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function ForecastingPage() {
  const [forecast, setForecast] = useState<{ summary: CRMApiRecord; items: CRMApiRecord[] } | null>(null);
  const [teamRows, setTeamRows] = useState<CRMApiRecord[]>([]);
  const [territoryRows, setTerritoryRows] = useState<CRMApiRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = () => {
    setLoading(true);
    setError(null);
    Promise.all([crmApi.forecast(), crmApi.forecastByTeam(), crmApi.forecastByTerritory()])
      .then(([main, byTeam, byTerritory]) => {
        setForecast({ summary: main.data.summary || {}, items: main.data.items || [] });
        setTeamRows(byTeam.data.items || []);
        setTerritoryRows(byTerritory.data.items || []);
      })
      .catch((err) => setError(err?.response?.data?.detail || "Forecast data could not be loaded."))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);
  const summary = forecast?.summary || {};
  const scenarios = (summary.scenarios as CRMApiRecord) || {};
  const snapshot = () => {
    crmApi.createForecastSnapshot({ snapshotName: "Manual CRM forecast snapshot" }).then(load).catch((err) => setError(err?.response?.data?.detail || "Forecast snapshot could not be created."));
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Forecasting" description="Weighted forecast by owner, team, territory, pipeline, expected close date, and SRM invoice/collection actuals." action="Snapshot forecast" onAction={snapshot} />
      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div> : null}
      <div className="grid gap-3 md:grid-cols-4 xl:grid-cols-7">
        <Metric icon={IndianRupee} label="Total pipeline" value={formatCurrency(Number(summary.pipelineAmount || 0))} tone="blue" />
        <Metric icon={Target} label="Weighted forecast" value={formatCurrency(Number(summary.weightedAmount || 0))} tone="emerald" />
        <Metric icon={CheckCircle2} label="Committed" value={formatCurrency(Number(summary.committedAmount || 0))} tone="violet" />
        <Metric icon={Sparkles} label="Best case" value={formatCurrency(Number(summary.bestCaseAmount || 0))} tone="blue" />
        <Metric icon={AlertTriangle} label="Upside" value={formatCurrency(Number(summary.upsideAmount || 0))} tone="red" />
        <Metric icon={FileCheck2} label="Invoiced" value={formatCurrency(Number(summary.invoicedAmount || 0))} tone="emerald" />
        <Metric icon={IndianRupee} label="Collected" value={formatCurrency(Number(summary.collectedAmount || 0))} tone="violet" />
      </div>
      <Card>
        <CardHeader><CardTitle>Scenario Forecast</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3">
          {["conservative", "expected", "aggressive"].map((scenario) => (
            <div key={scenario} className="rounded-lg border p-4">
              <p className="text-sm text-muted-foreground">{labelFor(scenario)}</p>
              <p className="mt-2 text-2xl font-semibold">{formatCurrency(Number(scenarios[scenario] || 0))}</p>
              <Badge className="mt-3" variant="outline">{scenario === "expected" ? "Weighted model" : "Scenario"}</Badge>
            </div>
          ))}
        </CardContent>
      </Card>
      {loading ? <p className="text-sm text-muted-foreground">Loading forecast...</p> : null}
      <div className="grid gap-4 xl:grid-cols-3">
        <ReportTable title="Forecast by Owner" rows={forecast?.items || []} columns={["label", "dealCount", "pipelineAmount", "weightedAmount", "committedAmount", "invoicedAmount", "collectedAmount"]} />
        <ReportTable title="Forecast by Team" rows={teamRows} columns={["label", "dealCount", "pipelineAmount", "weightedAmount", "committedAmount"]} />
        <ReportTable title="Forecast by Territory" rows={territoryRows} columns={["label", "dealCount", "pipelineAmount", "weightedAmount", "committedAmount"]} />
      </div>
    </div>
  );
}

function SalesTargetsPage() {
  const [targets, setTargets] = useState<CRMApiRecord[]>([]);
  const [performance, setPerformance] = useState<CRMApiRecord[]>([]);
  const [draft, setDraft] = useState<CRMApiRecord>({ periodType: "monthly", periodStart: "2026-06-01", periodEnd: "2026-06-30", targetOwnerType: "user", targetOwnerId: 100, targetAmount: 1000000, currency: "INR" });
  const [error, setError] = useState<string | null>(null);
  const load = () => {
    Promise.all([crmApi.targets(), crmApi.targetPerformance()])
      .then(([targetRows, performanceRows]) => {
        setTargets(targetRows.data.items || []);
        setPerformance(performanceRows.data.items || []);
      })
      .catch((err) => setError(err?.response?.data?.detail || "Targets could not be loaded."));
  };
  useEffect(load, []);
  const create = () => crmApi.createTarget(draft).then(load).catch((err) => setError(err?.response?.data?.detail || "Target could not be created."));
  const patchDraft = (key: string, value: CRMApiRecord[string]) => setDraft((current) => ({ ...current, [key]: value }));
  return (
    <div className="space-y-6">
      <PageHeader title="Sales Targets" description="Create monthly, quarterly, or yearly quotas and compare achieved, invoiced, and collected amounts." action="Create target" onAction={create} />
      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div> : null}
      <Card>
        <CardContent className="grid gap-3 p-4 md:grid-cols-3 xl:grid-cols-[8rem_9rem_9rem_10rem_8rem_10rem_6rem] xl:items-end">
          <Field label="Period"><select className="h-10 rounded-md border bg-background px-3 text-sm" value={String(draft.periodType)} onChange={(event) => patchDraft("periodType", event.target.value)}>{["monthly", "quarterly", "yearly"].map((item) => <option key={item} value={item}>{labelFor(item)}</option>)}</select></Field>
          <Field label="Start"><Input type="date" value={String(draft.periodStart || "")} onChange={(event) => patchDraft("periodStart", event.target.value)} /></Field>
          <Field label="End"><Input type="date" value={String(draft.periodEnd || "")} onChange={(event) => patchDraft("periodEnd", event.target.value)} /></Field>
          <Field label="Owner type"><select className="h-10 rounded-md border bg-background px-3 text-sm" value={String(draft.targetOwnerType)} onChange={(event) => patchDraft("targetOwnerType", event.target.value)}>{["user", "team", "territory", "company"].map((item) => <option key={item} value={item}>{labelFor(item)}</option>)}</select></Field>
          <Field label="Owner ID"><Input type="number" value={Number(draft.targetOwnerId || 0)} onChange={(event) => patchDraft("targetOwnerId", Number(event.target.value))} /></Field>
          <Field label="Target"><Input type="number" value={Number(draft.targetAmount || 0)} onChange={(event) => patchDraft("targetAmount", Number(event.target.value))} /></Field>
          <Button onClick={create}>Save</Button>
        </CardContent>
      </Card>
      <div className="grid gap-4 xl:grid-cols-2">
        <ReportTable title="Targets" rows={targets} columns={["periodType", "periodStart", "periodEnd", "targetOwnerType", "targetOwnerId", "targetAmount", "currency"]} />
        <ReportTable title="Target Performance" rows={performance} columns={["targetOwnerType", "targetOwnerId", "targetAmount", "achievedAmount", "achievementPercent", "invoicedAmount", "collectionPercent"]} />
      </div>
    </div>
  );
}

function SalesPerformancePage() {
  const [rows, setRows] = useState<CRMApiRecord[]>([]);
  const [summary, setSummary] = useState<CRMApiRecord>({});
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    crmApi.salesPerformance().then((response) => {
      setRows(response.data.items || []);
      setSummary(response.data.summary || {});
    }).catch((err) => setError(err?.response?.data?.detail || "Sales performance could not be loaded."));
  }, []);
  return (
    <div className="space-y-6">
      <PageHeader title="Sales Performance" description="Owner-level pipeline, weighted forecast, activity, conversion, SRM invoice, and collection performance." action="Refresh" onAction={() => window.location.reload()} />
      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div> : null}
      <div className="grid gap-3 md:grid-cols-4">
        <Metric icon={IndianRupee} label="Pipeline" value={formatCurrency(Number(summary.pipelineAmount || 0))} tone="blue" />
        <Metric icon={Target} label="Weighted" value={formatCurrency(Number(summary.weightedAmount || 0))} tone="emerald" />
        <Metric icon={CheckCircle2} label="Closed won" value={formatCurrency(Number(summary.closedWonAmount || 0))} tone="violet" />
        <Metric icon={FileCheck2} label="Collected" value={formatCurrency(Number(summary.collectedAmount || 0))} tone="emerald" />
      </div>
      <ReportTable title="Sales Performance by Owner" rows={rows} columns={["owner", "dealCount", "wonDeals", "lostDeals", "activityCount", "conversionRate", "weightedAmount", "invoicedAmount", "collectedAmount"]} />
    </div>
  );
}

function FunnelAnalyticsPage() {
  const [rows, setRows] = useState<CRMApiRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    crmApi.funnel().then((response) => setRows(response.data.items || [])).catch((err) => setError(err?.response?.data?.detail || "Funnel could not be loaded."));
  }, []);
  return (
    <div className="space-y-6">
      <PageHeader title="Sales Funnel" description="Lead-to-cash funnel from lead qualification through SRM sales orders, invoice generation, and receipt collection." action="Export funnel" />
      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div> : null}
      <Card>
        <CardHeader><CardTitle>Lead-to-Cash Conversion</CardTitle></CardHeader>
        <CardContent className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} layout="vertical" margin={{ left: 28 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis type="category" dataKey="stage" width={140} />
              <Tooltip formatter={(value, name) => name === "amount" ? formatCurrency(Number(value)) : value} />
              <Bar dataKey="count" fill="#2563eb" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
      <ReportTable title="Funnel Details" rows={rows} columns={["stage", "count", "amount", "conversionRate", "stageToStageRate"]} />
    </div>
  );
}

function LostAnalysisPage() {
  const [report, setReport] = useState<CRMApiRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    crmApi.lostAnalysis().then((response) => setReport(response.data)).catch((err) => setError(err?.response?.data?.detail || "Lost analysis could not be loaded."));
  }, []);
  const summary = (report?.summary as CRMApiRecord) || {};
  return (
    <div className="space-y-6">
      <PageHeader title="Lost Analysis" description="Lost reasons, competitors, lost amount, owner trends, and AI pattern-detection readiness." action="Review lost deals" />
      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div> : null}
      <div className="grid gap-3 md:grid-cols-3">
        <Metric icon={AlertTriangle} label="Lost deals" value={String(summary.lostDeals || 0)} tone="red" />
        <Metric icon={IndianRupee} label="Lost amount" value={formatCurrency(Number(summary.lostAmount || 0))} tone="red" />
        <Metric icon={Sparkles} label="AI pattern detection" value="Placeholder" tone="violet" />
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <ReportTable title="Lost Reasons" rows={(report?.lostReasonBreakdown as CRMApiRecord[]) || []} columns={["reason", "count", "amount"]} />
        <ReportTable title="Top Competitors" rows={(report?.topCompetitors as CRMApiRecord[]) || []} columns={["competitor", "count"]} />
        <ReportTable title="Owner Trends" rows={(report?.ownerTrends as CRMApiRecord[]) || []} columns={["key", "lost", "lostAmount", "winRate"]} />
      </div>
      <ReportTable title="Lost Deals" rows={(report?.deals as CRMApiRecord[]) || []} columns={["name", "status", "lostReason", "amount", "ownerId"]} />
    </div>
  );
}

function Customer360Page() {
  const companyState = useCrmRecords<CRMRecord>("companies", emptyRecords);
  const customers = companyState.data.map((company) => customer360For(String(company.name)));
  return (
    <div className="space-y-6">
      <PageHeader title="Customer 360" description="Contacts, companies, deals, tickets, activities, quotations, files, and campaigns in one customer view." action="Open customer" />
      <div className="grid gap-4 xl:grid-cols-2">
        {customers.map((customer) => (
          <Card key={customer.company}>
            <CardHeader className="flex-row items-start justify-between">
              <div><CardTitle>{customer.company}</CardTitle><p className="text-sm text-muted-foreground">{customer.industry}</p></div>
              <Badge>{customer.status}</Badge>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-3">
              {customer.metrics.map(([label, value]) => (
                <div key={label} className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="text-lg font-semibold">{value}</p></div>
              ))}
              <div className="md:col-span-3 rounded-lg border bg-muted/30 p-3 text-sm">
                <p className="font-medium">Timeline</p>
                <div className="mt-2 space-y-2">
                  {customer.timeline.map((item) => <TimelineItem key={item} text={item} />)}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function ImportExportPage() {
  const imports = [
    { file: "crm-contacts-may.csv", rows: 428, duplicates: 12, valid: 409, status: "Preview ready" },
    { file: "partner-leads.xlsx", rows: 96, duplicates: 4, valid: 88, status: "Imported" },
    { file: "company-cleanup.csv", rows: 74, duplicates: 9, valid: 61, status: "Rolled back" },
  ];
  const mapping = [
    ["Full Name", "name", "Required"],
    ["Email Address", "email", "Duplicate key"],
    ["Mobile", "phone", "Normalize"],
    ["Company", "company", "Create if missing"],
    ["Owner Email", "owner", "Assign user"],
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Import & Export Engine" description="Field mapping, duplicate detection, validation preview, rollback, and import history for CRM data." action="Upload import" />
      <div className="grid gap-3 md:grid-cols-5">
        <Metric icon={Upload} label="Imports" value={imports.length} tone="blue" />
        <Metric icon={FileCheck2} label="Valid rows" value={imports.reduce((sum, row) => sum + row.valid, 0)} tone="emerald" />
        <Metric icon={AlertTriangle} label="Duplicates" value={imports.reduce((sum, row) => sum + row.duplicates, 0)} tone="amber" />
        <Metric icon={Download} label="Exports" value="12" tone="violet" />
        <Metric icon={Clock} label="Rollback window" value="24h" tone="red" />
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_24rem]">
        <Card>
          <CardHeader><CardTitle>Import History</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {imports.map((row) => (
              <div key={row.file} className="grid gap-3 rounded-lg border p-4 md:grid-cols-[1fr_7rem_7rem_7rem_auto] md:items-center">
                <p className="font-medium">{row.file}</p>
                <span className="text-sm">{row.rows} rows</span>
                <span className="text-sm text-amber-700">{row.duplicates} dupes</span>
                <span className="text-sm text-emerald-700">{row.valid} valid</span>
                <Button variant="outline" size="sm">{row.status === "Imported" ? "Rollback" : "Open"}</Button>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Field Mapping Preview</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {mapping.map(([source, target, rule]) => (
              <div key={source} className="rounded-lg border p-3 text-sm">
                <div className="flex items-center justify-between gap-2"><span className="font-medium">{source}</span><span>{target}</span></div>
                <p className="mt-1 text-xs text-muted-foreground">{rule}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Toolbar({
  search,
  onSearch,
  selectedView,
  onViewChange,
  onToggleFilters,
  contacts,
  onImportContacts,
  onExportServer,
  importLabel = "Import Contacts",
  exportLabel = "Export Contacts",
}: {
  search: string;
  onSearch: (value: string) => void;
  selectedView?: string;
  onViewChange?: (value: string) => void;
  onToggleFilters?: () => void;
  contacts?: CRMRecord[];
  onImportContacts?: (rows: CRMRecord[]) => void;
  onExportServer?: () => void;
  importLabel?: string;
  exportLabel?: string;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const handleImport = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !onImportContacts) return;
    file.text().then((text) => {
      const imported = parseCsv(text);
      if (imported.length) onImportContacts(imported);
    });
    event.target.value = "";
  };

  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-card p-3 xl:flex-row xl:items-center">
      <div className="flex min-w-0 flex-1 items-center gap-2 rounded-md border px-3 py-2">
        <Search className="h-4 w-4 text-muted-foreground" />
        <Input value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Search records, owners, companies..." className="border-0 p-0 shadow-none focus-visible:ring-0" />
      </div>
      {selectedView && onViewChange ? (
        <div className="flex flex-wrap gap-2">
          {savedViews.map((view) => (
            <Button key={view} type="button" size="sm" variant={selectedView === view ? "default" : "outline"} onClick={() => onViewChange(view)}>
              {view}
            </Button>
          ))}
        </div>
      ) : null}
      <Button variant="outline" onClick={onToggleFilters}><Filter className="h-4 w-4" />Filters</Button>
      <Button variant="outline" onClick={onExportServer || (() => exportRows("crm-contacts.csv", contacts || []))}><Download className="h-4 w-4" />{exportLabel}</Button>
      <input ref={inputRef} type="file" accept=".csv,text/csv" className="hidden" onChange={handleImport} />
      <Button variant="outline" onClick={() => inputRef.current?.click()}><Upload className="h-4 w-4" />{importLabel}</Button>
    </div>
  );
}

function FilterPanel({
  filters,
  onChange,
  owners,
  statuses,
  types,
  territories,
  onClear,
}: {
  filters: CRMFilters;
  onChange: (filters: CRMFilters) => void;
  owners: string[];
  statuses: string[];
  types: string[];
  territories: string[];
  onClear: () => void;
}) {
  const patch = (update: Partial<CRMFilters>) => onChange({ ...filters, ...update });
  return (
    <Card>
      <CardContent className="grid gap-3 p-4 md:grid-cols-[1fr_1fr_1fr_1fr_auto] md:items-end">
        <Field label="Owner">
          <select className="h-10 rounded-md border bg-background px-3 text-sm" value={filters.owner} onChange={(event) => patch({ owner: event.target.value })}>
            <option value="all">All owners</option>
            {owners.map((owner) => <option key={owner} value={owner}>{owner}</option>)}
          </select>
        </Field>
        <Field label="Status">
          <select className="h-10 rounded-md border bg-background px-3 text-sm" value={filters.status} onChange={(event) => patch({ status: event.target.value })}>
            <option value="all">All statuses</option>
            {statuses.map((status) => <option key={status} value={status}>{status}</option>)}
          </select>
        </Field>
        <Field label="Type">
          <select className="h-10 rounded-md border bg-background px-3 text-sm" value={filters.type} onChange={(event) => patch({ type: event.target.value })}>
            <option value="all">All types</option>
            {types.map((type) => <option key={type} value={type}>{type}</option>)}
          </select>
        </Field>
        <Field label="Territory">
          <select className="h-10 rounded-md border bg-background px-3 text-sm" value={filters.territory} onChange={(event) => patch({ territory: event.target.value })}>
            <option value="all">All territories</option>
            {territories.map((territory) => <option key={territory} value={territory}>Territory {territory}</option>)}
          </select>
        </Field>
        <Button variant="outline" onClick={onClear}>Clear</Button>
      </CardContent>
    </Card>
  );
}

const preferredGridColumns: Partial<Record<CRMPageKind, string[]>> = {
  leads: ["leadId", "name", "company", "status", "rating", "leadScore", "owner", "nextFollowUp"],
  contacts: ["contactId", "name", "company", "email", "phone", "status", "owner", "nextFollowUp"],
  companies: ["name", "industry", "accountType", "status", "owner", "revenue", "nextFollowUp"],
  deals: ["name", "company", "stage", "amount", "probability", "owner", "closeDate", "nextStep"],
  activities: ["subject", "type", "status", "priority", "owner", "nextFollowUp"],
  tasks: ["name", "subject", "status", "priority", "owner", "nextFollowUp"],
  campaigns: ["name", "type", "status", "budget", "expectedRevenue", "owner", "startDate"],
  products: ["name", "sku", "category", "price", "status", "owner"],
  services: ["serviceCode", "name", "category", "billingType", "price", "status"],
  priceBooks: ["name", "currency", "region", "segment", "status"],
  quotations: ["quote", "name", "company", "status", "total", "issueDate", "expiryDate"],
  quotes: ["quote", "name", "company", "status", "total", "issueDate", "expiryDate"],
  tickets: ["number", "subject", "priority", "status", "company", "owner", "nextFollowUp"],
  files: ["fileName", "name", "type", "size", "visibility", "owner"],
  admin: ["adminArea", "name", "email", "permission", "status"],
};

function SmartCRMTable({ rows, title, kind, onSelect, onOpen, onInlineSave, onBulkDelete, loading, error }: { rows: CRMRecord[]; title: string; kind: CRMPageKind; onSelect: (row: CRMRecord) => void; onOpen?: (row: CRMRecord) => void; onInlineSave?: (row: CRMRecord, key: string, value: string | number | boolean | null) => Promise<unknown>; onBulkDelete?: (rows: CRMRecord[]) => Promise<unknown>; loading?: boolean; error?: string | null }) {
  const [sort, setSort] = useState<SortState>(null);
  const [columnOrder, setColumnOrder] = useState<string[]>([]);
  const [widths, setWidths] = useState<Record<string, number>>({});
  const [selectedIds, setSelectedIds] = useState<Record<string, boolean>>({});
  const [bulkError, setBulkError] = useState<string | null>(null);
  const [bulkSaving, setBulkSaving] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const columns = useMemo(() => {
    const keys = Array.from(rows.reduce((set, row) => {
      Object.keys(row).forEach((key) => set.add(key));
      return set;
    }, new Set<string>()));
    const known = columnOrder.filter((key) => keys.includes(key));
    const fresh = keys.filter((key) => !known.includes(key));
    return [...known, ...fresh];
  }, [rows, columnOrder]);
  const visibleRows = useMemo(() => {
    if (!sort) return rows;
    return [...rows].sort((a, b) => compareValues(a[sort.key], b[sort.key], sort.direction));
  }, [rows, sort]);
  const pageCount = Math.max(1, Math.ceil(visibleRows.length / pageSize));
  const pagedRows = useMemo(() => visibleRows.slice((page - 1) * pageSize, page * pageSize), [visibleRows, page, pageSize]);
  const visibleColumns = useMemo(() => {
    const preferred = preferredGridColumns[kind] || [];
    const ordered = [...preferred.filter((key) => columns.includes(key)), ...columns.filter((key) => !preferred.includes(key))];
    return ordered.slice(0, 8);
  }, [columns, kind]);
  const selectableRows = pagedRows.filter((row) => row.id !== undefined && row.id !== null);
  const selectedRows = selectableRows.filter((row) => selectedIds[String(row.id)]);
  const allSelected = Boolean(selectableRows.length) && selectedRows.length === selectableRows.length;

  useEffect(() => {
    setSelectedIds((current) => {
      const visibleIds = new Set(selectableRows.map((row) => String(row.id)));
      return Object.fromEntries(Object.entries(current).filter(([id]) => visibleIds.has(id)));
    });
  }, [pagedRows]);

  useEffect(() => {
    setPage((current) => Math.min(current, pageCount));
  }, [pageCount]);

  useEffect(() => {
    setPage(1);
  }, [rows, pageSize, sort]);

  const toggleSort = (key: string) => {
    setSort((current) => {
      if (current?.key !== key) return { key, direction: "asc" };
      if (current.direction === "asc") return { key, direction: "desc" };
      return null;
    });
  };
  const moveColumn = (key: string, direction: -1 | 1) => {
    const current = columns;
    const index = current.indexOf(key);
    const target = index + direction;
    if (target < 0 || target >= current.length) return;
    const next = [...current];
    [next[index], next[target]] = [next[target], next[index]];
    setColumnOrder(next);
  };
  const startResize = (key: string, event: React.MouseEvent) => {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = widths[key] || 160;
    const onMove = (moveEvent: MouseEvent) => {
      setWidths((current) => ({ ...current, [key]: Math.max(96, startWidth + moveEvent.clientX - startX) }));
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };
  const toggleAllRows = (checked: boolean) => {
    setSelectedIds(checked ? Object.fromEntries(selectableRows.map((row) => [String(row.id), true])) : {});
  };
  const toggleRow = (row: CRMRecord, checked: boolean) => {
    setSelectedIds((current) => ({ ...current, [String(row.id)]: checked }));
  };
  const bulkDelete = () => {
    if (!onBulkDelete || !selectedRows.length) return;
    if (!window.confirm(`Delete ${selectedRows.length} selected ${title.toLowerCase()} record${selectedRows.length === 1 ? "" : "s"}?`)) return;
    setBulkSaving(true);
    setBulkError(null);
    onBulkDelete(selectedRows)
      .then(() => setSelectedIds({}))
      .catch((err) => setBulkError(err?.response?.data?.detail || err?.message || "Selected records could not be deleted."))
      .finally(() => setBulkSaving(false));
  };

  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
        <div>
          <CardTitle className="text-base">{title} Grid</CardTitle>
          {selectedRows.length ? <p className="text-sm text-muted-foreground">{selectedRows.length} selected</p> : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {columns.length > visibleColumns.length ? <Badge variant="outline" className="h-8 rounded-md px-2.5">Showing {visibleColumns.length} of {columns.length} fields</Badge> : null}
          {onBulkDelete && selectedRows.length ? <Button variant="outline" size="sm" onClick={bulkDelete} disabled={bulkSaving}>{bulkSaving ? "Deleting..." : "Delete selected"}</Button> : null}
          <Button variant="outline" size="sm" onClick={() => exportRows(`${title.toLowerCase().replace(/\s+/g, "-")}.csv`, visibleRows)}>
            <Download className="h-4 w-4" />Export Grid
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {error ? <div className="border-t bg-amber-50 px-4 py-2 text-sm text-amber-800">{error}</div> : null}
        {bulkError ? <div className="border-t bg-red-50 px-4 py-2 text-sm text-red-700">{bulkError}</div> : null}
        <div className="max-w-full overflow-x-auto">
          <table className="crm-desktop-table">
            <thead className="sticky top-0 bg-muted/70 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="w-10 px-3 py-3">
                  <input type="checkbox" checked={allSelected} disabled={!selectableRows.length} onChange={(event) => toggleAllRows(event.target.checked)} aria-label={`Select all ${title}`} />
                </th>
                {visibleColumns.map((key) => (
                  <th key={key} style={{ width: widths[key] || undefined }} className="relative px-3 py-3 font-medium">
                    <div className="flex items-center gap-1">
                      <button className="flex min-w-0 items-center gap-1 truncate" onClick={() => toggleSort(key)}>
                        <span className="truncate">{key.replace(/([A-Z])/g, " $1")}</span>
                        <ArrowUpDown className="h-3 w-3 shrink-0" />
                      </button>
                      <button className="rounded p-0.5 hover:bg-background" onClick={() => moveColumn(key, -1)} aria-label={`Move ${key} left`}><ChevronLeft className="h-3 w-3" /></button>
                      <button className="rounded p-0.5 hover:bg-background" onClick={() => moveColumn(key, 1)} aria-label={`Move ${key} right`}><ChevronRight className="h-3 w-3" /></button>
                    </div>
                    <button className="absolute right-0 top-0 h-full w-1 cursor-col-resize bg-border/60 opacity-0 hover:opacity-100" onMouseDown={(event) => startResize(key, event)} aria-label={`Resize ${key}`} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td className="px-4 py-12 text-center text-muted-foreground" colSpan={Math.max(visibleColumns.length + 1, 1)}>Loading CRM records...</td></tr>
              ) : null}
              {!loading && pagedRows.map((row, index) => (
                <tr key={index} className="border-t hover:bg-muted/35">
                  <td className="px-3 py-3">
                    <input type="checkbox" checked={Boolean(selectedIds[String(row.id)])} disabled={row.id === undefined || row.id === null} onChange={(event) => toggleRow(row, event.target.checked)} aria-label={`Select record ${String(row.id || index + 1)}`} />
                  </td>
                  {visibleColumns.map((key) => (
                    <td key={key} style={{ width: widths[key] || undefined }} className="px-3 py-3">
                      <InlineTableCell row={row} fieldKey={key} kind={kind} value={row[key]} onSelect={onSelect} onOpen={onOpen} onSave={onInlineSave} />
                    </td>
                  ))}
                </tr>
              ))}
              {!loading && !visibleRows.length ? (
                <tr><td className="px-4 py-12 text-center text-muted-foreground" colSpan={Math.max(visibleColumns.length + 1, 1)}>No CRM records found</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
        <div className="flex flex-col gap-3 border-t px-4 py-3 text-sm md:flex-row md:items-center md:justify-between">
          <span className="text-muted-foreground">
            Showing {visibleRows.length ? (page - 1) * pageSize + 1 : 0}-{Math.min(page * pageSize, visibleRows.length)} of {visibleRows.length}
          </span>
          <div className="flex flex-wrap items-center gap-2">
            <select className="h-9 rounded-md border bg-background px-2" value={pageSize} onChange={(event) => setPageSize(Number(event.target.value))} aria-label="Rows per page">
              {[10, 25, 50, 100].map((size) => <option key={size} value={size}>{size} rows</option>)}
            </select>
            <Button variant="outline" size="sm" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page <= 1}>Previous</Button>
            <Badge variant="outline" className="h-9 rounded-md px-3">Page {page} / {pageCount}</Badge>
            <Button variant="outline" size="sm" onClick={() => setPage((current) => Math.min(pageCount, current + 1))} disabled={page >= pageCount}>Next</Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function InlineTableCell({ row, fieldKey, kind, value, onSelect, onOpen, onSave }: { row: CRMRecord; fieldKey: string; kind: CRMPageKind; value: CRMApiValue; onSelect: (row: CRMRecord) => void; onOpen?: (row: CRMRecord) => void; onSave?: (row: CRMRecord, key: string, value: string | number | boolean | null) => Promise<unknown> }) {
  const config = listInlineEditConfig[kind]?.[fieldKey];
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(valueText(value));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setDraft(valueText(value)), [value]);
  const commit = () => {
    if (!config || !onSave || draft === valueText(value)) {
      setEditing(false);
      return;
    }
    setSaving(true);
    setError(null);
    onSave(row, fieldKey, draft)
      .then(() => setEditing(false))
      .catch((err) => {
        setDraft(valueText(value));
        setError(err?.message || "Could not save.");
      })
      .finally(() => setSaving(false));
  };
  const cancel = () => {
    setDraft(valueText(value));
    setError(null);
    setEditing(false);
  };
  if (editing && config) {
    return (
      <div className="space-y-1" onClick={(event) => event.stopPropagation()}>
        <InlineEditor config={config} value={draft} autoFocus onChange={setDraft} onCommit={commit} onCancel={cancel} />
        <div className="flex items-center gap-2 text-xs">
          {saving ? <span className="text-muted-foreground">Saving...</span> : null}
          {error ? <span className="text-destructive">{error}</span> : null}
        </div>
      </div>
    );
  }
  return (
    <button type="button" className="group flex w-full items-center justify-between gap-2 truncate text-left" onClick={() => onSelect(row)} onDoubleClick={() => onOpen?.(row)}>
      <span className="truncate">{renderCell(fieldKey, value)}</span>
      {config ? <span className="shrink-0 rounded p-0.5 text-muted-foreground opacity-0 group-hover:opacity-100" onClick={(event) => { event.stopPropagation(); setEditing(true); }}><Edit3 className="h-3.5 w-3.5" /></span> : null}
    </button>
  );
}

function InlineEditor({ config, value, autoFocus, onChange, onCommit, onCancel }: { config: InlineEditConfig; value: string; autoFocus?: boolean; onChange: (value: string) => void; onCommit: () => void; onCancel: () => void }) {
  const common = {
    value,
    autoFocus,
    onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => onChange(event.target.value),
    onKeyDown: (event: React.KeyboardEvent<HTMLInputElement | HTMLSelectElement>) => {
      if (event.key === "Enter") onCommit();
      if (event.key === "Escape") onCancel();
    },
    onBlur: onCommit,
  };
  if (config.type === "select") {
    return (
      <select className="h-9 w-full rounded-md border bg-background px-2 text-sm" {...common}>
        {(config.options || []).map((option) => <option key={option} value={option}>{option}</option>)}
      </select>
    );
  }
  return <Input className="h-9" type={config.type === "number" ? "number" : config.type === "date" ? "date" : "text"} {...common} />;
}

function PageHeader({ title, description, action, onAction }: { title: string; description: string; action?: string; onAction?: () => void }) {
  return (
    <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div>
        <h1 className="page-title">{title}</h1>
        <p className="page-description">{description}</p>
      </div>
      {action ? <Button onClick={onAction}><Plus className="h-4 w-4" />{action}</Button> : null}
    </div>
  );
}

function Metric({ icon: Icon, label, value, tone }: { icon: React.ElementType; label: string; value: string | number; tone: "blue" | "emerald" | "violet" | "amber" | "red" }) {
  const tones = {
    blue: "bg-blue-100 text-blue-700",
    emerald: "bg-emerald-100 text-emerald-700",
    violet: "bg-violet-100 text-violet-700",
    amber: "bg-amber-100 text-amber-700",
    red: "bg-red-100 text-red-700",
  };
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className={`rounded-lg p-3 ${tones[tone]}`}><Icon className="h-5 w-5" /></div>
        <div><p className="text-sm text-muted-foreground">{label}</p><p className="text-2xl font-semibold">{value}</p></div>
      </CardContent>
    </Card>
  );
}

function RecordPanel({ record, kind }: { record: CRMRecord | null; kind: CRMPageKind }) {
  if (!record) return <Card><CardContent className="p-5 text-sm text-muted-foreground">Select a record to inspect details.</CardContent></Card>;
  const customer360 = kind === "contacts" || kind === "companies" ? customer360For(String(record.company || record.name || "")) : null;
  return (
    <Card className="h-fit">
      <CardHeader className="space-y-1">
        <CardTitle className="text-base">{String(record.name || record.company || record.deal || record.subject || record.quote || record.number || record.file || record.rule || pageTitles[kind])}</CardTitle>
        <p className="text-sm text-muted-foreground">Operational detail panel</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid max-h-[28rem] gap-2 overflow-y-auto pr-1">
          {Object.entries(record).map(([key, value]) => (
            <div key={key} className="flex items-center justify-between gap-3 rounded-md border bg-muted/30 px-3 py-2 text-sm">
              <span className="text-muted-foreground">{key.replace(/([A-Z])/g, " $1")}</span>
              <span className="text-right font-medium">{typeof value === "number" && isMoneyField(key) ? formatCurrency(value) : String(value)}</span>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Button variant="outline"><Phone className="h-4 w-4" />Log call</Button>
          <Button variant="outline"><Mail className="h-4 w-4" />Log email</Button>
          <Button variant="outline"><CalendarDays className="h-4 w-4" />Schedule</Button>
          <Button variant="outline"><ListFilter className="h-4 w-4" />Task</Button>
        </div>
        {customer360 ? (
          <div className="rounded-lg border bg-primary/5 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Customer 360</p>
            <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
              {customer360.metrics.map(([label, value]) => (
                <div key={label} className="rounded-md bg-background p-2">
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <p className="font-semibold">{value}</p>
                </div>
              ))}
            </div>
            <div className="mt-3 space-y-2 text-sm">
              {customer360.timeline.slice(0, 3).map((item) => <TimelineItem key={item} text={item} />)}
            </div>
          </div>
        ) : null}
        <div className="rounded-lg border bg-muted/30 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Timeline</p>
          <div className="mt-3 space-y-3 text-sm">
            <TimelineItem text="Record updated by owner" />
            <TimelineItem text="Follow-up task generated" />
            <TimelineItem text="Notification sent to assigned user" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function customer360For(companyName: string) {
  return {
    company: companyName || "Customer",
    industry: "Account",
    status: "Active",
    metrics: [
      ["Contacts", "-"],
      ["Deals", "-"],
      ["Pipeline", "-"],
      ["Notes", "-"],
    ] as Array<[string, string | number]>,
    timeline: [
      "Customer 360 reads from CRM APIs.",
      "Open related CRM grids for persisted contacts, deals, notes, and quotations.",
    ],
  };
}

function DashboardQuickCreateDialog({
  kind,
  saving,
  error,
  onKindChange,
  onClose,
  onCreate,
}: {
  kind: DashboardQuickCreateKind;
  saving?: boolean;
  error?: string | null;
  onKindChange: (kind: DashboardQuickCreateKind) => void;
  onClose: () => void;
  onCreate: (draft: CRMRecord, customFields?: CRMApiRecord) => void;
}) {
  return (
    <CreateRecordDialog
      kind={kind}
      saving={saving}
      error={error}
      onClose={onClose}
      onCreate={onCreate}
      header={
        <div className="flex flex-wrap gap-2">
          {dashboardQuickCreateKinds.map((item) => (
            <Button key={item.kind} type="button" size="sm" variant={kind === item.kind ? "default" : "outline"} onClick={() => onKindChange(item.kind)} disabled={saving}>
              {item.label}
            </Button>
          ))}
        </div>
      }
    />
  );
}

function CreateRecordDialog({ kind, saving, error, onClose, onCreate, header }: { kind: CRMPageKind; saving?: boolean; error?: string | null; onClose: () => void; onCreate: (draft: CRMRecord, customFields?: CRMApiRecord) => void; header?: React.ReactNode }) {
  const title = actionFor(kind) || "Create record";
  const entity = apiEntityForKind[kind];
  const customFieldState = useCrmRecords<CRMApiRecord>(entity && customFieldEntities.some((item) => item.value === entity) ? "custom-fields" : undefined, [], entity ? { entityType: entity } : undefined);
  const formFields = quickFormFieldsByKind[kind] || [
    { key: "name", label: "Name", required: true, placeholder: "Record name" },
    { key: "status", label: "Status", placeholder: "New" },
    { key: "owner", label: "Owner", placeholder: "Owner ID or name" },
    { key: "nextFollowUp", label: "Next follow-up", type: "date" as const },
  ];
  const defaultName = `New ${pageTitles[kind].replace("CRM ", "").replace(/s$/, "")}`;
  const initialDraft = useMemo(() => ({
    name: defaultName,
    subject: defaultName,
    owner: "",
    status: kind === "tickets" ? "Open" : "New",
    nextFollowUp: new Date().toISOString().slice(0, 10),
  }), [defaultName, kind]);
  const [draft, setDraft] = useState<CRMRecord>(initialDraft);
  const [customValues, setCustomValues] = useState<CRMApiRecord>({});
  useEffect(() => {
    setDraft(initialDraft);
    setCustomValues({});
  }, [initialDraft]);
  const patchDraft = (key: string, value: CRMApiValue) => setDraft((current) => ({ ...current, [key]: value }));
  if (kind === "deals") {
    return <CreateDealDialog saving={saving} error={error} onClose={onClose} onCreate={onCreate} />;
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <Card className="w-full max-w-lg">
        <CardHeader className="flex-row items-start justify-between">
          <div><CardTitle>{title}</CardTitle><p className="text-sm text-muted-foreground">Fast-create form with required CRM fields.</p></div>
          <Button variant="ghost" size="sm" onClick={onClose}><X className="h-4 w-4" /></Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {header}
          {error ? <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div> : null}
          <div className="grid gap-4 md:grid-cols-2">
            {formFields.map((field) => (
              <div key={field.key} className={field.width === "full" ? "md:col-span-2" : undefined}>
                <Field label={`${field.label}${field.required ? " *" : ""}`}>
                  <QuickFormInput field={field} draft={draft} patchDraft={patchDraft} />
                </Field>
              </div>
            ))}
          </div>
          {customFieldState.data.filter((field) => Boolean(field.isVisible ?? field.is_visible ?? true)).map((field) => (
            <Field key={String(field.id)} label={`${String(field.fieldName || field.label || field.field_key)}${field.isRequired || field.is_required ? " *" : ""}`}>
              <CustomFieldInput field={field} value={customValues[String(field.fieldKey || field.field_key || field.id)]} onChange={(value) => setCustomValues((current) => ({ ...current, [String(field.fieldKey || field.field_key || field.id)]: value }))} />
            </Field>
          ))}
          <div className="flex justify-end gap-2"><Button variant="outline" onClick={onClose} disabled={saving}>Cancel</Button><Button onClick={() => onCreate(draft, customValues)} disabled={saving}>{saving ? "Creating..." : "Create"}</Button></div>
        </CardContent>
      </Card>
    </div>
  );
}

function CreateDealDialog({ saving, error, onClose, onCreate }: { saving?: boolean; error?: string | null; onClose: () => void; onCreate: (draft: CRMRecord, customFields?: CRMApiRecord) => void }) {
  const [mode, setMode] = useState<"simple" | "advanced">("simple");
  const [stageOpen, setStageOpen] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [draft, setDraft] = useState<CRMRecord>(() => ({
    name: "",
    company: "",
    contact: "",
    stage: "Negotiation/Review",
    stageId: 4,
    pipelineId: 1,
    amount: "",
    probability: 75,
    status: "Open",
    nextFollowUp: new Date().toISOString().slice(0, 10),
    description: "",
    owner: "",
    source: "Manual Entry",
  }));
  const [lines, setLines] = useState<DealProductLine[]>([{ id: 1, product: "", listPrice: 0, quantity: 1, discount: 0 }]);
  const selectedStage = createDealStages.find((stage) => stage.name === draft.stage) || createDealStages[3];
  const lineItems = lines.filter((line) => line.product.trim() || line.listPrice || line.quantity > 1 || line.discount);
  const lineSubtotal = lines.reduce((sum, line) => sum + Number(line.listPrice || 0) * Number(line.quantity || 0), 0);
  const lineDiscount = lines.reduce((sum, line) => sum + Number(line.listPrice || 0) * Number(line.quantity || 0) * (Number(line.discount || 0) / 100), 0);
  const lineTotal = Math.max(0, lineSubtotal - lineDiscount);
  const displayAmount = lineTotal || Number(draft.amount || 0);
  const patchDraft = (key: string, value: CRMApiValue) => {
    setDraft((current) => ({ ...current, [key]: value }));
    setLocalError(null);
  };
  const selectStage = (stageName: string) => {
    const stage = createDealStages.find((item) => item.name === stageName) || createDealStages[0];
    setDraft((current) => ({
      ...current,
      stage: stage.name,
      stageId: stage.id,
      probability: stage.probability,
      status: stage.isWon ? "Won" : stage.isLost ? "Lost" : "Open",
    }));
    setLocalError(null);
    setStageOpen(false);
  };
  const updateLine = (id: number, key: keyof DealProductLine, value: string | number) => {
    setLines((current) => current.map((line) => line.id === id ? { ...line, [key]: key === "product" ? String(value) : Number(value || 0) } : line));
  };
  const addLine = () => setLines((current) => [...current, { id: Date.now(), product: "", listPrice: 0, quantity: 1, discount: 0 }]);
  const removeLine = (id: number) => setLines((current) => current.length === 1 ? current : current.filter((line) => line.id !== id));
  const saveDeal = () => {
    const missing = [
      ["Company name", draft.company],
      ["Contact name", draft.contact],
      ["Deal name", draft.name],
      ["Closing date", draft.nextFollowUp],
    ].filter(([, value]) => !String(value || "").trim());
    if (missing.length) {
      setLocalError(`${missing.map(([label]) => label).join(", ")} ${missing.length === 1 ? "is" : "are"} required.`);
      return;
    }
    onCreate({
      ...draft,
      amount: displayAmount,
      probability: selectedStage.probability,
      stageId: selectedStage.id,
      status: selectedStage.isWon ? "Won" : selectedStage.isLost ? "Lost" : "Open",
      products: lineItems.map((line) => line.product).filter(Boolean),
      associatedProducts: lineItems,
      nextStep: String(draft.description || ""),
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-3 backdrop-blur-sm">
      <div className="flex max-h-[94vh] w-full max-w-6xl flex-col overflow-hidden rounded-lg border bg-background shadow-2xl">
        <div className="flex flex-col gap-3 border-b px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <div className="rounded-md bg-emerald-100 p-2 text-emerald-700"><Target className="h-4 w-4" /></div>
              <div>
                <h2 className="text-xl font-semibold tracking-tight">Create Deal</h2>
                <p className="text-sm text-muted-foreground">Capture the opportunity, products, value, and next sales commitment in one place.</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="inline-flex rounded-md border bg-muted p-1">
              {(["simple", "advanced"] as const).map((item) => (
                <button key={item} type="button" className={`rounded px-3 py-1.5 text-sm font-medium capitalize transition ${mode === item ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`} onClick={() => setMode(item)}>
                  {item}
                </button>
              ))}
            </div>
            <Button variant="ghost" size="sm" onClick={onClose}><X className="h-4 w-4" /></Button>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_19rem]">
            <div className="space-y-6 px-5 py-5">
              {(error || localError) ? <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-700">{localError || error}</div> : null}
              <section className="grid gap-4 lg:grid-cols-2">
                <DealField label="Company Name" required>
                  <IconInput icon={<Building2 className="h-4 w-4" />} value={String(draft.company || "")} onChange={(value) => patchDraft("company", value)} placeholder="Acme India Pvt Ltd" required />
                </DealField>
                <DealField label="Contact Name" required>
                  <IconInput icon={<Users className="h-4 w-4" />} value={String(draft.contact || "")} onChange={(value) => patchDraft("contact", value)} placeholder="Meera Shah" required />
                </DealField>
                <DealField label="Deal Name" required>
                  <Input className="border-l-4 border-l-red-400" value={String(draft.name || "")} onChange={(event) => patchDraft("name", event.target.value)} placeholder="ERP rollout - Phase 1" />
                </DealField>
                <DealField label="Stage">
                  <DealStagePicker selectedStage={selectedStage} open={stageOpen} onToggle={() => setStageOpen((current) => !current)} onSelect={selectStage} />
                </DealField>
                <DealField label="Amount">
                  <Input type="number" value={String(draft.amount || "")} onChange={(event) => patchDraft("amount", event.target.value)} placeholder="500000" />
                </DealField>
                <DealField label="Closing Date" required>
                  <Input className="border-l-4 border-l-red-400" type="date" value={String(draft.nextFollowUp || "")} onChange={(event) => patchDraft("nextFollowUp", event.target.value)} />
                </DealField>
                <DealField label="Description" className="lg:col-span-2">
                  <textarea className="min-h-24 w-full rounded-md border bg-background px-3 py-2 text-sm" value={String(draft.description || "")} onChange={(event) => patchDraft("description", event.target.value)} placeholder="Commercial context, competitors, risks, buyer priorities..." />
                </DealField>
              </section>
              {mode === "advanced" ? (
                <section className="grid gap-4 rounded-md border bg-muted/20 p-4 lg:grid-cols-3">
                  <DealField label="Owner">
                    <Input value={String(draft.owner || "")} onChange={(event) => patchDraft("owner", event.target.value)} placeholder="Sales owner" />
                  </DealField>
                  <DealField label="Source">
                    <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={String(draft.source || "")} onChange={(event) => patchDraft("source", event.target.value)}>
                      {["Manual Entry", "Website", "Referral", "Partner", "Event", "Outbound"].map((source) => <option key={source}>{source}</option>)}
                    </select>
                  </DealField>
                  <DealField label="Probability">
                    <Input type="number" value={String(draft.probability || 0)} onChange={(event) => patchDraft("probability", event.target.value)} />
                  </DealField>
                </section>
              ) : null}
              <section className="space-y-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h3 className="text-base font-semibold">Associated Products</h3>
                    <p className="text-sm text-muted-foreground">Add products or services to auto-calculate deal value.</p>
                  </div>
                  <Button type="button" variant="outline" size="sm" onClick={addLine}><Plus className="h-4 w-4" />Add line</Button>
                </div>
                <div className="overflow-x-auto rounded-md border">
                  <table className="crm-desktop-table">
                    <thead className="bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <tr>
                        <th className="px-3 py-3">Product</th>
                        <th className="px-3 py-3">List Price (INR)</th>
                        <th className="px-3 py-3">Quantity</th>
                        <th className="px-3 py-3">Discount (%)</th>
                        <th className="px-3 py-3 text-right">Total (INR)</th>
                        <th className="px-3 py-3" />
                      </tr>
                    </thead>
                    <tbody>
                      {lines.map((line) => {
                        const total = Math.max(0, Number(line.listPrice || 0) * Number(line.quantity || 0) * (1 - Number(line.discount || 0) / 100));
                        return (
                          <tr key={line.id} className="border-t">
                            <td className="px-3 py-2"><Input value={line.product} onChange={(event) => updateLine(line.id, "product", event.target.value)} placeholder="Search Product" /></td>
                            <td className="px-3 py-2"><Input type="number" value={String(line.listPrice || "")} onChange={(event) => updateLine(line.id, "listPrice", event.target.value)} placeholder="0" /></td>
                            <td className="px-3 py-2"><Input type="number" min={1} value={String(line.quantity || 1)} onChange={(event) => updateLine(line.id, "quantity", event.target.value)} /></td>
                            <td className="px-3 py-2"><Input type="number" min={0} max={100} value={String(line.discount || "")} onChange={(event) => updateLine(line.id, "discount", event.target.value)} placeholder="0" /></td>
                            <td className="px-3 py-2 text-right font-medium">{formatCurrency(total)}</td>
                            <td className="px-3 py-2 text-right"><Button type="button" variant="ghost" size="sm" onClick={() => removeLine(line.id)} disabled={lines.length === 1}><X className="h-4 w-4" /></Button></td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
            <aside className="border-t bg-muted/20 p-5 lg:border-l lg:border-t-0">
              <div className="space-y-4">
                <div className={`rounded-md border p-4 ${selectedStage.tone}`}>
                  <p className="text-xs font-semibold uppercase tracking-wide">Selected stage</p>
                  <p className="mt-1 text-lg font-semibold">{selectedStage.name}</p>
                  <p className="mt-1 text-sm">{selectedStage.probability}% probability</p>
                </div>
                <div className="rounded-md border bg-background p-4">
                  <p className="text-sm font-semibold">Deal value</p>
                  <p className="mt-2 text-2xl font-semibold">{formatCurrency(displayAmount)}</p>
                  <div className="mt-3 space-y-1 text-sm text-muted-foreground">
                    <div className="flex justify-between"><span>Subtotal</span><span>{formatCurrency(lineSubtotal)}</span></div>
                    <div className="flex justify-between"><span>Discount</span><span>{formatCurrency(lineDiscount)}</span></div>
                    <div className="flex justify-between font-medium text-foreground"><span>Total</span><span>{formatCurrency(lineTotal || Number(draft.amount || 0))}</span></div>
                  </div>
                </div>
                <div className="rounded-md border bg-background p-4 text-sm">
                  <p className="font-semibold">Quality checks</p>
                  <ul className="mt-3 space-y-2 text-muted-foreground">
                    <li className="flex gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" />Mandatory buyer and close-date fields are validated.</li>
                    <li className="flex gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" />Closed Won/Lost stages map to final deal status.</li>
                    <li className="flex gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" />Product totals recalculate before save.</li>
                  </ul>
                </div>
              </div>
            </aside>
          </div>
        </div>
        <div className="flex flex-col gap-3 border-t bg-background px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <Button type="button" variant="link" className="justify-start px-0 text-blue-700">Customize Fields</Button>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
            <Button onClick={saveDeal} disabled={saving} className="bg-emerald-600 hover:bg-emerald-700"><Save className="h-4 w-4" />{saving ? "Saving..." : "Save"}</Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function DealField({ label, required, className, children }: { label: string; required?: boolean; className?: string; children: React.ReactNode }) {
  return (
    <div className={`space-y-2 ${className || ""}`}>
      <span className="block text-sm font-medium">{label}{required ? <span className="text-red-600"> *</span> : null}</span>
      {children}
    </div>
  );
}

function IconInput({ icon, value, onChange, placeholder, required }: { icon: React.ReactNode; value: string; onChange: (value: string) => void; placeholder?: string; required?: boolean }) {
  return (
    <div className="relative">
      <Input className={`pr-10 ${required ? "border-l-4 border-l-red-400" : ""}`} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />
      <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-500">{icon}</span>
    </div>
  );
}

function DealStagePicker({ selectedStage, open, onToggle, onSelect }: { selectedStage: typeof createDealStages[number]; open: boolean; onToggle: () => void; onSelect: (stageName: string) => void }) {
  return (
    <div className="relative">
      <button
        type="button"
        className="flex h-11 w-full items-center justify-between rounded-md border border-emerald-400 bg-background px-3 text-left text-sm shadow-sm transition hover:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-200"
        onClick={onToggle}
        aria-expanded={open}
      >
        <span className="flex min-w-0 items-center gap-2">
          <span className={`h-2.5 w-2.5 rounded-full ${selectedStage.isWon ? "bg-emerald-500" : selectedStage.isLost ? "bg-red-500" : "bg-blue-500"}`} />
          <span className="truncate font-medium">{selectedStage.name}</span>
        </span>
        <ChevronDown className={`h-4 w-4 text-muted-foreground transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open ? (
        <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-md border border-emerald-300 bg-background shadow-xl">
          <div className="border-l-2 border-l-emerald-400 py-1">
            {createDealStages.map((stage) => {
              const selected = stage.name === selectedStage.name;
              return (
                <button
                  key={stage.name}
                  type="button"
                  className={`flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left text-sm transition ${selected ? "bg-sky-100 text-sky-950" : "hover:bg-muted/70"}`}
                  onClick={() => onSelect(stage.name)}
                >
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{stage.name}</span>
                    <span className="block text-xs text-muted-foreground">{stage.probability}% probability</span>
                  </span>
                  {stage.isWon ? (
                    <span className="rounded-full bg-emerald-100 p-1 text-emerald-700"><CheckCircle2 className="h-4 w-4" /></span>
                  ) : stage.isLost ? (
                    <span className="rounded-full bg-red-100 p-1 text-red-700"><X className="h-4 w-4" /></span>
                  ) : selected ? (
                    <CheckCircle2 className="h-4 w-4 text-sky-700" />
                  ) : (
                    <span className="h-2 w-2 rounded-full bg-slate-300" />
                  )}
                </button>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function CustomFieldInput({ field, value, onChange }: { field: CRMApiRecord; value: CRMApiRecord[string]; onChange: (value: CRMApiRecord[string]) => void }) {
  const type = String(field.fieldType || field.field_type || "text");
  const options = parseOptions(field.options ?? field.options_json);
  if (type === "dropdown") {
    return <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={String(value || "")} onChange={(event) => onChange(event.target.value)}><option value="">Select</option>{options.map((option) => <option key={option} value={option}>{option}</option>)}</select>;
  }
  if (type === "multi_select") {
    return <Input value={Array.isArray(value) ? value.join(", ") : String(value || "")} onChange={(event) => onChange(parseOptions(event.target.value))} placeholder={options.length ? options.join(", ") : "Comma separated values"} />;
  }
  if (type === "checkbox") {
    return <ToggleBox checked={Boolean(value)} onChange={onChange} />;
  }
  const inputType = type === "number" || type === "currency" || type === "user" || type === "owner" ? "number" : type === "date" ? "date" : type === "datetime" ? "datetime-local" : type === "email" ? "email" : type === "url" ? "url" : "text";
  return <Input type={inputType} value={String(value || "")} onChange={(event) => onChange(event.target.value)} />;
}

function QuickFormInput({
  field,
  draft,
  patchDraft,
}: {
  field: QuickFormField;
  draft: CRMRecord;
  patchDraft: (key: string, value: CRMApiValue) => void;
}) {
  const value = String(draft[field.key] || "");
  const updateValue = (nextValue: string) => {
    patchDraft(field.key, nextValue);
    if (field.key === "name" && !String(draft.subject || "").trim()) {
      patchDraft("subject", nextValue);
    }
    if (field.key === "subject" && !String(draft.name || "").trim()) {
      patchDraft("name", nextValue);
    }
  };

  if (field.type === "select") {
    return (
      <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={value} onChange={(event) => updateValue(event.target.value)}>
        <option value="">{field.placeholder || "Select"}</option>
        {(field.options || []).map((option) => <option key={option} value={option}>{option}</option>)}
      </select>
    );
  }

  if (field.type === "textarea") {
    return (
      <textarea
        className="min-h-24 w-full rounded-md border bg-background px-3 py-2 text-sm"
        value={value}
        placeholder={field.placeholder}
        onChange={(event) => updateValue(event.target.value)}
      />
    );
  }

  return (
    <Input
      type={field.type === "number" ? "number" : field.type === "date" ? "date" : field.type === "email" ? "email" : "text"}
      value={value}
      placeholder={field.placeholder}
      onChange={(event) => updateValue(event.target.value)}
    />
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="space-y-2"><Label>{label}</Label>{children}</div>;
}

function TimelineItem({ text }: { text: string }) {
  return <div className="flex gap-2"><span className="mt-1 h-2 w-2 rounded-full bg-primary" /><span>{text}</span></div>;
}

function Insight({ text }: { text: string }) {
  return <div className="rounded-lg border bg-muted/40 p-4 text-sm">{text}</div>;
}

function filterRecords(records: CRMRecord[], search: string, view: string, filters: CRMFilters) {
  const text = search.toLowerCase();
  const today = new Date("2026-05-10");
  const weekEnd = new Date("2026-05-17");
  return records.filter((row) => {
    const matchesSearch = Object.values(row).join(" ").toLowerCase().includes(text);
    const matchesOwner = filters.owner === "all" || row.owner === filters.owner;
    const matchesStatus = filters.status === "all" || row.status === filters.status;
    const matchesType = filters.type === "all" || row.type === filters.type;
    const matchesTerritory = filters.territory === "all" || String(row.territoryId || row.territory_id || "") === filters.territory;
    const dueValue = String(row.due || row.nextFollowUp || row.closeDate || row.expiryDate || "");
    const dueDate = dueValue ? new Date(dueValue) : null;
    const matchesView =
      view === "Due this week"
        ? !!dueDate && dueDate >= today && dueDate <= weekEnd
        : view === "Hot pipeline"
          ? ["Hot", "High", "Urgent", "Critical", "Negotiation", "Contract Sent"].some((value) => Object.values(row).includes(value))
          : view === "No follow-up"
            ? !dueValue
            : true;
    return matchesSearch && matchesOwner && matchesStatus && matchesType && matchesTerritory && matchesView;
  });
}

function uniqueValues(records: CRMRecord[], key: string) {
  return Array.from(new Set(records.map((row) => row[key]).filter(Boolean).map(String))).sort();
}

function parseCsv(text: string): CRMRecord[] {
  const lines = text.split(/\r?\n/).filter((line) => line.trim());
  if (lines.length < 2) return [];
  const headers = splitCsvLine(lines[0]);
  return lines.slice(1).map((line) => {
    const values = splitCsvLine(line);
    return headers.reduce<CRMRecord>((row, header, index) => {
      row[header || `field${index + 1}`] = values[index] || "";
      return row;
    }, {});
  });
}

function splitCsvLine(line: string) {
  const values: string[] = [];
  let current = "";
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    const next = line[index + 1];
    if (char === '"' && quoted && next === '"') {
      current += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      values.push(current);
      current = "";
    } else {
      current += char;
    }
  }
  values.push(current);
  return values.map((value) => value.trim());
}

function compareValues(a: unknown, b: unknown, direction: "asc" | "desc") {
  const multiplier = direction === "asc" ? 1 : -1;
  if (typeof a === "number" && typeof b === "number") return (a - b) * multiplier;
  const dateA = Date.parse(String(a));
  const dateB = Date.parse(String(b));
  if (!Number.isNaN(dateA) && !Number.isNaN(dateB)) return (dateA - dateB) * multiplier;
  return String(a ?? "").localeCompare(String(b ?? "")) * multiplier;
}

function renderCell(key: string, value: CRMApiRecord[string]) {
  if (key === "leadScore") return <Badge className={statusColor(scoreLabel(Number(value || 0)))}>{Number(value || 0)} / {scoreLabel(Number(value || 0))}</Badge>;
  if (isBadgeField(key)) return <Badge className={statusColor(String(value))}>{String(value)}</Badge>;
  if (key.toLowerCase().includes("date") || key.toLowerCase().includes("due") || key.toLowerCase().includes("followup")) return formatDate(String(value));
  if (typeof value === "number" && isMoneyField(key)) return formatCurrency(value);
  return String(value ?? "");
}

function scoreLabel(score: number) {
  if (score <= 30) return "Cold";
  if (score <= 70) return "Warm";
  return "Hot";
}

function valueText(value: unknown) {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "";
}

function duplicateRecordTitle(record: CRMApiRecord, entityType: string) {
  if (entityType === "account") return valueText(record.name) || `Account #${record.id}`;
  return valueText(record.full_name || record.name) || `${labelFor(entityType)} #${record.id}`;
}

function mergeFieldsFor(entityType: string) {
  if (entityType === "account") return ["name", "website", "email", "phone", "industry", "account_type", "city", "state", "country", "notes"];
  if (entityType === "lead") return ["first_name", "last_name", "full_name", "email", "phone", "company_name", "job_title", "source", "status", "rating", "notes"];
  return ["first_name", "last_name", "full_name", "email", "phone", "job_title", "department", "lifecycle_stage", "status", "notes"];
}

function mergeDefaultFieldValues(records: CRMApiRecord[], entityType: string) {
  return mergeFieldsFor(entityType).reduce<CRMApiRecord>((values, field) => {
    const recordWithValue = records.find((record) => valueText(record[field]));
    values[field] = recordWithValue?.[field] as CRMApiRecord[string];
    return values;
  }, {});
}

function InfoTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-muted/30 p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="truncate text-sm font-medium">{value}</p>
    </div>
  );
}

function FilterSelect({ label, value, values, allLabel, onChange }: { label: string; value: string; values: string[]; allLabel: string; onChange: (value: string) => void }) {
  return (
    <label className="space-y-1 text-sm">
      <span className="font-medium">{label}</span>
      <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="all">{allLabel}</option>
        {values.map((item) => <option key={item} value={item}>{item.replace("_", " ")}</option>)}
      </select>
    </label>
  );
}

function uniqueCalendarValues(values: string[]) {
  return Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b));
}

function calendarRange(cursor: Date, view: CalendarView) {
  if (view === "month") {
    const start = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    const end = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0, 23, 59, 59);
    start.setDate(start.getDate() - mondayIndex(start));
    end.setDate(end.getDate() + (6 - mondayIndex(end)));
    return { start, end };
  }
  if (view === "week") {
    const start = startOfDay(cursor);
    start.setDate(start.getDate() - mondayIndex(start));
    const end = new Date(start);
    end.setDate(start.getDate() + 6);
    end.setHours(23, 59, 59, 999);
    return { start, end };
  }
  const start = startOfDay(cursor);
  const end = new Date(start);
  end.setHours(23, 59, 59, 999);
  return { start, end };
}

function startOfDay(date: Date) {
  const output = new Date(date);
  output.setHours(0, 0, 0, 0);
  return output;
}

function mondayIndex(date: Date) {
  return (date.getDay() + 6) % 7;
}

function monthDays(cursor: Date) {
  const { start, end } = calendarRange(cursor, "month");
  const days: Date[] = [];
  const day = new Date(start);
  while (day <= end) {
    days.push(new Date(day));
    day.setDate(day.getDate() + 1);
  }
  return days;
}

function weekDays(cursor: Date) {
  const { start } = calendarRange(cursor, "week");
  return Array.from({ length: 7 }, (_, index) => {
    const day = new Date(start);
    day.setDate(start.getDate() + index);
    return day;
  });
}

function dateKey(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function parseLocalDateKey(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year || 1970, (month || 1) - 1, day || 1);
}

function eventsForDay(events: CRMCalendarEvent[], day: Date) {
  const key = dateKey(day);
  return events.filter((event) => dateKey(new Date(event.start)) === key).sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime());
}

function calendarTitle(cursor: Date, view: CalendarView) {
  if (view === "month") return cursor.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  if (view === "week") {
    const days = weekDays(cursor);
    return `${days[0].toLocaleDateString(undefined, { month: "short", day: "numeric" })} - ${days[6].toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}`;
  }
  return cursor.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" });
}

function timeLabel(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "-" : date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function calendarEventTone(event: CRMCalendarEvent) {
  const value = [event.source, event.type, event.category].join(" ").toLowerCase();
  if (value.includes("call")) return { border: "#8b5cf6", className: "border-violet-100 bg-violet-50 text-violet-950" };
  if (value.includes("meeting") || value.includes("event")) return { border: "#0ea5e9", className: "border-sky-100 bg-sky-50 text-sky-950" };
  if (value.includes("quotation") || value.includes("quote")) return { border: "#f59e0b", className: "border-amber-100 bg-amber-50 text-amber-950" };
  if (value.includes("deal")) return { border: "#10b981", className: "border-emerald-100 bg-emerald-50 text-emerald-950" };
  return { border: "#f59e0b", className: "border-amber-100 bg-amber-50 text-amber-950" };
}

function dateWithTime(date: Date, time: string) {
  const [hours, minutes] = time.split(":").map(Number);
  const output = new Date(date);
  output.setHours(hours || 0, minutes || 0, 0, 0);
  return output;
}

function calendarPatchFor(event: CRMCalendarEvent, start: Date, end: Date): CRMApiRecord {
  if (event.source === "tasks") return { due_date: start.toISOString() };
  if (event.source === "meetings") return { start_time: start.toISOString(), end_time: end.toISOString() };
  if (event.source === "calls") return { call_time: start.toISOString() };
  if (event.source === "activities") return { activity_date: start.toISOString(), due_date: start.toISOString() };
  if (event.source === "quotations") return { expiry_date: dateKey(start) };
  if (event.source === "deals") return { expected_close_date: dateKey(start) };
  return {};
}

function relatedCalendarPath(event: CRMCalendarEvent) {
  if (event.entityType === "lead" && event.entityId) return `/crm/leads/${event.entityId}`;
  if (event.entityType === "contact" && event.entityId) return `/crm/contacts/${event.entityId}`;
  if (event.entityType === "account" && event.entityId) return `/crm/accounts/${event.entityId}`;
  if (event.entityType === "deal" && event.entityId) return `/crm/deals/${event.entityId}`;
  if (event.entityType === "quotation" && event.entityId) return `/crm/quotations/${event.entityId}`;
  return "";
}

function markCalendarTaskComplete(event: CRMCalendarEvent, setEvents: React.Dispatch<React.SetStateAction<CRMCalendarEvent[]>>, setError: React.Dispatch<React.SetStateAction<string | null>>) {
  crmApi
    .update("tasks", event.recordId, { status: "Completed", completed_at: new Date().toISOString() })
    .then(() => setEvents((items) => items.map((item) => (item.id === event.id ? { ...item, status: "Completed" } : item))))
    .catch((err) => setError(err?.response?.data?.detail || "Could not mark task complete."));
}

function normalizeInlineValue(config: InlineEditConfig, value: string | number | boolean | null) {
  if (value === null || value === "") return null;
  if (config.type === "number") return Number(value);
  if (config.type === "date") return String(value).slice(0, 10);
  return value;
}

function detailPathFor(kind: CRMPageKind) {
  if (kind === "leads") return "/crm/leads";
  if (kind === "contacts") return "/crm/contacts";
  if (kind === "companies") return "/crm/accounts";
  if (kind === "deals") return "/crm/deals";
  if (kind === "products") return "/crm/products";
  if (kind === "services") return "/crm/services";
  if (kind === "priceBooks") return "/crm/price-books";
  if (kind === "quotes") return "/crm/quotes";
  if (kind === "quotations") return "/crm/quotations";
  return "";
}

function normalizeApiRecord(kind: string, record: CRMApiRecord): CRMRecord {
  const id = Number(record.id || 0);
  if (kind === "leads") {
    return { id, name: String(record.full_name || [record.first_name, record.last_name].filter(Boolean).join(" ") || "Lead"), company: String(record.company_name || ""), email: String(record.email || ""), phone: String(record.phone || ""), source: String(record.source || "Other"), status: String(record.status || "New"), rating: String(record.scoreLabel || record.lead_score_label || record.rating || "Warm"), leadScore: Number(record.leadScore || record.lead_score || 0), scoreLabel: String(record.scoreLabel || record.lead_score_label || record.rating || "Cold"), owner: String(record.ownerId || record.owner_user_id || ""), territoryId: Number(record.territoryId || record.territory_id || 0), value: Number(record.estimated_value || 0), nextFollowUp: String(record.next_follow_up_at || ""), lastContacted: String(record.last_contacted_at || ""), industry: String(record.industry || ""), createdAt: String(record.createdAt || "") };
  }
  if (kind === "contacts") {
    return { id, name: String(record.full_name || [record.first_name, record.last_name].filter(Boolean).join(" ") || "Contact"), email: String(record.email || ""), phone: String(record.phone || ""), companyId: Number(record.company_id || 0), title: String(record.job_title || ""), stage: String(record.lifecycle_stage || ""), source: String(record.source || ""), status: String(record.status || "Active"), owner: String(record.ownerId || record.owner_user_id || "") };
  }
  if (kind === "companies") {
    return { id, name: String(record.name || "Company"), industry: String(record.industry || ""), type: String(record.account_type || ""), status: String(record.status || "Active"), revenue: Number(record.annual_revenue || 0), owner: String(record.ownerId || record.owner_user_id || ""), territoryId: Number(record.territoryId || record.territory_id || 0), city: String(record.city || ""), email: String(record.email || "") };
  }
  if (kind === "deals") {
    return { id, name: String(record.name || "Deal"), companyId: Number(record.company_id || 0), contactId: Number(record.contact_id || 0), owner: String(record.ownerId || record.owner_user_id || ""), territoryId: Number(record.territoryId || record.territory_id || 0), stageId: Number(record.stage_id || 0), pipelineId: Number(record.pipeline_id || 0), stage: String(record.stage || record.status || "Open"), amount: Number(record.amount || 0), probability: Number(record.probability || 0), closeDate: String(record.expected_close_date || ""), nextStep: String(record.description || record.status || ""), status: String(record.status || "Open") };
  }
  if (kind === "activities") {
    return { id, subject: String(record.subject || "Activity"), type: String(record.activity_type || ""), owner: String(record.ownerId || record.owner_user_id || ""), due: String(record.due_date || ""), status: String(record.status || "Pending"), priority: String(record.priority || "Medium") };
  }
  if (kind === "tasks") {
    return { id, subject: String(record.title || "Task"), owner: String(record.ownerId || record.owner_user_id || ""), due: String(record.due_date || ""), status: String(record.status || "To Do"), priority: String(record.priority || "Medium") };
  }
  if (kind === "meetings") {
    return { id, subject: String(record.title || "Meeting"), type: "Meeting", location: String(record.location || ""), due: String(record.start_time || ""), status: String(record.status || "Scheduled"), syncStatus: String(record.syncStatus || record.sync_status || "not_synced"), externalProvider: String(record.externalProvider || record.external_provider || "") };
  }
  if (kind === "products") {
    return { id, name: String(record.name || "Product"), productCode: String(record.productCode || record.product_code || record.sku || ""), sku: String(record.sku || record.productCode || ""), category: String(record.category || ""), price: Number(record.listPrice || record.list_price || record.unit_price || 0), cost: Number(record.costPrice || record.cost_price || 0), status: String(record.status || "Active") };
  }
  if (kind === "services") {
    return { id, name: String(record.name || "Service"), serviceCode: String(record.serviceCode || record.service_code || ""), category: String(record.category || ""), billingType: String(record.billingType || record.billing_type || "fixed"), price: Number(record.defaultRate || record.default_rate || 0), cost: Number(record.defaultCost || record.default_cost || 0), status: record.active === false ? "Inactive" : "Active" };
  }
  if (kind === "priceBooks") {
    return { id, name: String(record.name || "Price Book"), currency: String(record.currency || "INR"), region: String(record.region || ""), segment: String(record.customerSegment || record.customer_segment || ""), status: String(record.status || "active") };
  }
  if (kind === "quotations" || kind === "quotes" || kind === "quoteBuilder") {
    return { id, quote: String(record.quoteNumber || record.quote_number || ""), dealId: Number(record.dealId || record.deal_id || 0), companyId: Number(record.companyId || record.company_id || 0), status: String(record.status || "Draft"), approvalStatus: String(record.approvalStatus || record.approval_status || "not_submitted"), issueDate: String(record.quoteDate || record.quote_date || record.issue_date || ""), expiryDate: String(record.validUntil || record.valid_until || record.expiry_date || ""), total: Number(record.grandTotal || record.grand_total || record.total_amount || 0), margin: Number(record.expectedMargin || record.expected_margin || 0) };
  }
  if (kind === "quoteApprovals") {
    return { id, quoteId: Number(record.quoteId || record.quote_id || 0), status: String(record.status || "pending"), reason: String(record.reason || ""), comments: String(record.comments || ""), approver: String(record.approverUserId || record.approver_user_id || record.approved_by || "") };
  }
  if (kind === "cpq") {
    return { id, name: String(record.name || "CPQ Rule"), type: String(record.ruleType || record.rule_type || "recommendation"), status: record.active === false ? "Inactive" : "Active" };
  }
  if (kind === "guidedSelling") {
    return { id, name: String(record.name || "Guided Selling Flow"), status: record.active === false ? "Inactive" : "Active" };
  }
  if (kind === "campaigns") {
    return { id, name: String(record.name || "Campaign"), type: String(record.campaign_type || ""), status: String(record.status || "Planned"), startDate: String(record.start_date || ""), endDate: String(record.end_date || ""), budget: Number(record.budget_amount || 0), expectedRevenue: Number(record.expected_revenue || 0) };
  }
  if (kind === "tickets") {
    return { id, number: String(record.ticket_number || ""), subject: String(record.subject || "Ticket"), priority: String(record.priority || "Medium"), status: String(record.status || "Open"), category: String(record.category || ""), source: String(record.source || "Manual"), due: String(record.due_date || "") };
  }
  if (kind === "files") {
    return { id, name: String(record.original_name || record.file_name || "File"), fileName: String(record.file_name || ""), type: String(record.mime_type || ""), size: Number(record.size_bytes || 0), visibility: String(record.visibility || "Internal"), storagePath: String(record.storage_path || "") };
  }
  if (kind === "settings") {
    return { id, setting: String(record.label || record.field_key || "Custom field"), area: String(record.entity || ""), type: String(record.field_type || ""), status: record.is_active === false ? "Inactive" : "Ready" };
  }
  if (kind === "admin") {
    return { id, adminArea: String(record.full_name || "Owner"), permission: String(record.role || ""), email: String(record.email || ""), status: String(record.status || "Active") };
  }
  if (kind === "lead-scoring-rules") {
    return { id, name: String(record.name || ""), field: String(record.field || ""), operator: String(record.operator || ""), value: String(record.value || ""), points: Number(record.points || 0), is_active: Boolean(record.is_active ?? record.isActive ?? true) };
  }
  return { id, ...record };
}

function recordToLead(record: CRMRecord): CRMLead {
  return {
    id: Number(record.id || 0),
    name: String(record.name || record.full_name || "Lead"),
    company: String(record.company || record.company_name || ""),
    email: String(record.email || ""),
    phone: String(record.phone || ""),
    source: String(record.source || "Other"),
    status: String(record.status || "New"),
    rating: String(record.rating || "Warm"),
    leadScore: Number(record.leadScore || record.lead_score || 0),
    scoreLabel: String(record.scoreLabel || record.lead_score_label || record.rating || "Cold"),
    owner: String(record.owner || record.ownerId || ""),
    value: Number(record.value || record.estimated_value || 0),
    nextFollowUp: String(record.nextFollowUp || record.next_follow_up_at || ""),
    lastContacted: String(record.lastContacted || record.last_contacted_at || ""),
    industry: String(record.industry || ""),
  };
}

function recordToDeal(record: CRMRecord, stages: CRMRecord[], companyNames = new Map<number, string>()): CRMDeal {
  const stageId = Number(record.stageId || record.stage_id || 0);
  const stage = stages.find((item) => Number(item.id) === stageId);
  const companyId = Number(record.companyId || record.company_id || 0);
  return {
    id: Number(record.id || 0),
    name: String(record.name || "Deal"),
    company: String(record.company || record.companyName || record.company_name || companyNames.get(companyId) || (companyId ? `Company #${companyId}` : "")),
    contact: String(record.contact || record.contactId || record.contact_id || ""),
    owner: String(record.owner || record.ownerId || ""),
    pipelineId: Number(record.pipelineId || record.pipeline_id || stage?.pipeline_id || 0),
    stageId,
    stage: String(record.stage || stage?.name || record.status || "Open"),
    amount: Number(record.amount || 0),
    probability: Number(record.probability || 0),
    closeDate: String(record.closeDate || record.expected_close_date || ""),
    nextStep: String(record.nextStep || record.description || ""),
    products: [],
  };
}

function createPayloadForKind(kind: CRMPageKind, record: CRMRecord): CRMApiRecord {
  const ownerId = Number(record.owner || record.ownerId || 0) || undefined;
  if (kind === "leads") {
    const name = String(record.name || "New Lead");
    const [firstName, ...rest] = name.split(" ");
    return { first_name: firstName || name, last_name: rest.join(" "), full_name: name, email: record.email, phone: record.phone, company_name: record.company, source: record.source, status: record.status, rating: record.rating, lead_score: record.leadScore, estimated_value: record.value, industry: record.industry, next_follow_up_at: record.nextFollowUp, ownerId };
  }
  if (kind === "contacts") {
    const name = String(record.name || "New Contact");
    const [firstName, ...rest] = name.split(" ");
    return { first_name: firstName || name, last_name: rest.join(" "), full_name: name, email: record.email, phone: record.phone, lifecycle_stage: record.stage || "Lead", source: record.source, status: record.status, next_follow_up_at: record.nextFollowUp, ownerId };
  }
  if (kind === "companies") return { name: record.name, industry: record.industry, account_type: record.type, status: record.status, annual_revenue: record.revenue, ownerId };
  if (kind === "deals") return { name: record.name, pipeline_id: record.pipelineId || 1, stage_id: record.stageId || 1, amount: record.amount, probability: record.probability, status: record.status || "Open", expected_close_date: record.nextFollowUp, description: record.description || record.nextStep, lead_source: record.source, source: record.source, ownerId };
  if (kind === "activities") return { activity_type: record.type || "Task", subject: record.subject || record.name || "Activity", status: record.status, priority: record.priority, due_date: record.nextFollowUp, ownerId };
  if (kind === "tasks") return { title: record.subject || record.name || "Task", status: record.status, priority: record.priority, due_date: record.nextFollowUp, ownerId };
  if (kind === "products") return { name: record.name, sku: record.sku, category: record.category, unit_price: record.price, status: record.status, ownerId };
  if (kind === "services") return { service_code: record.serviceCode || `SVC-${Date.now()}`, name: record.name, category: record.category, billing_type: record.billingType || "fixed", default_rate: record.price || 0, default_cost: record.cost || 0, active: record.status !== "Inactive" };
  if (kind === "priceBooks") return { name: record.name, currency: record.currency || "INR", region: record.region, customer_segment: record.segment, status: record.status || "active", active: record.status !== "inactive" };
  if (kind === "quotations" || kind === "quotes") return { quote_number: record.quote || `QT-${Date.now()}`, quote_date: record.issueDate || new Date().toISOString().slice(0, 10), valid_until: record.expiryDate || new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 10), status: record.status || "Draft", grand_total: record.total };
  if (kind === "cpq") return { name: record.name || "CPQ Rule", rule_type: record.type || "recommendation", condition: { minAmount: Number(record.amount || 0) }, action: { message: "Review recommended configuration" }, active: true };
  if (kind === "guidedSelling") return { name: record.name || "Guided Selling Flow", questions: [], recommendations: [], active: true };
  if (kind === "campaigns") return { name: record.name, campaign_type: record.type || "Email", status: record.status || "Planned", start_date: record.startDate || new Date().toISOString().slice(0, 10), end_date: record.endDate || new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10), budget_amount: record.budget || 0, expected_revenue: record.expectedRevenue || 0, ownerId };
  if (kind === "tickets") return { ticket_number: record.number || `TCK-${Date.now()}`, subject: record.subject || record.name || "Customer request", priority: record.priority || "Medium", status: record.status || "Open", category: record.category || "General", source: record.source || "Manual", due_date: record.nextFollowUp, ownerId };
  if (kind === "files") return { file_name: record.fileName || `crm-file-${Date.now()}.txt`, original_name: record.name || "CRM file", storage_path: record.storagePath || "metadata-only", mime_type: record.type || "text/plain", size_bytes: record.size || 0, visibility: record.visibility || "Internal" };
  if (kind === "settings") return { entity: record.area || "leads", field_key: String(record.setting || "custom_field").toLowerCase().replace(/\W+/g, "_"), label: record.setting || "Custom field", field_type: record.type || "text" };
  if (kind === "admin") return { full_name: record.adminArea || "CRM Owner", email: record.email || `owner${Date.now()}@example.com`, role: record.permission || "Sales Executive", status: record.status || "Active" };
  return record;
}

function defaultRecordFor(kind: CRMPageKind, id: number, title: string): CRMRecord {
  if (kind === "leads") return {
    leadId: `LD-${String(1100 + id).padStart(4, "0")}`,
    name: `${title} ${id}`,
    company: "New Account",
    designation: "Decision Maker",
    email: `lead${id}@newaccount.example`,
    phone: "+91 90000 00000",
    mobile: "+91 90000 00001",
    city: "Bengaluru",
    state: "Karnataka",
    country: "India",
    source: "Website",
    campaign: "Inbound Demo",
    status: "New",
    rating: "Warm",
    lifecycleStage: "Lead",
    owner: "Ananya Rao",
    value: 250000,
    expectedCloseDate: "2026-06-20",
    productInterest: "CRM Starter",
    requirement: "Evaluate CRM workflow",
    budgetRange: "2L-5L",
    decisionMaker: "Yes",
    leadScore: 62,
    probability: "25%",
    nextFollowUp: "2026-05-14",
    lastContacted: "2026-05-10",
    lastActivity: "Created lead",
    preferredChannel: "Email",
    tags: "New, Website",
    notes: "Fresh inbound lead",
  };
  if (kind === "contacts") return {
    contactId: `CT-${String(2100 + id).padStart(4, "0")}`,
    name: `${title} ${id}`,
    company: "New Account",
    title: "Manager",
    department: "Sales",
    email: `contact${id}@newaccount.example`,
    alternateEmail: "",
    phone: "+91 90000 00000",
    mobile: "+91 90000 00001",
    city: "Bengaluru",
    state: "Karnataka",
    country: "India",
    lifecycle: "Opportunity",
    accountType: "Prospect",
    owner: "Ananya Rao",
    status: "Active",
    source: "Manual Entry",
    leadSource: "Website",
    lastContacted: "2026-05-10",
    nextFollowUp: "2026-05-14",
    birthday: "1990-01-01",
    linkedin: "linkedin.com/in/new-contact",
    preferredChannel: "Email",
    emailOptIn: "Yes",
    smsOptIn: "Yes",
    openDeals: 0,
    lifetimeValue: 0,
    supportStatus: "None",
    tags: "New",
    notes: "New CRM contact",
  };
  if (kind === "deals") return { name: `${title} ${id}`, company: "New Account", owner: "Karan Shah", stage: "Prospecting", amount: 500000, probability: "10%", closeDate: "2026-06-15" };
  if (kind === "tickets") return { number: `TCK-${1100 + id}`, subject: "New customer request", priority: "Medium", status: "Open", company: "New Account", owner: "Support Desk" };
  return { name: `${title} ${id}`, owner: "Ananya Rao", status: "New", nextFollowUp: "2026-05-14" };
}

function toLeadRecord(lead: CRMLead): CRMRecord {
  const index = lead.id - 1;
  const designations = ["Founder", "Operations Head", "Director", "Clinic Administrator", "Plant Manager", "Retail Growth Lead", "Managing Partner", "Principal Consultant"];
  const cities = ["Hyderabad", "Kochi", "Pune", "Mumbai", "Chennai", "Bengaluru", "Delhi", "Ahmedabad"];
  const states = ["Telangana", "Kerala", "Maharashtra", "Maharashtra", "Tamil Nadu", "Karnataka", "Delhi", "Gujarat"];
  const campaigns = ["Website Demo", "Referral Connect", "Education Expo", "Healthcare Outreach", "Partner Pipeline", "Retail Growth Ads", "Marketplace Listing", "Social Prospecting"];
  const products = ["CRM Growth", "CRM Starter", "Training Pack", "Support Retainer", "Enterprise Suite", "Marketing Automation", "CRM Growth", "Data Migration"];
  const requirements = [
    "Centralize sales follow-ups and opportunity tracking",
    "Manage site visits, broker leads, and quotation follow-ups",
    "Track admissions enquiries and training partnerships",
    "Improve patient enquiry follow-up and SLA visibility",
    "Connect plant enquiries with ERP implementation pipeline",
    "Automate retail campaigns and lead assignment",
    "Track advisory prospects and compliance-heavy deal notes",
    "Manage consulting proposals and cloud migration leads",
  ];

  return {
    leadId: `LD-${String(1000 + lead.id).padStart(4, "0")}`,
    name: lead.name,
    company: lead.company,
    designation: designations[index] || "Decision Maker",
    email: lead.email,
    phone: lead.phone,
    mobile: String(lead.phone || "").replace("110", "220"),
    city: cities[index] || "Bengaluru",
    state: states[index] || "Karnataka",
    country: "India",
    source: lead.source,
    campaign: campaigns[index] || lead.source,
    status: lead.status,
    rating: lead.rating,
    lifecycleStage: lead.status === "Converted" ? "Customer" : "Lead",
    owner: lead.owner,
    value: lead.value,
    expectedCloseDate: ["2026-05-28", "2026-06-10", "2026-06-02", "2026-06-18", "2026-05-24", "2026-05-30", "2026-06-05", "2026-06-12"][index] || "2026-06-20",
    productInterest: products[index] || "CRM Starter",
    requirement: requirements[index] || "Evaluate CRM workflow",
    budgetRange: lead.value >= 800000 ? "8L+" : lead.value >= 400000 ? "4L-8L" : "2L-4L",
    decisionMaker: ["Yes", "No", "Influencer", "Yes", "Yes", "Influencer", "Yes", "No"][index] || "Yes",
    leadScore: [92, 74, 68, 48, 95, 71, 88, 41][index] || 60,
    probability: lead.rating === "Hot" ? "70%" : lead.rating === "Warm" ? "40%" : "15%",
    nextFollowUp: lead.nextFollowUp,
    lastContacted: lead.lastContacted,
    lastActivity: ["Discovery call", "Referral email", "Event scan", "Intro call", "Partner handoff", "Campaign click", "Marketplace enquiry", "Social DM"][index] || "Follow-up",
    preferredChannel: ["Phone", "Email", "WhatsApp", "Phone", "Email", "Email", "Phone", "LinkedIn"][index] || "Email",
    tags: [lead.rating, lead.source, lead.industry].join(", "),
    notes: requirements[index] || "Qualified CRM enquiry",
  };
}

function toContactRecord(lead: CRMLead): CRMRecord {
  const index = lead.id - 1;
  const leadRecord = toLeadRecord(lead);
  const titles = ["Founder", "Sales Director", "Program Head", "Clinic Admin", "Manufacturing Head", "Retail Lead", "Partner", "Consultant"];
  const departments = ["Leadership", "Sales", "Admissions", "Operations", "Manufacturing", "Marketing", "Advisory", "Consulting"];

  return {
    contactId: `CT-${String(2000 + lead.id).padStart(4, "0")}`,
    name: lead.name,
    company: lead.company,
    title: titles[index] || String(leadRecord.designation),
    department: departments[index] || "Sales",
    email: lead.email,
    alternateEmail: String(lead.email || "").replace("@", ".alt@"),
    phone: lead.phone,
    mobile: String(leadRecord.mobile),
    city: String(leadRecord.city),
    state: String(leadRecord.state),
    country: "India",
    lifecycle: lead.status === "Converted" ? "Customer" : "Opportunity",
    accountType: lead.status === "Converted" ? "Customer" : "Prospect",
    owner: lead.owner,
    status: lead.status === "Converted" ? "Active" : "Open",
    source: lead.source,
    leadSource: lead.source,
    lastContacted: lead.lastContacted,
    nextFollowUp: lead.nextFollowUp,
    birthday: ["1986-02-14", "1990-08-21", "1982-11-02", "1988-04-18", "1979-07-09", "1992-12-05", "1984-09-27", "1991-03-30"][index] || "1990-01-01",
    linkedin: `linkedin.com/in/${lead.name.toLowerCase().replace(/\s+/g, "-")}`,
    preferredChannel: String(leadRecord.preferredChannel),
    emailOptIn: index % 3 === 0 ? "No" : "Yes",
    smsOptIn: index % 2 === 0 ? "Yes" : "No",
    openDeals: lead.status === "Converted" ? 0 : 1,
    lifetimeValue: lead.status === "Converted" ? lead.value : 0,
    supportStatus: lead.status === "Converted" ? "Active SLA" : "None",
    tags: `${lead.rating}, ${lead.industry}`,
    notes: `Primary contact for ${lead.company}`,
  };
}

function descriptionFor(kind: CRMPageKind) {
  const descriptions: Record<CRMPageKind, string> = {
    dashboard: "",
    leads: "Capture, qualify, assign, import, export, and convert leads.",
    contacts: "Manage people, lifecycle stages, follow-up dates, and account links.",
    companies: "Account master data with owners, industries, revenue, and status.",
    deals: "Opportunities with amount, probability, products, quotations, and owners.",
    pipeline: "",
    pipelineSettings: "Multiple sales pipelines, custom stages, probabilities, colors, and win/loss mapping.",
    activities: "Calls, emails, meetings, demos, proposals, and follow-up outcomes.",
    tasks: "CRM task queue for owners, teams, reminders, and related records.",
    calendar: "Follow-ups, meetings, expected close dates, campaigns, and quote expiries.",
    calendarIntegrations: "Google, Outlook, and development calendar sync configuration.",
    webhooks: "Outbound signed events for Zapier, n8n, and CRM integrations.",
    campaigns: "Campaign planning, lead generation, ROI, and conversion tracking.",
    products: "Products used in deals, price books, quotes, and SRM handoff.",
    services: "Service catalog with billing type, default rate, delivery cost, and quote readiness.",
    priceBooks: "Regional and segment price books with product and service pricing.",
    quotes: "Draft, calculate, approve, send, accept, and convert quotes to SRM.",
    quoteBuilder: "Build quote lines, calculate totals, manage versions, and trigger SRM conversion.",
    quoteApprovals: "Review quote approval requests, discount exceptions, and decision comments.",
    cpq: "Configure CPQ validation, discount, bundle, and recommendation rules.",
    guidedSelling: "Question flows and recommendation sets for guided selling.",
    quotations: "Draft, send, accept, reject, and convert quotations.",
    approvalSettings: "Configure deal discount, quotation, stage, high-value, contract, and price approvals.",
    myApprovals: "Review CRM approvals assigned to you and record decisions.",
    duplicates: "Detect and review duplicate CRM leads, contacts, and accounts.",
    territories: "Manage sales territories, rule priority, assigned users, and automatic CRM routing.",
    tickets: "Customer support tickets linked to contacts, companies, and deals.",
    files: "Attachments for leads, contacts, accounts, deals, quotes, and tickets.",
    reports: "",
    automation: "Owner assignment, reminders, quote expiry, critical ticket escalation, and stale lead rules.",
    leadCash: "Lead-to-cash conversion from lead to contact, account, deal, quote, and invoice handoff.",
    forecasting: "Weighted forecasts by owner, team, territory, expected close date, and SRM invoice/collection actuals.",
    targets: "Create sales quotas and compare achieved, invoiced, and collected values.",
    salesPerformance: "Owner performance across pipeline, weighted forecast, activities, conversion, invoices, and collections.",
    funnel: "Lead-to-cash funnel across CRM stages and SRM order, invoice, and receipt milestones.",
    lostAnalysis: "Lost reasons, competitors, lost amount, owner trends, and AI pattern-detection readiness.",
    customer360: "Unified customer view across contacts, companies, deals, tickets, activities, quotations, files, and campaigns.",
    importExport: "Field mapping, duplicate detection, validation preview, rollback, and import history.",
    settings: "Lead sources, statuses, pipelines, quote settings, ticket categories, notifications, and import/export.",
    leadScoring: "Automatic and manual numeric lead scoring from 0 to 100.",
    featureChecklist: "Admin/developer readiness matrix for CRM APIs, frontend surfaces, and integration notes.",
    admin: "CRM roles, permissions, teams, audit logs, templates, and system settings.",
  };
  return descriptions[kind];
}

function actionFor(kind: CRMPageKind) {
  if (["leads", "contacts", "companies", "deals", "activities", "tasks", "campaigns", "products", "services", "priceBooks", "quotes", "quotations", "tickets", "cpq", "guidedSelling"].includes(kind)) return `Create ${pageTitles[kind].replace("CRM ", "").replace(/s$/, "")}`;
  if (kind === "approvalSettings") return "Create workflow";
  if (kind === "pipelineSettings") return "Back to board";
  if (kind === "leadScoring") return "Recalculate all";
  if (kind === "automation") return "Create rule";
  if (kind === "files") return "Upload metadata";
  return undefined;
}

function isBadgeField(key: string) {
  const lower = key.toLowerCase();
  return ["status", "priority", "rating", "stage", "visibility", "type"].some((item) => lower.includes(item));
}

function labelFor(key: string) {
  return key.replace(/_/g, " ").replace(/-/g, " ").replace(/([A-Z])/g, " $1").replace(/\b\w/g, (char) => char.toUpperCase());
}

function isMoneyField(key: string) {
  const lower = key.toLowerCase();
  return ["amount", "value", "revenue", "budget", "price", "total"].some((item) => lower.includes(item));
}

function stageProbability(stage: string) {
  return ({
    Prospecting: 10,
    Qualification: 25,
    "Needs Analysis": 40,
    "Proposal Sent": 55,
    Negotiation: 70,
    "Contract Sent": 85,
    Won: 100,
    Lost: 0,
  } as Record<string, number>)[stage] ?? 0;
}
