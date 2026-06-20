export type SRMRecord = Record<string, unknown>;

export type SRMViewKind =
  | "dashboard"
  | "salesOrders"
  | "posSessions"
  | "cashierClosing"
  | "posReturns"
  | "contracts"
  | "engagements"
  | "billingPlans"
  | "invoiceDrafts"
  | "invoices"
  | "collections"
  | "revenueRecognition"
  | "profitability"
  | "customer360"
  | "reports"
  | "settings";
