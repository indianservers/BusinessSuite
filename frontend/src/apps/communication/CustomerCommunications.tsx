import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import { standardRecordGroups } from "@/shared/data-grid/record-group-fields";
import GroupedRecords from "@/shared/data-grid/GroupedRecords";
import {ProductPicker} from '@/apps/crm/GrowthWorkspace';
import type {OfferingFilter} from './whatsapp/InboxFilters';
import {whatsappBase,type Template} from './whatsapp/types';
import CampaignTemplatePicker,{CampaignTemplatePreview} from './whatsapp/CampaignTemplatePicker';
import {useCenterScope} from './center/shared';
import PhoneActions from "@/components/PhoneActions";
import { NativeSelect } from "@/components/ui/native-select";
import { useEffect,useState } from "react";
import { useSearchParams } from "react-router-dom";
import { RecordPicker,type PickedRecord } from "./center/shared";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import CustomerEmailSettings from "./CustomerEmailSettings";
import CustomerMatchButton from './CustomerMatchButton';

type Row = Record<string, any>;
const base = "/communication/customers";
const load = (path: string) => api.get(base + path).then((r) => r.data);
const save = (path: string, data: unknown, method: "post" | "put" = "post") =>
  api[method](base + path, data).then((r) => r.data);
const purposes = ["transactional", "marketing", "greeting"];
const label = (value: string) => value.replace(/_/g, " ").replace(/\./g, " · ");
const selectClass = "h-10 w-full rounded-md border bg-background px-3 text-sm";
const initialRecipient = {
  name: "",
  email: "",
  phone: "",
  role: "service",
  timezone: "Asia/Kolkata",
  language: "en",
  preferred_channel: "email",
  consent_source: "",
  preferences: {} as Record<string, boolean>,
  active: true,
  birthday: "",
  anniversary: "",
};
const initialRule = {
  name: "",
  trigger: "service.due",
  purpose: "transactional",
  channel: "email",
  subject: "Service reminder: {{reference}}",
  body: "Hello {{name}}, your service {{reference}} is due on {{due_date}}. Please contact us if you need help.",
  status: "draft",
  steps: [0],
  conditions: {},
  quiet_start: 20,
  quiet_end: 8,
  weekdays: [0, 1, 2, 3, 4, 5, 6],
  stop_on_reply: true,
  whatsapp_template: null,
};
const presets: Record<string, Partial<typeof initialRule>> = {
  "Service due": {},
  "Festival greeting": {
    trigger: "greeting",
    purpose: "greeting",
    subject: "Warm wishes, {{name}}",
    body: "Hello {{name}}, warm wishes from our team! Thank you for being part of our journey.",
  },
  "Pending service follow-up": {
    trigger: "follow_up.due",
    subject: "Service follow-up: {{reference}}",
    body: "Hello {{name}}, your service follow-up {{reference}} is due on {{due_date}}. Please contact our team.",
  },
  "Order update": {
    trigger: "order.changed",
    subject: "Order {{reference}} update",
    body: "Hello {{name}}, your order {{reference}} is now {{status}}.",
  },
  "Payment reminder": {
    trigger: "invoice.due",
    subject: "Payment reminder: {{reference}}",
    body: "Hello {{name}}, {{amount}} {{currency}} is pending for invoice {{reference}}, due {{due_date}}.",
    conditions: { roles: ["billing", "primary"], days_before: 0 },
  },
  "Payment due in 3 days": {
    trigger: "invoice.due",
    subject: "Upcoming payment: {{reference}}",
    body: "Hello {{name}}, {{amount}} {{currency}} remains for invoice {{reference}}, due {{due_date}}. Please let us know if you need assistance.",
    conditions: { roles: ["billing", "primary"], days_before: 3 },
  },
  "Payment 3 days overdue": {
    trigger: "invoice.due",
    subject: "Payment follow-up: {{reference}}",
    body: "Hello {{name}}, invoice {{reference}} was due {{due_date}}. The outstanding amount is {{amount}} {{currency}}. Please contact accounts if there is a query.",
    conditions: { roles: ["billing", "primary"], days_before: -3 },
  },
  "Delivery update": {
    trigger: "shipment.changed",
    subject: "Delivery {{reference}} update",
    body: "Hello {{name}}, shipment {{reference}} is now {{status}}.",
  },
  "Contract renewal": {
    trigger: "contract.due",
    subject: "Renewal reminder: {{reference}}",
    body: "Hello {{name}}, contract {{reference}} is due for renewal on {{due_date}}.",
  },
  "Birthday greeting": {
    trigger: "birthday",
    purpose: "greeting",
    subject: "Happy birthday, {{name}}!",
    body: "Happy birthday, {{name}}! Wishing you a wonderful year ahead.",
  },
  Promotion: {
    trigger: "campaign",
    purpose: "marketing",
    subject: "An update for {{name}}",
    body: "Hello {{name}}, we have news to share. Contact our team to learn more.",
  },
  Welcome: {
    trigger: "welcome",
    subject: "Welcome, {{name}}",
    body: "Hello {{name}}, welcome! Our team is here to help with your services and orders.",
  },
};
function Field({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <label className="grid gap-1 text-sm">
      <span>{title}</span>
      {children}
    </label>
  );
}

