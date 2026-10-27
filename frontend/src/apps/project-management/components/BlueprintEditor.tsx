import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { ArrowDown, ArrowUp, Plus, Trash2, X } from "lucide-react";
import { RichTextField } from "@/components/rich-text/LazyRichText";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export type BlueprintDraft = { name: string; project_id: number; description: string; task_titles: string[] };

export default function BlueprintEditor({ initial, saved, projects, busy, canEdit, manages, enabled, error, onClose, onUse, onSave }: {
  initial: BlueprintDraft;
  saved: boolean;
  projects: { id: number; name: string }[];
  busy: boolean;
  canEdit: boolean;
  manages: boolean;
  enabled: boolean;
  error: string;
  onClose: () => void;
  onUse: (draft: BlueprintDraft) => void;
  onSave: (draft: BlueprintDraft) => void;
}) {
  const [draft, setDraft] = useState(() => ({ ...initial, task_titles: [...initial.task_titles] }));
  const [attempted, setAttempted] = useState(false);
  const invalid = !draft.name.trim() || !draft.project_id || !draft.task_titles.length || draft.task_titles.length > 20
    || draft.task_titles.some(title => !title.trim() || title.trim().length > 220);
  const clean = () => ({ ...draft, name: draft.name.trim(), task_titles: draft.task_titles.map(title => title.trim()) });
  function move(index: number, offset: number) {
    const titles = [...draft.task_titles];
    [titles[index], titles[index + offset]] = [titles[index + offset], titles[index]];
    setDraft({ ...draft, task_titles: titles });
  }

  return <Dialog.Root open onOpenChange={open => { if (!open && !busy) onClose(); }}><Dialog.Portal>
    <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
    <Dialog.Content onEscapeKeyDown={event => { if (busy) event.preventDefault(); }} onInteractOutside={event => event.preventDefault()} className="fixed left-1/2 top-1/2 z-50 max-h-[90dvh] w-[calc(100%_-_2rem)] max-w-3xl -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-xl border bg-background p-5 shadow-xl sm:p-6">
      <div className="flex items-start justify-between gap-3"><Dialog.Title className="text-xl font-semibold">{saved ? "Customize workspace blueprint" : "Customize blueprint"}</Dialog.Title><Button type="button" size="icon" variant="ghost" disabled={busy} aria-label="Close blueprint editor" onClick={onClose}><X className="h-4 w-4" /></Button></div>
      <Dialog.Description className="mt-2 text-sm text-muted-foreground">{saved ? "Use your edits for this run, or save changes to the reusable workspace version." : "Make a personal plan from this starting point. Saving a workspace copy keeps the built-in blueprint available for everyone."}</Dialog.Description>
      {error && <p role="alert" className="mt-3 rounded border border-destructive p-3 text-sm text-destructive">{error}</p>}
      <form className="mt-5 space-y-5" onSubmit={event => { event.preventDefault(); setAttempted(true); if (!invalid) onUse(clean()); }}>
        <fieldset disabled={busy || !canEdit} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2"><label className="text-sm font-medium">Blueprint name<Input required maxLength={120} aria-label="Blueprint name" value={draft.name} onChange={event => setDraft({ ...draft, name: event.target.value })} /></label>
            <label className="text-sm font-medium">Destination project<select required aria-label="Blueprint destination project" disabled={saved} className="mt-1 min-h-11 w-full rounded-md border bg-background px-3 text-sm" value={draft.project_id || ""} onChange={event => setDraft({ ...draft, project_id: Number(event.target.value) })}><option value="" disabled>Choose a project</option>{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label></div>
          {!projects.length && <p className="text-sm text-muted-foreground">Create a project in this workspace before saving or using a blueprint.</p>}
          <label className="block text-sm font-medium">Instructions and definition of done<RichTextField aria-label="Blueprint instructions" maxLength={4000} value={draft.description} onChange={event => setDraft({ ...draft, description: event.target.value })} /></label>
          <div className="flex items-center justify-between gap-2"><h3 className="font-semibold">Task checklist</h3><span className="text-sm text-muted-foreground">{draft.task_titles.length} / 20 tasks</span></div>
          <ol className="space-y-3">{draft.task_titles.map((title, index) => <li key={index} className="rounded-lg border p-3">
            <label className="block text-xs font-medium text-muted-foreground">Task {index + 1}<Input required maxLength={220} aria-label={`Blueprint task ${index + 1}`} className="mt-1" value={title} onChange={event => setDraft({ ...draft, task_titles: draft.task_titles.map((item, i) => i === index ? event.target.value : item) })} /></label>
            <div className="mt-2 flex justify-end gap-1"><Button type="button" variant="ghost" size="icon" disabled={index === 0} aria-label={`Move task ${index + 1} up`} onClick={() => move(index, -1)}><ArrowUp className="h-4 w-4" /></Button><Button type="button" variant="ghost" size="icon" disabled={index === draft.task_titles.length - 1} aria-label={`Move task ${index + 1} down`} onClick={() => move(index, 1)}><ArrowDown className="h-4 w-4" /></Button><Button type="button" variant="ghost" size="icon" disabled={draft.task_titles.length === 1} aria-label={`Remove task ${index + 1}`} onClick={() => setDraft({ ...draft, task_titles: draft.task_titles.filter((_, i) => i !== index) })}><Trash2 className="h-4 w-4" /></Button></div>
          </li>)}</ol>
          <Button type="button" variant="outline" disabled={draft.task_titles.length >= 20} onClick={() => setDraft({ ...draft, task_titles: [...draft.task_titles, ""] })}><Plus className="h-4 w-4" />Add task</Button>
        </fieldset>
        {attempted && invalid && <p role="alert" className="text-sm text-destructive">Choose a project, enter a name, and provide 1–20 nonempty task titles (up to 220 characters each).</p>}
        <div className="rounded-lg border bg-muted/30 p-3 text-sm text-muted-foreground"><strong className="text-foreground">Before you create:</strong> This adds {draft.task_titles.length} new tasks to {projects.find(project => project.id === draft.project_id)?.name || "your selected project"}. Assign owners, dates, and dependencies afterward. Saving a blueprint creates no tasks.</div>
        {!canEdit && <p className="text-sm text-muted-foreground">Guests can preview blueprints. Workspace members can customize and create tasks.</p>}
        {saved && !enabled && <p className="text-sm text-muted-foreground">This blueprint is paused. An owner or admin can enable it from Manage workspace blueprints.</p>}
        {canEdit && !manages && <p className="text-sm text-muted-foreground">Your edits apply to this run. Owners and admins can save reusable workspace versions.</p>}
        <div className="flex flex-wrap justify-end gap-3 border-t pt-4"><Button type="button" variant="outline" disabled={busy} onClick={onClose}>Cancel</Button>{manages && <Button type="button" variant="outline" disabled={busy || !projects.length} onClick={() => { setAttempted(true); if (!invalid) onSave(clean()); }}>{saved ? "Save changes" : "Save workspace copy"}</Button>}<Button type="submit" disabled={busy || !canEdit || !enabled || !projects.length}>{busy ? "Working…" : `Create ${draft.task_titles.length} tasks`}</Button></div>
      </form>
    </Dialog.Content>
  </Dialog.Portal></Dialog.Root>;
}
