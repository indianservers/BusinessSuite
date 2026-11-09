import { useMobile } from "@/components/mobile/useMobile";
import { MobileDisclosure, MobileSheet } from "@/components/mobile/MobilePrimitives";
import { AlertDialog, AlertDialogContent, AlertDialogTitle, AlertDialogDescription, AlertDialogCancel, AlertDialogAction } from "@/components/ui/alert-dialog";
import "./helpdesk-mobile.css";
import { standardRecordGroups } from "@/shared/data-grid/record-group-fields";
import { SmartCreateModal } from "@/shared/creation/SmartCreateModal";
import GroupedRecords from "@/shared/data-grid/GroupedRecords";
import { NativeSelect } from "@/components/ui/native-select";
import CompactForm from "@/components/forms/CompactForm";
import RichTextEditor, { RichTextField, RichTextContent, richTextPlainText } from "@/components/rich-text/LazyRichText";
import { useCreateIntent } from "@/hooks/use-create-intent";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BarChart3, LifeBuoy, MessageSquare, Plus, RefreshCw, Send, Star } from "lucide-react";
import { Controller, useForm } from "react-hook-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/hooks/use-toast";
import { statusColor, formatDateTime } from "@/lib/utils";
import { usePageTitle } from "@/hooks/use-page-title";
import { helpdeskApi } from "@/services/api";
import { NOTIF_UNREAD_KEY } from "@/components/layout/Topbar";

interface Ticket {
  id: number;
  ticket_number: string;
  subject: string;
  description: string;
  category?: { name: string };
  priority: string;
  status: string;
  created_at: string;
  updated_at: string;
  resolution_due_at?: string;
  satisfaction_rating?: number;
}

interface Reply {
  id: number;
  message: string;
  is_internal: boolean;
  created_at: string;
  author?: { first_name: string; last_name: string };
}

interface TicketForm {
  subject: string;
  description: string;
  priority: string;
  category_id?: number;
}

interface HelpdeskAnalytics {
  total: number;
  open: number;
  resolved: number;
  sla_breached: number;
  due_soon: number;
  first_response_breached: number;
  csat_average: number;
  csat_responses: number;
  by_status: Record<string, number>;
}

const PRIORITIES = ["Low", "Medium", "High", "Critical"];
const STATUSES = ["Open", "In Progress", "Resolved", "Closed"];

