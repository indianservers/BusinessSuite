import { useRef, useState, type FormEvent } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { UserPlus, X } from "lucide-react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PhoneInput } from "@/lib/validation/PhoneInput";

export type PosCustomerRecord = { id: number; name: string; phone: string | null; phone_country_code?: string | null; email: string | null };

export default function QuickAddCustomer({ onClose, onCreated }: { onClose: () => void; onCreated: (customer: PosCustomerRecord) => void }) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [countryCode, setCountryCode] = useState("+91");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submitting = useRef(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post<PosCustomerRecord>("/srm/business/customers", { name: name.trim(), phone: phone.trim() || null, phone_country_code: countryCode, email: email.trim() || null });
      onCreated(data);
    } catch (error) {
      const detail = (error as { response?: { data?: { detail?: string | { msg?: string }[] } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map(issue => issue.msg).filter(Boolean).join(" ") : "Unable to save the customer. Please try again.");
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  return <Dialog.Root open onOpenChange={open => { if (!open && !busy) onClose(); }}><Dialog.Portal>
    <Dialog.Overlay className="fixed inset-0 z-[100] bg-black/60"/>
    <Dialog.Content className="fixed left-1/2 top-1/2 z-[101] max-h-[90dvh] w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 overflow-auto rounded-xl border bg-background p-6 text-foreground shadow-xl">
      <div className="flex items-start justify-between gap-4">
        <div><Dialog.Title className="flex items-center gap-2 text-lg font-semibold"><UserPlus size={20}/>Quick add customer</Dialog.Title><Dialog.Description className="mt-1 text-sm text-muted-foreground">Save their details and select them for this sale and any follow-ups.</Dialog.Description></div>
        <Dialog.Close asChild><Button type="button" variant="ghost" size="icon" aria-label="Close quick add customer" disabled={busy}><X size={18}/></Button></Dialog.Close>
      </div>
      <form className="mt-5 space-y-4" onSubmit={submit}>
        <fieldset disabled={busy} className="space-y-4">
          <label className="block space-y-1 text-sm font-medium">Customer name<Input autoFocus required maxLength={180} autoComplete="name" value={name} onChange={e => setName(e.target.value)} placeholder="Full name"/></label>
          <div className="space-y-1 text-sm font-medium"><span>Phone number</span><PhoneInput value={phone} countryCode={countryCode} onChange={setPhone} onCountryCodeChange={setCountryCode} disabled={busy}/></div>
          <label className="block space-y-1 text-sm font-medium">Email<Input type="email" maxLength={150} autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="customer@example.com"/></label>
        </fieldset>
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        <div className="flex justify-end gap-2"><Button type="button" variant="outline" disabled={busy} onClick={onClose}>Cancel</Button><Button type="submit" disabled={busy || !name.trim()}>{busy ? "Saving…" : "Save & select customer"}</Button></div>
      </form>
    </Dialog.Content>
  </Dialog.Portal></Dialog.Root>;
}
