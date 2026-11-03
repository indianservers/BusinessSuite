import { toast } from "@/hooks/use-toast";
import { ToastAction } from "@/components/ui/toast";

/** Offer only after a successful write, with a server-checked inverse supplied by the caller. */
export function savedWithUndo(title: string, undo: () => Promise<void>) {
  let busy = false;
  const notice = toast({title, duration: 10000, action: <ToastAction altText={`Undo: ${title}`} onClick={async event => {
    event.preventDefault();
    if (busy) return;
    busy = true;
    notice.update({id: notice.id, title: "Undoing change…", action: undefined, open: true});
    try { await undo(); notice.update({id: notice.id, title: "Change undone", action: undefined, open: true}); }
    catch (error) { notice.update({id: notice.id, title: "Could not undo change", description: error instanceof Error ? error.message : "Refresh the record and try again.", variant: "destructive", action: undefined, open: true}); }
  }}>Undo</ToastAction>});
}
