import { lazy, Suspense, useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";

const FieldLibrary = lazy(() => import("../pages/CustomFieldManagerPage"));

/** Keep the authenticated tab and the owning record's unsaved draft mounted. */
export default function ManageCustomFields({ entity, onChanged }: { entity: "task" | "project"; onChanged: () => void }) {
  const [open, setOpen] = useState(false);
  return <>
    <button type="button" aria-label={`Manage ${entity} custom fields`} className="text-xs text-primary" onClick={() => setOpen(true)}>Manage <Plus className="inline h-3 w-3" /></button>
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-6xl" style={{zIndex:181}} overlayClassName="z-[180]" onPointerDownOutside={event => event.preventDefault()} onSubmit={event => event.stopPropagation()}>
        <DialogTitle>Manage {entity} custom fields</DialogTitle>
        <DialogDescription>Your draft stays open. Added fields become available in the form automatically.</DialogDescription>
        <Suspense fallback={<p role="status">Loading field library…</p>}>
          <FieldLibrary embeddedEntity={entity} onChanged={onChanged} />
        </Suspense>
        <div className="flex justify-end"><Button type="button" variant="outline" onClick={() => setOpen(false)}>Done</Button></div>
      </DialogContent>
    </Dialog>
  </>;
}
