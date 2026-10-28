import { useRefreshableEffect } from "@/lib/page-refresh";
import { useEffect, useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { Bootstrap, errorMessage, leadsApi } from "./api";

export default function LeadEmployeeAssignment({
  leadId,
  ownerId,
  onAssigned,
}: {
  leadId: number;
  ownerId?: number;
  onAssigned: () => void;
}) {
  const id = useId();
  const [directory, setDirectory] = useState<Bootstrap>();
  const [selected, setSelected] = useState(String(ownerId || ""));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useRefreshableEffect(() => {
    let active = true;
    leadsApi
      .bootstrap()
      .then((r) => {
        if (active) setDirectory(r.data);
      })
      .catch((err) => {
        if (active) setError(errorMessage(err));
      });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    setSelected(String(ownerId || ""));
  }, [ownerId]);
  const current = directory?.owners.find((owner) => owner.id === ownerId);
  return (
    <div className="flex flex-wrap items-center gap-2">
      <label htmlFor={id}>Assigned employee</label>
      {directory?.canManage ? (
        <>
          <select
            id={id}
            className="max-w-[260px] rounded-md border border-border bg-background px-2 py-1 text-sm text-foreground"
            value={selected}
            disabled={busy}
            onChange={(event) => setSelected(event.target.value)}
          >
            <option value="" disabled>
              Unassigned — choose employee
            </option>
            {!!ownerId && !current && (
              <option value={ownerId} disabled>
                Current assignee (unavailable)
              </option>
            )}
            {directory.owners.map((owner) => (
              <option key={owner.id} value={owner.id}>
                {owner.name}
              </option>
            ))}
          </select>
          <Button
            size="sm"
            variant="outline"
            disabled={busy || !selected || selected === String(ownerId || "")}
            onClick={async () => {
              setBusy(true);
              setError("");
              try {
                await leadsApi.update(leadId, {
                  values: { owner_user_id: Number(selected) },
                });
                onAssigned();
              } catch (err) {
                setError(errorMessage(err));
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy ? "Assigning…" : "Assign employee"}
          </Button>
        </>
      ) : (
        <span>{current?.name || (ownerId ? "Assigned" : "Unassigned")}</span>
      )}
      {error && (
        <span className="text-destructive" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
