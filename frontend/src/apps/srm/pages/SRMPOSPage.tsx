import { pharmaCheckoutQuote } from '@/lib/pharma-checkout-money';
import { effectiveOperationalSelection, type OperationalSelection } from '@/lib/effective-operational-selection';
import { currentPOSOperationalPin, installPOSOperationalPin, operationalOwner } from '@/lib/pos-operational-context';
import { selectedBranch } from '@/lib/branch-context';
import { securityAuthStamp } from "@/lib/security-auth-stamp";
import { logicalIntentScope } from "@/lib/logical-intent-scope";
import { financialIntentKey, readFinancialIntent, saveFinancialIntent, clearFinancialIntent, findPendingCashIntent } from "@/lib/financial-intent";
import { readPOSCheckoutIntent } from "@/lib/pos-checkout-intent";
import { POSQuickAddCustomer, POSCustomerProfile, type POSFeatures } from '../components/POSBasicCustomer';
import AnonymousCashSetup, { type AnonymousCashConfiguration } from '../industry/AnonymousCashSetup';
import { selectedPackContext } from '@/lib/pack-context';
import ServiceCheckoutBillingPanel from '../industry/ServiceCheckoutBillingPanel';
import RetailReturnPanel from '../components/RetailReturnPanel';
import { isAxiosError } from 'axios';
import { useRecordScope } from '@/lib/record-scope';
import { useRecordScopeOwner } from '@/hooks/use-record-scope-owner';
import POSServiceScheduling, { type BookingSelection } from '../industry/POSServiceScheduling';
import { dealError } from '@/apps/crm/deals/deal-utils';
import { defaultText } from "@/lib/form-defaults";
import { CompanyProfile } from "@/shared/master-data/CompanySelect";
import CompactActions from "@/components/actions/CompactActions";
import { NativeSelect } from "@/components/ui/native-select";
import { api } from "@/services/api";
import QuickAddCustomer, { type PosCustomerRecord } from "../components/QuickAddCustomer";
import { ScheduleFields, newDefaultSchedule, type Schedule } from "@/shared/follow-ups/ScheduleFields";
import { RichTextContent } from "@/components/rich-text/RichTextContent";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import "./srm-pos-mobile.css";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { canAccessRoute } from "@/lib/roles";
import { useAuthStore } from "@/store/authStore";
import { phoneLinks } from "@/components/PhoneActions";
import {
  Banknote,
  Calculator,
  CheckCircle2,
  CreditCard,
  DoorClosed,
  LayoutGrid,
  List,
  Minus,
  PauseCircle,
  Plus,
  Printer,
  Receipt,
  RotateCcw,
  Search,
  Settings,
  ShoppingCart,
  Table2,
  Trash2,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "@/hooks/use-toast";
import { srmApi } from "../api";
import { syncSrmNow, useSrmRealtimeInvalidation } from "../realtime";
import type { SRMRecord } from "../types";

type PosMode = "Retail" | "Supermarket" | "Restaurant" | "Services" | "Wholesale" | "Pharmacy" | "Electronics" | "Garments";
type PaymentMode = "Cash" | "Card" | "UPI" | "Wallet" | "Credit" | "Split";
type ProductViewMode = "tiles" | "list" | "details";

type Product = {
  id: number;
  name: string;
  image?: string;
  sku: string;
  barcode: string;
  category: string;
  rate: number;
  mrp: number;
  taxRate: number;
  stock: number;
  reorderLevel: number;
  trackInventory: boolean;
  checkoutSupported?: boolean;
  bookingRequired?: boolean;
  unsupportedReason?: string;
  followUp?: Schedule;
  kind: string;
  duration?: string;
  active?: boolean;
  batchTracking?: boolean;
  serialTracking?: boolean;
  lotAllocation?: "fefo";
  decimalAllowed?: boolean;
  batch?: string;
  serials?: string[];
};

type Customer = {
  id: number;
  name: string;
  phone: string;
  email?: string;
  type: "Walk-in" | "Retail" | "Wholesale" | "Credit";
  creditLimit: number;
  outstanding: number;
  loyaltyPoints: number;
};

type CartLine = Product & {
  lineId: string;
  booking?: BookingSelection;
  draftScope?: string;
  heldBillDiscount?: number;
  heldCoupon?: string;
  qty: number;
  discount: number;
  note: string;
  batchNo?: string;
  serialNo?: string;
};

type HeldBill = {
  id: string | number;
  holdNo: string;
  billDiscount?: number;
  coupon?: string;
  customerId: number;
  notes: string;
  cart: CartLine[];
  amount: number;
  createdAt: string;
};

type Sale = {
  id: string;
  invoiceNo: string;
  customer: string;
  amount: number;
  mode: PaymentMode;
  createdAt: string;
  items: number;
  checkoutId?: number;
  paid?: string;
  balance?: string;
  receiptNumbers?: string[];
  hasBookings?: boolean;
};

type NativeCheckoutPayload = { request_id: string; buyer_mode?: "registered"|"anonymous_cash"; customer_id?: number; pos_session_id: number; currency: string; billing_mode: "invoice_at_checkout"; note:string; expected_total: string; bill_discount_amount: string; lines: {client_line_key:string;line_kind:"product"|"unscheduled_service"|"booked_service";product_id:number;quantity:string;unit_price:string;discount_amount:string;note:string;follow_up?:Schedule;booking?:BookingSelection}[]; payments:{payment_key:string;method:string;amount:string;reference?:string}[] };
type NativeCheckoutResult = {id:number;state:string;sales_order_id:number;invoice:{id:number;number:string;status:string;total:string;paid:string;balance:string};receipts:{id:number;number:string}[]};
type CheckoutAfter = "done"|"print"|"whatsapp"|"email"|"request_payment";
type CheckoutAttempt = {payload:NativeCheckoutPayload; sale:Sale;after?:CheckoutAfter;recoverySourceKeys?:string[]};

type PaymentRow = {
  id: string;
  mode: Exclude<PaymentMode, "Split">;
  amount: number;
  reference: string;
};

type PosStoreProfile = {
  id: string;
  name: string;
  mode: PosMode;
  branch: string;
  register: string;
  description: string;
  categories: string[];
  features: string[];
};

const walkInCustomer: Customer = { id: 0, name: "Walk-in customer", phone: "", type: "Walk-in", creditLimit: 0, outstanding: 0, loyaltyPoints: 0 };
const savedCustomer = (item: PosCustomerRecord): Customer => ({ id: item.id, name: item.name, phone: item.phone ? `${item.phone_country_code || ""} ${item.phone}`.trim() : "", email: item.email || "", type: "Retail", creditLimit: 0, outstanding: 0, loyaltyPoints: 0 });

const posStoreProfiles: PosStoreProfile[] = [
  {
    id: "bookstore-retail",
    name: "Bookstore Retail",
    mode: "Retail",
    branch: "Main Branch",
    register: "Books Counter",
    description: "Books, stationery, school supplies, and counter billing.",
    categories: ["General", "Stationery", "Office Supplies"],
    features: ["Barcode scan", "Loyalty points", "Thermal receipt"],
  },
  {
    id: "electronics-retail",
    name: "Electronics Retail",
    mode: "Electronics",
    branch: "Main Branch",
    register: "Electronics Desk",
    description: "Serial-number billing, warranty capture, and device lookup.",
    categories: ["General", "Electronics", "Office Supplies"],
    features: ["Serial required", "Warranty capture", "IMEI/device note"],
  },
  {
    id: "pharmacy-counter",
    name: "Pharmacy Counter",
    mode: "Pharmacy",
    branch: "Main Branch",
    register: "Pharmacy POS",
    description: "Batch-aware sale flow with medicine stock visibility.",
    categories: ["General", "Pharmacy"],
    features: ["Batch required", "Expiry visible", "Prescription ref"],
  },
  {
    id: "uniform-garments",
    name: "Uniforms & Garments",
    mode: "Garments",
    branch: "Main Branch",
    register: "Garments Counter",
    description: "Size/color sale flow for uniforms and accessories.",
    categories: ["General", "Garments"],
    features: ["Size/color lookup", "Alteration note", "Exchange support"],
  },
];

const defaultStoreProfile = posStoreProfiles[0];
const paymentModes: PaymentMode[] = ["Cash", "Card", "UPI", "Wallet", "Credit", "Split"];
const rowModes: Exclude<PaymentMode, "Split">[] = ["Cash", "Card", "UPI", "Wallet", "Credit"];

function uid(prefix = "id") {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function currency(value: number) {
  return value.toLocaleString("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });
}

function shortCurrency(value: number) {
  return value.toLocaleString("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
}

function cashNumber(value: unknown) {
  if ((typeof value !== "number" && typeof value !== "string") || (typeof value === "string" && !value.trim())) return NaN;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : NaN;
}

function recordNumber(value: unknown, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function listItems(data: unknown): SRMRecord[] {
  if (Array.isArray(data)) return data as SRMRecord[];
  if (data && typeof data === "object" && Array.isArray((data as { items?: unknown }).items)) return (data as { items: SRMRecord[] }).items;
  return [];
}

function heldBillFromRecord(item: SRMRecord): HeldBill {
  return {
    id: (item.id as string | number) || uid("hold"),
    holdNo: String(item.holdNo || item.hold_number || "HOLD"),
    customerId: recordNumber(item.customer_id, 0),
    notes: String(item.notes || ""),
    cart: ((item.cart || item.cart_json || []) as CartLine[]),
    billDiscount: ((item.cart || item.cart_json || []) as CartLine[])[0]?.heldBillDiscount || 0,
    coupon: ((item.cart || item.cart_json || []) as CartLine[])[0]?.heldCoupon || "",
    amount: recordNumber(item.amount),
    createdAt: String(item.created_at || new Date().toISOString()),
  };
}

function productFromRecord(item: SRMRecord): Product {
  return {
    id: recordNumber(item.id),
    name: String(item.item_name || item.name || "Unnamed product"),
    image: ((item.metadata_json as { images?: string[] } | undefined)?.images || [])[0],
    followUp: (item.metadata_json as {follow_up?:Schedule} | undefined)?.follow_up,
    kind: String(["service","services"].includes(String(item.product_type).toLowerCase()) ? "Services" : item.product_type === "package" ? "Packages" : "Products"),
    duration: String((item.metadata_json as Record<string, unknown> | undefined)?.duration || ""),
    active: item.active !== false,
    sku: String(item.sku || ""),
    barcode: String(item.barcode || item.sku || ""),
    category: String(item.category_name || (item.category as SRMRecord | undefined)?.category_name || "General"),
    rate: recordNumber(item.sales_rate),
    mrp: recordNumber(item.mrp, recordNumber(item.sales_rate)),
    taxRate: recordNumber(item.gst_rate),
    stock: recordNumber((item.stock as {available_quantity?:string}|undefined)?.available_quantity, recordNumber(item.current_quantity)),
    checkoutSupported: item.checkout_supported !== false,
    bookingRequired: Boolean((item.booking_policy as {required?:boolean}|undefined)?.required),
    unsupportedReason: item.unsupported_reason ? String(item.unsupported_reason) : undefined,
    reorderLevel: recordNumber(item.reorder_level),
    trackInventory: !["service","services"].includes(String(item.product_type).toLowerCase()) && item.track_inventory !== false,
    batchTracking: Boolean(item.batch_tracking),
    serialTracking: Boolean(item.serial_tracking),
    lotAllocation: item.lot_allocation === "fefo" ? "fefo" : undefined,
    decimalAllowed: item.lot_allocation === "fefo" || String(item.unit_code || "").toUpperCase() !== "PCS",
  };
}

function lineBase(line: CartLine) {
  return line.qty * line.rate;
}

function lineDiscount(line: CartLine) {
  return (lineBase(line) * line.discount) / 100;
}

function lineTaxable(line: CartLine) {
  return Math.max(lineBase(line) - lineDiscount(line), 0);
}

function lineTax(line: CartLine) {
  return (lineTaxable(line) * line.taxRate) / 100;
}

function lineTotal(line: CartLine) {
  return lineTaxable(line) + lineTax(line);
}

function buildCartLine(product: Product): CartLine {
  return {
    ...product,
    lineId: crypto.randomUUID(),
    qty: 1,
    discount: 0,
    note: "",
    batchNo: product.batchTracking ? product.batch : undefined,
    serialNo: product.serialTracking ? product.serials?.[0] : undefined,
  };
}

function usePersistedState<T>(key: string, initialValue: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw ? (JSON.parse(raw) as T) : initialValue;
    } catch {
      return initialValue;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // Local storage is optional for POS draft recovery.
    }
  }, [key, value]);

  return [value, setValue] as const;
}

function posDraftScope() {
  const user = useAuthStore.getState().user;
  return encodeURIComponent(JSON.stringify(['pos-draft-v3',logicalIntentScope(),securityAuthStamp(user)]));
}
function normalizeCart(lines: CartLine[]) { return lines.map(line => ({...line, lineId: /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(line.lineId) ? line.lineId : crypto.randomUUID(), qty: line.booking ? 1 : line.qty})); }
function isService(line: Product) { return ['service','services'].includes(line.kind.toLowerCase()); }
export default function SRMPOSPage() {
  const scope = useRecordScope(), [packGeneration, setPackGeneration] = useState(0);
  useEffect(() => { const changed = () => setPackGeneration(value => value + 1); const events = ['suite:pack-context-changed','suite:business-pack-changed']; events.forEach(name => window.addEventListener(name, changed)); return () => events.forEach(name => window.removeEventListener(name, changed)); }, []);
  const draftScope = posDraftScope();
  return <POSAuthority key={`${scope}:${packGeneration}:${draftScope}`} scope={`${scope}:${draftScope}`} draftScope={draftScope}/>;
}
function POSAuthority({scope,draftScope}:{scope:string;draftScope:string}) {
  const [mount] = useState(() => crypto.randomUUID());
  const [bound,setBound] = useState(false);
  const owner=operationalOwner(), branch=selectedBranch();
  const branchQuery=useQuery({queryKey:['srm','pos-branch-bootstrap',scope,mount],enabled:branch===null,retry:false,staleTime:0,gcTime:0,
    queryFn:async()=>{
      const response=await api.get('/branches/context',{headers:{'X-Suite-Pack-Context':null},recordCache:false});
      if(selectedBranch()!==null)window.dispatchEvent(new Event('suite:branch-changed'));
      return response.data;
    }});
  const verified=useQuery<OperationalSelection>({queryKey:['srm','pos-operational-selection',scope,mount],enabled:branch!==null && branch!=='all',retry:false,staleTime:0,gcTime:0,refetchOnWindowFocus:false,
    queryFn:async()=>{
      const captured=operationalOwner(),user=useAuthStore.getState().user;
      const established=currentPOSOperationalPin();
      const config=established?.owner===captured ? {recordCache:false as const} : {recordCache:false as const,headers:{'X-Suite-Pack-Context':selectedPackContext()}};
      const identityConfig={recordCache:false as const,headers:{'X-Suite-Pack-Context':selectedPackContext()}};
      const [identity,access,response]=await Promise.all([api.get('/auth/me',identityConfig),api.get('/access/me',identityConfig),api.get('/srm/industry/capabilities',config)]);
      if(captured!==operationalOwner())throw new Error('POS context changed. Reload before continuing.');
      const role=typeof identity.data.role==='string' ? identity.data.role : identity.data.role?.name || null;
      const fresh={...user,...identity.data,role,primary_role:role,access:access.data};
      if(securityAuthStamp(fresh)!==securityAuthStamp(user))throw new Error('Your access changed. Reload the page before continuing.');
      return effectiveOperationalSelection(response.data?.operational_scope,fresh,selectedBranch(),selectedPackContext());
    }});
  useLayoutEffect(()=>{
    if(!verified.data || owner!==operationalOwner())return;
    const cleanup=installPOSOperationalPin(verified.data,owner);
    setBound(true);
    return cleanup;
  },[verified.data,owner]);
  const pin=currentPOSOperationalPin();
  if(!verified.data || !bound || verified.isError || pin?.owner!==owner) {
    const error=verified.error || branchQuery.error;
    return <div className="p-4"><div role={error ? 'alert' : 'status'} className="rounded-lg border bg-white p-4 text-sm">
      {branch==='all' ? 'Select one branch to use POS.' : error ? (error instanceof Error ? error.message : 'POS access could not be verified.') : 'Verifying POS access�'}
      {(error || branch==='all') && <button type="button" className="ml-3 rounded border px-3 py-1" onClick={()=>{if(error instanceof Error && error.message.startsWith('Your access changed.'))window.location.reload();else if(branch===null)void branchQuery.refetch();else void verified.refetch();}}>Reload POS access</button>}
    </div></div>;
  }
  return <ScopedPOS scope={`${scope}:${mount}`} draftScope={draftScope} selectedPOS={verified.data.realm==='pack'} operationalPackKey={verified.data.pack_key}/>;
}
function ScopedPOS({scope,draftScope,selectedPOS,operationalPackKey}:{scope:string;draftScope:string;selectedPOS:boolean;operationalPackKey:string|null}) {
  const owns = useRecordScopeOwner();
  const storage = (key:string) => `business-suite-srm-pos-v2:${draftScope}:${key}`;
  const navigate = useNavigate();
  const authUser = useAuthStore(state => state.user);
  const queryClient = useQueryClient();
  useSrmRealtimeInvalidation(queryClient);
  const [activeProfileId, setActiveProfileId] = usePersistedState(storage("profile"), defaultStoreProfile.id);
  const [tileDensity, setTileDensity] = usePersistedState<"comfortable" | "compact">(storage("density"), "comfortable");
  const [productView, setProductView] = usePersistedState<ProductViewMode>(storage("product-view"), "tiles");
  const activeStoreProfile = useMemo(() => posStoreProfiles.find((profile) => profile.id === activeProfileId) || defaultStoreProfile, [activeProfileId]);
  const mode = activeStoreProfile.mode;
  const [customerId, setCustomerId] = usePersistedState(storage("customer"), 0);
  const [customerProfile,setCustomerProfile]=useState(false);
  const [quickAddOpen, setQuickAddOpen] = useState(false);
  const customersQuery = useQuery<Customer[]>({ queryKey: ["srm", "posCustomers", scope], queryFn: async () => {
    const items: Customer[] = [];
    let after: number | null = 0;
    while (after !== null) {
      const { data }: { data: { items: PosCustomerRecord[]; next: number | null } } = await api.get(selectedPOS ? "/srm/pos/customers" : "/srm/business/customers", { params: { after }, progress: false,recordCache:false });
      items.push(...data.items.map(savedCustomer));
      after = data.next;
    }
    return items;
  } });
  const customers = [walkInCustomer, ...(customersQuery.data || [])];
  function customerCreated(record: PosCustomerRecord) {
    queryClient.setQueryData<Customer[]>(["srm", "posCustomers", scope], current => [...(current || []).filter(c => c.id !== record.id), savedCustomer(record)]);
    setCustomerId(record.id);
    setQuickAddOpen(false);
    void queryClient.invalidateQueries({ queryKey: ["follow-up-options"] });
    toast({ title: "Customer added", description: `${record.name} is selected for this sale and its follow-ups.` });
  }
  const [query, setQuery] = useState("");
  const [mobileView, setMobileView] = useState<"products" | "cart">("products");
  const [configurationOpen, setConfigurationOpen] = useState(false);
  const [sessionDetailsOpen, setSessionDetailsOpen] = useState(false);
  const [category, setCategory] = useState("All");
  const [cart, setCart] = usePersistedState<CartLine[]>(storage("cart"), []);
  const [localHeldBills, setLocalHeldBills] = usePersistedState<HeldBill[]>(storage("held"), []);
  const [sales, setSales] = usePersistedState<Sale[]>(storage("sales"), []);
  const [billDiscount, setBillDiscount] = usePersistedState(storage("bill-discount"), 0);
  const [coupon, setCoupon] = usePersistedState(storage("coupon"), "");
  const [note, setNote] = usePersistedState(storage("note"), "");
  const [activeModal, setActiveModal] = useState<"payment" | "held" | "success" | "close" | "cash" | "profile" | null>(null);
  const [paymentMode, setPaymentMode] = useState<PaymentMode>(() => paymentModes.find(mode => mode.toLowerCase() === defaultText("payment_mode_name", "srm").toLowerCase() || mode.toLowerCase() === defaultText("payment_mode_type", "srm").toLowerCase()) || "Cash");
  const [paymentRows, setPaymentRows] = usePersistedState<PaymentRow[]>(storage("payment-rows"), []);
  const [lastSale, setLastSale] = useState<Sale | null>(null);
  const [closingCash, setClosingCash] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);
  const productsQuery = useQuery({ queryKey: ["srm", "inventoryItems", "pos", scope], queryFn: async () => {
    if(selectedPOS) {
      const items:SRMRecord[]=[];let after:number|null=0;let features:POSFeatures|undefined;
      while(after!==null){const data:{items:SRMRecord[];next:number|null;features:POSFeatures}=(await api.get("/srm/pos/catalog",{params:{after},progress:false,recordCache:false})).data;items.push(...data.items);features=data.features;after=data.next;}
      return {items,total:items.length,features};
    }
    const items:SRMRecord[]=[];let page=1,total=Infinity;
    while(items.length<total){const response=await api.get("/srm/inventory/items",{params:{page,per_page:200},progress:false,recordCache:false});items.push(...response.data.items);total=response.data.total;if(!response.data.items.length)break;page++;}
    return {items,total,features:undefined as POSFeatures|undefined};
  }, refetchInterval: 30000, refetchIntervalInBackground: true, refetchOnWindowFocus: true });
  const posFeatures = productsQuery.data?.features;
  const heldBillsQuery = useQuery({ enabled:!selectedPOS, queryKey: ["srm", "posHeldBills", scope], queryFn: () => srmApi.posHeldBills(), refetchInterval: 5000, refetchIntervalInBackground: true, refetchOnWindowFocus: true });

  const followUpOptions = useQuery({enabled:!selectedPOS,queryKey:["follow-up-options",scope],queryFn:()=>api.get("/follow-ups/options").then(r=>r.data)});
  const [checkoutKey, setCheckoutKey] = usePersistedState(storage("checkout-key"), crypto.randomUUID());
  const intentKey = financialIntentKey("checkout");
  const [recovery] = useState(() => readPOSCheckoutIntent<CheckoutAttempt>(intentKey));
  const [uncertain, setUncertain] = useState<CheckoutAttempt|null>(recovery.payload);
  const [opaqueLock, setOpaqueLock] = useState(recovery.pending && !recovery.payload);
  const uncertainty = useRef(uncertain);
  const [nativeBusy, setNativeBusy] = useState(false), [nativeError, setNativeError] = useState('');
  const locked = opaqueLock || !!uncertain || nativeBusy;
  const [requirements, setRequirements] = useState<Record<string,boolean>>({});
  const [openingCash, setOpeningCash] = useState('0'), [opening, setOpening] = useState(false);
  const activeRegister = useQuery({queryKey:['srm','pos-active-session',scope],queryFn:()=>srmApi.activePosSession(),retry:false});
  const paymentCaps = useQuery({queryKey:['srm','pos-checkout-payment-capabilities',scope],queryFn:()=>api.get<{collect:boolean}>('/srm/industry/capabilities').then(response=>response.data),enabled:!!lastSale?.checkoutId,retry:false});
  type CheckoutAuthority = {invoice?:boolean;collect?:boolean;checkout_create?:boolean;checkout_collect?:boolean};
  const recoveryAuthority = useQuery({queryKey:['srm','pos-checkout-recovery-authority',scope],queryFn:({signal})=>api.get<CheckoutAuthority>('/srm/industry/capabilities',{signal,recordCache:false}).then(response=>response.data),retry:false,placeholderData:undefined});
  const permitsRecovery = (authority:CheckoutAuthority|undefined, attempt:CheckoutAttempt|null) => !!authority && !!attempt && Array.isArray(attempt.payload.payments) && authority.checkout_create === true && (!attempt.payload.payments.length || authority.checkout_collect === true);
  const canReplay = recoveryAuthority.isSuccess && !recoveryAuthority.isFetching && permitsRecovery(recoveryAuthority.data, uncertain);

  const register = (activeRegister.data as {session?:{id:number;session_number?:string;status?:string;opening_cash?:number}}|undefined)?.session;
  function saveAttempt(value:CheckoutAttempt|null) { if(value) saveFinancialIntent(intentKey,value); else clearFinancialIntent(intentKey); uncertainty.current=value; setUncertain(value); }
  useEffect(()=>{setCart(current=>normalizeCart(current));},[]);
  const checkoutBusy = useRef(false);
  const customer = customers.find((item) => item.id === customerId) || customers[0];
  const serverHeldBills = useMemo(() => listItems(heldBillsQuery.data).map(heldBillFromRecord).filter(bill=>bill.cart.length>0&&bill.cart.every(line=>line.draftScope===draftScope)), [heldBillsQuery.data,draftScope]);
  const heldBills = useMemo(() => selectedPOS ? [] : [...serverHeldBills, ...localHeldBills], [selectedPOS, localHeldBills, serverHeldBills]);
  const dbProducts = useMemo(() => listItems(productsQuery.data).map(productFromRecord).filter((item) => item.active !== false), [productsQuery.data]);
  const productSource = dbProducts;
  const storeProducts = productSource;
  const [catalogTab, setCatalogTab] = useState("All");
  const [catalogSort, setCatalogSort] = useState("name");
  const [recentIds, setRecentIds] = usePersistedState<number[]>(storage("recent-catalog"), []);
  const categories = useMemo(() => ["All", ...Array.from(new Set(storeProducts.map((item) => item.category)))], [storeProducts]);
  const couponDiscount = coupon.trim().toUpperCase() === "WELCOME10" ? Math.min(250, Math.max(0, cart.reduce((sum, item) => sum + lineTaxable(item), 0) * 0.1)) : 0;

  const totals = useMemo(() => {
    const subtotal = cart.reduce((sum, item) => sum + lineBase(item), 0);
    const lineDiscountTotal = cart.reduce((sum, item) => sum + lineDiscount(item), 0);
    const taxableBeforeBill = cart.reduce((sum, item) => sum + lineTaxable(item), 0);
    const safeBillDiscount = Math.min(Math.max(billDiscount, 0), taxableBeforeBill);
    const taxable = Math.max(taxableBeforeBill - safeBillDiscount - couponDiscount, 0);
    const taxBeforeScale = cart.reduce((sum, item) => sum + lineTax(item), 0);
    const tax = taxableBeforeBill ? taxBeforeScale * (taxable / taxableBeforeBill) : 0;
    const unrounded = taxable + tax;
    const grandTotal = Math.max(Math.round((unrounded + Number.EPSILON) * 100) / 100, 0);
    const nativeQuote = operationalPackKey === "pharma" && cart.some(line => line.lotAllocation === "fefo")
      ? pharmaCheckoutQuote(cart.map(line => ({quantity: String(line.qty), price: line.rate.toFixed(2),
          discount: lineDiscount(line).toFixed(2), taxRate: String(line.taxRate)})),
          (safeBillDiscount + couponDiscount).toFixed(2)) : null;
    return {
      subtotal,
      lineDiscount: lineDiscountTotal,
      billDiscount: safeBillDiscount,
      couponDiscount,
      taxable,
      tax,
      roundOff: grandTotal - unrounded,
      grandTotal,
      qty: cart.reduce((sum, item) => sum + item.qty, 0),
      ...(nativeQuote ? {...nativeQuote, qty: nativeQuote.quantity, roundOff: 0} : {}),
    };
  }, [billDiscount, cart, couponDiscount, operationalPackKey]);

  const filteredProducts = useMemo(() => {
    const text = query.trim().toLowerCase();
    return storeProducts.filter((product) => {
      const categoryMatch = category === "All" || product.category === category;
      const textMatch = !text || [product.name, product.sku, product.barcode, product.category, product.batch || "", ...(product.serials || [])].join(" ").toLowerCase().includes(text);
      return categoryMatch && textMatch && (catalogTab === "All" || (catalogTab === "Recently Used" ? recentIds.includes(product.id) : product.kind === catalogTab));
    }).sort((a,b) => catalogSort === "price" ? a.rate-b.rate : a.name.localeCompare(b.name));
  }, [category, query, storeProducts, catalogTab, catalogSort, recentIds]);

  const received = paymentRows.reduce((sum, row) => row.mode === "Credit" ? sum : sum + row.amount, 0);
  const balanceDue = Math.max(totals.grandTotal - received, 0);
  const changeDue = Math.max(received - totals.grandTotal, 0);
  const explicitCredit = paymentRows.filter(row=>row.mode==="Credit").reduce((sum,row)=>sum+row.amount,0);
  const validSplitCredit = customerId>0 && paymentMode==="Split" && explicitCredit>0 && Math.abs(explicitCredit-balanceDue)<0.005;
  const registerCash = activeRegister.data as {expected_cash?: number | string | null; cash_sales?: number | string | null; reconciliation_required?: boolean} | undefined;
  const expectedCash = cashNumber(registerCash?.expected_cash);
  const cashReceived = cashNumber(registerCash?.cash_sales);
  const countedClosingCash = cashNumber(closingCash);
  const canCloseSession = Boolean(register?.id) && !registerCash?.reconciliation_required && Number.isFinite(expectedCash) && Number.isFinite(countedClosingCash) && countedClosingCash >= 0;
  const lowStockCount = storeProducts.filter((product) => product.trackInventory && product.stock <= product.reorderLevel).length;

  function addProduct(product: Product) {
    if (locked) return;
    setRecentIds(current => [product.id, ...current.filter(id => id !== product.id)].slice(0, 50));
    if(product.checkoutSupported===false){toast({title:'Item unavailable for checkout',description:product.unsupportedReason,variant:'destructive'});return;}
    if (product.trackInventory && product.stock <= 0) {
      toast({ title: "Out of stock", description: `${product.name} cannot be added.` });
      return;
    }
    setCart((current) => {
      const existing = current.find((line) => line.id === product.id && !line.serialTracking && !isService(line));
      if (!existing) return [...current, buildCartLine(product)];
      return current.map((line) => line.lineId === existing.lineId ? { ...line, qty: line.trackInventory ? Math.min(line.stock, line.qty + 1) : line.qty + 1 } : line);
    });
  }

  function removeProduct(productId: number) {
    if (locked) return;
    setCart((current) => {
      const existing = current.find((line) => line.id === productId);
      if (!existing) return current;
      if (existing.qty <= 1) return current.filter((line) => line.lineId !== existing.lineId);
      return current.map((line) => line.lineId === existing.lineId ? { ...line, qty: line.qty - 1 } : line);
    });
  }

  function updateLine(lineId: string, patch: Partial<CartLine>) {
    if (locked) return;
    if(patch.booking) patch={...patch,qty:1};
    setCart((current) => current.map((line) => line.lineId === lineId ? { ...line, ...patch } : line));
  }

  function switchProfile(profileId: string) {
    if(locked)return;
    if (profileId === activeStoreProfile.id) return;
    if (cart.length) {
      toast({ title: "Clear cart before changing template", description: "Template changes are locked while a bill is active." });
      return;
    }
    setActiveProfileId(profileId);
    setCategory("All");
  }

  function openPayment(nextMode: PaymentMode = "Cash") {
    if(locked) return;
    if (!cart.length) {
      toast({ title: "Cart is empty", description: "Scan or select an item before checkout." });
      return;
    }
    setPaymentMode(nextMode);
    setPaymentRows(nextMode === "Split"
      ? [{ id: crypto.randomUUID(), mode: "Cash", amount: totals.grandTotal, reference: "" }]
      : [{ id: crypto.randomUUID(), mode: nextMode === "Credit" ? "Credit" : nextMode, amount: nextMode === "Credit" ? 0 : totals.grandTotal, reference: "" }]);
    setActiveModal("payment");
  }

  async function submitNative(attempt:CheckoutAttempt, replay=false) {
    if(!attempt || checkoutBusy.current || !owns()) return;
    checkoutBusy.current=true; setNativeBusy(true); setNativeError(''); setActiveModal(null);
    try {
      const authority = await recoveryAuthority.refetch();
      if (!owns() || !authority.isSuccess || !permitsRecovery(authority.data, attempt)) { if (owns()) setNativeError('Checkout permissions could not be verified. The saved request remains locked.'); return; }
      const {data:result}=await api.post<NativeCheckoutResult>('/srm/service-checkout',attempt.payload);
      if(result.state!=='committed'||!result.invoice?.number||!Number.isSafeInteger(result.id)) throw new Error('Checkout confirmation is incomplete. Retry the same saved checkout.');
      // Persist the known-success reset before removing the recovery payload.
      const nextKey=crypto.randomUUID();
      for(const [key,value] of Object.entries({'cart':[],'bill-discount':0,'coupon':'','note':'','payment-rows':[],'checkout-key':nextKey})) localStorage.setItem(storage(key),JSON.stringify(value));
      clearFinancialIntent(intentKey); recovery.sourceKeys.forEach(key=>localStorage.removeItem(key));
      if(!owns()) return;
      uncertainty.current=null; setUncertain(null); setCheckoutKey(nextKey); setCart([]);setBillDiscount(0);setCoupon('');setNote('');setPaymentRows([]);
      const sale:Sale={...attempt.sale,invoiceNo:result.invoice.number,amount:Number(result.invoice.total),checkoutId:result.id,paid:result.invoice.paid,balance:result.invoice.balance,receiptNumbers:result.receipts.map(row=>row.number),hasBookings:attempt.payload.lines.some(line=>!!line.booking)};
      setSales(current=>[sale,...current].slice(0,25));setLastSale(sale);setActiveModal('success');
      void syncSrmNow(queryClient,{type:'pos_sale_completed',source:'pos-terminal',ids:{sales_order_id:result.sales_order_id}});
      void productsQuery.refetch();if(!selectedPOS)void heldBillsQuery.refetch();void activeRegister.refetch();
      if(attempt.after==='print')setTimeout(()=>window.print(),150);
      if(attempt.after==='email')toast({title:'Checkout completed',description:'Email receipt delivery is not configured. No email has been queued.'});
      if(attempt.after==='whatsapp'&&phoneLinks(customer.phone)?.whatsapp)navigate('/crm/whatsapp',{state:{whatsappDraft:{key:`checkout:${sale.checkoutId}`,to:phoneLinks(customer.phone)!.call.slice(4),body:`Hello ${sale.customer}, thank you for your purchase. Invoice: ${sale.invoiceNo}. Total: ${shortCurrency(sale.amount)}. Paid: ${shortCurrency(Number(sale.paid))}. Balance: ${shortCurrency(Number(sale.balance))}.`}}});
    } catch(error) {
      const status=isAxiosError(error)?error.response?.status:undefined;
      if(!replay&&status!==undefined&&status>=400&&status<500) {
        clearFinancialIntent(intentKey); recovery.sourceKeys.forEach(key=>localStorage.removeItem(key));
        if(!owns())return;
        uncertainty.current=null;setUncertain(null);setCheckoutKey(crypto.randomUUID());setActiveModal('payment');
        toast({title:'Checkout rejected',description:dealError(error)+' Your basket is retained. Review and reload scheduling before trying again.',variant:'destructive'});
        void activeRegister.refetch();
      } else if(owns()) setNativeError(dealError(error)+' The original checkout is retained; retry the same checkout to confirm its outcome.');
    } finally {checkoutBusy.current=false;if(owns())setNativeBusy(false);}
  }
  async function prepareNative(after:CheckoutAfter) {
    if(checkoutBusy.current||opaqueLock||!owns())return;
    try { const stored=readFinancialIntent<CheckoutAttempt>(intentKey); if(stored.pending) { if(stored.payload?.payload?.request_id) { uncertainty.current=stored.payload;setUncertain(stored.payload); } else setOpaqueLock(true); setActiveModal(null);return; } } catch { toast({title:'Checkout recovery unavailable',description:'Local recovery storage must be available before checkout.',variant:'destructive'});return; }
    if(selectedPOS&&(productsQuery.isFetching||productsQuery.isError||cart.some(line=>{const item=dbProducts.find(item=>item.id===line.id);return !item||item.checkoutSupported===false||!!line.followUp||(!posFeatures?.appointments_schedule&&!!line.booking);}))){toast({title:'Review POS availability',description:'Reload the catalogue and remove unsupported follow-up or unavailable items before checkout.',variant:'destructive'});return;}
    if(cart.some(line=>isService(line)&&(!selectedPOS||!!posFeatures?.appointments_schedule)&&(!(line.lineId in requirements)||(requirements[line.lineId]&&!line.booking)))) {toast({title:'Complete service scheduling',description:'Wait for each service policy and apply booking details for every required service.',variant:'destructive'});return;}
    if(cart.some(line=>!isService(line)&&(line.serialTracking||(line.batchTracking&&line.lotAllocation!=="fefo")))) {toast({title:'Tracking checkout unavailable',description:'This checkout does not support batch or serial selection yet. Keep this basket for a supported stock workflow.',variant:'destructive'});return;}
    if(paymentRows.some(row=>row.mode==='Wallet'&&row.amount>0)||paymentMode==='Wallet') {toast({title:'Wallet is not supported for native checkout',description:'Choose cash, card, UPI or credit.',variant:'destructive'});return;}
    checkoutBusy.current=true;setNativeBusy(true);
    try {
      const response=await srmApi.activePosSession();
      const session=(response as {session?:{id:number;status?:string}}).session;
      if(!session?.id||(session.status&&session.status!=='open'))throw new Error('Open a POS register using Session & actions before checkout.');
      if(paymentRows.some(row=>!Number.isFinite(row.amount)||row.amount<0))throw new Error('Payment amounts must be nonnegative.');
      const nonCash=paymentRows.filter(row=>!['Cash','Credit'].includes(row.mode)).reduce((sum,row)=>sum+row.amount,0);
      if(paymentMode!=='Credit'&&nonCash>totals.grandTotal+0.001)throw new Error('Non-cash payments exceed the invoice total. Only cash can include change returned.');
      let cashRemaining=Math.max(0,totals.grandTotal-nonCash);
      const payments=paymentMode==='Credit'?[]:paymentRows.filter(row=>row.mode!=='Credit'&&row.amount>0).map(row=>{const amount=row.mode==='Cash'?Math.min(row.amount,cashRemaining):row.amount;if(row.mode==='Cash')cashRemaining=Math.max(0,cashRemaining-amount);return {payment_key:row.id,method:row.mode.toLowerCase(),amount:amount.toFixed(2),...(row.reference.trim()?{reference:row.reference.trim()}:{})};}).filter(row=>Number(row.amount)>0);
      if(!customerId) {
        if(cart.some(line=>line.booking||line.followUp))throw new Error('Select a registered customer for appointments and follow-ups.');
        if(paymentMode==='Credit'||Math.abs(payments.reduce((sum,row)=>sum+Number(row.amount),0)-totals.grandTotal)>0.001)throw new Error('Walk-in checkout must be fully paid. Select a registered customer for credit.');
        const configuration=(await api.get<AnonymousCashConfiguration>('/srm/anonymous-cash/configuration')).data;
        if(!configuration.schema_ready||!configuration.configured||!configuration.enabled)throw new Error('A company administrator must enable the explicit walk-in counter account before checkout.');
      }
      const payload:NativeCheckoutPayload={request_id:checkoutKey,...(customerId>0?{buyer_mode:'registered' as const,customer_id:customerId}:{buyer_mode:'anonymous_cash' as const}),pos_session_id:session.id,currency:'INR',billing_mode:'invoice_at_checkout',note,expected_total:totals.grandTotal.toFixed(2),bill_discount_amount:(totals.billDiscount+totals.couponDiscount).toFixed(2),
        lines:cart.map(line=>({client_line_key:line.lineId,line_kind:line.booking?'booked_service':isService(line)?'unscheduled_service':'product',product_id:line.id,quantity:String(line.booking?1:line.qty),unit_price:line.rate.toFixed(2),discount_amount:lineDiscount(line).toFixed(2),note:line.note,...(line.followUp?{follow_up:line.followUp}:{}),...(line.booking?{booking:line.booking}:{})})),payments};
      const attempt:CheckoutAttempt={payload,after,sale:{id:checkoutKey,invoiceNo:'',customer:customer.name,amount:totals.grandTotal,mode:paymentMode,createdAt:new Date().toISOString(),items:cart.length}};
      saveAttempt(attempt);checkoutBusy.current=false;setNativeBusy(false);await submitNative(attempt);
    } catch(error) {if(owns())toast({title:'Checkout not started',description:error instanceof Error?error.message:dealError(error),variant:'destructive'});checkoutBusy.current=false;if(owns())setNativeBusy(false);}
  }

  async function completeSale(after: "done" | "print" | "whatsapp" | "email" | "request_payment") {
    if(uncertainty.current) {await submitNative(uncertainty.current,true);return;}
    if(nativeBusy||opaqueLock||!owns())return;
    if (after === "request_payment" && !customerId) {
      toast({ title: "Select a customer", description: "A saved customer is required for a payment request.", variant: "destructive" });
      return;
    }
    if (after === "whatsapp" && (!phoneLinks(customer.phone)?.whatsapp || !canAccessRoute("/crm/whatsapp", authUser?.role, authUser?.is_superuser))) {
      toast({ title: "WhatsApp receipt unavailable", description: "Select a customer with an international phone number and make sure you have access to WhatsApp in Communication.", variant: "destructive" });
      return;
    }
    if (!cart.length) return;
    if (customerId && customer.id !== customerId) {
      toast({ title: "Select a customer", description: "The selected customer is unavailable. Reload customers or select another customer.", variant: "destructive" });
      return;
    }
    if (paymentMode === "Credit" && customer.type === "Walk-in") {
      toast({ title: "Customer required", description: "Credit sale needs a registered customer." });
      return;
    }
    if (after !== "request_payment" && paymentMode !== "Credit" && received < totals.grandTotal && !validSplitCredit) {
      toast({ title: "Payment short", description: "Received amount is less than the bill total." });
      return;
    }
    for (const line of cart) {
      if (line.trackInventory && line.qty > line.stock) {
        toast({ title: "Stock check failed", description: `Only ${line.stock} available for ${line.name}.` });
        return;
      }
      if (line.serialTracking && !line.serialNo) {
        toast({ title: "Serial required", description: `${line.name} needs a serial number.` });
        return;
      }
    }
    if(customerId>0) {
      if(after==='request_payment') {toast({title:'Use Credit for an unpaid checkout',description:'Payment-request preparation is not linked to native service checkout. Choose Credit to save the invoice and bookings together without receiving payment.',variant:'destructive'});return;}
      await prepareNative(after);return;
    }
    if(cart.some(line=>line.booking||line.followUp)) {toast({title:'Select a registered customer',description:'Appointments and follow-ups require a named customer.',variant:'destructive'});return;}
    await prepareNative(after);
  }

  async function holdCart() {
    if(selectedPOS){toast({title:"Held bills unavailable",description:"Held bills are not integrated in this Business Pack POS yet."});return;}
    if(locked) return;
    if (!cart.length) {
      toast({ title: "Cart is empty", description: "Add items before holding a bill." });
      return;
    }
    const held: HeldBill = {
      id: uid("hold"),
      holdNo: `HOLD-${String(heldBills.length + 1).padStart(4, "0")}`,
      customerId,
      notes: note || `${customer.name} counter bill`,
      cart: cart.map(line=>({...line,draftScope,heldBillDiscount:billDiscount,heldCoupon:coupon})),
      billDiscount,coupon,
      amount: totals.grandTotal,
      createdAt: new Date().toISOString(),
    };
    try {
      const activeSession = await srmApi.activePosSession();
      const posSession = (activeSession as { session?: { id?: number } | null })?.session || null;
      const saved = await srmApi.createPosHeldBill({
        session_id: posSession?.id,
        customer_id: customerId || undefined,
        customer_name: customer.name,
        notes: held.notes,
        cart_json: held.cart,
        amount: totals.grandTotal,
        item_count: cart.length,
      });
      await heldBillsQuery.refetch();
      held.holdNo = String((saved as SRMRecord).holdNo || (saved as SRMRecord).hold_number || held.holdNo);
    } catch {
      setLocalHeldBills((current) => [held, ...current]);
      toast({ title: "Held locally", description: "Could not sync held bill to SRM; it is saved in this browser.", variant: "destructive" });
    }
    setCart([]);
    setBillDiscount(0);setCoupon("");
    setNote("");
    toast({ title: "Bill held", description: `${held.holdNo} is ready for recall.` });
  }

  async function recallBill(bill: HeldBill) {
    if(selectedPOS)return;
    if(locked) return;
    let recalled = bill;
    if (typeof bill.id === "number") {
      try {
        recalled = heldBillFromRecord(await srmApi.recallPosHeldBill(bill.id));
        await heldBillsQuery.refetch();
      } catch {
        toast({ title: "Recall failed", description: "Could not recall held bill from SRM.", variant: "destructive" });
        return;
      }
    }
    setCart(normalizeCart(recalled.cart));
    setNote(recalled.notes);setBillDiscount(recalled.billDiscount||0);setCoupon(recalled.coupon||"");
    setCustomerId(recalled.customerId);
    setLocalHeldBills((current) => current.filter((item) => item.id !== bill.id));
    setActiveModal(null);
    toast({ title: "Bill recalled", description: `${bill.holdNo} restored to cart.` });
  }

  async function deleteHeldBill(bill: HeldBill) {
    if(selectedPOS)return;
    if(locked)return;
    if (typeof bill.id === "number") {
      try {
        await srmApi.deletePosHeldBill(bill.id);
        await heldBillsQuery.refetch();
        return;
      } catch {
        toast({ title: "Delete failed", description: "Could not delete held bill in SRM.", variant: "destructive" });
        return;
      }
    }
    setLocalHeldBills((current) => current.filter((item) => item.id !== bill.id));
  }

  function scanSearch() {
    const exact = storeProducts.find((product) => product.barcode === query.trim() || product.sku.toLowerCase() === query.trim().toLowerCase());
    if (exact) {
      addProduct(exact);
      setQuery("");
      return;
    }
    if (filteredProducts.length === 1) {
      addProduct(filteredProducts[0]);
      setQuery("");
    }
  }

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if(locked)return;
      if (event.key === "F2") {
        event.preventDefault();
        searchRef.current?.focus();
      }
      if (event.key === "F4") {
        event.preventDefault();
        holdCart();
      }
      if (event.key === "F5") {
        event.preventDefault();
        setActiveModal("held");
      }
      if (event.key === "F7") {
        event.preventDefault();
        openPayment("Cash");
      }
      if (event.key === "F8") {
        event.preventDefault();
        window.print();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });

  useEffect(() => {
    if (category !== "All" && !categories.includes(category)) {
      setCategory("All");
    }
  }, [categories, category]);

  return (
    <><fieldset disabled={locked} className="contents">
    <div className={`srm-pos srm-pos-view-${mobileView} min-h-full bg-[linear-gradient(135deg,#eef7f2_0%,#f7f4ee_48%,#eef2ff_100%)] text-slate-950`}>
      <header className="relative z-30 border-b border-white/70 bg-white/85 px-4 py-3 shadow-sm backdrop-blur">
        <div className="flex flex-col gap-3 2xl:flex-row 2xl:items-center 2xl:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-[#3157d8] text-white shadow-sm">
              <ShoppingCart className="h-6 w-6" />
            </span>
            <div className="min-w-0">
              <h1 className="truncate text-xl font-semibold">Sales & Inventory POS</h1>
              <p className="text-sm text-slate-500">{activeStoreProfile.branch} / {activeStoreProfile.register} / Session {register?.session_number || (register ? `#${register.id}` : "not open")}</p>
            </div>
          </div>
          <button type="button" className="srm-pos-session-toggle" aria-expanded={sessionDetailsOpen} aria-controls="pos-session-details" onClick={() => setSessionDetailsOpen(value => !value)}><Settings size={18} />Session & actions<span aria-hidden="true">{sessionDetailsOpen ? "−" : "+"}</span></button>
          <div id="pos-session-details" className={`srm-pos-session-details ${sessionDetailsOpen ? "is-open" : ""}`}>
          <div className="grid grid-cols-2 gap-2 text-xs md:flex md:items-center">
            <SessionPill label="Template" value={activeStoreProfile.name} />
            <SessionPill label="Cashier" value="Sales Manager" />
            <SessionPill label="Opening cash" value={shortCurrency(Number(register?.opening_cash||0))} />
            <SessionPill label="Expected cash" value={Number.isFinite(expectedCash)?shortCurrency(expectedCash):"Unavailable"} />
          </div>
          <CompactActions className="flex flex-wrap gap-2">
            {!register && <><Input aria-label="POS opening cash" className="w-28 border-slate-200 bg-slate-50 text-slate-950" type="number" min="0" value={openingCash} onChange={event=>setOpeningCash(event.target.value)}/><Button variant="outline" className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50" disabled={opening||activeRegister.isFetching} onClick={async()=>{if(locked||!owns())return;setOpening(true);try{await srmApi.openPosSession({branch:activeStoreProfile.branch,register_name:activeStoreProfile.register,opening_cash:openingCash});if(owns())await activeRegister.refetch();}catch(error){if(owns())toast({title:"Register not opened",description:dealError(error),variant:"destructive"});}finally{if(owns())setOpening(false);}}}>Open POS register</Button></>}
            {activeRegister.isError && <Button variant="outline" onClick={()=>void activeRegister.refetch()}>Reload POS register</Button>}
            <Button variant="outline" className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50" onClick={() => setActiveModal("cash")}><Banknote className="h-4 w-4" />Cash drawer</Button>
            <Button variant="outline" className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50" onClick={() => setActiveModal("profile")}><Settings className="h-4 w-4" />Template</Button>
            <Button variant="outline" className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50" onClick={() => window.print()}><Printer className="h-4 w-4" />Print</Button>
            <Button variant="destructive" onClick={() => setActiveModal("close")}><DoorClosed className="h-4 w-4" />Close</Button>
          </CompactActions>
          </div>
        </div>
      </header>

      <section className="grid gap-3 border-b border-white/70 bg-white/75 px-4 py-3 backdrop-blur xl:grid-cols-[minmax(20rem,1fr)_24rem_auto]">
        <div className="relative">
          <Search className="absolute left-3 top-3 h-5 w-5 text-slate-400" />
          <Input
            ref={searchRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") scanSearch();
            }}
            className="h-11 border-slate-200 bg-slate-50 pl-10 text-base text-slate-950 placeholder:text-slate-400"
            placeholder="Search or scan product, SKU, barcode [F2]"
          />
        </div>
        <div className="min-w-0"><div className="flex gap-2">
          <Select loading={customersQuery.isFetching} error={customersQuery.isError} value={String(customerId)} onValueChange={(value) => setCustomerId(Number(value))}>
            <SelectTrigger aria-label="Sale customer" className="h-11 min-w-0 border-slate-200 bg-white text-slate-950"><SelectValue /></SelectTrigger>
            <SelectContent>{customers.map(item => <SelectItem key={item.id} value={String(item.id)}>{item.name}{item.phone ? ` · ${item.phone}` : ""}</SelectItem>)}</SelectContent>
          </Select>
          {customerId>0&&<Button type="button" variant="outline" aria-label="Open customer 360" onClick={()=>setCustomerProfile(true)}>360°</Button>}
          {customerProfile&&customerId>0&&<>{selectedPOS?<POSCustomerProfile id={customerId} onClose={()=>setCustomerProfile(false)}/>:<CompanyProfile id={customerId} source="srm" onClose={()=>setCustomerProfile(false)}/>}</>}
          <Button type="button" variant="outline" className="h-11 shrink-0 border-slate-200 bg-white text-slate-950" disabled={selectedPOS&&!posFeatures?.customers_register} title={selectedPOS?posFeatures?.registration_unavailable_reason||undefined:undefined} onClick={() => setQuickAddOpen(true)}><Plus size={16}/>Quick add</Button>
        </div>{customerId===0&&<AnonymousCashSetup canConfigure={!!authUser?.is_superuser||!!(authUser?.access as {isAccessAdmin?:boolean}|undefined)?.isAccessAdmin}/>} {customersQuery.isError && <p role="alert" className="mt-1 text-xs text-red-700">Unable to load customers. <Button variant="outline" type="button" className="underline" onClick={() => void customersQuery.refetch()}>Retry</Button></p>}</div>
        <Button className="h-11 bg-[#3157d8] px-6 text-white hover:bg-[#2748b8]" onClick={() => openPayment("Cash")}><CreditCard className="h-4 w-4" />Payment [F7]</Button>
      </section>

      <nav className="srm-pos-mobile-tabs" aria-label="POS workspace">
        <button type="button" aria-pressed={mobileView === "products"} onClick={() => setMobileView("products")}><LayoutGrid size={18} />Products</button>
        <button type="button" aria-pressed={mobileView === "cart"} onClick={() => setMobileView("cart")}><ShoppingCart size={18} />Cart ({cart.length})</button>
      </nav>
      <main className="grid min-h-[calc(100vh-13.5rem)] gap-4 p-4 xl:grid-cols-[15rem_minmax(0,1fr)_28rem]">
        <aside className={`srm-pos-configuration ${configurationOpen ? "is-open" : ""} rounded-2xl border border-white/80 bg-white/90 p-3 shadow-sm backdrop-blur`}>
          <button type="button" className="srm-pos-configuration-toggle" aria-expanded={configurationOpen} aria-controls="pos-register-configuration" onClick={() => setConfigurationOpen(value => !value)}><Settings size={18} />Categories & register<span>{configurationOpen ? "−" : "+"}</span></button>
          <div id="pos-register-configuration">
          <div className="mb-3 flex items-center justify-between px-2">
            <strong className="text-sm">Categories</strong>
            <span className="text-xs text-slate-400">{storeProducts.length} items</span>
          </div>
          <div className="space-y-1">
            {categories.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setCategory(item)}
                className={`flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm transition ${
                  category === item ? "bg-[#e8edff] font-semibold text-[#3157d8]" : "text-slate-600 hover:bg-slate-50 hover:text-slate-950"
                }`}
              >
                <span className="flex min-w-0 items-center gap-2">
                  <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-xs font-semibold ${category === item ? "bg-white text-[#3157d8]" : "bg-slate-100 text-slate-500"}`}>
                    {item === "All" ? "A" : item.slice(0, 1)}
                  </span>
                  <span className="truncate">{item}</span>
                </span>
                <span className="text-xs text-slate-400">{item === "All" ? storeProducts.length : storeProducts.filter((product) => product.category === item).length}</span>
              </button>
            ))}
          </div>
          <div className="mt-4 space-y-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
            <div>
              <span className="text-xs font-semibold uppercase text-slate-500">Register template</span>
              <Select value={activeStoreProfile.id} onValueChange={switchProfile}>
                <SelectTrigger className="mt-2 border-slate-200 bg-slate-50 text-slate-950">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {posStoreProfiles.map((profile) => <SelectItem key={profile.id} value={profile.id}>{profile.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Button type="button" variant={tileDensity === "comfortable" ? "default" : "outline"} className={tileDensity === "comfortable" ? "bg-[#3157d8] text-white hover:bg-[#2748b8]" : "border-slate-200 text-slate-700"} onClick={() => setTileDensity("comfortable")}>Comfort</Button>
              <Button type="button" variant={tileDensity === "compact" ? "default" : "outline"} className={tileDensity === "compact" ? "bg-[#3157d8] text-white hover:bg-[#2748b8]" : "border-slate-200 text-slate-700"} onClick={() => setTileDensity("compact")}>Compact</Button>
            </div>
          </div>
          <div className="mt-4 rounded-xl border border-emerald-100 bg-emerald-50/80 p-3 text-xs text-slate-600">
            <div className="flex items-center gap-2 font-semibold text-slate-900"><Settings className="h-4 w-4" />Active template</div>
            <div className="mt-2"><RichTextContent legacyFormat="plain" value={activeStoreProfile.description}/></div>
          </div>
          </div>
        </aside>
        <section className="srm-pos-catalog min-w-0 space-y-4 overflow-y-auto rounded-2xl border border-white/80 bg-white/65 p-4 shadow-sm backdrop-blur">
          <div className="srm-pos-stock-summary grid gap-3 md:grid-cols-3">
            <StatusTile label="Products" value={String(storeProducts.length)} detail={`${filteredProducts.length} visible`} />
            <StatusTile label="Low stock" value={String(lowStockCount)} detail="Reorder watch" />
            <StatusTile label="Cart quantity" value={String(totals.qty)} detail={`${cart.length} lines`} />
          </div>
          <div className="srm-pos-mode-summary"><ModePanel mode={mode} customer={customer} /></div>
          <div className="flex flex-col gap-3 rounded-2xl border border-white bg-white p-3 shadow-sm md:flex-row md:items-center md:justify-between">
            <div>
              <strong className="text-sm text-slate-950">Products & services</strong>
              <p className="text-xs text-slate-500">{filteredProducts.length} eligible products & services</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button asChild variant="outline"><Link to="/srm/inventory/products">Manage catalog</Link></Button>
              {(authUser?.is_superuser || (authUser?.access?.grants.srm?.enabled && authUser.access.grants.srm.actions.includes("create")) || (!authUser?.access?.managed && ["admin", "srm_admin", "srm_sales_manager", "srm_sales_executive"].includes(String(authUser?.role).toLowerCase()))) && <><Button asChild variant="outline"><Link to="/srm/inventory/products?new=item&kind=product"><Plus size={16}/>Add product</Link></Button><Button asChild variant="outline"><Link to="/srm/inventory/products?new=item&kind=service"><Plus size={16}/>Add service</Link></Button></>}
              <ViewModeButton active={productView === "tiles"} icon={LayoutGrid} label="Tiles" onClick={() => setProductView("tiles")} />
              <ViewModeButton active={productView === "list"} icon={List} label="List" onClick={() => setProductView("list")} />
              <ViewModeButton active={productView === "details"} icon={Table2} label="Details" onClick={() => setProductView("details")} />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2" aria-label="Catalogue filters">
            {["All", "Products", "Services", "Packages", "Recently Used"].map(tab => <Button key={tab} variant={catalogTab === tab ? "default" : "outline"} size="sm" onClick={() => setCatalogTab(tab)}>{tab} ({storeProducts.filter(p => tab === "All" || (tab === "Recently Used" ? recentIds.includes(p.id) : p.kind === tab)).length})</Button>)}
            <NativeSelect aria-label="Sort catalogue" className="rounded border p-2 text-sm" value={catalogSort} onChange={e => setCatalogSort(e.target.value)}><option value="name">Name</option><option value="price">Price: low to high</option></NativeSelect>
          </div>
          {productsQuery.isLoading && <div role="status" aria-label="Loading products and services" aria-busy="true"><span className="sr-only">Loading products and services</span><div aria-hidden="true" className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 motion-safe:animate-pulse">{Array.from({length:10},(_,i)=><div key={i} className="overflow-hidden rounded-xl border bg-white"><div className="h-20 bg-slate-100"/><div className="space-y-3 p-3"><div className="h-3 w-4/5 rounded bg-slate-100"/><div className="h-3 w-1/2 rounded bg-slate-100"/><div className="h-4 w-1/3 rounded bg-slate-100"/></div></div>)}</div></div>}
          {productsQuery.isError && <p role="alert">Unable to load the catalog. <Button variant="outline" type="button" className="underline" onClick={() => void productsQuery.refetch()}>Retry</Button></p>}
          {!productsQuery.isLoading && !productsQuery.isError && !filteredProducts.length && <p className="rounded-lg border border-dashed p-6 text-sm text-slate-600">No active products or services match this view. Add an item in the shared catalog or change your filters.</p>}
          {productView === "details" ? (
            <div className="srm-pos-product-details overflow-x-auto rounded-2xl border border-white bg-white shadow-sm">
              <div className="grid grid-cols-[2fr_1fr_1fr_0.8fr_0.9fr_8rem] border-b border-slate-100 bg-slate-50 px-3 py-2 text-xs font-semibold uppercase text-slate-500">
                <span>Product</span>
                <span>SKU</span>
                <span>Category</span>
                <span>Stock</span>
                <span>Rate</span>
                <span className="text-center">Qty</span>
              </div>
              {filteredProducts.map((product) => {
                const qty = cart.filter((line) => line.id === product.id).reduce((sum, line) => sum + line.qty, 0);
                const lowStock = product.trackInventory && product.stock <= product.reorderLevel;
                return (
                  <div key={product.id} className={`grid grid-cols-[2fr_1fr_1fr_0.8fr_0.9fr_8rem] items-center border-b border-slate-100 px-3 py-2 text-sm last:border-b-0 ${qty ? "bg-[#f3f6ff]" : "bg-white hover:bg-slate-50"}`}>
                    <button type="button" className="flex min-w-0 items-center gap-2 text-left" onClick={() => addProduct(product)}>
                      <ProductMark product={product} lowStock={lowStock} />
                      <span className="min-w-0">
                        <strong className="block truncate text-slate-950">{product.name}</strong>
                        <span className="block truncate text-xs text-slate-400">{product.barcode}</span>
                      </span>
                    </button>
                    <span className="truncate text-slate-500">{product.sku} · {product.category} · Tax {product.taxRate}% {product.duration}</span>
                    <span className="truncate text-slate-500">{product.category}</span>
                    <span className={lowStock ? "font-medium text-red-600" : "text-slate-600"}>{product.trackInventory ? product.stock : "Service"}</span>
                    <strong className="text-[#3157d8]">{currency(product.rate)}</strong>
                    <QuantityStepper qty={qty} onRemove={() => removeProduct(product.id)} onAdd={() => addProduct(product)} />
                  </div>
                );
              })}
            </div>
          ) : productView === "list" ? (
            <div className="space-y-2">
              {filteredProducts.map((product) => {
                const qty = cart.filter((line) => line.id === product.id).reduce((sum, line) => sum + line.qty, 0);
                const lowStock = product.trackInventory && product.stock <= product.reorderLevel;
                return (
                  <article key={product.id} className={`srm-pos-product-list-row flex items-center gap-3 rounded-xl border bg-white p-2 shadow-sm transition hover:shadow-md ${qty ? "border-[#3157d8] ring-2 ring-[#3157d8]/10" : "border-white"}`}>
                    <button type="button" className="flex min-w-0 flex-1 items-center gap-3 text-left" onClick={() => addProduct(product)}>
                      <ProductMark product={product} lowStock={lowStock} />
                      <span className="min-w-0 flex-1">
                        <strong className="block truncate text-sm text-slate-950">{product.name}</strong>
                        <span className="block truncate text-xs text-slate-400">{product.sku} / {product.category} · Tax {product.taxRate}% {product.duration && `· ${product.duration}`}</span>
                      </span>
                      <span className={`hidden rounded-full px-2 py-1 text-xs md:inline-flex ${lowStock ? "bg-red-50 text-red-600" : "bg-emerald-50 text-emerald-700"}`}>Stock {product.trackInventory ? product.stock : "Service"}</span>
                      <strong className="w-24 text-right text-[#3157d8]">{currency(product.rate)}</strong>
                    </button>
                    <QuantityStepper qty={qty} onRemove={() => removeProduct(product.id)} onAdd={() => addProduct(product)} />
                  </article>
                );
              })}
            </div>
          ) : (
            <div className={`grid gap-2 ${tileDensity === "compact" ? "grid-cols-2 sm:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6" : "grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5"}`}>
              {filteredProducts.map((product) => {
                const qty = cart.filter((line) => line.id === product.id).reduce((sum, line) => sum + line.qty, 0);
                const lowStock = product.trackInventory && product.stock <= product.reorderLevel;
                return (
                  <article key={product.id} className={`relative overflow-hidden rounded-xl border bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${qty ? "border-[#3157d8] ring-2 ring-[#3157d8]/10" : "border-white"}`}>
                    <button type="button" className="block w-full text-left" onClick={() => addProduct(product)}>
                      <ProductVisual product={product} lowStock={lowStock} density={tileDensity} />
                      <span className="mt-2 block truncate px-2 text-xs font-semibold text-slate-950">{product.name}</span>
                      <span className="mt-1 block truncate px-2 text-[11px] text-slate-400">{product.sku} · {product.category} · Tax {product.taxRate}% {product.duration}</span>
                      <span className="mt-2 flex items-center justify-between gap-2 px-2 pb-2">
                        <strong className="text-sm text-[#3157d8]">{shortCurrency(product.rate)}</strong>
                        <span className={`rounded-full px-1.5 py-0.5 text-[10px] ${lowStock ? "bg-red-50 text-red-600" : "bg-emerald-50 text-emerald-700"}`}>{product.trackInventory ? product.stock : "Svc"}</span>
                      </span>
                    </button>
                    <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50/80 p-1">
                      <Button size="icon" variant="ghost" className="h-7 w-7 text-slate-600 hover:bg-white" onClick={() => removeProduct(product.id)} disabled={!qty}><Minus className="h-3.5 w-3.5" /></Button>
                      <strong className="min-w-8 text-center text-sm text-slate-900">{qty}</strong>
                      <Button size="icon" variant="ghost" className="h-7 w-7 text-slate-600 hover:bg-white" onClick={() => addProduct(product)}><Plus className="h-3.5 w-3.5" /></Button>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>

        <aside className="srm-pos-cart space-y-4 rounded-2xl border border-white/80 bg-white/90 p-4 shadow-sm backdrop-blur">
          <Card className="overflow-hidden border-slate-200 bg-white text-slate-950 shadow-sm">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">Cart</CardTitle>
              <Button variant="ghost" size="sm" className="text-slate-500 hover:text-slate-950" onClick={() => setCart([])} disabled={!cart.length}><Trash2 className="h-4 w-4" />Clear</Button>
            </CardHeader>
            <CardContent className="space-y-3">
              {cart.length ? cart.map((line) => (
                <div key={line.lineId} className="rounded-md border border-slate-200 bg-white p-3 shadow-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <strong className="text-sm">{line.name}</strong>
                      <p className="text-xs text-slate-400">{line.sku}{line.batchNo ? ` / Batch ${line.batchNo}` : ""}{line.serialNo ? ` / Serial ${line.serialNo}` : ""}</p>
                    </div>
                    <Button size="icon" variant="ghost" className="h-7 w-7 text-slate-400 hover:text-red-600" onClick={() => setCart((current) => current.filter((item) => item.lineId !== line.lineId))}><X className="h-4 w-4" /></Button>
                  </div>
                  <div className="mt-3 grid grid-cols-[1fr_1fr_1fr] gap-2">
                    <label className="text-xs text-slate-500">Qty<Input disabled={!!line.booking} type="number" min="0.001" step={line.decimalAllowed ? "0.001" : "1"} value={line.qty} onChange={(event) => updateLine(line.lineId, { qty: line.booking ? 1 : line.trackInventory ? Math.min(line.stock, Math.max(0.001, Number(event.target.value) || 1)) : Math.max(0.001, Number(event.target.value) || 1) })} className="mt-1 border-slate-200 bg-slate-50 text-slate-950" /></label>
                    <label className="text-xs text-slate-500">Rate<Input type="number" min="0" value={line.rate} onChange={(event) => updateLine(line.lineId, { rate: Math.max(0, Number(event.target.value) || 0) })} className="mt-1 border-slate-200 bg-slate-50 text-slate-950" /></label>
                    <label className="text-xs text-slate-500">Disc %<Input type="number" min="0" max="50" value={line.discount} onChange={(event) => updateLine(line.lineId, { discount: Math.min(50, Math.max(0, Number(event.target.value) || 0)) })} className="mt-1 border-slate-200 bg-slate-50 text-slate-950" /></label>
                  </div>
                  <label className="mt-2 block text-xs text-slate-500">Line note<Input aria-label={`Line note ${line.lineId}`} value={line.note} onChange={event=>updateLine(line.lineId,{note:event.target.value})} className="mt-1 border-slate-200 bg-slate-50 text-slate-950"/></label>
                  {isService(line) && (!selectedPOS||posFeatures?.appointments_schedule) && <div className="mt-3"><POSServiceScheduling productId={line.id} lineKey={line.lineId} value={line.booking} onChange={booking=>updateLine(line.lineId,{booking,...(booking?{qty:1}:{})})} onRequirement={required=>setRequirements(current=>current[line.lineId]===required?current:{...current,[line.lineId]:required})}/></div>}
                  <div className="mt-2 flex items-center justify-between text-sm">
                    <span className="text-slate-400">Tax {line.taxRate}%</span>
                    <strong>{currency(operationalPackKey === "pharma" && line.lotAllocation === "fefo"
                      ? pharmaCheckoutQuote([{quantity: String(line.qty), price: line.rate.toFixed(2),
                          discount: lineDiscount(line).toFixed(2), taxRate: String(line.taxRate)}], "0.00")?.grandTotal ?? lineTotal(line)
                      : lineTotal(line))}</strong>
                  </div>
                </div>
              )) : (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center text-slate-500">
                  <ShoppingCart className="mx-auto mb-3 h-10 w-10 text-slate-300" />
                  <strong className="block text-slate-900">Ready for first scan</strong>
                  <span className="text-sm">Scan barcode or tap a product to start billing.</span>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="overflow-hidden border-slate-200 bg-white text-slate-950 shadow-sm">
            <CardContent className="space-y-3 p-4">
              <SummaryLine label="Subtotal" value={currency(totals.subtotal)} />
              <SummaryLine label="Line discount" value={currency(totals.lineDiscount)} />
              <div className="grid grid-cols-[1fr_8rem] items-center gap-3 text-sm">
                <span className="text-slate-500">Bill discount</span>
                <Input type="number" min="0" value={billDiscount} onChange={(event) => setBillDiscount(Number(event.target.value) || 0)} className="border-slate-200 bg-slate-50 text-right text-slate-950" />
              </div>
              <div className="grid grid-cols-[1fr_8rem] items-center gap-3 text-sm">
                <span className="text-slate-500">Coupon</span>
                <Input value={coupon} onChange={(event) => setCoupon(event.target.value)} placeholder="WELCOME10" className="border-slate-200 bg-slate-50 text-slate-950" />
              </div>
              <SummaryLine label="Coupon discount" value={currency(totals.couponDiscount)} />
              <SummaryLine label="Taxable" value={currency(totals.taxable)} />
              <SummaryLine label="Tax" value={currency(totals.tax)} />
              <SummaryLine label="Round off" value={currency(totals.roundOff)} />
              <div className="rounded-md bg-[#3157d8] p-4 text-white">
                <span className="block text-xs font-semibold uppercase">Amount payable</span>
                <strong className="text-3xl">{currency(totals.grandTotal)}</strong>
              </div>
              <Input value={note} onChange={(event) => setNote(event.target.value)} placeholder="Bill note / delivery instruction" className="border-slate-200 bg-slate-50 text-slate-950" />
              <div className="grid grid-cols-2 gap-2">
                <Button variant="outline" className="border-slate-200 text-slate-700" disabled={selectedPOS} title={selectedPOS?"Held bills are not integrated in this Business Pack POS yet":undefined} onClick={holdCart}><PauseCircle className="h-4 w-4" />Hold</Button>
                <Button className="bg-[#3157d8] text-white hover:bg-[#2748b8]" onClick={() => openPayment("Cash")}><Calculator className="h-4 w-4" />Pay</Button>
              </div>
            </CardContent>
          </Card>
        </aside>
      </main>

      <footer className="srm-pos-checkout sticky bottom-0 grid gap-2 border-t border-slate-200 bg-white p-3 shadow-[0_-8px_20px_rgba(15,23,42,0.06)] md:grid-cols-[repeat(3,1fr)_auto_auto_auto] md:items-center">
        <FooterMetric label="Items" value={String(cart.length)} />
        <FooterMetric label="Quantity" value={String(totals.qty)} />
        <FooterMetric label="Payable" value={operationalPackKey === "pharma" && cart.some(line => line.lotAllocation === "fefo") && !Number.isInteger(totals.grandTotal) ? currency(totals.grandTotal) : shortCurrency(totals.grandTotal)} />
        <Button variant="outline" className="border-slate-200 text-slate-700" disabled={selectedPOS} title={selectedPOS?"Held bills are not integrated in this Business Pack POS yet":undefined} onClick={() => setActiveModal("held")}><RotateCcw className="h-4 w-4" />Recall</Button>
        <Button variant="outline" className="border-slate-200 text-slate-700" onClick={() => window.print()}><Printer className="h-4 w-4" />Print Last</Button>
        <Button className="bg-[#3157d8] text-white hover:bg-[#2748b8]" onClick={() => openPayment("Cash")}><CreditCard className="h-4 w-4" />Payment</Button>
      </footer>

      {quickAddOpen && (selectedPOS&&posFeatures?<POSQuickAddCustomer features={posFeatures} onClose={()=>setQuickAddOpen(false)} onCreated={customerCreated}/>:!selectedPOS?<QuickAddCustomer onClose={() => setQuickAddOpen(false)} onCreated={customerCreated}/>:null)}
      {activeModal === "payment" ? (
        <Overlay title="Complete Payment" onClose={() => setActiveModal(null)} wide>
          <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
            <div className="space-y-4">
              <div className="space-y-3 rounded-lg bg-background p-3 text-foreground">
                <>{selectedPOS&&<p className="text-sm text-muted-foreground">Follow-up editing is not integrated in this Business Pack POS yet. Required follow-up items cannot be checked out here.</p>}</><div className="flex flex-wrap items-end gap-2"><label className="flex-1 text-xs">Customer for this sale & follow-ups<NativeSelect loading={customersQuery.isFetching} error={customersQuery.isError} aria-label="Follow-up customer" className="block w-full rounded border bg-background p-2 text-foreground" value={customerId || ""} onChange={e => setCustomerId(Number(e.target.value))}><option value="">Walk-in — select a customer to schedule</option>{customers.filter(c => c.id).map(c => <option key={c.id} value={c.id}>{c.name}{c.phone ? ` · ${c.phone}` : ""}</option>)}</NativeSelect></label><Button type="button" variant="outline" disabled={selectedPOS&&!posFeatures?.customers_register} title={selectedPOS?posFeatures?.registration_unavailable_reason||undefined:undefined} onClick={() => setQuickAddOpen(true)}><Plus size={16}/>Quick add customer</Button></div>
                {customerId>0&&<Button type="button" variant="outline" onClick={()=>setCustomerProfile(true)}>View customer 360</Button>}
                {!selectedPOS&&cart.map(line=><details key={line.lineId}><summary className="cursor-pointer text-sm">{line.name} · {line.followUp?.required?`${line.followUp.interval_days} day follow-up`:"Configure follow-up"}</summary><ScheduleFields template value={line.followUp||newDefaultSchedule()} employees={followUpOptions.data?.employees} teams={followUpOptions.data?.teams} onChange={value=>setCart(current=>current.map(l=>l.lineId===line.lineId?{...l,followUp:value}:l))}/></details>)}
              </div>
              <div className="rounded-lg bg-slate-950 p-4">
                <span className="text-xs uppercase text-slate-400">Grand total</span>
                <strong className="block text-3xl text-amber-300">{currency(totals.grandTotal)}</strong>
                {paymentMode === "Credit" && customer.creditLimit && customer.outstanding + totals.grandTotal > customer.creditLimit ? <p className="mt-2 text-sm text-red-300">Credit limit warning for {customer.name}</p> : null}
              </div>
              <div className="flex flex-wrap gap-2">
                {paymentModes.map((item) => (
                  <button key={item} type="button" onClick={() => {
                    setPaymentMode(item);
                    setPaymentRows(item === "Split" ? [{ id: crypto.randomUUID(), mode: "Cash", amount: totals.grandTotal, reference: "" }] : [{ id: crypto.randomUUID(), mode: item === "Credit" ? "Credit" : item, amount: item === "Credit" ? 0 : totals.grandTotal, reference: "" }]);
                  }} className={`rounded-md px-3 py-2 text-sm font-medium ${paymentMode === item ? "bg-amber-500 text-slate-950" : "bg-white/5 text-slate-200 hover:bg-white/10"}`}>
                    {item}
                  </button>
                ))}
              </div>
              <div className="space-y-2">
                {paymentRows.map((row) => (
                  <div key={row.id} className="grid gap-2 rounded-lg border border-white/10 bg-slate-950 p-2 md:grid-cols-[10rem_1fr_1fr_auto]">
                    <Select value={row.mode} onValueChange={(value) => setPaymentRows((current) => current.map((item) => item.id === row.id ? { ...item, mode: value as PaymentRow["mode"] } : item))}>
                      <SelectTrigger className="border-white/15 bg-slate-900 text-white"><SelectValue /></SelectTrigger>
                      <SelectContent>{rowModes.map((item) => <SelectItem key={item} value={item}>{item}</SelectItem>)}</SelectContent>
                    </Select>
                    <Input aria-label="Payment amount" type="number" min="0" value={row.amount} onChange={(event) => setPaymentRows((current) => current.map((item) => item.id === row.id ? { ...item, amount: Number(event.target.value) || 0 } : item))} className="border-white/15 bg-slate-900 text-white" />
                    <Input aria-label="Payment reference" value={row.reference} onChange={(event) => setPaymentRows((current) => current.map((item) => item.id === row.id ? { ...item, reference: event.target.value } : item))} placeholder="Reference" className="border-white/15 bg-slate-900 text-white" />
                    <Button size="icon" variant="ghost" className="text-slate-300 hover:bg-white/10 hover:text-white" onClick={() => setPaymentRows((current) => current.filter((item) => item.id !== row.id))}><X className="h-4 w-4" /></Button>
                  </div>
                ))}
              </div>
              <Button variant="outline" className="border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={() => { setPaymentMode("Split"); setPaymentRows((current) => [...current, { id: crypto.randomUUID(), mode: "Cash", amount: 0, reference: "" }]); }}><Plus className="h-4 w-4" />Add payment mode</Button>
            </div>
            <div className="space-y-3 rounded-lg bg-slate-950 p-4">
              <SummaryLine label="Amount received" value={currency(received)} />
              <SummaryLine label="Balance due" value={currency(balanceDue)} />
              <SummaryLine label="Change due" value={currency(changeDue)} />
              {paymentMode==="Split"&&explicitCredit>0&&<SummaryLine label="Explicit credit balance" value={currency(explicitCredit)}/>}
              <CompactActions><Button className="w-full bg-emerald-500 text-slate-950 hover:bg-emerald-400" onClick={() => completeSale("done")}>Complete Sale</Button>
<Button variant="outline" className="w-full border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={() => completeSale("print")}>Complete + Print</Button>
<Button variant="outline" className="w-full border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={() => completeSale("whatsapp")}>Complete + WhatsApp</Button>
<Button variant="outline" className="w-full border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={() => completeSale("request_payment")}>Save order & request payment</Button>
<Button variant="outline" className="w-full border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={() => completeSale("email")}>Complete + Email</Button></CompactActions>



            </div>
          </div>
        </Overlay>
      ) : null}

      {activeModal === "held" ? (
        <Overlay title="Recall Held Bills" onClose={() => setActiveModal(null)}>
          <div className="space-y-3">
            {heldBills.length ? heldBills.map((bill) => (
              <div key={bill.id} className="flex flex-col gap-3 rounded-lg border border-white/10 bg-slate-950 p-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <strong>{bill.holdNo}</strong>
                  <p className="text-sm text-slate-400">{customers.find((item) => item.id === bill.customerId)?.name || "Customer"} · {bill.cart.length} items · {currency(bill.amount)}</p>
                  <div className="text-xs text-slate-500"><RichTextContent legacyFormat="plain" value={bill.notes}/></div>
                </div>
                <div className="flex gap-2">
                  <Button onClick={() => recallBill(bill)}>Recall</Button>
                  <Button variant="outline" className="border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={() => deleteHeldBill(bill)}>Delete</Button>
                </div>
              </div>
            )) : <EmptyPanel icon={PauseCircle} title="No held bills" description="Held bills for this register session will appear here." />}
          </div>
        </Overlay>
      ) : null}

      {activeModal === "success" && lastSale ? (
        <Overlay title="Sale Completed" titleClassName="text-slate-100" onClose={() => setActiveModal(null)}>
          <div className="text-center">
            <CheckCircle2 className="mx-auto h-14 w-14 text-emerald-400" />
            <h2 className={`mt-3 text-2xl font-semibold ${lastSale.checkoutId?"text-slate-100":""}`}>{lastSale.invoiceNo}</h2>
            <p className="text-slate-400">{lastSale.customer} · {currency(lastSale.amount)} · {lastSale.mode}</p>
            {lastSale.checkoutId && <div className="mt-3 space-y-1 text-sm"><p>Invoice: {lastSale.invoiceNo}</p><p>Paid {currency(Number(lastSale.paid))} / Balance {currency(Number(lastSale.balance))}</p><p>Receipts: {lastSale.receiptNumbers?.join(', ') || 'No payment received (credit invoice)'}</p>{lastSale.hasBookings&&<Button variant="outline" className="border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={()=>navigate('/srm/scheduled-services')}>View Scheduled Services</Button>}</div>}
            {lastSale.checkoutId&&<div className="mt-4 rounded-lg bg-card p-3 text-left text-foreground"><ServiceCheckoutBillingPanel checkoutId={lastSale.checkoutId} canCollect={!!paymentCaps.data?.collect} onChanged={()=>{const id=lastSale.checkoutId;void api.get<NativeCheckoutResult>(`/srm/service-checkout/${id}`).then(({data})=>{if(owns())setLastSale(current=>current&&current.checkoutId===id?{...current,paid:data.invoice.paid,balance:data.invoice.balance,receiptNumbers:data.receipts.map(row=>row.number)}:current);}).catch(error=>{if(owns())toast({title:"Checkout refresh failed",description:dealError(error),variant:"destructive"});});void activeRegister.refetch();}}/>{paymentCaps.isError&&<p role="alert">Payment permissions could not load. <Button variant="outline" onClick={()=>void paymentCaps.refetch()}>Reload payment permissions</Button></p>}</div>}
            {lastSale.checkoutId&&operationalPackKey==='retail'&&posFeatures&&'retail_returns' in posFeatures&&posFeatures.retail_returns===true&&<RetailReturnPanel checkoutId={lastSale.checkoutId} sessionId={register?.id||null} onChanged={()=>{void productsQuery.refetch();void activeRegister.refetch();}}/>}
            {!lastSale.checkoutId&&<p className="mt-2 text-xs text-slate-400">Sales order reference. Payment is not confirmed for this older sale.</p>}
            <div className="mt-5 grid gap-2 md:grid-cols-2">
              <Button onClick={() => window.print()}><Printer className="h-4 w-4" />Print Receipt</Button>
              <Button variant="outline" className="border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={() => setActiveModal(null)}>New Sale</Button>
            </div>
          </div>
        </Overlay>
      ) : null}

      {activeModal === "cash" ? (
        <Overlay title="Cash Drawer Movement" onClose={() => setActiveModal(null)}>
          <CashMovementForm onSave={async row => {
            if(!owns()||locked){toast({title:'Cash movement unavailable',variant:'destructive'});return;}
            try {
              const coordinationKey=financialIntentKey('cash_movement');
              if(!navigator.locks)throw new Error('Cash coordination is unavailable. Use a supported secure browser.');
              await navigator.locks.request(coordinationKey,{mode:'exclusive',ifAvailable:true},async lock=>{
              if(!owns()||financialIntentKey('cash_movement')!==coordinationKey)return;
              if(!lock)throw new Error('Another cash request is in progress. Wait, then Save again.');
              type CashIntent={session_id:number;request_key:string;movement_type:string;amount:string;reason:string};
              const recovery=findPendingCashIntent<CashIntent>();
              const pending=recovery.payload;
              if(recovery.pending&&(!recovery.key||!pending||recovery.recordId!==pending.session_id||!Number.isSafeInteger(pending.session_id)||pending.session_id<=0||typeof pending.request_key!=='string'||!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(pending.request_key)||!['cash_in','cash_out'].includes(pending.movement_type)||typeof pending.reason!=='string'||typeof pending.amount!=='string'||!Number.isFinite(Number(pending.amount))||Number(pending.amount)<=0||Number(pending.amount)>=1e12||Number(pending.amount).toFixed(2)!==pending.amount||Object.keys(pending).sort().join(',')!=='amount,movement_type,reason,request_key,session_id'))throw new Error('A prior cash movement needs recovery. Its stored details cannot be verified; no new cash movement was submitted.');
              if(!recovery.pending&&(!Number.isFinite(row.amount)||row.amount<=0||!row.reason.trim())){toast({title:'Amount and reason required'});return;}
              if(!recovery.pending&&(!register?.id||!Number.isFinite(row.amount)||row.amount<=0||row.amount>=1e12||Math.round(row.amount*100)/100!==row.amount))throw new Error('Open an active register and enter a positive amount with at most two decimal places.');
              const sessionId=recovery.pending?pending!.session_id:register!.id;
              const key=recovery.pending?recovery.key!:financialIntentKey('cash_movement',sessionId);
              if(financialIntentKey('cash_movement',sessionId)!==key)throw new Error('Cash recovery context changed. No cash movement was submitted.');
              const fresh=await api.get<unknown>(recovery.pending?'/srm/pos/sessions':'/srm/pos/sessions/active',{_recordSyncBypass:true,headers:{'Cache-Control':'no-cache, no-store'},params:{_cash_intent_probe:crypto.randomUUID()}});
              const summary=fresh.data as {session?:{id?:number};cash_intent_version?:number};
              const supported=recovery.pending?Array.isArray(fresh.data)&&fresh.data.some(item=>item?.cash_intent_version===119):summary?.session?.id===sessionId&&summary?.cash_intent_version===119;
              if(!owns()||financialIntentKey('cash_movement',sessionId)!==key||!supported)throw new Error('Cash movement recovery is unavailable in this context. Reload after the server update before collecting cash.');
              if(recovery.pending){const current=readFinancialIntent<CashIntent>(key);if(!current.pending||JSON.stringify(current.payload)!==JSON.stringify(pending))throw new Error('Cash recovery storage changed. Retry before submitting another cash movement.');}
              else if(findPendingCashIntent<CashIntent>().pending)throw new Error('A prior cash movement is awaiting recovery. Save again to recover it first.');
              const payload=recovery.pending?pending!:{session_id:sessionId,movement_type:row.type==='Withdrawal'?'cash_out':'cash_in',amount:row.amount.toFixed(2),reason:row.reason,request_key:crypto.randomUUID()};
              if(!recovery.pending)saveFinancialIntent(key,payload);
              let result;
              try {result=await srmApi.createPosCashMovement(payload);}
              catch(error){
                const headers=isAxiosError(error)?error.response?.headers:undefined;
                const notCreated=recovery.pending&&isAxiosError(error)&&error.response?.status===400&&headers?.['x-cash-intent-outcome']==='not_created'&&headers?.['x-cash-intent-request-key']===payload.request_key&&headers?.['x-cash-intent-session-id']===String(payload.session_id);
                if(notCreated&&owns()&&financialIntentKey('cash_movement',sessionId)===key){const current=readFinancialIntent<CashIntent>(key);if(current.pending&&JSON.stringify(current.payload)===JSON.stringify(payload)){clearFinancialIntent(key);await activeRegister.refetch().catch(()=>undefined);if(!owns()||financialIntentKey('cash_movement',sessionId)!==key)return;setActiveModal(null);toast({title:'Previous cash movement was not created',description:'The original register is closed. The prior request was not recorded; no new movement was submitted.'});return;}}
                throw error;
              }
              if(!Number.isSafeInteger(result?.movement_id)||result.movement_id<=0||result.request_key!==payload.request_key)throw new Error('Cash movement outcome is awaiting confirmation. Save again to recover the original request.');
              if(owns()&&financialIntentKey('cash_movement',sessionId)===key){const current=readFinancialIntent<CashIntent>(key);if(current.pending&&JSON.stringify(current.payload)===JSON.stringify(payload))clearFinancialIntent(key);await activeRegister.refetch().catch(()=>undefined);if(!owns()||financialIntentKey('cash_movement',sessionId)!==key)return;setActiveModal(null);toast({title:recovery.pending?'Previous cash movement confirmed':'Cash movement confirmed',description:`${payload.movement_type==='cash_out'?'Withdrawal':'Cash In'} ${currency(Number(payload.amount))}${recovery.pending?'. No new cash movement was submitted.':''}`});}
              });
            }
            catch(error){if(owns())toast({title:'Cash movement not confirmed',description:dealError(error),variant:'destructive'});}
          }} />
        </Overlay>
      ) : null}

      {activeModal === "profile" ? (
        <Overlay title="POS Templates & Layout" onClose={() => setActiveModal(null)} wide>
          <ProfileSettingsPanel
            activeProfile={activeStoreProfile}
            profiles={posStoreProfiles}
            tileDensity={tileDensity}
            onProfileChange={switchProfile}
            onDensityChange={setTileDensity}
          />
        </Overlay>
      ) : null}

      {activeModal === "close" ? (
        <Overlay title="Close POS Session" onClose={() => setActiveModal(null)}>
          <div className="space-y-3">
            <SummaryLine label="Opening cash" value={register?currency(Number(register.opening_cash||0)):"No open register"} />
            <SummaryLine label="Cash received" value={register&&Number.isFinite(cashReceived)?currency(cashReceived):"Unavailable"} />
            <SummaryLine label="Expected closing cash" value={Number.isFinite(expectedCash)?currency(expectedCash):"Unavailable"} />
            <label className="block text-sm text-slate-400">Actual counted cash<Input value={closingCash} onChange={(event) => setClosingCash(event.target.value)} type="number" className="mt-1 border-white/15 bg-slate-950 text-white" /></label>
            {Number.isFinite(countedClosingCash) && countedClosingCash >= 0 && Number.isFinite(expectedCash) ? <SummaryLine label="Cash variance" value={currency(countedClosingCash - expectedCash)} /> : null}
            <Button className="w-full" variant="destructive" disabled={!canCloseSession||nativeBusy} onClick={async () => {
              if(!register?.id||!canCloseSession||!owns()||locked)return;
              setNativeBusy(true);
              try {await srmApi.closePosSession({session_id:register.id,counted_cash:closingCash});if(owns()){await activeRegister.refetch();setActiveModal(null);toast({title:'POS session closed',description:'The native cashier closing was confirmed.'});}}
              catch(error){if(owns())toast({title:'Session closing not confirmed',description:dealError(error),variant:'destructive'});}
              finally{if(owns())setNativeBusy(false);}
            }}>Close POS session</Button>
          </div>
        </Overlay>
      ) : null}
    </div></fieldset>
    {opaqueLock && <section className="fixed inset-x-3 bottom-20 z-[100] rounded-lg border bg-card p-4" role="alert">An unresolved checkout requires reconciliation. New checkout is locked; recovery details are unavailable.</section>}
    {uncertain && <section className="fixed inset-x-3 bottom-20 z-[100] space-y-2 rounded-lg border bg-card p-4 shadow-lg" aria-label="Unresolved POS checkout"><p role="status">Checkout outcome is unresolved. This basket is frozen. Retry the exact saved checkout before starting another transaction; missing records alone do not prove rejection.</p>{nativeError&&<p role="alert">{nativeError}</p>}<Button disabled={nativeBusy || !canReplay} onClick={()=>void submitNative(uncertainty.current!,true)}>{nativeBusy?'Confirming checkout...':'Retry same checkout'}</Button>{!canReplay && <Button variant="outline" disabled={recoveryAuthority.isFetching} onClick={()=>void recoveryAuthority.refetch()}>Reload checkout permissions</Button>}</section>}
    </>
  );
}

function SessionPill({ label, value }: { label: string; value: string }) {
  return (
    <span className="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2 shadow-sm">
      <small className="block text-slate-500">{label}</small>
      <strong className="text-slate-950">{value}</strong>
    </span>
  );
}

function StatusTile({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-2xl border border-white bg-white p-4 shadow-sm">
      <span className="text-xs font-medium text-slate-500">{label}</span>
      <div className="mt-1 flex items-end justify-between gap-3">
        <strong className="text-2xl text-slate-950">{value}</strong>
        <span className="rounded-full bg-emerald-50 px-2 py-1 text-xs text-emerald-700">{detail}</span>
      </div>
    </div>
  );
}

function ViewModeButton({ active, icon: Icon, label, onClick }: { active: boolean; icon: typeof LayoutGrid; label: string; onClick: () => void }) {
  return (
    <Button
      type="button"
      variant={active ? "default" : "outline"}
      className={active ? "h-8 bg-[#3157d8] px-2.5 text-white hover:bg-[#2748b8]" : "h-8 border-slate-200 bg-white px-2.5 text-slate-700 hover:bg-slate-50"}
      onClick={onClick}
    >
      <Icon className="h-4 w-4" />
      {label}
    </Button>
  );
}

function ProductMark({ product, lowStock }: { product: Product; lowStock: boolean }) {
  const initials = product.name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
  return (
    <span className={`relative flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border text-xs font-bold ${lowStock ? "border-red-100 bg-red-50 text-red-600" : "border-slate-100 bg-slate-50 text-slate-600"}`}>
      {product.image ? <img src={product.image} alt={product.name} className="h-full w-full rounded-lg object-cover" referrerPolicy="no-referrer" /> : initials}
    </span>
  );
}

function QuantityStepper({ qty, onRemove, onAdd }: { qty: number; onRemove: () => void; onAdd: () => void }) {
  return (
    <span className="flex shrink-0 items-center justify-end gap-1">
      <Button size="icon" variant="ghost" aria-label="Decrease quantity" className="h-7 w-7 text-slate-600 hover:bg-slate-100" onClick={onRemove} disabled={!qty}><Minus className="h-3.5 w-3.5" /></Button>
      <strong className="min-w-8 text-center text-sm text-slate-900">{qty}</strong>
      <Button size="icon" variant="ghost" aria-label="Increase quantity" className="h-7 w-7 text-slate-600 hover:bg-slate-100" onClick={onAdd}><Plus className="h-3.5 w-3.5" /></Button>
    </span>
  );
}

function ProductVisual({ product, lowStock, density }: { product: Product; lowStock: boolean; density: "comfortable" | "compact" }) {
  const tone: Record<string, string> = {
    General: "from-indigo-100 to-blue-50 text-indigo-600",
    Stationery: "from-amber-100 to-orange-50 text-amber-700",
    "Office Supplies": "from-emerald-100 to-teal-50 text-emerald-700",
    Electronics: "from-sky-100 to-cyan-50 text-sky-700",
    Pharmacy: "from-rose-100 to-red-50 text-rose-700",
    Garments: "from-violet-100 to-fuchsia-50 text-violet-700",
  };
  const initials = product.name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
  return (
    <span className={`relative flex ${density === "compact" ? "h-14" : "h-20"} items-center justify-center bg-gradient-to-br ${tone[product.category] || "from-slate-100 to-slate-50 text-slate-600"}`}>
      {lowStock ? <span className="absolute right-1.5 top-1.5 rounded-full bg-red-500 px-1.5 py-0.5 text-[10px] font-semibold text-white">Low</span> : null}
      {product.image ? <img src={product.image} alt={product.name} className="h-full w-full object-cover" referrerPolicy="no-referrer" /> : <span className={`${density === "compact" ? "h-9 w-9 text-sm" : "h-12 w-12 text-base"} flex items-center justify-center rounded-full border border-white/80 bg-white/80 font-bold shadow-sm`}>{initials}</span>}
    </span>
  );
}

function ModePanel({ mode, customer }: { mode: PosMode; customer: Customer }) {
  const details: Record<PosMode, string[]> = {
    Retail: ["Fast scan billing", "Loyalty points", "Thermal receipt"],
    Supermarket: ["Barcode queue", "Weighted items", "Express checkout"],
    Restaurant: ["Table/token", "KOT hook", "Split bill"],
    Services: ["Staff assignment", "Appointment ref", "Service notes"],
    Wholesale: [`Credit ${shortCurrency(customer.creditLimit)}`, "Bulk pricing", "E-way bill check"],
    Pharmacy: ["Batch required", "Expiry visible", "Prescription ref"],
    Electronics: ["Serial required", "Warranty capture", "IMEI/device note"],
    Garments: ["Size/color lookup", "Alteration note", "Exchange support"],
  };
  return (
    <div className="rounded-2xl border border-white bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <strong className="text-slate-950">{mode} mode</strong>
          <p className="text-sm text-slate-500">Customer: {customer.name} / Outstanding {shortCurrency(customer.outstanding)} / Points {customer.loyaltyPoints}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {details[mode].map((item) => <Badge key={item} variant="secondary">{item}</Badge>)}
        </div>
      </div>
    </div>
  );
}

function SummaryLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="opacity-65">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function FooterMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-slate-50 px-3 py-2">
      <span className="block text-xs text-slate-500">{label}</span>
      <strong className="text-slate-950">{value}</strong>
    </div>
  );
}

function Overlay({ title, onClose, children, wide, titleClassName }: { title: string; onClose: () => void; children: React.ReactNode; wide?: boolean; titleClassName?:string }) {
  return (
    <Dialog.Root open onOpenChange={open => { if (!open) onClose(); }}><Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-50 bg-black/70" />
      <Dialog.Content aria-describedby={undefined} className={`srm-pos-dialog fixed left-1/2 top-1/2 z-50 max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] -translate-x-1/2 -translate-y-1/2 overflow-auto rounded-lg border border-white/10 bg-slate-900 p-4 text-slate-100 shadow-2xl ${wide ? "max-w-5xl" : "max-w-2xl"}`}>
        <div className="mb-4 flex items-center justify-between gap-3">
          <Dialog.Title className={`text-lg font-semibold ${titleClassName||""}`}>{title}</Dialog.Title>
          <Button size="icon" variant="ghost" aria-label={`Close ${title}`} className="shrink-0 text-slate-300 hover:bg-white/10 hover:text-white" onClick={onClose}><X className="h-4 w-4" /></Button>
        </div>
        {children}
      </Dialog.Content>
    </Dialog.Portal></Dialog.Root>
  );
}

function EmptyPanel({ icon: Icon, title, description }: { icon: typeof Search; title: string; description: string }) {
  return (
    <div className="rounded-lg border border-dashed border-white/15 p-8 text-center">
      <Icon className="mx-auto mb-3 h-8 w-8 text-slate-400" />
      <strong className="block">{title}</strong>
      <span className="text-sm text-slate-400">{description}</span>
    </div>
  );
}

function ProfileSettingsPanel({
  activeProfile,
  profiles,
  tileDensity,
  onProfileChange,
  onDensityChange,
}: {
  activeProfile: PosStoreProfile;
  profiles: PosStoreProfile[];
  tileDensity: "comfortable" | "compact";
  onProfileChange: (profileId: string) => void;
  onDensityChange: (density: "comfortable" | "compact") => void;
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_18rem]">
      <div className="space-y-3">
        {profiles.map((profile) => {
          const active = profile.id === activeProfile.id;
          return (
            <button
              key={profile.id}
              type="button"
              onClick={() => onProfileChange(profile.id)}
              className={`block w-full rounded-md border p-4 text-left transition ${active ? "border-amber-400 bg-amber-400/10" : "border-white/10 bg-slate-950 hover:border-white/30"}`}
            >
              <span className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <span>
                  <strong className="text-base text-white">{profile.name}</strong>
                  <div className="mt-1 block text-sm text-slate-400"><RichTextContent legacyFormat="plain" value={profile.description}/></div>
                </span>
                <Badge variant={active ? "default" : "secondary"}>{profile.mode}</Badge>
              </span>
              <span className="mt-3 flex flex-wrap gap-2">
                {profile.categories.map((item) => <Badge key={item} variant="outline" className="border-white/15 text-slate-200">{item}</Badge>)}
              </span>
            </button>
          );
        })}
      </div>
      <div className="space-y-4 rounded-md bg-slate-950 p-4">
        <div>
          <span className="text-xs uppercase text-slate-400">Active register</span>
          <strong className="mt-1 block text-xl">{activeProfile.register}</strong>
          <p className="mt-1 text-sm text-slate-400">{activeProfile.branch}</p>
        </div>
        <div>
          <span className="text-xs uppercase text-slate-400">Features</span>
          <div className="mt-2 flex flex-wrap gap-2">
            {activeProfile.features.map((item) => <Badge key={item} variant="secondary">{item}</Badge>)}
          </div>
        </div>
        <div>
          <span className="text-xs uppercase text-slate-400">Cashier layout</span>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <Button type="button" variant={tileDensity === "comfortable" ? "default" : "outline"} onClick={() => onDensityChange("comfortable")}>Comfort</Button>
            <Button type="button" variant={tileDensity === "compact" ? "default" : "outline"} onClick={() => onDensityChange("compact")}>Compact</Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function CashMovementForm({ onSave }: { onSave: (row: { id: string; type: string; amount: number; reason: string; createdAt: string }) => Promise<void> }) {
  const [type, setType] = useState("Withdrawal");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  return (
    <div className="space-y-3">
      <Select value={type} onValueChange={setType}>
        <SelectTrigger className="border-white/15 bg-slate-950 text-white"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="Withdrawal">Withdrawal</SelectItem>
          <SelectItem value="Cash In">Cash In</SelectItem>
        </SelectContent>
      </Select>
      <Input value={amount} onChange={(event) => setAmount(event.target.value)} type="number" placeholder="Amount" className="border-white/15 bg-slate-950 text-white" />
      <Input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Reason" className="border-white/15 bg-slate-950 text-white" />
      <Button className="w-full" disabled={saving} onClick={async () => {
        const parsed = Number(amount);
        setSaving(true);
        try { await onSave({ id: uid("cash"), type, amount: parsed, reason, createdAt: new Date().toISOString() }); }
        finally { setSaving(false); }
      }}>Record Movement</Button>
    </div>
  );
}
