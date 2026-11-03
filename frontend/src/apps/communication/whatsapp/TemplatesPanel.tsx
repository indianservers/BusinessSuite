import { useState } from "react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { whatsappBase as base, whatsappError, type Template } from "./types";

export default function TemplatesPanel({ templates, admin, refresh }: { templates: Template[]; admin: boolean; refresh: () => Promise<void> }) {
  const [draft, setDraft] = useState({ name: "", language: "en_US", category: "UTILITY", body: "", samples: "" });
  const [busy, setBusy] = useState(false), [notice, setNotice] = useState("");
  async function submit() {
    setBusy(true); setNotice("");
    try {
      const { samples, ...fields } = draft;
      await api.post(base + "/templates", { ...fields, sampleValues: samples ? samples.split("\n").map(s => s.trim()) : [] });
      setNotice("Submitted to Meta for review. You can send it after Meta approves it.");
      await refresh();
    } catch (error) { setNotice(whatsappError(error)); }
    finally { setBusy(false); }
  }
  return <div className="space-y-5">
    <p className="text-sm text-muted-foreground">These are templates from the connected Meta account. The hello_world sample is Meta’s demonstration template. Create your own approved templates for Indian Servers or your customer business.</p>
    <div className="grid gap-3 md:grid-cols-2">{templates.map(template => <article key={template.id || template.name + template.language} className="rounded-xl border p-4">
      <div className="flex flex-wrap justify-between gap-2"><h3 className="font-medium">{template.name}</h3><span className="text-xs">{template.status}</span></div>
      <p className="mt-1 text-xs text-muted-foreground">{template.language} · {template.category}</p>
      <p className="mt-3 whitespace-pre-wrap text-sm">{template.components?.find(c => c.type === "BODY")?.text}</p>
    </article>)}</div>
    {!templates.length && <p className="text-sm">No templates loaded from Meta.</p>}
    {admin && <section className="space-y-3 rounded-xl border p-4">
      <h3 className="font-medium">Submit a text template</h3>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-sm">Name<Input placeholder="order_update" value={draft.name} onChange={e => setDraft({ ...draft, name: e.target.value })} /></label>
        <label className="text-sm">Language code<Input value={draft.language} onChange={e => setDraft({ ...draft, language: e.target.value })} /></label>
        <label className="text-sm">Category<select className="h-10 w-full rounded-md border bg-background px-3" value={draft.category} onChange={e => setDraft({ ...draft, category: e.target.value })}><option value="UTILITY">Utility</option><option value="MARKETING">Marketing</option></select></label>
      </div>
      <label className="block text-sm">Message body<textarea className="mt-1 min-h-28 w-full rounded-md border bg-background p-3" maxLength={1024} placeholder="Hello {{1}}, your service request {{2}} has been updated." value={draft.body} onChange={e => setDraft({ ...draft, body: e.target.value })} /></label>
      <label className="block text-sm">Sample values, one per line in placeholder order<textarea className="mt-1 w-full rounded-md border bg-background p-3" value={draft.samples} onChange={e => setDraft({ ...draft, samples: e.target.value })} /></label>
      <Button disabled={busy || !draft.name || !draft.body.trim()} onClick={() => void submit()}>{busy ? "Submitting…" : "Submit to Meta"}</Button>
      {notice && <p role="status" className="text-sm">{notice}</p>}
    </section>}
  </div>;
}