export default function CustomerCommunications({whatsappOnly=false}:{whatsappOnly?:boolean}={}) {
  const scope=useCenterScope();
  const [queryParams]=useSearchParams();
  const [tab, setTab] = useState(queryParams.get("customerTab")||"overview");
  useEffect(()=>{if(queryParams.get("customerTab"))setTab(queryParams.get("customerTab")!);},[queryParams.get("customerTab")]);
  const [recipient, setRecipient] = useState<Row>(initialRecipient);
  const [recipientEdit, setRecipientEdit] = useState<number | null>(null);
  const [rule, setRule] = useState<Row>(whatsappOnly?{...initialRule,channel:'whatsapp',trigger:'campaign',purpose:'marketing'}:initialRule);
  const [ruleEdit, setRuleEdit] = useState<number | null>(null);
  const [steps, setSteps] = useState("0");
  const [statuses, setStatuses] = useState("");
  const [daysBefore, setDaysBefore] = useState(0);
  const [waTemplate, setWaTemplate] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const [boundRecord,setBoundRecord]=useState<PickedRecord|null>(null);
  const [note, setNote] = useState("");
  const [followUp, setFollowUp] = useState("");
  const [assignee, setAssignee] = useState("");
  const [preview, setPreview] = useState<Row | null>(null);
  const [schedule, setSchedule] = useState("");
  const [approveBulk, setApproveBulk] = useState(false);
  const [campaignOfferings,setCampaignOfferings]=useState<OfferingFilter[]>([]),[campaignTag,setCampaignTag]=useState(''),[campaignType,setCampaignType]=useState('');
  const [audienceIds,setAudienceIds]=useState<number[]>([]),[audienceSearch,setAudienceSearch]=useState(''),[previewVersion,setPreviewVersion]=useState<number>();
  useEffect(()=>{setPreview(null);},[audienceIds,campaignOfferings,campaignTag,campaignType]);
  const audienceParams=()=>({recipient_ids:audienceIds,offerings:campaignOfferings.length?JSON.stringify(campaignOfferings.map(p=>({kind:p.kind,id:Number(p.id)}))):'',tag:campaignTag.trim(),contact_type:campaignType||undefined});
  const [previewRule, setPreviewRule] = useState<number | null>(null);
  const [shipment, setShipment] = useState<Row>({
    sales_order_id: "",
    reference: "",
    status: "ready",
    carrier: "",
    tracking_url: "",
    expected_date: "",
  });
  const [shipmentEdit, setShipmentEdit] = useState<number | null>(null);
  const [settingsEdit, setSettingsEdit] = useState<Row | null>(null);
  const { toast } = useToast();
  const qc = useQueryClient();
  const campaignTemplates=useQuery({queryKey:['whatsapp',scope,'campaign-templates'],enabled:whatsappOnly||rule.channel==='whatsapp',queryFn:async()=>(await api.get<{items:Template[]}>(whatsappBase+'/templates')).data.items});
  const dashboard = useQuery({
    queryKey: ["customer-comms", scope, "dashboard"],
    queryFn: () => load("/dashboard"),
    refetchInterval: 15000,
  });
  const recipients = useQuery({
    queryKey: ["customer-comms", scope, "recipients"],
    queryFn: () => load("/recipients"),
  });
  const rules = useQuery({
    queryKey: ["customer-comms", scope, "rules"],
    queryFn: () => load("/automations"),
  });
  const deliveries = useQuery({
    queryKey: ["customer-comms", scope, "deliveries"],
    queryFn: () => load("/deliveries"),
    refetchInterval: 15000,
  });
  const shipments = useQuery({
    queryKey: ["customer-comms", scope, "shipments"],
    queryFn: () => load("/shipments"),
    enabled: tab === "logistics",
  });
  const settings = useQuery({
    queryKey: ["customer-comms", scope, "settings"],
    queryFn: () => load("/settings"),
  });
  const history = useQuery({
    queryKey: ["customer-comms", scope, "history", selected],
    queryFn: () => load(`/recipients/${selected}/history`),
    enabled: !!selected,
    refetchInterval: 15000,
  });
  const bindings = useQuery({
    queryKey: ["customer-comms", scope, "bindings", selected],
    queryFn: () => load(`/recipients/${selected}/bindings`),
    enabled: !!selected,
  });
  const action = useMutation({
    mutationFn: async (fn: () => Promise<unknown>) => fn(),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["customer-comms"] });
      toast({ title: "Saved" });
    },
    onError: (error: any) =>
      toast({
        title: "Could not complete action",
        description:
          typeof error?.response?.data?.detail === "string"
            ? error.response.data.detail
            : "Check the form values and your permissions.",
        variant: "destructive",
      }),
  });
  const run = (fn: () => Promise<unknown>) => action.mutate(fn);
  return (
    <div className="space-y-5" data-testid="customer-communications">
      <div>
        <h2 className="text-xl font-semibold">{whatsappOnly?'WhatsApp campaigns':'Customer communications'}</h2>
        <p className="text-sm text-muted-foreground">
          Keep customers informed about services, orders, payments and
          deliveries.
        </p>
      </div>
      <nav
        className="flex flex-wrap gap-2"
        aria-label="Customer communication workspace"
      >
        {[
          "overview",
          "customers",
          "automations",
          "deliveries",
          "logistics",
          "settings",
        ].filter(t=>!whatsappOnly||['customers','automations','deliveries'].includes(t)).map((t) => (
          <Button
            key={t}
            size="sm"
            variant={tab === t ? "default" : "outline"}
            onClick={() => setTab(t)}
          >
            {label(t)}
          </Button>
        ))}
      </nav>
      {(dashboard.error ||
        recipients.error ||
        rules.error ||
        deliveries.error) && (
        <p role="alert" className="text-destructive">
          Unable to load customer communications. Check your access and database
          migrations.
        </p>
      )}
      {dashboard.isLoading && (
        <p role="status">Loading customer communications…</p>
      )}
      {tab === "overview" && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            {[
              ["Customers", dashboard.data?.recipients ?? 0],
              ["Active automations", dashboard.data?.active_automations ?? 0],
              [
                "Queued messages",
                (dashboard.data?.statuses?.queued ?? 0) +
                  (dashboard.data?.statuses?.waiting_provider ?? 0),
              ],
            ].map(([name, value]) => (
              <Card key={name}>
                <CardContent className="p-4">
                  <p className="text-sm text-muted-foreground">{name}</p>
                  <p className="text-3xl font-semibold">{value}</p>
                </CardContent>
              </Card>
            ))}
          </div>
          <Card>
            <CardContent className="space-y-3 p-4">
              <h3 className="font-semibold">Delivery health</h3>
              <div className="flex flex-wrap gap-2">
                {Object.entries(dashboard.data?.statuses ?? {}).map(
                  ([state, count]) => (
                    <Badge key={state} variant="secondary">
                      {label(state)}: {String(count)}
                    </Badge>
                  ),
                )}
              </div>
              <p className="text-sm text-muted-foreground">
                {dashboard.data?.note}
              </p>
              <p className="text-sm">
                Add a customer, record their preferences, link an order or
                service, then enable an automation.
              </p>
            </CardContent>
          </Card>
        </>
      )}
      {tab === "customers" && (
        <div className="grid gap-5 xl:grid-cols-2">
          <Card>
            <CardContent className="space-y-4 p-4">
              <h3 className="font-semibold">
                {recipientEdit
                  ? "Edit customer preferences"
                  : "Add customer recipient"}
              </h3>
              <SmartCreateSection title="Add customer recipient" size="large"><form
                className="space-y-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  run(async () => {
                    const result = await save(
                      "/recipients" +
                        (recipientEdit ? `/${recipientEdit}` : ""),
                      {
                        ...recipient,
                        email: recipient.email || null,
                        phone: recipient.phone || null,
                        birthday: recipient.birthday || null,
                        anniversary: recipient.anniversary || null,
                      },
                      recipientEdit ? "put" : "post",
                    );
                    setRecipient(initialRecipient);
                    setRecipientEdit(null);
                    return result;
                  });
                }}
              >
                <div className="grid gap-3 sm:grid-cols-2">
                  {[
                    ["name", "Customer name"],
                    ["email", "Email"],
                    ["phone", "WhatsApp number (+country code)"],
                    ["timezone", "Timezone"],
                    ["language", "Language"],
                    ["consent_source", "Consent evidence / source"],
                  ].map(([key, title]) => (
                    <Field key={key} title={title}>
                      <Input
                        required={[
                          "name",
                          "timezone",
                          "consent_source",
                        ].includes(key)}
                        type={key === "email" ? "email" : "text"}
                        value={recipient[key] ?? ""}
                        onChange={(e) =>
                          setRecipient({ ...recipient, [key]: e.target.value })
                        }
                      />
                    </Field>
                  ))}
                  <Field title="Contact role">
                    <NativeSelect
                      className={selectClass}
                      value={recipient.role}
                      onChange={(e) =>
                        setRecipient({ ...recipient, role: e.target.value })
                      }
                    >
                      {["primary", "billing", "service", "delivery"].map(
                        (v) => (
                          <option key={v}>{v}</option>
                        ),
                      )}
                    </NativeSelect>
                  </Field>
                  <Field title="Preferred channel">
                    <NativeSelect
                      className={selectClass}
                      value={recipient.preferred_channel}
                      onChange={(e) =>
                        setRecipient({
                          ...recipient,
                          preferred_channel: e.target.value,
                        })
                      }
                    >
                      <option>email</option>
                      <option>whatsapp</option>
                    </NativeSelect>
                  </Field>
                  {["birthday", "anniversary"].map((key) => (
                    <Field key={key} title={label(key)}>
                      <Input
                        type="date"
                        value={recipient[key] ?? ""}
                        onChange={(e) =>
                          setRecipient({ ...recipient, [key]: e.target.value })
                        }
                      />
                    </Field>
                  ))}
                </div>
                <fieldset className="space-y-2 rounded border p-3">
                  <legend className="px-1 text-sm font-medium">
                    Customer permissions
                  </legend>
                  <p className="text-xs text-muted-foreground">
                    Select only permissions explicitly granted by the customer.
                    Signup does not imply marketing consent.
                  </p>
                  {["email", "whatsapp"].map((channel) => (
                    <div key={channel} className="flex flex-wrap gap-3">
                      <span className="w-20 text-sm">{channel}</span>
                      {purposes.map((p) => (
                        <label
                          key={p}
                          className="flex items-center gap-1 text-sm"
                        >
                          <input
                            type="checkbox"
                            checked={
                              !!recipient.preferences?.[`${channel}.${p}`]
                            }
                            onChange={(e) =>
                              setRecipient({
                                ...recipient,
                                preferences: {
                                  ...recipient.preferences,
                                  [`${channel}.${p}`]: e.target.checked,
                                },
                              })
                            }
                          />
                          {p}
                        </label>
                      ))}
                    </div>
                  ))}
                </fieldset>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={recipient.active}
                    onChange={(e) =>
                      setRecipient({ ...recipient, active: e.target.checked })
                    }
                  />
                  Active recipient
                </label>
                <Button disabled={action.isPending}>Save customer</Button>
                {recipientEdit && (
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setRecipient(initialRecipient);
                      setRecipientEdit(null);
                    }}
                  >
                    Cancel edit
                  </Button>
                )}
              </form></SmartCreateSection>
            </CardContent>
          </Card>
          <div className="space-y-4">
            <Card>
              <CardContent className="space-y-3 p-4">
                <h3 className="font-semibold">Customers</h3>
                {!recipients.data?.items?.length && (
                  <p className="text-sm text-muted-foreground">
                    No customer recipients yet.
                  </p>
                )}
                {<GroupedRecords scope="apps/communication/CustomerCommunications:records-1" items={(recipients.data?.items) || []} fields={standardRecordGroups((recipients.data?.items) || [])} gridClassName="space-y-3" renderItem={(r: Row) => (
                  <div
                    key={r.id}
                    className="flex flex-wrap items-center justify-between gap-2 border-b pb-2"
                  >
                    <div>
                      <p className="font-medium">
                        {r.name} <Badge variant="outline">{r.role}</Badge>
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {r.email || <PhoneActions value={r.phone} record={r} />}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setSelected(r.id)}
                      >
                        History & links
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setRecipient(r);
                          setRecipientEdit(r.id);
                        }}
                      >
                        Edit
                      </Button>
                    </div>
                  </div>
                )}/>}
              </CardContent>
            </Card>
            {selected && (
              <Card>
                <CardContent className="space-y-3 p-4">
                  <h3 className="font-semibold">
                    Customer history & record links
                  </h3>
                  <CustomerMatchButton/>
                  {history.data?.crm_match?.status==='ambiguous'&&<p className="text-xs text-amber-700">Multiple CRM records match this customer. Review the record links below.</p>}
                  {history.data?.crm_match?.status==='conflict'&&<p className="text-xs text-amber-700">The phone and email match different CRM records. Review before linking.</p>}
                  <p className="text-xs text-muted-foreground">
                    Email replies appear when a receiving-service adapter is
                    connected. Open WhatsApp in the Communication Hub to reply
                    there.
                  </p>
                  <RecordPicker label="Find a business record to link" value={boundRecord} onChange={setBoundRecord} types={['order','invoice','service','follow_up','contract','lead','meeting','quotation','shipment','contact']}/>
                  <Button disabled={!boundRecord||action.isPending} onClick={()=>boundRecord&&run(()=>save(`/recipients/${selected}/bindings`,{source_type:boundRecord.entity,source_id:boundRecord.id}))}>Link selected business record</Button>
                  {<GroupedRecords scope="apps/communication/CustomerCommunications:records-2" items={(bindings.data?.items) || []} fields={standardRecordGroups((bindings.data?.items) || [])} gridClassName="space-y-3" renderItem={(b: Row) => (
                    <div
                      key={b.id}
                      className="flex items-center justify-between text-sm"
                    >
                      <span>
                        {b.source_type} #{b.source_id}
                      </span>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() =>
                          run(() => api.delete(base + `/bindings/${b.id}`))
                        }
                      >
                        Unlink
                      </Button>
                    </div>
                  )}/>}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      run(async () => {
                        const result = await save(
                          `/recipients/${selected}/preference-link`,
                          {},
                        );
                        await navigator.clipboard.writeText(result.url);
                        toast({
                          title: "Preference link copied",
                          description:
                            "Expires in 30 days; earlier links are revoked.",
                        });
                        return result;
                      })
                    }
                  >
                    Copy unsubscribe link
                  </Button>
                  <SmartCreateSection title="Add internal note" size="large"><form
                    className="space-y-2"
                    onSubmit={(e) => {
                      e.preventDefault();
                      run(async () => {
                        const result = await save(
                          `/recipients/${selected}/notes`,
                          {
                            body: note,
                            follow_up_at: followUp
                              ? new Date(followUp).toISOString()
                              : null,
                            assigned_user_id: assignee
                              ? Number(assignee)
                              : null,
                          },
                        );
                        setNote("");
                        return result;
                      });
                    }}
                  >
                    <Field title="Internal note (never sent to customer)">
                      <Input
                        required
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                      />
                    </Field>
                    <div className="grid gap-2 sm:grid-cols-2">
                      <Field title="Follow up (local time)">
                        <Input
                          type="datetime-local"
                          value={followUp}
                          onChange={(e) => setFollowUp(e.target.value)}
                        />
                      </Field>
                      <Field title="Assign to user ID">
                        <Input
                          type="number"
                          min="1"
                          value={assignee}
                          onChange={(e) => setAssignee(e.target.value)}
                        />
                      </Field>
                    </div>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        run(() =>
                          save(`/recipients/${selected}/assignment`, {
                            assigned_user_id: assignee
                              ? Number(assignee)
                              : null,
                          }),
                        )
                      }
                    >
                      Assign conversation
                    </Button>
                    <Button size="sm" disabled={action.isPending}>
                      Save internal note
                    </Button>
                  </form></SmartCreateSection>
                  {!!history.data?.unread_email_count && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        run(() => save(`/recipients/${selected}/read`, {}))
                      }
                    >
                      Mark {history.data.unread_email_count} email replies read
                    </Button>
                  )}
                  {history.data?.email_replies?.map((m: Row) => (
                    <div
                      key={"reply" + m.id}
                      className="rounded border p-3 text-sm"
                    >
                      <Badge variant="outline">Email reply</Badge>
                      <p className="font-medium">{m.subject}</p>
                      <p className="whitespace-pre-wrap">{m.body}</p>
                    </div>
                  ))}
                  {history.data?.internal_notes.map((n: Row) => (
                    <p key={n.id} className="rounded bg-muted p-2 text-sm">
                      <strong>Internal:</strong> {n.body}
                    </p>
                  ))}
                  {history.data?.whatsapp.map((m: Row) => (
                    <p key={"wa" + m.id} className="rounded border p-2 text-sm">
                      <Badge variant="outline">WhatsApp · {m.direction}</Badge>{" "}
                      {m.body} <span className="text-xs">{m.status}</span>
                    </p>
                  ))}
                  {history.data?.deliveries.map((d: Row) => (
                    <p
                      key={"delivery" + d.id}
                      className="border-b pb-2 text-sm"
                    >
                      {d.subject}{" "}
                      <Badge variant="secondary">{label(d.status)}</Badge>
                      <span className="block text-xs text-muted-foreground">
                        {d.source_type} #{d.source_id} · {d.error}
                      </span>
                    </p>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
      {tab === "automations" && (
        <div className="grid gap-5 xl:grid-cols-2">
          <Card>
            <CardContent className="space-y-3 p-4">
              <h3 className="font-semibold">
                {ruleEdit ? "Edit automation" : "Build automation"}
              </h3>
              <div className="flex flex-wrap gap-1">
                {Object.entries(presets).map(([name, preset]) => (
                  <Button
                    key={name}
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setRule({ ...initialRule, ...preset, name, ...(whatsappOnly?{channel:'whatsapp',trigger:'campaign',purpose:'marketing'}:{}) });
                      setRuleEdit(null);
                      setSteps("0");
                      setStatuses("");
                      setDaysBefore(0);
                      setWaTemplate("");
                    }}
                  >
                    {name}
                  </Button>
                ))}
              </div>
              <SmartCreateSection title="Create customer automation" size="large"><form
                className="space-y-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  run(async () => {
                    const result = await save(
                      "/automations" + (ruleEdit ? `/${ruleEdit}` : ""),
                      {
                        ...rule,
                        steps: steps.split(",").map((s) => Number(s.trim())),
                        conditions: {
                          statuses: statuses
                            .split(",")
                            .map((s) => s.trim())
                            .filter(Boolean),
                          days_before: daysBefore,
                        },
                        whatsapp_template: waTemplate
                          ? JSON.parse(waTemplate)
                          : null,
                      },
                      ruleEdit ? "put" : "post",
                    );
                    setPreview(null);
                    setRuleEdit(result.id);
                    setRule(result);
                    return result;
                  });
                }}
              >
                <Field title="Automation name">
                  <Input
                    required
                    value={rule.name}
                    onChange={(e) => setRule({ ...rule, name: e.target.value })}
                  />
                </Field>
                <div className="grid gap-3 sm:grid-cols-2">
                  {[
                    ["trigger", rules.data?.triggers ?? []],
                    ["purpose", purposes],
                    ["channel", whatsappOnly?["whatsapp"]:["email", "whatsapp"]],
                    ["status", ["draft", "active", "paused"]],
                  ].map(([key, options]) => (
                    <Field key={String(key)} title={label(String(key))}>
                      <NativeSelect
                        className={selectClass}
                        value={rule[String(key)]}
                        onChange={(e) =>
                          setRule({ ...rule, [String(key)]: e.target.value })
                        }
                      >
                        {(options as string[]).map((v) => (
                          <option key={v} value={v}>
                            {label(v)}
                          </option>
                        ))}
                      </NativeSelect>
                    </Field>
                  ))}
                </div>
                <Field title={rule.channel==='whatsapp'?"Campaign reference":"Subject"}>
                  <Input
                    required
                    value={rule.subject}
                    onChange={(e) =>
                      setRule({ ...rule, subject: e.target.value })
                    }
                  />
                </Field>
                {rule.channel!=="whatsapp"&&<Field title="Message">
                  <textarea
                    required
                    className="min-h-28 rounded border bg-background p-3"
                    value={rule.body}
                    onChange={(e) => setRule({ ...rule, body: e.target.value })}
                  />
                </Field>}
                {rule.channel==="whatsapp"&&<p className="text-sm">The approved template below is the customer message.</p>}
                <p className="text-xs text-muted-foreground">
                  Variables: name, reference, status, due_date, amount,
                  currency, tracking_url. Use double braces, e.g. {"{{name}}"}.
                </p>
                {rule.channel === "whatsapp" && (
                  <CampaignTemplatePicker value={waTemplate} onChange={setWaTemplate}/>
                )}
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field title="Step delays in minutes (comma separated)">
                    <Input
                      value={steps}
                      onChange={(e) => setSteps(e.target.value)}
                    />
                  </Field>
                  <Field title="Matching statuses (optional)">
                    <Input
                      value={statuses}
                      onChange={(e) => setStatuses(e.target.value)}
                    />
                  </Field>
                  <Field title="Days before due (negative = overdue)">
                    <Input
                      type="number"
                      min="-365"
                      max="365"
                      value={daysBefore}
                      onChange={(e) => setDaysBefore(Number(e.target.value))}
                    />
                  </Field>
                  {["quiet_start", "quiet_end"].map((key) => (
                    <Field
                      key={key}
                      title={label(key) + " hour (customer timezone)"}
                    >
                      <Input
                        type="number"
                        min="0"
                        max="23"
                        value={rule[key]}
                        onChange={(e) =>
                          setRule({ ...rule, [key]: Number(e.target.value) })
                        }
                      />
                    </Field>
                  ))}
                </div>
                <fieldset className="flex flex-wrap gap-2">
                  <legend className="text-sm">Business days</legend>
                  {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(
                    (day, i) => (
                      <label
                        key={day}
                        className="flex items-center gap-1 text-sm"
                      >
                        <input
                          type="checkbox"
                          checked={rule.weekdays.includes(i)}
                          onChange={(e) =>
                            setRule({
                              ...rule,
                              weekdays: e.target.checked
                                ? [...rule.weekdays, i].sort()
                                : rule.weekdays.filter((v: number) => v !== i),
                            })
                          }
                        />
                        {day}
                      </label>
                    ),
                  )}
                </fieldset>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={rule.stop_on_reply}
                    onChange={(e) =>
                      setRule({ ...rule, stop_on_reply: e.target.checked })
                    }
                  />
                  Stop follow-ups after a customer reply
                </label>
                <Button disabled={action.isPending}>Save automation</Button>
              </form></SmartCreateSection>
            </CardContent>
          </Card>
          <div className="space-y-4">
            <section className="space-y-2 rounded border p-3"><h3>Campaign audience</h3><div className="grid gap-2 sm:grid-cols-2"><label>Lead / customer type<NativeSelect aria-label="Campaign contact type" value={campaignType} onChange={e=>setCampaignType(e.target.value)}><option value="">Any type</option>{['lead','customer','vendor','employee','other'].map(t=><option key={t}>{t}</option>)}</NativeSelect></label><label>CRM tag<input aria-label="Campaign CRM tag" className="w-full rounded border p-2" value={campaignTag} maxLength={100} onChange={e=>setCampaignTag(e.target.value)}/></label><div><ProductPicker kind="" id="" name="" change={(kind,id,name)=>{if(id&&campaignOfferings.length<50&&!campaignOfferings.some(v=>v.kind===kind&&v.id===id))setCampaignOfferings([...campaignOfferings,{kind,id,name}]);}}/>{campaignOfferings.map(p=><button type="button" key={p.kind+p.id} onClick={()=>setCampaignOfferings(campaignOfferings.filter(v=>v!==p))}>{p.name} ×</button>)}</div><small>Type, tag and product filters use authorized CRM contact/lead links; unlinked recipients are excluded. Products match any selection.</small></div><p className="text-sm">{audienceIds.length?`${audienceIds.length} selected recipients`:'All active recipients in this branch'}. Consent and exclusions are checked by preview and again before delivery.</p><input aria-label="Search campaign audience" className="w-full rounded border p-2" placeholder="Search name, phone, email or role" value={audienceSearch} onChange={e=>setAudienceSearch(e.target.value)}/><div className="max-h-48 overflow-auto">{recipients.data?.items.filter((r:Row)=>(r.name+' '+r.phone+' '+r.email+' '+r.role).toLowerCase().includes(audienceSearch.toLowerCase())).map((r:Row)=><label className="flex items-center gap-2" key={r.id}><input type="checkbox" checked={audienceIds.includes(r.id)} onChange={e=>setAudienceIds(e.target.checked?[...audienceIds,r.id]:audienceIds.filter(id=>id!==r.id))}/>{r.name} · {r.phone||r.email} · {r.role}</label>)}</div><button type="button" onClick={()=>setAudienceIds([])}>Use all active recipients</button></section>
            {<GroupedRecords scope="apps/communication/CustomerCommunications:records-3" items={(rules.data?.items.filter((r:Row)=>!whatsappOnly||r.channel==='whatsapp')) || []} fields={standardRecordGroups((rules.data?.items.filter((r:Row)=>!whatsappOnly||r.channel==='whatsapp')) || [])} gridClassName="space-y-3" renderItem={(r: Row) => (
              <Card key={r.id}>
                <CardContent className="space-y-2 p-4">
                  <div className="flex justify-between gap-2">
                    <h3 className="font-semibold">{r.name}</h3>
                    <Badge variant="outline">{r.status}</Badge>
                  </div>
                  <p className="text-sm">
                    {label(r.trigger)} · {r.channel} · {r.purpose} · v
                    {r.version}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {r.steps.length} steps · quiet hours {r.quiet_start}:00–
                    {r.quiet_end}:00
                  </p>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setRule(r);
                        setRuleEdit(r.id);
                        setSteps(r.steps.join(","));
                        setStatuses((r.conditions?.statuses ?? []).join(","));
                        setDaysBefore(r.conditions?.days_before ?? 0);
                        setWaTemplate(
                          r.whatsapp_template
                            ? JSON.stringify(r.whatsapp_template, null, 2)
                            : "",
                        );
                      }}
                    >
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        run(async () => {
                          const result = await save(
                            `/automations/${r.id}/preview`,
                            audienceParams(),
                          );
                          setPreview(result);
                          setPreviewRule(r.id);setPreviewVersion(r.version);
                          return result;
                        })
                      }
                    >
                      Preview audience
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}/>}
            {preview && (
              <Card>
                <CardContent className="space-y-3 p-4">
                  <h3 className="font-semibold">Audience preview</h3>
                  <p>
                    {preview.eligible} eligible · {preview.excluded} excluded ·
                    about {preview.usage_estimate} messages
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {preview.cost_note}
                  </p>
                  {preview.sample && (
                    <div className="rounded bg-muted p-3">
                      {preview.channel==='whatsapp'?<CampaignTemplatePreview templates={campaignTemplates.data||[]} payload={preview.sample.template}/>:<><strong>{preview.sample.subject}</strong>
                      <p className="whitespace-pre-wrap">
                        {preview.sample.body}
                      </p></>}
                    </div>
                  )}
                  {preview.sample_error && (
                    <p className="text-sm">{preview.sample_error}</p>
                  )}
                  <Field title="Schedule (local time; empty to queue now)">
                    <Input
                      type="datetime-local"
                      value={schedule}
                      onChange={(e) => setSchedule(e.target.value)}
                    />
                  </Field>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={approveBulk}
                      onChange={(e) => setApproveBulk(e.target.checked)}
                    />
                    Approve bulk launch (CRM administrators)
                  </label>
                  <Button
                    disabled={action.isPending}
                    onClick={() =>
                      run(() =>
                        save(`/automations/${previewRule}/launch`, {
                          ...audienceParams(),expected_version:previewVersion,
                          scheduled_at: schedule
                            ? new Date(schedule).toISOString()
                            : null,
                          approve_bulk: approveBulk,
                        }),
                      )
                    }
                  >
                    Launch campaign / welcome
                  </Button>
                  <p className="text-xs text-muted-foreground">
                    Event automations run on source changes or due dates.
                    Launching the same campaign version twice does not duplicate
                    messages.
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
      {tab === "deliveries" && (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Provider acceptance does not prove customer delivery. Investigate
            uncertain outcomes before retrying.
          </p>
          {!deliveries.data?.items.length && <p>No messages queued yet.</p>}
          {<GroupedRecords scope="apps/communication/CustomerCommunications:records-4" items={(deliveries.data?.items.filter((d:Row)=>!whatsappOnly||d.channel==='whatsapp')) || []} fields={standardRecordGroups((deliveries.data?.items.filter((d:Row)=>!whatsappOnly||d.channel==='whatsapp')) || [])} gridClassName="space-y-3" renderItem={(d: Row) => (
            <Card key={d.id}>
              <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div>
                  <p className="font-medium">{d.subject}</p>
                  <p className="text-xs text-muted-foreground">
                    Customer #{d.recipient_id} · {d.source_type} #{d.source_id}{" "}
                    · {d.channel} · {new Date(d.due_at).toLocaleString()}
                  </p>
                  {d.error && (
                    <p className="text-sm text-destructive">{d.error}</p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">{label(d.status)}</Badge>
                  {["queued", "blocked", "waiting_provider"].includes(
                    d.status,
                  ) && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        run(() => save(`/deliveries/${d.id}/cancel`, {}))
                      }
                    >
                      Cancel
                    </Button>
                  )}
                  {(d.status === "failed" ||
                    (d.status === "blocked" &&
                      !d.email_outbox_id &&
                      !d.whatsapp_message_id)) && (
                    <Button
                      size="sm"
                      onClick={() =>
                        run(() => save(`/deliveries/${d.id}/retry`, {}))
                      }
                    >
                      Retry
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          )}/>}
        </div>
      )}
      {tab === "logistics" && (
        <div className="grid gap-5 xl:grid-cols-2">
          <Card>
            <CardContent className="space-y-3 p-4">
              <h3 className="font-semibold">
                {shipmentEdit ? "Update shipment" : "Create shipment"}
              </h3>
              <SmartCreateSection title="Create shipment" size="large"><form
                className="space-y-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  run(async () => {
                    const result = await save(
                      "/shipments" + (shipmentEdit ? `/${shipmentEdit}` : ""),
                      {
                        ...shipment,
                        sales_order_id: Number(shipment.sales_order_id),
                        expected_date: shipment.expected_date || null,
                        tracking_url: shipment.tracking_url || null,
                        carrier: shipment.carrier || null,
                      },
                      shipmentEdit ? "put" : "post",
                    );
                    setShipmentEdit(result.id);
                    setShipment(result);
                    return result;
                  });
                }}
              >
                {[
                  ["sales_order_id", "Sales order ID"],
                  ["reference", "Shipment reference"],
                  ["carrier", "Carrier"],
                  ["tracking_url", "HTTPS tracking link"],
                  ["expected_date", "Expected date"],
                ].map(([key, title]) => (
                  <Field key={key} title={title}>
                    <Input
                      required={["sales_order_id", "reference"].includes(key)}
                      type={
                        key === "sales_order_id"
                          ? "number"
                          : key === "expected_date"
                            ? "date"
                            : "text"
                      }
                      value={shipment[key] ?? ""}
                      onChange={(e) =>
                        setShipment({ ...shipment, [key]: e.target.value })
                      }
                    />
                  </Field>
                ))}
                <Field title="Shipment status">
                  <NativeSelect
                    className={selectClass}
                    value={shipment.status}
                    onChange={(e) =>
                      setShipment({ ...shipment, status: e.target.value })
                    }
                  >
                    {[
                      "ready",
                      "dispatched",
                      "out_for_delivery",
                      "rescheduled",
                      "exception",
                      "delivered",
                      "failed_delivery",
                      "returned",
                    ].map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </NativeSelect>
                </Field>
                <Button disabled={action.isPending}>Save shipment</Button>
              </form></SmartCreateSection>
            </CardContent>
          </Card>
          <div className="space-y-3">
            {<GroupedRecords scope="apps/communication/CustomerCommunications:records-5" items={(shipments.data?.items) || []} fields={standardRecordGroups((shipments.data?.items) || [])} gridClassName="space-y-3" renderItem={(s: Row) => (
              <Card key={s.id}>
                <CardContent className="space-y-2 p-4">
                  <h3 className="font-semibold">{s.reference}</h3>
                  <p className="text-sm">
                    Order #{s.sales_order_id} · {label(s.status)}
                  </p>
                  {s.tracking_url && (
                    <a
                      className="text-sm underline"
                      href={s.tracking_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Track shipment
                    </a>
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setShipment(s);
                      setShipmentEdit(s.id);
                    }}
                  >
                    Update
                  </Button>
                </CardContent>
              </Card>
            )}/>}
          </div>
        </div>
      )}
      {tab === "settings" && (
        <Card>
          <CardContent className="max-w-xl space-y-4 p-4">
            <h3 className="font-semibold">Business communication controls</h3>
            <p className="text-sm text-muted-foreground">
              CRM administrators can pause sending and set message limits.
              Connect WhatsApp in the WhatsApp section; email uses the suite’s
              configured transport.
            </p>
            {settings.data && (
              <form
                className="space-y-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  run(() =>
                    save("/settings", settingsEdit ?? settings.data, "put"),
                  );
                }}
              >
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={(settingsEdit ?? settings.data).paused}
                    onChange={(e) =>
                      setSettingsEdit({
                        ...(settingsEdit ?? settings.data),
                        paused: e.target.checked,
                      })
                    }
                  />
                  Pause customer communications for this business
                </label>
                {[
                  ["daily_limit", "Business daily message limit"],
                  ["customer_daily_limit", "Customer daily message limit"],
                  ["bulk_approval_threshold", "Bulk approval threshold"],
                ].map(([key, title]) => (
                  <Field key={key} title={title}>
                    <Input
                      type="number"
                      min="1"
                      value={(settingsEdit ?? settings.data)[key]}
                      onChange={(e) =>
                        setSettingsEdit({
                          ...(settingsEdit ?? settings.data),
                          [key]: Number(e.target.value),
                        })
                      }
                    />
                  </Field>
                ))}
                <Button disabled={action.isPending}>Save controls</Button>
              </form>
            )}
            <CustomerEmailSettings />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
