import { useEffect, useState } from "react";
import CompactForm from "@/components/forms/CompactForm";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { api } from "@/services/api";
import { errorMessage } from "./leads/api";

type Stage = {
  id: number;
  name: string;
  is_lost: boolean;
  approval_required?: boolean;
  required: string[];
  recommended_actions: string;
  completion_criteria: string;
};

const numericFields = ["company_id", "contact_id", "amount"];
const fieldLabel = (field: string) => field.replace(/_/g, " ");

export default function CRMStageDialog({ id, targetStage, close, saved }: {
  id: number; targetStage?: number; close: () => void; saved: () => void;
}) {
  const [version, setVersion] = useState<number>();
  const [stages, setStages] = useState<Stage[]>([]);
  const [selected, setSelected] = useState(targetStage || 0);
  const [values, setValues] = useState<Record<string, string>>({});
  const [reason, setReason] = useState("");
  const [review, setReview] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const stage = stages.find(item => item.id === selected);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    void api.get(`/crm/productivity/deals/${id}/stages`).then(({ data }) => {
      if (!active) return;
      setVersion(data.version);
      setStages(data.stages);
      setSelected(targetStage || data.current_stage_id);
      setValues(data.values || {});
    }).catch(err => {
      if (active) setError(errorMessage(err));
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [id, targetStage]);

  async function move() {
    if (loading || busy || !stage || (stage.is_lost && reason.trim().length < 5)) return;
    setBusy(true);
    setError("");
    try {
      const corrections = Object.fromEntries(Object.entries(values)
        .filter(([field, value]) => value !== "" && stage.required.includes(field))
        .map(([field, value]) => [
          field, numericFields.includes(field) ? Number(value)
            : field === "next_follow_up_at" ? new Date(value).toISOString() : value,
        ]));
      await api.post(`/crm/productivity/deals/${id}/transition`, {
        expected_version: version,
        stage_id: selected,
        corrections,
        lost_reason: reason,
        reactivate_at: review ? new Date(review).toISOString() : null,
      });
      saved();
      close();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={open => { if (!open && !busy) close(); }}>
      <DialogContent overlayClassName="z-[110]" className="ed-deal-decision z-[111]">
        <header className="ed-deal-decision-header">
          <DialogTitle>Review deal stage move</DialogTitle>
          <DialogDescription>Deal #{id}</DialogDescription>
        </header>
        <CompactForm className="ed-deal-decision-form" compactTabs={false} onSubmit={event => {
          event.preventDefault();
          void move();
        }}>
          <div className="ed-deal-decision-fields">
            <label>Destination stage
              <NativeSelect aria-label="Destination stage" value={selected || ""} disabled={loading || busy} onChange={event => setSelected(Number(event.target.value))}>
                <option value="">{loading ? "Loading stages…" : "Choose stage"}</option>
                {stages.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}
              </NativeSelect>
            </label>
            {stage && <>
              {stage.approval_required && <p className="ed-decision-notice">An approved deal approval request is required before entry.</p>}
              {(stage.recommended_actions || stage.completion_criteria) && (
                <dl className="ed-stage-guidance">
                  {stage.recommended_actions && <div><dt>Recommended actions</dt><dd>{stage.recommended_actions}</dd></div>}
                  {stage.completion_criteria && <div><dt>Completion criteria</dt><dd>{stage.completion_criteria}</dd></div>}
                </dl>
              )}
              {stage.required.map(field => (
                <label key={field}>{fieldLabel(field)}
                  <Input required value={values[field] || ""} step={field === "amount" ? "0.01" : undefined}
                    type={field.includes("date") ? "date" : field === "next_follow_up_at" ? "datetime-local" : numericFields.includes(field) ? "number" : "text"}
                    onChange={event => setValues(current => ({ ...current, [field]: event.target.value }))}
                  />
                </label>
              ))}
              {stage.is_lost && <>
                <label>Meaningful lost reason
                  <Input required minLength={5} maxLength={1000} value={reason} onChange={event => setReason(event.target.value)} />
                </label>
                <label>Reactivation review date
                  <Input type="datetime-local" value={review} onChange={event => setReview(event.target.value)} />
                </label>
              </>}
            </>}
            {error && <p role="alert" className="ed-decision-error">{error}</p>}
          </div>
          <footer className="ed-deal-decision-submit">
            <Button type="button" variant="outline" disabled={busy} onClick={close}>Cancel</Button>
            <Button type="submit" disabled={busy || loading || !stage || (stage.is_lost && reason.trim().length < 5)}>
              {busy ? "Applying…" : "Apply reviewed stage move"}
            </Button>
          </footer>
        </CompactForm>
      </DialogContent>
    </Dialog>
  );
}