export default function HelpdeskPage() {
  usePageTitle("Helpdesk");
  const phone = useMobile(480);
  const [discardReply, setDiscardReply] = useState(false);
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  useCreateIntent(kind => { if (kind === "ticket") setShowForm(true); });
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);
  const [replyText, setReplyText] = useState("");
  const [statusFilter, setStatusFilter] = useState("Open");

  const ticketsQuery = useQuery({
    queryKey: ["tickets", statusFilter],
    queryFn: () => helpdeskApi.tickets({ status: statusFilter || undefined }).then((r) => r.data as Ticket[]),
  });

  const categoriesQuery = useQuery({
    queryKey: ["helpdesk-categories"],
    queryFn: () => helpdeskApi.categories().then((r) => r.data),
  });

  const analyticsQuery = useQuery({
    queryKey: ["helpdesk-analytics"],
    queryFn: () => helpdeskApi.analytics().then((r) => r.data as HelpdeskAnalytics),
    retry: false,
  });

  const slaQuery = useQuery({
    queryKey: ["helpdesk-sla-breaches"],
    queryFn: () => helpdeskApi.slaBreaches().then((r) => r.data as Ticket[]),
    retry: false,
  });

  const repliesQuery = useQuery({
    queryKey: ["ticket-replies", selectedTicket?.id],
    queryFn: () => helpdeskApi.getReplies(selectedTicket!.id).then((r) => r.data as Reply[]),
    enabled: !!selectedTicket,
  });

  const { data: tickets, isLoading, refetch } = ticketsQuery;
  const { data: categories } = categoriesQuery;
  const { data: analytics } = analyticsQuery;
  const { data: slaBreaches } = slaQuery;
  const { data: replies, refetch: refetchReplies } = repliesQuery;

  const { control: editorControl, register, handleSubmit, reset, formState: { errors } } = useForm<TicketForm>({
    defaultValues: { priority: "Medium" },
  });

  const createMutation = useMutation({
    mutationFn: (data: TicketForm) =>
      helpdeskApi.createTicket({
        subject: data.subject,
        description: data.description,
        priority: data.priority,
        category_id: data.category_id ? Number(data.category_id) : undefined,
      }),
    onSuccess: () => {
      toast({ title: "Ticket raised successfully" });
      reset();
      setShowForm(false);
      refetch();
      qc.invalidateQueries({ queryKey: ["helpdesk-analytics"] });
      qc.invalidateQueries({ queryKey: NOTIF_UNREAD_KEY });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed";
      toast({ title: "Error", description: msg, variant: "destructive" });
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) => helpdeskApi.updateStatus(id, status),
    onSuccess: (_, { id, status }) => {
      toast({ title: `Ticket ${status}` });
      refetch();
      qc.invalidateQueries({ queryKey: ["helpdesk-analytics"] });
      qc.invalidateQueries({ queryKey: ["helpdesk-sla-breaches"] });
      qc.invalidateQueries({ queryKey: NOTIF_UNREAD_KEY });
      setSelectedTicket((ticket) => ticket && (!phone || ticket.id === id) ? { ...ticket, status } : ticket);
    },
  });

  const replyMutation = useMutation({
    mutationFn: (message: string) => helpdeskApi.addReply(selectedTicket!.id, message),
    onSuccess: () => {
      setReplyText("");
      refetchReplies();
      qc.invalidateQueries({ queryKey: NOTIF_UNREAD_KEY });
    },
    onError: () => toast({ title: "Failed to send reply", variant: "destructive" }),
  });

  const csatMutation = useMutation({
    mutationFn: ({ id, rating }: { id: number; rating: number }) => helpdeskApi.submitCsat(id, rating),
    onSuccess: (_, { id, rating }) => {
      toast({ title: "CSAT captured", description: `${rating}/5 rating saved.` });
      refetch();
      qc.invalidateQueries({ queryKey: ["helpdesk-analytics"] });
      setSelectedTicket((ticket) => ticket && (!phone || ticket.id === id) ? { ...ticket, satisfaction_rating: rating } : ticket);
    },
    onError: () => toast({ title: "Unable to save CSAT", variant: "destructive" }),
  });

  const priorityBadge: Record<string, string> = {
    Low: "bg-green-100 text-green-800",
    Medium: "bg-yellow-100 text-yellow-800",
    High: "bg-orange-100 text-orange-800",
    Critical: "bg-red-100 text-red-800",
  };


  const ticketBusy = updateStatusMutation.isPending || replyMutation.isPending || csatMutation.isPending;
  function chooseTicket(ticket: Ticket) {
    if (phone) {
      if (ticketBusy) return;
      updateStatusMutation.reset(); replyMutation.reset(); csatMutation.reset();
      setReplyText("");
    }
    setSelectedTicket(ticket);
  }
  function closeTicket() {
    if (ticketBusy) return;
    if (richTextPlainText(replyText).trim()) { setDiscardReply(true); return; }
    setSelectedTicket(null); setReplyText("");
  }
  const ticketDetails = selectedTicket ? (
            <Card className="hrms-helpdesk-ticket-sheet">
              <CardHeader>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <CardTitle className="text-base">{selectedTicket.subject}</CardTitle>
                    <CardDescription>{selectedTicket.ticket_number} - {selectedTicket.category?.name || "Uncategorized"}</CardDescription>
                  </div>
                  <NativeSelect aria-label="Ticket status" disabled={phone && ticketBusy} value={selectedTicket.status} onChange={(e) => updateStatusMutation.mutate({ id: selectedTicket.id, status: e.target.value })} className="h-8 rounded border border-input bg-background px-2 text-xs">
                    {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </NativeSelect>
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                {phone && updateStatusMutation.isError && <p role="alert" className="text-sm text-destructive">Status could not update. Choose the status to retry.</p>}
                <div className="rounded-lg bg-muted/30 p-4">
                  <div className="text-sm"><RichTextContent legacyFormat="plain" value={selectedTicket.description}/></div>
                  <p className="mt-2 text-xs text-muted-foreground">{formatDateTime(selectedTicket.created_at)}</p>
                </div>

                <div className="space-y-3">
                  <h3 className="text-sm font-semibold">Conversation</h3>
                  {phone && repliesQuery.isPending && <p role="status">Loading conversation…</p>}
                  {phone && repliesQuery.isError && <p role="alert">Conversation could not load. <Button variant="outline" onClick={() => void refetchReplies()}>Retry conversation</Button></p>}
                  {(replies || []).map((reply) => (
                    <div key={reply.id} className={`rounded-lg p-3 text-sm ${reply.is_internal ? "border border-yellow-200 bg-yellow-50 dark:bg-yellow-900/20" : "bg-muted/40"}`}>
                      <div className="mb-1 flex items-center justify-between">
                        <span className="text-xs font-medium">
                          {reply.author ? `${reply.author.first_name} ${reply.author.last_name}` : "System"}
                          {reply.is_internal && <span className="ml-1 text-yellow-600">(Internal)</span>}
                        </span>
                        <span className="text-xs text-muted-foreground">{formatDateTime(reply.created_at)}</span>
                      </div>
                      <div><RichTextContent legacyFormat="plain" value={reply.message}/></div>
                    </div>
                  ))}
                </div>

                {selectedTicket.status !== "Closed" && (
                  <div className="hrms-helpdesk-reply flex gap-2">
                    <RichTextField aria-label="Ticket reply" className="min-w-0 flex-1" rows={3} disabled={replyMutation.isPending} value={replyText} onChange={(e) => setReplyText(e.target.value)} placeholder="Type a reply..." onKeyDown={(e) => {
                      if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && replyText.trim() && (!phone || !replyMutation.isPending)) {
                        e.preventDefault();
                        replyMutation.mutate(replyText.trim());
                      }
                    }} />
                    <Button aria-label="Send ticket reply" size="icon" disabled={!replyText.trim() || replyMutation.isPending} onClick={() => replyText.trim() && replyMutation.mutate(replyText.trim())}>
                      <Send className="h-4 w-4" />
                    </Button>
                  </div>
                )}

                {phone && replyMutation.isError && <p role="alert" className="text-sm text-destructive">Reply could not send. Your text is retained.</p>}
                {["Resolved", "Closed"].includes(selectedTicket.status) && (
                  <div className="rounded-lg border p-4">
                    <p className="mb-3 text-sm font-medium">CSAT rating</p>
                    {phone && selectedTicket.satisfaction_rating && <p className="mb-2 text-sm">Saved rating: {selectedTicket.satisfaction_rating}/5</p>}
                    {phone && csatMutation.isError && <p role="alert" className="text-sm text-destructive">Rating could not save. Select a rating to retry.</p>}
                    <div className="flex flex-wrap gap-2">
                      {[1, 2, 3, 4, 5].map((rating) => (
                        <Button key={rating} aria-pressed={phone ? selectedTicket.satisfaction_rating === rating : undefined} aria-label={phone ? `Rate support ${rating} out of 5` : undefined} disabled={phone && ticketBusy} variant={selectedTicket.satisfaction_rating === rating ? "default" : "outline"} size="sm" onClick={() => csatMutation.mutate({ id: selectedTicket.id, rating })}>
                          <Star className="mr-1 h-4 w-4" />
                          {rating}
                        </Button>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
  ) : null;

  return (
    <div className="hrms-helpdesk-page space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="page-title">Helpdesk</h1>
          <p className="page-description">Raise, resolve, and measure HR support tickets with SLA and CSAT visibility.</p>
        </div>
        <Button size="sm" onClick={() => setShowForm((v) => !v)}>
          <Plus className="mr-2 h-4 w-4" />
          New Ticket
        </Button>
      </div>

      <div className="hrms-helpdesk-kpis grid grid-cols-2 gap-4 lg:grid-cols-6">
        {[
          { label: "Open", value: analytics?.open ?? 0, icon: LifeBuoy },
          { label: "Resolved", value: analytics?.resolved ?? 0, icon: MessageSquare },
          { label: "SLA Breached", value: analytics?.sla_breached ?? 0, icon: AlertTriangle },
          { label: "Due Soon", value: analytics?.due_soon ?? 0, icon: RefreshCw },
          { label: "First Response", value: analytics?.first_response_breached ?? 0, icon: BarChart3 },
          { label: "CSAT", value: analytics?.csat_average ? `${analytics.csat_average}/5` : "-", icon: Star },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <Card key={item.label}>
              <CardContent className="p-4 text-center">
                <Icon className="mx-auto mb-2 h-4 w-4 text-primary" />
                <p className="text-2xl font-bold">{phone && analytics === undefined ? "—" : item.value}</p>
                <p className="mt-1 text-xs text-muted-foreground">{item.label}</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {phone && [ticketsQuery, categoriesQuery, analyticsQuery, slaQuery].some(query => query.isError) && <p role="alert" className="text-sm text-destructive">Helpdesk information could not load. <Button variant="outline" onClick={() => { for (const query of [ticketsQuery, categoriesQuery, analyticsQuery, slaQuery]) if (query.isError) void query.refetch(); }}>Retry helpdesk</Button></p>}
      <MobileDisclosure title="SLA and queue analytics" maxWidth={480}><div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">SLA Breach Dashboard</CardTitle>
            <CardDescription>Tickets past resolution SLA, ordered by oldest due date.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {(slaBreaches || []).slice(0, phone ? undefined : 5).map((ticket) => (
              <div data-priority-row data-priority={ticket.priority} key={ticket.id} className="flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-medium">{ticket.subject}</p>
                  <p className="text-xs text-muted-foreground">{ticket.ticket_number} - due {ticket.resolution_due_at ? formatDateTime(ticket.resolution_due_at) : "-"}</p>
                </div>
                <Badge data-priority-badge data-priority={ticket.priority} variant="destructive">{ticket.priority}</Badge>
              </div>
            ))}
            {(!phone || slaQuery.isSuccess) && !slaBreaches?.length && <p className="rounded-lg border p-4 text-sm text-muted-foreground">No breached tickets right now.</p>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">CSAT + Queue Mix</CardTitle>
            <CardDescription>{phone && analytics === undefined ? "Satisfaction responses have not loaded." : `${analytics?.csat_responses || 0} satisfaction responses captured.`}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {Object.entries(analytics?.by_status || {}).map(([status, count]) => (
              <div key={status} className="flex items-center justify-between rounded-lg border p-3">
                <span className="text-sm font-medium">{status}</span>
                <Badge variant="outline">{count}</Badge>
              </div>
            ))}
            {!analytics && <p className="text-sm text-muted-foreground">Analytics are available for helpdesk managers.</p>}
          </CardContent>
        </Card>
      </div></MobileDisclosure>

      {showForm && (
        <SmartCreateModal definition={{ entity: "ticket", title: "Create support ticket", presentation: "page", size: "standard" }} busy={createMutation.isPending} mobileSheet={phone} onClose={() => setShowForm(false)}>
        <Card className="hrms-helpdesk-create-card">
          <CardHeader><CardTitle className="text-base">Raise a Ticket</CardTitle></CardHeader>
          <CardContent>
            <CompactForm onSubmit={handleSubmit((data) => createMutation.mutate(data))} className="hrms-helpdesk-create grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5 sm:col-span-2">
                <Label>Subject *</Label>
                <Input aria-label="Ticket subject" aria-invalid={!!errors.subject} autoFocus {...register("subject", { required: "Required" })} placeholder="Brief description of the issue" />
                {errors.subject && <div className="text-xs text-red-500"><RichTextContent legacyFormat="plain" value={errors.subject.message}/></div>}
              </div>
              <div className="space-y-1.5">
                <Label>Category</Label>
                <NativeSelect aria-label="Ticket category" loading={phone && categoriesQuery.isFetching} error={phone && categoriesQuery.isError} {...register("category_id")} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                  <option value="">Select category</option>
                  {(categories as { id: number; name: string }[])?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </NativeSelect>
              </div>
              <div className="space-y-1.5">
                <Label>Priority</Label>
                <NativeSelect aria-label="Ticket priority" {...register("priority")} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                  {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
                </NativeSelect>
              </div>
              <div className="space-y-1.5 sm:col-span-2">
                <Label>Description *</Label>
                <Controller name="description" control={editorControl} rules={{validate: value => Boolean(richTextPlainText(value || "")) || "Required"}} render={({field}) => <RichTextEditor legacyFormat="plain" label="Description" value={field.value || ""} onChange={field.onChange} onBlur={field.onBlur} required />}/>
                {errors.description && <div className="text-xs text-red-500"><RichTextContent legacyFormat="plain" value={errors.description.message}/></div>}
              </div>
              {phone && categoriesQuery.isError && <p role="alert" className="hrms-helpdesk-create-error text-sm text-destructive">Categories could not load. <Button type="button" variant="outline" onClick={() => void categoriesQuery.refetch()}>Retry categories</Button></p>}
              {phone && createMutation.isError && <p role="alert" className="hrms-helpdesk-create-error text-sm text-destructive">Ticket could not create. Your ticket details are retained.</p>}
              <div className="hrms-helpdesk-create-actions flex gap-3 sm:col-span-2">
                <Button data-save-action={phone ? "" : undefined} type="submit" disabled={createMutation.isPending}>{createMutation.isPending ? "Submitting..." : "Raise Ticket"}</Button>
                <Button type="button" variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
              </div>
            </CompactForm>
          </CardContent>
        </Card>
        </SmartCreateModal>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-1">
          <div className="flex gap-2">
            <NativeSelect aria-label="Filter ticket status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="flex h-9 flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm">
              <option value="">All</option>
              {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </NativeSelect>
            <Button aria-label="Refresh tickets" variant="ghost" size="icon" className="h-9 w-9" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>

          <div className="space-y-2">
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => <Card key={i}><CardContent className="p-4"><div className="h-16 rounded bg-muted/40" /></CardContent></Card>)
            ) : phone && ticketsQuery.isError && !tickets ? (<p role="alert">Tickets could not load. <Button variant="outline" onClick={() => void refetch()}>Retry tickets</Button></p>) : !tickets?.length ? (
              <Card><CardContent className="p-8 text-center text-muted-foreground"><LifeBuoy className="mx-auto mb-2 h-8 w-8 opacity-30" /><p className="text-sm">No tickets found</p></CardContent></Card>
            ) : <GroupedRecords onOpenRecord={phone ? chooseTicket : undefined} scope="apps/hrms/pages/helpdesk/HelpdeskPage:records-1" items={(tickets) || []} fields={standardRecordGroups((tickets) || [])} gridClassName="space-y-3" renderItem={(ticket) => (
              <Card data-priority-row data-priority={ticket.priority} key={ticket.id} className={`cursor-pointer transition-shadow hover:shadow-md ${selectedTicket?.id === ticket.id ? "ring-2 ring-primary" : ""}`} onClick={() => phone ? chooseTicket(ticket) : setSelectedTicket(selectedTicket?.id === ticket.id ? null : ticket)}>
                <CardContent className="space-y-2 p-4">
                  <div className="hrms-helpdesk-ticket-heading flex items-start justify-between gap-2">
                    <p className="text-sm font-medium leading-tight">{ticket.subject}</p>
                    {!phone && <span data-priority-badge data-priority={ticket.priority} className={`shrink-0 rounded-full px-1.5 py-0.5 text-xs font-medium ${priorityBadge[ticket.priority] || ""}`}>{ticket.priority}</span>}
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">{ticket.ticket_number}</span>
                    {phone && <span data-priority-badge data-priority={ticket.priority} className={`shrink-0 rounded-full px-1.5 py-0.5 text-xs font-medium ${priorityBadge[ticket.priority] || ""}`}>{ticket.priority}</span>}
                    <span className={`rounded-full px-1.5 py-0.5 text-xs font-medium ${statusColor(ticket.status)}`}>{ticket.status}</span>
                  </div>
                  {phone ? <div className="flex items-center justify-between gap-2"><p className="text-xs text-muted-foreground">{formatDateTime(ticket.created_at)}</p><Button type="button" variant="outline" aria-label={`View details for ticket ${ticket.ticket_number}`} onClick={event => { event.stopPropagation(); chooseTicket(ticket); }}>View ticket</Button></div> : <p className="text-xs text-muted-foreground">{formatDateTime(ticket.created_at)}</p>}
                </CardContent>
              </Card>
            )}/>}
          </div>
        </div>

        <div className="lg:col-span-2">
          {!selectedTicket ? (phone ? null : (
            <Card className="h-full">
              <CardContent className="flex h-64 items-center justify-center text-muted-foreground">
                <div className="text-center">
                  <MessageSquare className="mx-auto mb-3 h-10 w-10 opacity-30" />
                  <p>Select a ticket to view details</p>
                </div>
              </CardContent>
            </Card>
          )) : (
            phone ? <MobileSheet open onClose={closeTicket} title="Ticket details">{ticketDetails}</MobileSheet> : ticketDetails
          )}
        </div>
      </div>
      {phone && <AlertDialog open={discardReply} onOpenChange={setDiscardReply}><AlertDialogContent><AlertDialogTitle>Discard unsent reply?</AlertDialogTitle><AlertDialogDescription>Your unsent reply will be cleared. The existing conversation stays unchanged.</AlertDialogDescription><AlertDialogCancel>Continue editing</AlertDialogCancel><AlertDialogAction disabled={ticketBusy} onClick={() => { setDiscardReply(false); setSelectedTicket(null); setReplyText(""); }}>Discard reply</AlertDialogAction></AlertDialogContent></AlertDialog>}
    </div>
  );
}
