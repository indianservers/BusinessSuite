import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import ConnectionPanel from "./whatsapp/ConnectionPanel";
import TemplatesPanel from "./whatsapp/TemplatesPanel";
import Composer from "./whatsapp/Composer";
import LinkConversation from "./whatsapp/LinkConversation";
import ProfilePanel from "./whatsapp/ProfilePanel";
import SentMessages from "./whatsapp/SentMessages";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { whatsappBase as base, whatsappError, type Status, type Template, type Contact, type Message } from "./whatsapp/types";

export default function WhatsAppCloudPanel() {
  const user = useAuthStore(state => state.user);
  const scope = `${user?.id}:${sessionStorage.getItem("suite-organization") || "default"}:${sessionStorage.getItem("suite-branch") || "default"}`;
  return <WhatsAppWorkspace key={scope} scope={scope} />;
}
function WhatsAppWorkspace({ scope }: { scope: string }) {
  const cache = useQueryClient();
  const location=useLocation(),navigate=useNavigate();
  const [params,setParams]=useSearchParams();
  const routeTab=location.pathname.split('/').pop() || '';
  const tab=['inbox','templates','sent','profile','settings'].includes(routeTab)?routeTab:'send';
  const selected=/^[1-9]\d*$/.test(params.get('conversation')||'')?Number(params.get('conversation')):null;
  const setTab=(key:string)=>navigate(key==='send'?'/crm/whatsapp':`/crm/whatsapp/${key}`);
  const setSelected=(id:number)=>setParams({conversation:String(id)});
  const [before, setBefore] = useState<number | undefined>(), [historyBefore, setHistoryBefore] = useState<number | undefined>();
  const status = useQuery({ queryKey: ["whatsapp", scope, "status"], queryFn: async () => (await api.get<Status>(base + "/status")).data });
  const templates = useQuery({ queryKey: ["whatsapp", scope, "templates"], enabled: !!status.data?.configured,
    queryFn: async () => (await api.get<{ items: Template[]; hasMore: boolean }>(base + "/templates")).data });
  const conversations = useQuery({ queryKey: ["whatsapp", scope, "conversations", before], enabled: !!status.data?.configured && tab === "inbox", refetchInterval: tab === "inbox" ? 15000 : false,
    queryFn: async () => (await api.get<{ items: Contact[]; nextBefore: number | null }>(base + "/conversations", { params: { before } })).data });
  const history = useQuery({ queryKey: ["whatsapp", scope, "history", selected, historyBefore], enabled: selected !== null && tab === "inbox", refetchInterval: tab === "inbox" ? 10000 : false,
    queryFn: async () => (await api.get<{ contact: Contact; items: Message[]; nextBefore: number | null }>(base + `/conversations/${selected}/messages`, { params: { before: historyBefore } })).data });
  async function refresh() { await cache.invalidateQueries({ queryKey: ["whatsapp", scope] }); }
  if (status.isPending) return <p className="p-4 text-sm">Loading WhatsApp account…</p>;
  if (status.isError || !status.data) return <p role="alert" className="p-4 text-sm">{whatsappError(status.error)}</p>;
  const account = status.data;
  return <section className="space-y-5">
    <header className="rounded-xl border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-xl font-semibold">WhatsApp Business</h2>
        <p className="mt-1 text-sm text-muted-foreground">{account.connection?.businessName || "Business Suite"} · {account.connection?.displayNumber || (account.configured ? "Deployment sender connected" : "No active sender")}</p></div>
        <span className="rounded-full border px-3 py-1 text-xs">{account.connection?.status.replace(/_/g, " ") || (account.configured ? "connected" : "setup required")}</span></div>
      <p className="mt-3 text-sm text-muted-foreground">Connect each organization’s own account. Customers pay Meta for messaging; Indian Servers provides the CRM and API software.</p>
      <p className="mt-2 text-xs text-muted-foreground">Select a writable branch in the top bar before sending. Account settings controls the branch for new inbound conversations.</p>
      {!account.webhookConfigured && <p className="mt-2 text-sm text-destructive">Webhook verification settings are incomplete for this deployment.</p>}
    </header>
    <nav aria-label="WhatsApp workspace" className="flex flex-wrap gap-2">{[["send", "Send message"], ["inbox", "Received messages"], ["sent", "Sent & delivery"], ["templates", "Meta templates"], ["profile", "Business profile"], ...(account.canAdmin ? [["settings", "Account settings"]] : [])].map(([key, label]) => <Button key={key} variant={tab === key ? "default" : "outline"} onClick={() => setTab(key)}>{label}</Button>)}<Button variant="ghost" onClick={() => void refresh()}>Refresh</Button></nav>
    {!account.configured && tab !== "settings" && <p className="rounded-xl border p-4 text-sm">An organization administrator must connect and verify a WhatsApp sender in Account settings.</p>}
    {templates.isError && tab !== "settings" && <p role="alert" className="text-sm">Templates could not load: {whatsappError(templates.error)}</p>}
    {templates.data?.hasMore && tab !== "settings" && <p className="text-xs text-muted-foreground">Showing the first 100 Meta templates.</p>}
    {account.configured && tab === "send" && <Composer scope={scope} templates={templates.data?.items || []} admin={account.canAdmin} refresh={refresh} />}
    {account.configured && tab === "templates" && <TemplatesPanel templates={templates.data?.items || []} admin={account.canAdmin} refresh={refresh} />}
    {account.configured && tab === "sent" && <SentMessages scope={scope} />}
    {account.configured && tab === "profile" && <ProfilePanel scope={scope} admin={account.canAdmin} />}
    {tab === "settings" && account.canAdmin && <ConnectionPanel status={account} refresh={refresh} />}
    {account.configured && tab === "inbox" && <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
      <aside className="space-y-2 rounded-xl border p-3"><h3 className="mb-3 font-medium">Conversations</h3>
        {conversations.isPending && <p className="text-sm">Loading conversations…</p>}
        {conversations.isError && <p role="alert" className="text-sm">{whatsappError(conversations.error)}</p>}
        {conversations.data?.items.map(contact => <button key={contact.id} className={`block w-full rounded-lg border p-3 text-left text-sm ${selected === contact.id ? "bg-muted" : ""}`} onClick={() => { setSelected(contact.id); setHistoryBefore(undefined); }}><strong className="block">{contact.name || "+" + contact.recipient}</strong><span className="text-xs">+{contact.recipient} · {contact.consent.replace(/_/g, " ")}</span></button>)}
        {!conversations.isPending && !conversations.data?.items.length && <p className="text-sm">No received conversations in this branch yet. Reply from a customer’s WhatsApp phone to the connected business number to start one. Only messages delivered to the webhook after setup appear here; WhatsApp does not provide this app with earlier chat history.</p>}
        <div className="flex gap-2">{before && <Button size="sm" variant="outline" onClick={() => setBefore(undefined)}>Latest</Button>}{conversations.data?.nextBefore && <Button size="sm" variant="outline" onClick={() => setBefore(conversations.data!.nextBefore!)}>Older</Button>}</div>
      </aside>
      <div className="space-y-4">{!selected && <p className="rounded-xl border p-4 text-sm">Choose a conversation to view replies and delivery updates.</p>}
        {history.isError && <p role="alert" className="text-sm">{whatsappError(history.error)}</p>}
        {history.data && <><div className="space-y-3 rounded-xl border p-4"><div className="flex flex-wrap justify-between gap-2"><h3 className="font-medium">{history.data.contact.name || "+" + history.data.contact.recipient}</h3><span className="text-xs">{history.data.contact.entityType ? `CRM ${history.data.contact.entityType} ${history.data.contact.entityId}` : "Unlinked conversation · administrator access"}</span></div>
          <div className="flex gap-2">{historyBefore && <Button size="sm" variant="outline" onClick={() => setHistoryBefore(undefined)}>Latest messages</Button>}{history.data.nextBefore && <Button size="sm" variant="outline" onClick={() => setHistoryBefore(history.data!.nextBefore!)}>Older messages</Button>}</div>
          {history.data.items.map(message => <article key={message.id} className={`max-w-[90%] rounded-xl border p-3 ${message.direction === "outbound" ? "ml-auto bg-muted" : ""}`}><p className="whitespace-pre-wrap break-words text-sm">{message.body}</p><p className="mt-2 text-xs text-muted-foreground">{message.direction} · {message.status.replace(/_/g, " ")} · {new Date(message.createdAt).toLocaleString()}{message.errorCode ? ` · Meta ${message.errorCode}` : ""}</p></article>)}
        </div>{account.canAdmin && <LinkConversation key={`link-${selected}`} contactId={history.data.contact.id} refresh={refresh} />}<Composer key={selected} scope={scope} contact={history.data.contact} templates={templates.data?.items || []} admin={account.canAdmin} refresh={refresh} /></>}
      </div>
    </div>}
  </section>;
}
