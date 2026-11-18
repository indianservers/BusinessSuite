import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export default function SalaryAdvanceReviewButtons({ item, canReview, busy, onReview }: {
  item: { id: number; status: string; payroll_record_id?: number | null };
  canReview: boolean;
  busy: boolean;
  onReview: (value: { id: number; action: "approve" | "reject" }) => void;
}) {
  const pending = String(item.status || "").toLowerCase() === "pending" && item.payroll_record_id == null;
  const disabled = !canReview || busy || !pending;
  return <div className="flex gap-2"><Badge variant="outline">{item.status}</Badge><Button type="button" size="sm" variant="outline" disabled={disabled} onClick={() => onReview({ id: item.id, action: "approve" })}>Approve</Button><Button type="button" size="sm" variant="outline" disabled={disabled} onClick={() => onReview({ id: item.id, action: "reject" })}>Reject</Button></div>;
}
