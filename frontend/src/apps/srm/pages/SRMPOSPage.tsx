import {posOfferingTabs,matchesOfferingTab} from "../components/pos-offering-types";
import { randomUUID } from "@/lib/random-uuid";
import FormDefaultsGate from "@/components/forms/FormDefaultsGate";
import {loadPOSCatalog} from "../pos-catalog-pages";
import POSBookingSettings, {type POSBookingPresentation} from '../components/POSBookingSettings';
import ModuleNewMenu from "@/components/app/ModuleNewMenu";
import NewMenu from "@/components/app/NewMenu";
import POSMobileCatalogue from "../components/POSMobileCatalogue";
import POSCatalogueQuantity from "../components/POSCatalogueQuantity";
import SuiteNotificationBell from "@/components/suite/SuiteNotificationBell";
import POSCustomerIdentity from "../components/POSCustomerIdentity";
import { BookingSummary } from "@/shared/scheduling/BookingUX";
import PrebookingPOSVisit from '../industry/PrebookingPOSVisit';
import { posPresentation } from "../pos-presentation";
import { catalogIcon } from "../components/catalog-icon";
import { useBusinessTerms } from "@/hooks/use-business-terms";
import POSCustomerPicker from "../components/POSCustomerPicker";
import POSReceipt, { downloadReceipt, receiptText } from "../components/POSReceipt";
import POSBranchSelection from "../components/POSBranchSelection";
import { pharmaCheckoutQuote } from '@/lib/pharma-checkout-money';
import { effectiveOperationalSelection, type OperationalSelection } from '@/lib/effective-operational-selection';
import { currentPOSOperationalPin, installPOSOperationalPin, operationalOwner } from '@/lib/pos-operational-context';
import { selectedBranch } from '@/lib/branch-context';
import { defaultBranch } from '@/lib/default-branch';
import { switchSuiteContext } from '@/lib/switch-suite-context';
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
import "./pos-ux25.css";
import "./pos-mobile-reference.css";
import { useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { canAccessRoute } from "@/lib/roles";
import { useAuthStore } from "@/store/authStore";
import { phoneLinks } from "@/components/PhoneActions";
import {
  FileText,
  Tag,
  ArrowLeft,
  ArrowRight,
  Split,
  ShoppingBag,
  Stethoscope,
  Banknote,
  Calculator,
  CalendarDays,
  Clock3,
  CalendarRange,
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

type POSLot = { id: number; number: string; quantity: string; rate: string };

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
  schedulingConfigured?: boolean;
  unsupportedReason?: string;
  followUp?: Schedule;
  kind: string;
  duration?: string;
  active?: boolean;
  batchTracking?: boolean;
  serialTracking?: boolean;
  lotAllocation?: "fefo";
  lots?: POSLot[];
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
  planStartDate?: string;planBeneficiaries?:number[];
  resourceCapacities?: Record<number,number>;
  lineId: string;
  booking?: BookingSelection;
  draftScope?: string;
  heldBillDiscount?: number;
  heldCoupon?: string;
  qty: number;
  discount: number;
  note: string;
  batchNo?: string;
  batchId?: number;
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
  lines?: {name:string;qty:number;rate:number;appointment?:string}[];
};

type NativeCheckoutPayload = { request_id: string; buyer_mode?: "registered"|"anonymous_cash"; customer_id?: number; pos_session_id: number; currency: string; billing_mode: "invoice_at_checkout"; note:string; expected_total: string; bill_discount_amount: string; lines: {client_line_key:string;line_kind:"product"|"unscheduled_service"|"booked_service";product_id:number;batch_id?:number;quantity:string;unit_price:string;discount_amount:string;note:string;plan_start_date?:string;plan_beneficiaries?:number[];follow_up?:Schedule;booking?:BookingSelection}[]; payments:{payment_key:string;method:string;amount:string;reference?:string}[] };
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
const paymentModes: PaymentMode[] = ["Cash", "Card", "UPI", "Credit", "Split"];
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

// Never reuse a pre-settlement register response after a confirmed checkout.
async function refreshSettledRegister(client: QueryClient, queryKey: readonly unknown[], read: (signal: AbortSignal) => Promise<SRMRecord>, owns: () => boolean) {
  await client.cancelQueries({queryKey, exact:true});
  if (!owns()) return;
  return client.fetchQuery({queryKey, queryFn:({signal})=>read(signal), staleTime:0, retry:false});
}

function registerCashDisplay(fetching: boolean, failed: boolean, amount: number, format: (amount: number) => string) {
  return fetching ? "Refreshing..." : failed || !Number.isFinite(amount) ? "Unavailable" : format(amount);
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
  const lots = Array.isArray(item.lots) ? item.lots as POSLot[] : undefined;
  return {
    id: recordNumber(item.id),
    name: String(item.item_name || item.name || "Unnamed product"),
    image: (Array.isArray(item.images) ? item.images as string[] : (item.metadata_json as { images?: string[] } | undefined)?.images || [])[0],
    followUp: (item.metadata_json as {follow_up?:Schedule} | undefined)?.follow_up,
    kind: String(["service","services"].includes(String(item.product_type).toLowerCase()) ? "Services" : item.product_type === "package" ? "Packages" : item.product_type === "membership" ? "Memberships" : item.product_type === "subscription" ? "Subscriptions" : item.product_type === "bundle" ? "Bundles" : "Products"),
    schedulingConfigured: 'booking_policy' in item ? Boolean(item.booking_policy && (item.booking_policy as {active?:boolean}).active !== false) : undefined,
    duration: item.duration_minutes ? `${item.duration_minutes} min` : String((item.metadata_json as Record<string, unknown> | undefined)?.duration || ""),
    active: item.active !== false,
    sku: String(item.sku || ""),
    barcode: String(item.barcode || item.sku || ""),
    category: String(item.category_name || (item.category as SRMRecord | undefined)?.category_name || "General"),
    rate: recordNumber(lots?.[0]?.rate, recordNumber(item.sales_rate)),
    lots,
    mrp: recordNumber(item.mrp, recordNumber(item.sales_rate)),
    taxRate: recordNumber(item.gst_rate),
    stock: recordNumber((item.stock as {available_quantity?:string}|undefined)?.available_quantity, recordNumber(item.current_quantity)),
    checkoutSupported: item.product_type !== "bundle" && item.checkout_supported !== false,
    bookingRequired: Boolean((item.booking_policy as {required?:boolean}|undefined)?.required),
    unsupportedReason: item.product_type === "bundle" ? "This bundle is not available for checkout." : item.unsupported_reason ? String(item.unsupported_reason) : undefined,
    reorderLevel: recordNumber(item.reorder_level),
    trackInventory: !["service","services","membership","subscription","bundle"].includes(String(item.product_type).toLowerCase()) && item.track_inventory !== false,
    batchTracking: Boolean(item.batch_tracking),
    serialTracking: Boolean(item.serial_tracking),
    lotAllocation: item.lot_allocation === "fefo" ? "fefo" : undefined,
    decimalAllowed: item.lot_allocation === "fefo",
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

function cartBookingConflict(cart: CartLine[], lineId: string, booking: BookingSelection, capacities: Record<number,number> = {}) {
  const start=Date.parse(booking.starts_at),end=start+booking.duration_minutes*60000;
  const overlapping=cart.filter(line=>line.lineId!==lineId && line.booking && Date.parse(line.booking.starts_at)<end && Date.parse(line.booking.starts_at)+line.booking.duration_minutes*60000>start);
  if(overlapping.some(line=>line.booking!.employee_id===booking.employee_id || line.booking!.provider_resource_id===booking.provider_resource_id))return true;
  return (booking.additional_resource_ids || []).some(resource=>{
    const events=overlapping.filter(line=>line.booking!.additional_resource_ids?.includes(resource)).flatMap(line=>[[Math.max(start,Date.parse(line.booking!.starts_at)),1],[Math.min(end,Date.parse(line.booking!.starts_at)+line.booking!.duration_minutes*60000),-1]]);
    let occupied=0;return events.sort((a,b)=>a[0]-b[0] || a[1]-b[1]).some(([,delta])=>{occupied+=delta;return occupied >= (capacities[resource] || 1);});
  });
}

function buildCartLine(product: Product): CartLine {
  return {
    ...product,
    lineId: randomUUID(),
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
function normalizeCart(lines: CartLine[]) { return lines.map(line => ({...line, lineId: /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(line.lineId) ? line.lineId : randomUUID(), qty: line.booking ? 1 : line.qty})); }
function isCustomerPlan(line: Product) { return ["Memberships","Subscriptions"].includes(line.kind); }
function isService(line: Product) { return ['service','services'].includes(line.kind.toLowerCase()); }
export default function SRMPOSPage() {
  const [routeParams]=useSearchParams();
  const prebooking=routeParams.get('prebooking');
  const scope = useRecordScope(), [packGeneration, setPackGeneration] = useState(0);
  useEffect(() => { const changed = () => setPackGeneration(value => value + 1); const events = ['suite:pack-context-changed','suite:business-pack-changed']; events.forEach(name => window.addEventListener(name, changed)); return () => events.forEach(name => window.removeEventListener(name, changed)); }, []);
  const draftScope = posDraftScope();
  if(prebooking && /^[1-9][0-9]*$/.test(prebooking))return <PrebookingPOSVisit key={`${scope}:${prebooking}`} id={Number(prebooking)}/>;
  return <POSAuthority key={`${scope}:${packGeneration}:${draftScope}`} scope={`${scope}:${draftScope}`} draftScope={draftScope}/>;
}
function POSAuthority({scope,draftScope}:{scope:string;draftScope:string}) {
  const client = useQueryClient();
  const [mount] = useState(() => randomUUID());
  const [bound,setBound] = useState(false);
  const owner=operationalOwner(), branch=selectedBranch();
  const branchQuery=useQuery({queryKey:['srm','pos-branch-bootstrap',scope,mount],enabled:branch===null,retry:false,staleTime:0,gcTime:0,
    queryFn:async()=>{
      const response=await api.get('/branches/context',{headers:{'X-Suite-Pack-Context':null},recordCache:false});
      const saved = defaultBranch(response.data.company_id);
      if (saved && saved !== selectedBranch() && response.data.branches?.some((choice:{id:number;can_write:boolean;is_active?:boolean;is_deleted?:boolean}) => String(choice.id) === saved && choice.can_write && choice.is_active !== false && !choice.is_deleted)) {
        await switchSuiteContext(client, response.data.company_id, saved, '/srm/pos/terminal');
      }
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
      if (fresh.id !== user?.id || access.data.companyId !== user?.access?.companyId) throw new Error('POS identity changed. Reload before continuing.');
      if(securityAuthStamp(fresh)!==securityAuthStamp(user)) {
        // Rebind all scoped queries and drafts to the verified permissions. The new
        // authority mount verifies again before it can expose a register.
        useAuthStore.getState().setUser(fresh);
        throw new Error('Refreshing POS access…');
      }
      return effectiveOperationalSelection(response.data?.operational_scope,fresh,selectedBranch(),selectedPackContext());
    }});
  useLayoutEffect(()=>{
    if(!verified.data || owner!==operationalOwner())return;
    const cleanup=installPOSOperationalPin(verified.data,owner);
    setBound(true);
    return cleanup;
  },[verified.data,owner]);
  const pin=currentPOSOperationalPin();
  if (branch === "all" || (branch === null && branchQuery.isSuccess)) return <POSBranchSelection/>;
  if(!verified.data || !bound || verified.isError || pin?.owner!==owner) {
    const error=verified.error || branchQuery.error;
    return <div className="p-4"><div role={error ? 'alert' : 'status'} className="rounded-lg border bg-white p-4 text-sm">
      {error ? (error instanceof Error ? error.message : 'POS access could not be verified.') : 'Verifying POS access…'}
      {error && <button type="button" className="ml-3 rounded border px-3 py-1" onClick={()=>{if(error instanceof Error && error.message.startsWith('Your access changed.'))window.location.reload();else if(branch===null)void branchQuery.refetch();else void verified.refetch();}}>Reload POS access</button>}
    </div></div>;
  }
  return <FormDefaultsGate><ScopedPOS scope={`${scope}:${mount}`} draftScope={draftScope} selectedPOS={verified.data.realm==='pack'} operationalPackKey={verified.data.pack_key}/></FormDefaultsGate>;
}
function ScopedPOS({scope,draftScope,selectedPOS,operationalPackKey}:{scope:string;draftScope:string;selectedPOS:boolean;operationalPackKey:string|null}) {
  const owns = useRecordScopeOwner();
  const workspaceRef=useRef<HTMLDivElement>(null), checkoutFooterRef=useRef<HTMLElement>(null), cartScrollRef=useRef<HTMLDivElement>(null);
  useLayoutEffect(()=>{const root=workspaceRef.current,footer=checkoutFooterRef.current,scroll=cartScrollRef.current;if(!root||!footer||!scroll)return;const measure=()=>{root.style.setProperty('--pos-footer-height',`${footer.getBoundingClientRect().height}px`);const main=root.querySelector('main'),cart=root.querySelector('.srm-pos-cart');if(main&&cart){const style=getComputedStyle(cart);const pieces=Array.from(cart.children).filter(el=>!el.classList.contains('pos-cart-items')&&!el.classList.contains('pos-cart-scroll-hint')&&getComputedStyle(el).display!=='none');const minimum=pieces.reduce((sum,el)=>sum+el.getBoundingClientRect().height,0)+340+18+(parseFloat(style.rowGap)||10)*pieces.length+parseFloat(style.paddingTop)+parseFloat(style.paddingBottom);root.style.setProperty('--pos-main-height',`${Math.max(minimum,window.innerHeight-main.getBoundingClientRect().top-14)}px`);}scroll.dataset.overflow=String(scroll.scrollHeight>scroll.clientHeight+2);};const observer=new ResizeObserver(measure);observer.observe(footer);observer.observe(scroll);root.querySelector('.srm-pos-cart')?.querySelectorAll(':scope > *').forEach(el=>{if(!el.classList.contains('pos-cart-items')&&!el.classList.contains('pos-cart-scroll-hint'))observer.observe(el);});root.querySelectorAll('.pos-shell-header,.pos-guidance').forEach(el=>observer.observe(el));window.addEventListener('resize',measure);if(scroll.firstElementChild)observer.observe(scroll.firstElementChild);measure();return()=>{observer.disconnect();window.removeEventListener('resize',measure);};},[]);
  const { term, profile } = useBusinessTerms();
  const presentation = posPresentation(operationalPackKey || profile.business_type);
  const storage = (key:string) => `business-suite-srm-pos-v2:${draftScope}:${key}`;
  const navigate = useNavigate();
  const authUser = useAuthStore(state => state.user);
  const queryClient = useQueryClient();
  useSrmRealtimeInvalidation(queryClient);
  const [activeProfileId, setActiveProfileId] = usePersistedState(storage("profile"), defaultStoreProfile.id);
  const [bookingPresentation,setBookingPresentation]=usePersistedState<POSBookingPresentation>(storage("service-booking-layout"),"cart");
  const [tileDensity, setTileDensity] = usePersistedState<"comfortable" | "compact">(storage("density"), "comfortable");
  const [productView, setProductView] = usePersistedState<ProductViewMode>(storage("product-view"), "tiles");
  const activeStoreProfile = useMemo(() => posStoreProfiles.find((profile) => profile.id === activeProfileId) || defaultStoreProfile, [activeProfileId]);
  const mode = activeStoreProfile.mode;
  const [customerId, setCustomerId] = usePersistedState(storage("customer"), 0);
  const [customerProfile,setCustomerProfile]=useState(false);
  const [customersRequested,setCustomersRequested]=useState(false);
  const [quickAddOpen, setQuickAddOpen] = useState(false);
  function customerCreated(record: PosCustomerRecord) {
    queryClient.setQueryData<Customer[]>(["srm", "posCustomers", scope], current => [...(current || []).filter(c => c.id !== record.id), savedCustomer(record)]);
    setCustomerId(record.id);
    setQuickAddOpen(false);
    void queryClient.invalidateQueries({ queryKey: ["follow-up-options"] });
    toast({ title: "Customer added", description: `${record.name} is selected for this sale and its follow-ups.` });
  }
  const [query, setQuery] = useState("");
  const [catalogSearch,setCatalogSearch]=useState(""),[catalogPages,setCatalogPages]=useState(1);
  useEffect(()=>{const timer=setTimeout(()=>{setCatalogSearch(query);setCatalogPages(1)},250);return()=>clearTimeout(timer)},[query]);
  const [scanFeedback,setScanFeedback] = useState('');
  const [phoneNotice,setPhoneNotice] = useState(false);
  useEffect(()=>{if(!scanFeedback){setPhoneNotice(false);return;}setPhoneNotice(true);const timer=window.setTimeout(()=>setPhoneNotice(false),2500);return()=>window.clearTimeout(timer);},[scanFeedback]);
  const [highlighted,setHighlighted] = useState<number|null>(null);
  const [undo,setUndo] = useState<{lines:CartLine[];message:string;customerId?:number}|null>(null);
  const [confirmClear,setConfirmClear] = useState(false);
  const [readinessOpen,setReadinessOpen] = useState(false);
  const [helpOpen,setHelpOpen] = useState(false);
  const [online,setOnline] = useState(navigator.onLine);
  const [paymentError,setPaymentError] = useState("");
  const [shareNotice,setShareNotice] = useState('');
  const [printAfterSale,setPrintAfterSale] = useState(false);
  const [printSale,setPrintSale] = useState<Sale|null>(null);
  useEffect(()=>{const connected=()=>setOnline(navigator.onLine);window.addEventListener('online',connected);window.addEventListener('offline',connected);return()=>{window.removeEventListener('online',connected);window.removeEventListener('offline',connected);};},[]);

  const [mobileView, setMobileView] = useState<"products" | "cart">("products");
  const [configurationOpen, setConfigurationOpen] = useState(false);
  const [sessionDetailsOpen, setSessionDetailsOpen] = useState(false);
  const [category, setCategory] = useState("All");
  const [draftCart, setCart] = usePersistedState<CartLine[]>(storage("cart"), []);
  const [phonePanel,setPhonePanel] = useState<'sessions'|'actions'|'customer'|'discounts'|null>(null);
  const [phoneLineId,setPhoneLineId] = useState<string|null>(null);
  const phonePaginationAnchor=useRef<string|null>(null);
  const [phonePage,setPhonePage] = useState(0);
  const [phonePageSize,setPhonePageSize] = useState(1);
  const [phoneWidth,setPhoneWidth] = useState(()=>window.innerWidth);
  useLayoutEffect(()=>{
    const resize=()=>setPhoneWidth(window.innerWidth);
    window.addEventListener('resize',resize);
    const node=cartScrollRef.current;
    const observer=new ResizeObserver(()=>{
      if(!node||!node.clientWidth||window.innerWidth>767)return;
      // Measure hidden pages without unmounting their scheduling/availability state.
      const heights=Array.from(node.querySelectorAll<HTMLElement>('.pos-cart-line')).map(row=>{
        if(getComputedStyle(row).display!=='none')return row.getBoundingClientRect().height;
        const copy=row.cloneNode(true) as HTMLElement;
        copy.dataset.phoneHidden='false';copy.setAttribute('aria-hidden','true');
        Object.assign(copy.style,{position:'absolute',visibility:'hidden',pointerEvents:'none',width:`${node.clientWidth-18}px`,left:'-10000px'});
        row.parentElement!.append(copy);const height=copy.getBoundingClientRect().height;copy.remove();return height;
      });
      const needed=Math.max(0,...heights.filter((_,index)=>index%2===0).map((height,index)=>height+(heights[index*2+1]||0)))+4;
      const pager=workspaceRef.current?.querySelector<HTMLElement>('.pos-phone-pagination');
      const reclaimed=draftCart.length<=2&&pager&&getComputedStyle(pager).display!=='none'?pager.offsetHeight+6:0;
      setPhonePageSize(node.clientHeight+reclaimed>=needed?2:1);
    });
    if(node){observer.observe(node);node.querySelectorAll('.pos-cart-line').forEach(row=>observer.observe(row));}
    return()=>{observer.disconnect();window.removeEventListener('resize',resize);};
  },[draftCart]);
  useLayoutEffect(()=>{const index=draftCart.findIndex(line=>line.lineId===phonePaginationAnchor.current);if(index>=0)setPhonePage(Math.floor(index/phonePageSize));},[phonePageSize,draftCart]);
  const phonePages=Math.max(1,Math.ceil(draftCart.length/phonePageSize));
  const safePhonePage=Math.min(phonePage,phonePages-1);
  useEffect(()=>{setPhonePage(page=>Math.min(page,phonePages-1));},[phonePages]);

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
  const productsQuery = useQuery({queryKey:["srm","inventoryItems","pos",scope,catalogSearch,catalogPages],queryFn:({signal})=>loadPOSCatalog(api,!!selectedPOS,catalogSearch,catalogPages,signal),refetchInterval:selectedPOS?45000:false,refetchIntervalInBackground:false,refetchOnWindowFocus:false});
  const customersQuery = useQuery<Customer[]>({ enabled: customersRequested || phonePanel === "customer" || customerId > 0 || productsQuery.isSuccess, queryKey: ["srm", "posCustomers", scope], queryFn: async () => {
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
  const posFeatures = productsQuery.data?.features;
  const heldBillsQuery = useQuery({ enabled:!selectedPOS && (productsQuery.isSuccess || activeModal === "held" || draftCart.length > 0), queryKey: ["srm", "posHeldBills", scope], queryFn: () => srmApi.posHeldBills(), refetchInterval: activeModal === "held" ? 30000 : false, refetchIntervalInBackground: false, refetchOnWindowFocus: false });

  useEffect(()=>{if(!selectedPOS&&activeModal==="held")void heldBillsQuery.refetch()},[activeModal,selectedPOS]);
  const followUpOptions = useQuery({enabled:!selectedPOS&&draftCart.length>0,queryKey:["follow-up-options",scope],queryFn:()=>api.get("/follow-ups/options").then(r=>r.data)});
  const [checkoutKey, setCheckoutKey] = usePersistedState(storage("checkout-key"), randomUUID());
  const intentKey = financialIntentKey("checkout");
  const [recovery] = useState(() => readPOSCheckoutIntent<CheckoutAttempt>(intentKey));
  const [uncertain, setUncertain] = useState<CheckoutAttempt|null>(recovery.payload);
  const [opaqueLock, setOpaqueLock] = useState(recovery.pending && !recovery.payload);
  const uncertainty = useRef(uncertain);
  const [nativeBusy, setNativeBusy] = useState(false), [nativeError, setNativeError] = useState('');
  const locked = opaqueLock || !!uncertain || nativeBusy;
  const [bookingAvailability,setBookingAvailability] = useState<Record<string,boolean|null>>({});
  const [bookingSummaries,setBookingSummaries] = useState<Record<string,string>>({});
  const [requirements, setRequirements] = useState<Record<string,boolean>>({});
  const [openingCash, setOpeningCash] = useState('0'), [opening, setOpening] = useState(false);
  const registerQueryKey = ['srm','pos-active-session',scope] as const;
  const readActiveRegister = (signal: AbortSignal) => api.get<SRMRecord>('/srm/pos/sessions/active',{signal,recordCache:false}).then(response=>response.data);
  const activeRegister = useQuery({enabled:productsQuery.isSuccess || draftCart.length>0 || activeModal!==null || phonePanel==='sessions',queryKey:registerQueryKey,queryFn:({signal})=>readActiveRegister(signal),retry:false});
  const paymentCaps = useQuery({queryKey:['srm','pos-checkout-payment-capabilities',scope],queryFn:()=>api.get<{collect:boolean}>('/srm/industry/capabilities').then(response=>response.data),enabled:!!lastSale?.checkoutId,retry:false});
  type CheckoutAuthority = {invoice?:boolean;collect?:boolean;checkout_create?:boolean;checkout_collect?:boolean};
  const recoveryAuthority = useQuery({queryKey:['srm','pos-checkout-recovery-authority',scope],queryFn:({signal})=>api.get<CheckoutAuthority>('/srm/industry/capabilities',{signal,recordCache:false}).then(response=>response.data),retry:false,enabled:!!uncertain,placeholderData:undefined});
  const permitsRecovery = (authority:CheckoutAuthority|undefined, attempt:CheckoutAttempt|null) => !!authority && !!attempt && Array.isArray(attempt.payload.payments) && authority.checkout_create === true && (!attempt.payload.payments.length || authority.checkout_collect === true);
  const canReplay = recoveryAuthority.isSuccess && !recoveryAuthority.isFetching && permitsRecovery(recoveryAuthority.data, uncertain);

  const register = (activeRegister.data as {session?:{id:number;session_number?:string;status?:string;opening_cash?:number;register_name?:string}}|undefined)?.session;
  function saveAttempt(value:CheckoutAttempt|null) { if(value) saveFinancialIntent(intentKey,value); else clearFinancialIntent(intentKey); uncertainty.current=value; setUncertain(value); }
  useEffect(() => {
    setCart(current => normalizeCart(current));
    // Ignore a saved customer left behind by an older POS when there is no draft bill.
    if (!draftCart.length) setCustomerId(0);
  }, []);
  const checkoutBusy = useRef(false);
  const customer = customers.find((item) => item.id === customerId) || walkInCustomer;
  const customerLabel = customer.id ? customer.name : "Choose customer";
  const serverHeldBills = useMemo(() => listItems(heldBillsQuery.data).map(heldBillFromRecord).filter(bill=>bill.cart.length>0&&bill.cart.every(line=>line.draftScope===draftScope)), [heldBillsQuery.data,draftScope]);
  const heldBills = useMemo(() => selectedPOS ? [] : [...serverHeldBills, ...localHeldBills], [selectedPOS, localHeldBills, serverHeldBills]);
  const currentProducts=useMemo(()=>listItems(productsQuery.data).map(productFromRecord).filter(item=>item.active!==false),[productsQuery.data]);
  const knownProducts=useRef<{scope:string;items:Map<number,Product>}>({scope,items:new Map()});
  if(knownProducts.current.scope!==scope)knownProducts.current={scope,items:new Map()};
  for(const item of currentProducts)knownProducts.current.items.set(item.id,item);
  for(const id of knownProducts.current.items.keys()){if(knownProducts.current.items.size<=1000)break;if(!draftCart.some(line=>line.id===id))knownProducts.current.items.delete(id);}
  const dbProducts=[...knownProducts.current.items.values()];
  const cart = draftCart.map(line => {
    const product = knownProducts.current.items.get(line.id);
    return product ? {...line, rate: product.rate, taxRate: product.taxRate, stock: product.stock,
      lotAllocation: product.lotAllocation, lots: product.lots} : line;
  });
  const phoneLine = cart.find(line => line.lineId === phoneLineId);
  const remainingByLot = new Map<number, number>();
  const pricedLines = new Map<string, CartLine[]>();
  const incompleteLots = new Set<string>();
  for (const line of cart) {
    if (line.lotAllocation !== "fefo") {
      pricedLines.set(line.lineId, [line]);
      continue;
    }
    const parts: CartLine[] = [];
    // Allocate in thousandths so fractional stock does not leave a rounding remainder.
    let remaining = Math.round(line.qty * 1000);
    for (const lot of line.lots || []) {
      if (!remaining) break;
      const available = remainingByLot.get(lot.id) ?? Math.round(Number(lot.quantity) * 1000);
      const take = Math.min(available, remaining);
      if (!take) continue;
      parts.push({...line, qty: take / 1000, rate: Number(lot.rate), batchId: lot.id, batchNo: lot.number});
      remainingByLot.set(lot.id, available - take);
      remaining -= take;
    }
    if (remaining) incompleteLots.add(line.lineId);
    pricedLines.set(line.lineId, parts);
  }
  const checkoutLines = [...pricedLines.values()].flat();
  function displayRate(line: CartLine) {
    return line.lotAllocation === "fefo"
      ? (pricedLines.get(line.lineId) || []).map(part =>
          `Batch ${part.batchNo} · ${part.qty} × ${currency(part.rate)}`).join(" / ") || "No eligible batch stock"
      : currency(line.rate);
  }
  const productSource=currentProducts;
  const storeProducts=productSource;
  const [catalogTab, setCatalogTab] = useState("All");
  const [catalogSort, setCatalogSort] = useState("name");
  const [usageCounts,setUsageCounts] = usePersistedState<Record<string,number>>(storage("catalog-usage"), {});
  const [favoriteIds,setFavoriteIds] = usePersistedState<number[]>(storage("favorite-catalog"), []);
  const [recentIds, setRecentIds] = usePersistedState<number[]>(storage("recent-catalog"), []);
  const categories = useMemo(() => ["All", ...Array.from(new Set(storeProducts.map((item) => item.category)))], [storeProducts]);
  const couponDiscount = coupon.trim().toUpperCase() === "WELCOME10" ? Math.min(250, Math.max(0, checkoutLines.reduce((sum, item) => sum + lineTaxable(item), 0) * 0.1)) : 0;

  const totals = useMemo(() => {
    const subtotal = checkoutLines.reduce((sum, item) => sum + lineBase(item), 0);
    const lineDiscountTotal = checkoutLines.reduce((sum, item) => sum + lineDiscount(item), 0);
    const taxableBeforeBill = checkoutLines.reduce((sum, item) => sum + lineTaxable(item), 0);
    const safeBillDiscount = Math.min(Math.max(billDiscount, 0), taxableBeforeBill);
    const taxable = Math.max(taxableBeforeBill - safeBillDiscount - couponDiscount, 0);
    const taxBeforeScale = checkoutLines.reduce((sum, item) => sum + lineTax(item), 0);
    const tax = taxableBeforeBill ? taxBeforeScale * (taxable / taxableBeforeBill) : 0;
    const unrounded = taxable + tax;
    const grandTotal = Math.max(Math.round((unrounded + Number.EPSILON) * 100) / 100, 0);
    const nativeQuote = operationalPackKey === "pharma" && checkoutLines.some(line => line.lotAllocation === "fefo")
      ? pharmaCheckoutQuote(checkoutLines.map(line => ({quantity: String(line.qty), price: line.rate.toFixed(2),
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
      qty: checkoutLines.reduce((sum, item) => sum + item.qty, 0),
      ...(nativeQuote ? {...nativeQuote, qty: nativeQuote.quantity, roundOff: 0} : {}),
    };
  }, [billDiscount, checkoutLines, couponDiscount, operationalPackKey]);

  const filteredProducts = useMemo(() => {
    const text = query.trim().toLowerCase();
    return storeProducts.filter((product) => {
      const categoryMatch = category === "All" || product.category === category;
      const textMatch = !text || [product.name, product.sku, product.barcode, product.category, product.batch || "", ...(product.serials || [])].join(" ").toLowerCase().includes(text);
      return categoryMatch && textMatch && (catalogTab === "All" || (catalogTab === "Recently Used" ? recentIds.includes(product.id) : catalogTab === "Favorites" ? favoriteIds.includes(product.id) : catalogTab === "Frequently Used" ? (usageCounts[product.id] || 0)>0 : matchesOfferingTab(product,catalogTab)));
    }).sort((a,b) => catalogTab==="Frequently Used" || catalogSort==="frequent" ? (usageCounts[b.id] || 0)-(usageCounts[a.id] || 0) || a.name.localeCompare(b.name) : catalogSort === "price" ? a.rate-b.rate : a.name.localeCompare(b.name));
  }, [category, query, storeProducts, catalogTab, catalogSort, recentIds, favoriteIds, usageCounts]);

  const received = paymentRows.reduce((sum, row) => row.mode === "Credit" ? sum : sum + row.amount, 0);
  const balanceDue = Math.max(totals.grandTotal - received, 0);
  const changeDue = Math.max(received - totals.grandTotal, 0);
  const explicitCredit = paymentRows.filter(row=>row.mode==="Credit").reduce((sum,row)=>sum+row.amount,0);
  const validSplitCredit = customerId>0 && paymentMode==="Split" && explicitCredit>0 && Math.abs(explicitCredit-balanceDue)<0.005;
  const registerCash = activeRegister.data as {expected_cash?: number | string | null; cash_sales?: number | string | null; reconciliation_required?: boolean} | undefined;
  const expectedCash = cashNumber(registerCash?.expected_cash);
  const cashReceived = cashNumber(registerCash?.cash_sales);
  const countedClosingCash = cashNumber(closingCash);
  const registerCashReady = !activeRegister.isPending && !activeRegister.isFetching && !activeRegister.isError && Number.isFinite(expectedCash);
  const canCloseSession = registerCashReady && Boolean(register?.id) && !registerCash?.reconciliation_required && Number.isFinite(expectedCash) && Number.isFinite(countedClosingCash) && countedClosingCash >= 0;
  const lowStockCount = storeProducts.filter((product) => product.trackInventory && product.stock <= product.reorderLevel).length;

  const branchDisplay = useQuery({queryKey:['suite-branch-context',authUser?.id,authUser?.access?.companyId],staleTime:60_000,refetchOnWindowFocus:false,queryFn:()=>api.get<{branches:{id:number;name:string}[]}>('/branches/context',{recordCache:false}).then(response=>response.data),retry:false});
  const cashierName = authUser?.name || authUser?.email || 'Cashier';
  const branchName = branchDisplay.data?.branches?.find(branch=>String(branch.id)===selectedBranch())?.name || (authUser?.access as {branchName?:string}|undefined)?.branchName || `Branch ${selectedBranch()}`;
  const readiness: {id:string;text:string;lineId?:string}[] = [];
  if (!online) readiness.push({id:'connection',text:'Reconnect before taking payment. Your basket is retained.'});
  if (!register?.id || register.status && register.status!=='open') readiness.push({id:'register',text:phoneWidth<=767?'Tap Open register at the top of POS.':'Open a register in Session & actions.'});
  if (productsQuery.isError || !productsQuery.data) readiness.push({id:'catalog',text:'Reload the catalog to verify stock and service availability.'});
  if (customerId > 0 && !customers.some(item=>item.id===customerId)) readiness.push({id:'customer',text:'Choose an available customer.'});
  if (!customerId && cart.some(line=>line.booking || line.followUp || isService(line) && requirements[line.lineId])) readiness.push({id:'customer',text:'Select a registered customer for appointments and follow-ups.'});
  for (const line of cart) {
    const current = dbProducts.find(product=>product.id===line.id);
    if (incompleteLots.has(line.lineId)) readiness.push({id:`batch-${line.lineId}`,lineId:line.lineId,text:`${line.name}: reduce the quantity to available batch stock.`});
    if (!current || current.checkoutSupported===false) readiness.push({id:`item-${line.lineId}`,lineId:line.lineId,text:`${line.name}: ${current?.unsupportedReason || 'reload or remove this unavailable item'}.`});
    if (line.trackInventory && line.qty > (current?.stock ?? line.stock)) readiness.push({id:`stock-${line.lineId}`,lineId:line.lineId,text:`${line.name}: only ${current?.stock ?? line.stock} in stock.`});
    if (isService(line) && line.schedulingConfigured !== false && (!selectedPOS || posFeatures?.appointments_schedule) && (!(line.lineId in requirements) || requirements[line.lineId] && !line.booking)) readiness.push({id:`booking-${line.lineId}`,lineId:line.lineId,text:`${line.name}: ${line.lineId in requirements ? 'apply the required appointment details' : 'wait for scheduling rules to load'}.`});
    if (!isService(line) && (line.serialTracking || line.batchTracking && line.lotAllocation !== 'fefo')) readiness.push({id:`tracking-${line.lineId}`,lineId:line.lineId,text:`${line.name}: use the supported serial/batch stock workflow.`});
    if (line.booking && bookingAvailability[line.lineId]===false) readiness.push({id:`availability-${line.lineId}`,lineId:line.lineId,text:`${line.name}: this employee or resource is no longer available. Refresh scheduling.`});
    if (line.booking && cartBookingConflict(cart,line.lineId,line.booking,line.resourceCapacities)) readiness.push({id:`overlap-${line.lineId}`,lineId:line.lineId,text:`${line.name}: employee or resource capacity overlaps another appointment in this basket.`});
  }
  function reviewIssue(issue:{id:string;lineId?:string}) {
    if (issue.id==='register') {if(phoneWidth<=767)setPhonePanel('sessions');else setSessionDetailsOpen(true);}
    if (issue.id==='catalog') void productsQuery.refetch();
    if (issue.id==='customer' && phoneWidth<=767) {setPhonePanel('customer');return;}
    if (issue.id==='customer') document.querySelector<HTMLButtonElement>('[aria-label="Change sale customer"]')?.click();
    if (issue.lineId) {setPhonePage(Math.floor(cart.findIndex(line=>line.lineId===issue.lineId)/phonePageSize));setReadinessOpen(false);setMobileView('cart');requestAnimationFrame(()=>{const row=document.getElementById(`pos-line-${issue.lineId}`);row?.querySelectorAll('details').forEach(details=>details.open=true);row?.scrollIntoView({block:'center',behavior:'smooth'});});}
  }
  async function openRegister() {
    if(locked||!owns()||opening||!online)return;
    setOpening(true);
    try {
      await srmApi.openPosSession({branch:activeStoreProfile.branch,register_name:activeStoreProfile.register,opening_cash:openingCash});
      if(owns()){await activeRegister.refetch();setPhonePanel(null);}
    } catch(error) {if(owns())toast({title:'Register not opened',description:dealError(error),variant:'destructive'});}
    finally {if(owns())setOpening(false);}
  }
  function removeLine(lineId:string) {
    if(locked)return;
    setUndo({lines:cart.filter(line=>line.lineId===lineId),message:'Item removed'});setCart(current=>current.filter(line=>line.lineId!==lineId));
  }
  function printReceipt(sale:Sale|null = lastSale || sales.find(item=>!!item.checkoutId) || null) {
    if(!sale?.checkoutId)return;
    setPrintSale(sale);setTimeout(()=>window.print(),100);
  }
  async function shareReceipt(sale:Sale) {
    try {if(navigator.share)await navigator.share({title:`Invoice ${sale.invoiceNo}`,text:receiptText(sale)});else {await navigator.clipboard.writeText(receiptText(sale));setShareNotice('Receipt copied. Paste it into your preferred app.');}}catch(error){if(!(error instanceof DOMException && error.name==='AbortError'))setShareNotice('Sharing was unavailable. Download the receipt instead.');}
  }

  function addProduct(product: Product) {
    if (locked) return;
    setRecentIds(current => [product.id, ...current.filter(id => id !== product.id)].slice(0, 50));
    if(product.checkoutSupported===false){toast({title:'Item unavailable for checkout',description:product.unsupportedReason,variant:'destructive'});return;}
    if (product.trackInventory && product.stock <= 0) {
      toast({ title: "Out of stock", description: `${product.name} cannot be added.` });
      return;
    }
    const already = cart.filter(line=>line.id===product.id).reduce((sum,line)=>sum+line.qty,0);
    if(product.trackInventory && already>=product.stock){setScanFeedback(`${product.name}: only ${product.stock} in stock; no more added.`);return;}
    setUsageCounts(counts=>({...counts,[product.id]:(counts[product.id] || 0)+1}));
    setHighlighted(product.id);setScanFeedback(`${product.name} added to cart.`);
    const addedLine = buildCartLine(product);
    setCart((current) => {
      const existing = current.find((line) => line.id === product.id && !line.serialTracking && !isService(line) && !isCustomerPlan(line));
      phonePaginationAnchor.current = existing?.lineId || addedLine.lineId;
      if (!existing) return [...current, addedLine];
      return current.map((line) => line.lineId === existing.lineId ? { ...line, qty: line.trackInventory ? Math.min(line.stock, line.qty + 1) : line.qty + 1 } : line);
    });
  }

  function removeProduct(productId: number) {
    if(locked)return;
    const matching = cart.filter(line => line.id === productId).reverse();
    const existing = matching.find(line => !line.booking) ?? matching[0];
    if(!existing)return;
    if(existing.qty<=1)removeLine(existing.lineId);else updateLine(existing.lineId,{qty:existing.qty-1});
  }

  function updateLine(lineId: string, patch: Partial<CartLine>) {
    if (locked) return;
    const existing=cart.find(line=>line.lineId===lineId);
    if(patch.qty!==undefined && existing && !existing.decimalAllowed)patch={...patch,qty:Math.max(1,Math.floor(patch.qty))};
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
    setPaymentError("");setReadinessOpen(true);
    if(readiness.length) {setMobileView("cart");return;}
    setPaymentMode(nextMode);
    setPaymentRows(nextMode === "Split"
      ? [{ id: randomUUID(), mode: "Cash", amount: totals.grandTotal, reference: "" }]
      : [{ id: randomUUID(), mode: nextMode === "Credit" ? "Credit" : nextMode, amount: nextMode === "Credit" ? 0 : totals.grandTotal, reference: "" }]);
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
      const nextKey=randomUUID();
      for(const [key,value] of Object.entries({'cart':[],'customer':0,'bill-discount':0,'coupon':'','note':'','payment-rows':[],'checkout-key':nextKey})) localStorage.setItem(storage(key),JSON.stringify(value));
      clearFinancialIntent(intentKey); recovery.sourceKeys.forEach(key=>localStorage.removeItem(key));
      if(!owns()) return;
      uncertainty.current=null; setUncertain(null); setCheckoutKey(nextKey); setCart([]);setCustomerId(0);setCustomerProfile(false);setBillDiscount(0);setCoupon('');setNote('');setPaymentRows([]);
      const sale:Sale={...attempt.sale,invoiceNo:result.invoice.number,amount:Number(result.invoice.total),checkoutId:result.id,paid:result.invoice.paid,balance:result.invoice.balance,receiptNumbers:result.receipts.map(row=>row.number),hasBookings:attempt.payload.lines.some(line=>!!line.booking)};
      setUndo(null);setConfirmClear(false);setReadinessOpen(false);setSales(current=>[sale,...current].slice(0,25));setLastSale(sale);setActiveModal('success');
      void syncSrmNow(queryClient,{type:'pos_sale_completed',source:'pos-terminal',ids:{sales_order_id:result.sales_order_id}});
      void productsQuery.refetch();if(!selectedPOS)void heldBillsQuery.refetch();
      // Refresh failures must not turn a committed sale into an uncertain checkout.
      void refreshSettledRegister(queryClient,registerQueryKey,readActiveRegister,owns).catch(()=>undefined);
      if(attempt.after==='print')printReceipt(sale);
      if(attempt.after==='email')toast({title:'Checkout completed',description:'Email receipt delivery is not configured. No email has been queued.'});
      if(attempt.after==='whatsapp'&&phoneLinks(customer.phone)?.whatsapp)navigate('/crm/whatsapp',{state:{whatsappDraft:{key:`checkout:${sale.checkoutId}`,to:phoneLinks(customer.phone)!.call.slice(4),body:`Hello ${sale.customer}, thank you for your purchase. Invoice: ${sale.invoiceNo}. Total: ${shortCurrency(sale.amount)}. Paid: ${shortCurrency(Number(sale.paid))}. Balance: ${shortCurrency(Number(sale.balance))}.`}}});
    } catch(error) {
      const status=isAxiosError(error)?error.response?.status:undefined;
      if(!replay&&status!==undefined&&status>=400&&status<500) {
        clearFinancialIntent(intentKey); recovery.sourceKeys.forEach(key=>localStorage.removeItem(key));
        if(!owns())return;
        uncertainty.current=null;setUncertain(null);setCheckoutKey(randomUUID());setPaymentError(dealError(error));setActiveModal('payment');
        toast({title:'Checkout rejected',description:dealError(error)+' Your basket is retained. Review and reload scheduling before trying again.',variant:'destructive'});
        void activeRegister.refetch();
        void productsQuery.refetch();
      } else if(owns()) setNativeError(dealError(error)+' The original checkout is retained; retry the same checkout to confirm its outcome.');
    } finally {checkoutBusy.current=false;if(owns())setNativeBusy(false);}
  }
  async function prepareNative(after:CheckoutAfter) {
    if(checkoutBusy.current||opaqueLock||!owns())return;
    try { const stored=readFinancialIntent<CheckoutAttempt>(intentKey); if(stored.pending) { if(stored.payload?.payload?.request_id) { uncertainty.current=stored.payload;setUncertain(stored.payload); } else setOpaqueLock(true); setActiveModal(null);return; } } catch { toast({title:'Checkout recovery unavailable',description:'Local recovery storage must be available before checkout.',variant:'destructive'});return; }
    if(selectedPOS&&(productsQuery.isFetching||productsQuery.isError||cart.some(line=>{const item=dbProducts.find(item=>item.id===line.id);return !item||item.checkoutSupported===false||!!line.followUp||(!posFeatures?.appointments_schedule&&!!line.booking);}))){toast({title:'Review POS availability',description:'Reload the catalogue and remove unsupported follow-up or unavailable items before checkout.',variant:'destructive'});return;}
    if(cart.some(line=>isService(line)&&(!selectedPOS||!!posFeatures?.appointments_schedule)&&(!(line.lineId in requirements)||(requirements[line.lineId]&&!line.booking)))) {toast({title:'Complete service scheduling',description:'Wait for each service policy and apply booking details for every required service.',variant:'destructive'});return;}
    if (incompleteLots.size || checkoutLines.length > 100) {
      setPaymentError(incompleteLots.size ? 'Reduce the quantities to available batch stock.' : 'Split this sale into smaller bills. Checkout supports up to 100 lines.');
      return;
    }
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
        lines:checkoutLines.map(line=>({client_line_key:line.lotAllocation === "fefo" ? randomUUID() : line.lineId,line_kind:line.booking?'booked_service':isService(line)?'unscheduled_service':'product',product_id:line.id,...(line.batchId ? {batch_id:line.batchId} : {}),quantity:String(line.booking?1:line.qty),unit_price:line.rate.toFixed(2),discount_amount:lineDiscount(line).toFixed(2),note:line.note,...(line.planStartDate?{plan_start_date:line.planStartDate}:{}),...(line.planBeneficiaries?.length?{plan_beneficiaries:line.planBeneficiaries}:{}),...(line.followUp?{follow_up:line.followUp}:{}),...(line.booking?{booking:line.booking}:{})})),payments};
      const attempt:CheckoutAttempt={payload,after,sale:{id:checkoutKey,invoiceNo:'',customer:customer.name,amount:totals.grandTotal,mode:paymentMode,createdAt:new Date().toISOString(),items:cart.length,lines:checkoutLines.map(line=>({name:line.batchNo ? `${line.name} · Batch ${line.batchNo}` : line.name,qty:line.qty,rate:line.rate,...(line.booking?{appointment:bookingSummaries[line.lineId] || `${new Date(line.booking.starts_at).toLocaleString()} - ${new Date(Date.parse(line.booking.starts_at)+line.booking.duration_minutes*60000).toLocaleString()}`}:{})}))}};
      saveAttempt(attempt);checkoutBusy.current=false;setNativeBusy(false);await submitNative(attempt);
    } catch(error) {if(owns()){const message=error instanceof Error?error.message:dealError(error);setPaymentError(message);toast({title:'Checkout not started',description:message,variant:'destructive'});}checkoutBusy.current=false;if(owns())setNativeBusy(false);}
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
      setPaymentError('Received amount is less than the bill total. Increase the payment or assign the remaining balance to explicit credit.');
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
    setCustomerId(0);
    setCustomerProfile(false);
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
    setUndo(null);
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
    if(!query.trim())return;
    const exact = storeProducts.find((product) => product.barcode === query.trim() || product.sku.toLowerCase() === query.trim().toLowerCase());
    if (exact) {
      addProduct(exact);
      setQuery("");
      return;
    }
    if (filteredProducts.length === 1) {
      addProduct(filteredProducts[0]);
      setQuery("");
      return;
    }
    setScanFeedback(filteredProducts.length ? "Multiple matches. Select an item from the results." : "Barcode not found. Search by name or add the item in Stock Items.");
  }

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if(locked)return;
      if (event.key === "F2") {
        event.preventDefault();
        searchRef.current?.focus();
      }
      if (event.key === "F4" && !activeModal) {
        event.preventDefault();
        holdCart();
      }
      if (event.key === "F5" && !selectedPOS && !activeModal) {
        event.preventDefault();
        setActiveModal("held");
      }
      if (event.key === "F7" && !activeModal) {
        event.preventDefault();
        openPayment("Cash");
      }
      if (event.key === "F8") {
        event.preventDefault();
        printReceipt();
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
    <div ref={workspaceRef} className={`srm-pos pos-booking-workspace srm-pos-view-${mobileView} min-h-full bg-[linear-gradient(135deg,#eef7f2_0%,#f7f4ee_48%,#eef2ff_100%)] text-slate-950`}>
      <header className="pos-shell-header relative z-30 border-b border-white/70 bg-white/85 px-4 py-3 shadow-sm backdrop-blur">
        <div className="flex flex-col gap-3 2xl:flex-row 2xl:items-center 2xl:justify-between">
          <div className="pos-workspace-identity flex min-w-0 items-center gap-3"><button className="pos-phone-back" type="button" aria-label="Back to sales" onClick={()=>navigate("/srm")}><ArrowLeft size={23}/></button>
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-[#6d49d7] text-white shadow-sm">
              <ShoppingCart className="h-6 w-6 text-white" />
            </span>
            <div className="min-w-0">
              <span className="pos-workspace-eyebrow">Sales workspace</span>
              <h1 className="truncate text-xl font-semibold" title={presentation.title}>{phoneWidth<=767?"Billing & POS":presentation.title}</h1>
              <p className="text-sm text-slate-500">{branchName} · {register?.register_name || "Register not open"} · {register?.session_number || (register ? `#${register.id}` : "Not open")}</p>
              <button type="button" className="pos-phone-register" onClick={()=>setPhonePanel('sessions')}>
                {register?.id ? 'Register session' : 'Open register'}
              </button>
            </div>
            <div className="pos-phone-header-tools"><ModuleNewMenu>{actions=><NewMenu actions={[...actions,{label:'Register setup',description:'Open or manage the billing register',icon:Calculator,group:'POS tools',onSelect:()=>setPhonePanel('sessions')},{label:'Bill tools',description:'Customer, cash drawer, receipts and held bills',icon:Settings,group:'POS tools',onSelect:()=>setPhonePanel('actions')}]} iconOnly/>}</ModuleNewMenu><SuiteNotificationBell/><Link to="/srm/profile" aria-label="My profile" className="pos-phone-profile">{(authUser?.name || cashierName || "User").split(" ").slice(0,2).map(word=>word[0]).join("")}</Link></div>
          </div>
          <div className="pos-header-actions">
            <nav aria-label="Sales and scheduling" className="pos-workspace-links">
              <span aria-current="page"><ShoppingCart size={15}/>POS</span>
              {(!selectedPOS || posFeatures?.appointments_schedule) && canAccessRoute('/srm/appointments', authUser?.role, authUser?.is_superuser) && <Link to="/srm/appointments"><CalendarDays size={15}/>Appointments</Link>}
              {(!selectedPOS || posFeatures?.appointments_schedule) && canAccessRoute('/srm/service-scheduling', authUser?.role, authUser?.is_superuser) && <Link to="/srm/service-scheduling?view=schedule"><CalendarRange size={15}/>Scheduling</Link>}
            </nav>
          <button type="button" className="srm-pos-session-toggle" aria-expanded={sessionDetailsOpen} aria-controls="pos-session-details" onClick={() => setSessionDetailsOpen(value => !value)}><Settings size={18} />Session & actions<span aria-hidden="true">{sessionDetailsOpen ? "−" : "+"}</span></button>
          </div>
          <div id="pos-session-details" className={`srm-pos-session-details ${sessionDetailsOpen ? "is-open" : ""}`}>
          <div className="grid grid-cols-2 gap-2 text-xs md:flex md:items-center">
            <SessionPill label="Template" value={activeStoreProfile.name} />
            <SessionPill label="Cashier" value={cashierName} />
            <SessionPill label="Opening cash" value={shortCurrency(Number(register?.opening_cash||0))} />
            <SessionPill label="Expected cash" value={registerCashDisplay(activeRegister.isFetching,activeRegister.isError,expectedCash,shortCurrency)} />
          </div>
          <CompactActions className="flex flex-wrap gap-2">
            <Button variant="outline" disabled={!lastSale?.checkoutId && !sales.some(sale=>!!sale.checkoutId)} onClick={()=>{const sale=lastSale || sales.find(sale=>!!sale.checkoutId);if(sale){setLastSale(sale);setActiveModal('success');}}}>Last receipt</Button>
            {!register && <><label className="text-xs">Opening cash<Input aria-label="POS opening cash" className="w-28 border-slate-200 bg-slate-50 text-slate-950" type="number" min="0" value={openingCash} onChange={event=>setOpeningCash(event.target.value)}/></label><Button variant="outline" className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50" disabled={opening||activeRegister.isPending||activeRegister.isFetching} onClick={async()=>{if(locked||!owns())return;setOpening(true);try{await srmApi.openPosSession({branch:activeStoreProfile.branch,register_name:activeStoreProfile.register,opening_cash:openingCash});if(owns())await activeRegister.refetch();}catch(error){if(owns())toast({title:"Register not opened",description:dealError(error),variant:"destructive"});}finally{if(owns())setOpening(false);}}}>Open POS register</Button></>}
            {activeRegister.isError && <Button variant="outline" onClick={()=>void activeRegister.refetch()}>Reload POS register</Button>}
            <Button variant="outline" className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50" onClick={() => setActiveModal("cash")}><Banknote className="h-4 w-4" />Cash drawer</Button>
            <Button variant="outline" className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50" onClick={() => setActiveModal("profile")}><Settings className="h-4 w-4" />Settings</Button>
            <Button variant="outline" className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50" onClick={() => window.print()}><Printer className="h-4 w-4" />Print</Button>
            <Button variant="destructive" onClick={() => setActiveModal("close")}><DoorClosed className="h-4 w-4" />Close</Button>
          </CompactActions>
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
                  category === item ? "bg-[#f0ebff] font-semibold text-[#6d49d7]" : "text-slate-600 hover:bg-slate-50 hover:text-slate-950"
                }`}
              >
                <span className="flex min-w-0 items-center gap-2">
                  <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-xs font-semibold ${category === item ? "bg-white text-[#6d49d7]" : "bg-slate-100 text-slate-500"}`}>
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
              <Button type="button" variant={tileDensity === "comfortable" ? "default" : "outline"} className={tileDensity === "comfortable" ? "bg-[#6d49d7] text-white hover:bg-[#5934bd]" : "border-slate-200 text-slate-700"} onClick={() => setTileDensity("comfortable")}>Comfort</Button>
              <Button type="button" variant={tileDensity === "compact" ? "default" : "outline"} className={tileDensity === "compact" ? "bg-[#6d49d7] text-white hover:bg-[#5934bd]" : "border-slate-200 text-slate-700"} onClick={() => setTileDensity("compact")}>Compact</Button>
            </div>
          </div>
          <div className="mt-4 rounded-xl border border-emerald-100 bg-emerald-50/80 p-3 text-xs text-slate-600">
            <div className="flex items-center gap-2 font-semibold text-slate-900"><Settings className="h-4 w-4" />Active template</div>
            <div className="mt-2"><RichTextContent legacyFormat="plain" value={activeStoreProfile.description}/></div>
          </div>
          </div>
        </aside>
          </div>
        </div>
      </header>


      <div className="pos-phone-feedback" data-notice={phoneNotice} role="status">{scanFeedback ? <><CheckCircle2 size={19}/><span>{scanFeedback}</span><button aria-label="Dismiss item notification" onClick={()=>setScanFeedback('')}><X size={16}/></button></> : <><CheckCircle2 size={19}/><span>{cart.length ? 'Your bill is ready to review.' : 'Add products or services to your bill.'}</span></>}</div>
      <div className="pos-phone-bill"><button type="button" className="pos-phone-bill-customer" aria-label="Change sale customer" onClick={()=>setPhonePanel("customer")}><FileText size={27}/></button><div><strong>Current Bill <button className="pos-phone-customer-compact" aria-label={customerLabel} type="button" onClick={()=>setPhonePanel("customer")}>{customerLabel} ›</button></strong><span>{cart.length} items · {cart.filter(line=>!!line.booking).length} appointment{cart.filter(line=>!!line.booking).length===1?'':'s'}</span></div><Button className="pos-phone-trash" variant="outline" aria-label="Clear bill items" disabled={!cart.length} onClick={()=>setConfirmClear(true)}><Trash2 size={18}/></Button><Button variant="outline" disabled={!cart.length} onClick={()=>setConfirmClear(true)}>Clear</Button></div>
      <button className="pos-phone-customer-button" aria-label="Change sale customer" type="button" onClick={()=>setPhonePanel('customer')}>{customerLabel}<span>{customer.id ? "Change ›" : "Select ›"}</span></button>
      <div className="pos-guidance px-4 py-2 space-y-2">
        <ol className="flex flex-wrap gap-3 text-xs" aria-label="POS startup progress"><li>1. {branchName}</li><li>2. {register?.id ? `Register ${register.session_number || register.id} open` : 'Register not open'}</li><li>3. {register?.id ? `Opening cash ${currency(Number(register.opening_cash || 0))}` : 'Set opening cash'}</li><li>{register?.id && online ? 'Ready for billing' : 'Setup required'}</li></ol>
        {!register?.id && <Button variant="outline" size="sm" onClick={()=>phoneWidth<=767?setPhonePanel('sessions'):setSessionDetailsOpen(true)}>Set opening cash &amp; open register</Button>}
        <p className="text-xs">Customer: <strong>{customerLabel}</strong>{customer.phone ? ` - ${customer.phone}` : ''} | Cashier: {cashierName}</p>
        {!online && <p role="alert">Offline. Your basket is retained; reconnect to check availability and take payment.</p>}
        <p role="status" aria-live="polite" className="text-xs">{scanFeedback}</p>
        {helpOpen && <p className="text-sm">F2 Search / scan | F4 Hold (when supported) | F5 Recall (when supported) | F7 Checkout | F8 Print confirmed receipt. Tab moves between fields; Escape closes dialogs.</p>}
        {undo && <div role="status" className="flex items-center gap-3 text-sm">{undo.message}<Button variant="outline" size="sm" onClick={()=>{setCart(current=>[...current,...undo.lines.filter(line=>!current.some(item=>item.lineId===line.lineId))]);if (!cart.length && !customerId && undo.customerId) setCustomerId(undo.customerId);setUndo(null);}}>Undo removal</Button><Button size="sm" variant="ghost" onClick={()=>setUndo(null)}>Dismiss</Button></div>}
        {readinessOpen && readiness.length>0 && <section aria-label="Checkout readiness" className="rounded border bg-white p-3"><strong>{readiness.length ? `${readiness.length} items to review before payment` : 'Ready for payment'}</strong>{readiness.map(issue=><div key={issue.id} className="flex items-center justify-between gap-2 py-1 text-sm"><span>{issue.text}</span><Button size="sm" variant="outline" onClick={()=>reviewIssue(issue)}>Review</Button></div>)}<p className="text-xs text-slate-500">Stock, appointments and payment permissions are checked again when you confirm.</p></section>}
        {selectedPOS && <p className="text-xs text-slate-500">Hold and Recall are unavailable for this register type. Your active basket is saved on this device.</p>}
      </div>
      <nav className="srm-pos-mobile-tabs" aria-label="POS workspace">
        <button type="button" aria-pressed={mobileView === "products"} onClick={() => setMobileView("products")}><LayoutGrid size={18} />Products</button>
        <button type="button" aria-pressed={mobileView === "cart"} onClick={() => setMobileView("cart")}><ShoppingCart size={18} />Cart <span className="pos-cart-count">{cart.length}</span></button>
      </nav>
      <main className="grid min-h-[calc(100vh-13.5rem)] gap-4 p-4 xl:grid-cols-[minmax(0,1fr)_25rem]">
        <section aria-label="Products and services catalogue" className="srm-pos-catalog min-w-0 space-y-4 overflow-y-auto rounded-2xl border border-white/80 bg-white/65 p-4 shadow-sm backdrop-blur">
          {productsQuery.data?.hasMore&&<div className="flex items-center justify-between gap-2 text-xs"><span>Showing {currentProducts.length} items. Search the catalog or load more.</span><Button type="button" variant="outline" disabled={productsQuery.isFetching} onClick={()=>setCatalogPages(value=>value+1)}>Load more items</Button></div>}
          {phoneWidth<=767 ? <POSMobileCatalogue products={filteredProducts}
            counts={Object.fromEntries(posOfferingTabs.map(tab=>[tab,storeProducts.filter(product=>matchesOfferingTab(product,tab)).length]))}
            cart={cart} query={query} onQuery={setQuery} searchInputRef={searchRef} onScan={scanSearch}
            category={category} categories={categories} onCategory={setCategory} tab={catalogTab} onTab={setCatalogTab} sort={catalogSort} onSort={setCatalogSort}
            favorites={favoriteIds} onFavorite={id=>setFavoriteIds(ids=>ids.includes(id)?ids.filter(value=>value!==id):[...ids,id])}
            onAdd={addProduct} onRemove={removeProduct} isService={isService} formatMoney={currency} loading={productsQuery.isLoading} error={productsQuery.isError} onRetry={()=>void productsQuery.refetch()} locked={locked}
            canCreate={!!(authUser?.is_superuser || (authUser?.access?.grants.srm?.enabled && authUser.access.grants.srm.actions.includes('create')) || (!authUser?.access?.managed && ['admin','srm_admin','srm_sales_manager','srm_sales_executive'].includes(String(authUser?.role).toLowerCase())))}/>
          : <>

          <div className="srm-pos-stock-summary grid gap-3 md:grid-cols-3">
            <StatusTile label="Products" value={String(storeProducts.length)} detail={`${filteredProducts.length} visible`} />
            <StatusTile label="Low stock" value={String(lowStockCount)} detail="Reorder watch" />
            <StatusTile label="Cart quantity" value={String(totals.qty)} detail={`${cart.length} lines`} />
          </div>
          <div className="srm-pos-mode-summary"><ModePanel mode={mode} customer={customer} /></div>
          <div className="pos-catalog-toolbar flex flex-col gap-3 rounded-2xl border border-white bg-white p-3 shadow-sm md:flex-row md:items-center md:justify-between">
            <div>
              <strong className="text-sm text-slate-950">{presentation.catalogue}</strong>
              <p className="text-xs text-slate-500">{filteredProducts.length} eligible products & services</p>
            </div>
            <details className="pos-catalog-actions"><summary><Plus size={16}/>Add new</summary><div className="flex flex-wrap gap-2">

              {(authUser?.is_superuser || (authUser?.access?.grants.srm?.enabled && authUser.access.grants.srm.actions.includes("create")) || (!authUser?.access?.managed && ["admin", "srm_admin", "srm_sales_manager", "srm_sales_executive"].includes(String(authUser?.role).toLowerCase()))) && <><Button asChild variant="outline"><Link to="/srm/inventory/products?new=item&kind=product"><Plus size={16}/>Add product</Link></Button><Button asChild variant="outline"><Link to="/srm/inventory/products?new=item&kind=service"><Plus size={16}/>Add service</Link></Button></>}
            </div></details>
<details className="pos-catalog-actions"><summary><Settings size={16}/>View &amp; manage</summary><div className="flex flex-wrap gap-2"><Button asChild variant="outline"><Link to="/srm/inventory/products">Manage catalog</Link></Button>              <ViewModeButton active={productView === "tiles"} icon={LayoutGrid} label="Tiles" onClick={() => setProductView("tiles")} />
              <ViewModeButton active={productView === "list"} icon={List} label="List" onClick={() => setProductView("list")} />
              <ViewModeButton active={productView === "details"} icon={Table2} label="Details" onClick={() => setProductView("details")} />
</div></details>
          </div>

          <div className="pos-catalog-search">        <div className="relative">
          <Search className="absolute left-3 top-3 h-5 w-5 text-slate-400" />
          <Input
            ref={searchRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") scanSearch();
            }}
            className="h-11 border-slate-200 bg-slate-50 pl-10 text-base text-slate-950 placeholder:text-slate-400"
            aria-label="Search or scan items"
            placeholder="Search or scan product, SKU, barcode [F2]"
          />
        </div>
</div>
          <div className="flex flex-wrap items-center gap-2" aria-label="Catalogue filters">
{posOfferingTabs.map(tab => <Button key={tab} variant={catalogTab === tab ? "default" : "outline"} size="sm" onClick={() => setCatalogTab(tab)}>{tab} ({storeProducts.filter(p=>matchesOfferingTab(p,tab)).length})</Button>)}
<details className="pos-catalog-actions pos-filter-menu"><summary>Filters{!posOfferingTabs.some(tab=>tab===catalogTab)?` · ${catalogTab}`:''}</summary><div className="flex flex-wrap gap-2">{["Favorites", "Frequently Used", "Recently Used"].map(tab => <Button key={tab} variant={catalogTab === tab ? "default" : "outline"} size="sm" onClick={() => setCatalogTab(tab)}>{tab} ({storeProducts.filter(p => tab === "All" || (tab === "Recently Used" ? recentIds.includes(p.id) : tab === "Favorites" ? favoriteIds.includes(p.id) : tab === "Frequently Used" ? (usageCounts[p.id] || 0)>0 : matchesOfferingTab(p,tab))).length})</Button>)}
            <NativeSelect aria-label="Sort catalogue" className="rounded border p-2 text-sm" value={catalogSort} onChange={e => setCatalogSort(e.target.value)}><option value="name">Name</option><option value="price">Price: low to high</option><option value="frequent">Most used</option></NativeSelect>
</div></details>
          </div>
          <nav className="pos-category-chips" aria-label="Product categories">{categories.map(item => <Button key={item} size="sm" variant={category === item ? "default" : "outline"} onClick={() => setCategory(item)}><LayoutGrid size={15}/>{item === "All" ? "All categories" : item}</Button>)}</nav>
          <div className="pos-catalog-results" role="region" aria-label="Catalogue items" tabIndex={0}>
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
                  <div key={product.id} className={`grid grid-cols-[2fr_1fr_1fr_0.8fr_0.9fr_8rem] items-center border-b border-slate-100 px-3 py-2 text-sm last:border-b-0 ${qty ? "bg-[#f7f4ff]" : "bg-white hover:bg-slate-50"}`}>
                    <button type="button" className="flex min-w-0 items-center gap-2 text-left" onClick={() => addProduct(product)} data-product-id={product.id} disabled={product.checkoutSupported===false || product.trackInventory && product.stock<=0}>
                      <ProductMark product={product} lowStock={lowStock} />
                      <span className="min-w-0">
                        <strong className="block truncate text-slate-950">{product.name}</strong>
                        <span className="block truncate text-xs text-slate-400">{product.barcode}</span>
                      </span>
                    </button>
                    <span className="truncate text-slate-500">{isService(product) ? product.bookingRequired ? "Appointment required" : "Appointment options" : product.sku} · {product.category} · Tax {product.taxRate}% {product.duration}</span>
                    <span className="truncate text-slate-500">{product.category}</span>
                    <span className={lowStock ? "font-medium text-red-600" : "text-slate-600"}>{product.trackInventory ? product.stock : product.kind.replace(/s$/, "")}</span>
                    <strong className="text-[#6d49d7]">{currency(product.rate)}</strong>
                    <POSCatalogueQuantity product={product} quantity={qty} locked={locked} onRemove={() => removeProduct(product.id)} onAdd={() => addProduct(product)} />
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
                  <article key={product.id} data-highlighted={product.id===highlighted} className={`srm-pos-product-list-row pos-catalog-card flex items-center gap-3 rounded-xl border bg-white p-2 shadow-sm transition hover:shadow-md ${qty ? "border-[#6d49d7] ring-2 ring-[#6d49d7]/10" : "border-white"}`}>
                    <button type="button" className="flex min-w-0 flex-1 items-center gap-3 text-left" onClick={() => addProduct(product)} data-product-id={product.id} disabled={product.checkoutSupported===false || product.trackInventory && product.stock<=0}>
                      <ProductMark product={product} lowStock={lowStock} />
                      <span className="min-w-0 flex-1">
                        <strong className="block truncate text-sm text-slate-950">{product.name}</strong>
                        <span className="block truncate text-xs text-slate-400">{isService(product) ? product.bookingRequired ? "Appointment required" : "Appointment options" : product.sku} / {product.category} · Tax {product.taxRate}% {product.duration && `· ${product.duration}`}</span>
                      </span>
                      <span className={`hidden rounded-full px-2 py-1 text-xs md:inline-flex ${lowStock ? "bg-red-50 text-red-600" : "bg-emerald-50 text-emerald-700"}`}>Stock {product.trackInventory ? product.stock : product.kind.replace(/s$/, "")}</span>
                      <strong className="w-24 text-right text-[#6d49d7]">{currency(product.rate)}</strong>
                    </button>
                    <POSCatalogueQuantity product={product} quantity={qty} locked={locked} onRemove={() => removeProduct(product.id)} onAdd={() => addProduct(product)} />
                  </article>
                );
              })}
            </div>
          ) : (
            <div className={`pos-catalog-grid grid gap-2 ${tileDensity === "compact" ? "grid-cols-2 sm:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6" : "grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5"}`}>
              {filteredProducts.map((product) => {
                const qty = cart.filter((line) => line.id === product.id).reduce((sum, line) => sum + line.qty, 0);
                const lowStock = product.trackInventory && product.stock <= product.reorderLevel;
                const ItemIcon = catalogIcon(product.name, product.category, isService(product));
                return (
                  <article key={product.id} className={`pos-catalog-card ${isService(product) ? "pos-service-card" : ""} relative overflow-hidden rounded-xl border bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${qty ? "border-[#6d49d7] ring-2 ring-[#6d49d7]/10" : "border-white"}`}>

                    <button type="button" className="block w-full text-left" onClick={() => addProduct(product)} data-product-id={product.id} disabled={product.checkoutSupported===false || product.trackInventory && product.stock<=0}>
                      <ProductVisual product={product} lowStock={lowStock} density={tileDensity} />
                      <span className="mt-2 block truncate px-2 text-xs font-semibold text-slate-950"><ItemIcon size={21} className="shrink-0 text-violet-700"/>{product.name}</span>
                      <span className="mt-1 block truncate px-2 text-[11px] text-slate-400">{isService(product) ? product.bookingRequired ? "Appointment required" : "Appointment options" : product.sku} · {product.category} · Tax {product.taxRate}% {product.duration}</span>
                      <span className="mt-2 flex items-center justify-between gap-2 px-2 pb-2">
                        <span className="text-xs text-violet-700">{isService(product) ? product.duration : ""}</span>
                        <span className={`rounded-full px-1.5 py-0.5 text-[10px] ${lowStock ? "bg-red-50 text-red-600" : "bg-emerald-50 text-emerald-700"}`}>{product.trackInventory ? `Stock: ${product.stock}` : isService(product) ? `${product.duration || "Service"}${product.bookingRequired ? " · Booking required" : ""}` : product.kind.replace(/s$/, "")}</span>
                      </span>
                    </button>
                    {product.checkoutSupported===false && <p className="px-2 pb-2 text-xs text-red-700">{product.unsupportedReason || 'Unavailable for checkout'}</p>}
                    <Button type="button" variant="outline" size="sm" className="pos-favorite-toggle" aria-label={`Favorite ${product.name}`} aria-pressed={favoriteIds.includes(product.id)} onClick={()=>setFavoriteIds(ids=>ids.includes(product.id)?ids.filter(id=>id!==product.id):[...ids,product.id])}><span aria-hidden="true">{favoriteIds.includes(product.id)?'★':'☆'}</span><span className="sr-only">{favoriteIds.includes(product.id)?'Remove favorite':'Add favorite'}</span></Button>
                    <div className="pos-product-action flex flex-wrap items-center justify-between gap-1 p-3">
                      <strong>{shortCurrency(product.rate)}</strong>
                      <POSCatalogueQuantity product={product} quantity={qty} locked={locked} onRemove={() => removeProduct(product.id)} onAdd={() => addProduct(product)} />
                    </div>
                  </article>
                );
              })}
            </div>
          )}
          </div>
          </>}
        </section>

        <aside className="srm-pos-cart space-y-4 rounded-2xl border border-white/80 bg-white/90 p-4 shadow-sm backdrop-blur">
            <CardHeader className="flex flex-row items-center justify-between">
              <div className="min-w-0"><CardTitle className="text-base">{presentation.bill}</CardTitle><p className="pos-cart-caption">{cart.length} {cart.length === 1 ? "line" : "lines"}{cart.some(line=>!!line.booking) ? ` - ${cart.filter(line=>!!line.booking).length} appointment drafts` : " - Products & services"}</p></div>
              <Button variant="ghost" size="sm" className="text-slate-500 hover:text-slate-950" onClick={() => setConfirmClear(true)} disabled={!cart.length}><Trash2 className="h-4 w-4" />Clear</Button>
            </CardHeader>
<div className="pos-sale-customer"><strong className="text-xs">{term("customer")}</strong>        <div className="min-w-0"><div className="flex gap-2">
          <POSCustomerPicker onOpen={()=>setCustomersRequested(true)} customers={customers} value={customerId} onChange={setCustomerId} loading={customersQuery.isFetching} error={customersQuery.isError}/>
          {customerId>0&&<Button type="button" variant="outline" aria-label="Open customer 360" onClick={()=>setCustomerProfile(true)}>360°</Button>}
          {customerProfile&&customerId>0&&<>{selectedPOS?<POSCustomerProfile id={customerId} onClose={()=>setCustomerProfile(false)}/>:<CompanyProfile id={customerId} source="srm" onClose={()=>setCustomerProfile(false)}/>}</>}
          <Button type="button" variant="outline" className="h-11 shrink-0 border-slate-200 bg-white text-slate-950" disabled={selectedPOS&&!posFeatures?.customers_register} title={selectedPOS?posFeatures?.registration_unavailable_reason||undefined:undefined} onClick={() => setQuickAddOpen(true)}><Plus size={16}/>New {term("customer").toLowerCase()}</Button>
        </div>{selectedPOS && posFeatures?.customers_register===false && <p className="mt-1 text-xs text-slate-600">{posFeatures.registration_unavailable_reason || 'Quick add is unavailable for this register. Choose an existing customer.'}</p>}{customerId===0&&<AnonymousCashSetup enabled={productsQuery.isSuccess || cart.length > 0} canConfigure={!!authUser?.is_superuser||!!(authUser?.access as {isAccessAdmin?:boolean}|undefined)?.isAccessAdmin}/>} {customersQuery.isError && <p role="alert" className="mt-1 text-xs text-red-700">Unable to load customers. <Button variant="outline" type="button" className="underline" onClick={() => void customersQuery.refetch()}>Retry</Button></p>}</div>
<POSCustomerIdentity id={customerId} enabled={selectedPOS} pack={operationalPackKey || profile.business_type}/>

</div>
          <Card ref={cartScrollRef} role="region" tabIndex={0} aria-label={phoneWidth<=767 ? "Sale items, paginated" : "Sale items, scroll for more"} className="pos-cart-items overflow-hidden border-slate-200 bg-white text-slate-950 shadow-sm">

            <CardContent className="space-y-3">

              {cart.length ? cart.map((line,lineIndex) => (
                <div key={line.lineId} id={`pos-line-${line.lineId}`} onFocusCapture={()=>{phonePaginationAnchor.current=line.lineId;}} data-phone-hidden={lineIndex < safePhonePage*phonePageSize || lineIndex >= (safePhonePage+1)*phonePageSize} className={`pos-cart-line ${line.booking ? "has-appointment" : ""} rounded-md border border-slate-200 bg-white p-3 ${line.id===highlighted ? "pos-added" : ""}`}>
                  <div className="pos-compact-cart-row">
                    <button type="button" className="pos-phone-line-icon" aria-label={`Edit ${line.name} discount and note`} onClick={()=>setPhoneLineId(line.lineId)}>{line.image ? <img src={line.image} alt=""/> : isService(line) ? <Stethoscope size={27}/> : <ShoppingBag size={27}/>}</button><div className="pos-line-identity"><strong title={line.name}>{line.name}</strong><small>{isService(line) ? `Service${line.duration ? ` · ${line.duration}` : ''}` : <><span className="pos-desktop-product-prefix">{line.kind.slice(0,-1)} · </span>{line.sku}</>}{line.batchNo ? ` · Batch ${line.batchNo}` : ''}</small></div>
                    <div className="pos-inline-quantity" title={line.booking ? "One appointment per line. Use Add another appointment to book again." : undefined}><Button type="button" size="icon" variant="ghost" aria-label={`Decrease ${line.name} quantity`} disabled={!!line.booking || isCustomerPlan(line)} onClick={()=>line.qty<=1?removeLine(line.lineId):updateLine(line.lineId,{qty:line.qty-1})}><Minus size={14}/></Button><Input disabled={!!line.booking || isCustomerPlan(line)} type="number" aria-label={`Quantity ${line.name}`} min={line.decimalAllowed?'0.001':'1'} step={line.decimalAllowed?'0.001':'1'} value={line.qty} onChange={event=>updateLine(line.lineId,{qty:Math.max(line.decimalAllowed ? 0.001 : 1,Number(event.target.value)||1)})}/><Button type="button" size="icon" variant="ghost" aria-label={`Increase ${line.name} quantity`} disabled={!!line.booking || isCustomerPlan(line) || line.trackInventory && line.qty>=line.stock} onClick={()=>updateLine(line.lineId,{qty:line.qty+1})}><Plus size={14}/></Button></div>
                    <strong className="pos-line-amount">{currency(line.lotAllocation === 'fefo' ? (pricedLines.get(line.lineId) || []).reduce((total, part) => total + lineTotal(part), 0) : lineTotal(line))}</strong>
                    <Button type="button" size="icon" variant="ghost" aria-label={`Remove ${line.name}`} onClick={()=>removeLine(line.lineId)}><X size={16}/></Button>
                  </div>
                  <details className="mt-2"><summary className="cursor-pointer text-xs font-medium">Rate, discount &amp; note</summary><div className="grid grid-cols-2 gap-2 py-2">                    <div className="text-xs text-slate-500">Rate<div>{displayRate(line)}</div></div>
                    <label className="text-xs text-slate-500">Disc %<Input type="number" min="0" max="50" value={line.discount} onChange={(event) => updateLine(line.lineId, { discount: Math.min(50, Math.max(0, Number(event.target.value) || 0)) })} className="mt-1 border-slate-200 bg-slate-50 text-slate-950" /></label>
</div>                  {["Memberships","Subscriptions"].includes(line.kind)&&<label className="mt-2 block text-xs text-slate-500">Plan start date<Input type="date" aria-label={`Plan start date ${line.lineId}`} value={line.planStartDate||""} onChange={event=>updateLine(line.lineId,{planStartDate:event.target.value})} className="mt-1 border-slate-200 bg-slate-50 text-slate-950"/></label>}<label className="mt-2 block text-xs text-slate-500">Line note<Input aria-label={`Line note ${line.lineId}`} value={line.note} onChange={event=>updateLine(line.lineId,{note:event.target.value})} className="mt-1 border-slate-200 bg-slate-50 text-slate-950"/></label>
</details>
                  {isService(line) && line.schedulingConfigured !== false && (!selectedPOS||posFeatures?.appointments_schedule) && <><div className="pos-line-booking mt-3">{line.booking && <BookingSummary start={line.booking.starts_at} minutes={line.booking.duration_minutes} provider={bookingSummaries[line.lineId]?.split(' - ')[0] || `Employee #${line.booking.employee_id}`} zone={bookingSummaries[line.lineId]?.match(/\(([^)]+)\)/)?.[1] || defaultText('timezone','srm') || 'UTC'} resources={bookingSummaries[line.lineId]?.split(' - ').slice(2) || []}/>}<POSServiceScheduling presentation={bookingPresentation==='dialog'?'dialog':'cart'} onResourceCapacities={capacities=>updateLine(line.lineId,{resourceCapacities:capacities})} compactSummary={line.booking ? (phoneWidth<=767 ? 'Edit' : 'Booking details') : requirements[line.lineId] ? 'Choose employee & time' : 'Schedule service (optional)'} productId={line.id} lineKey={line.lineId} value={line.booking} onAvailability={available=>setBookingAvailability(current=>current[line.lineId]===available?current:{...current,[line.lineId]:available})} onSummary={summary=>setBookingSummaries(current=>current[line.lineId]===summary?current:{...current,[line.lineId]:summary})} onChange={booking=>{if(booking && cartBookingConflict(cart,line.lineId,booking,line.resourceCapacities)){toast({title:'Booking conflict',description:'This employee or resource capacity overlaps another booking in this sale.',variant:'destructive'});return;}updateLine(line.lineId,{booking,...(booking?{qty:1}:{})});}} onRequirement={required=>setRequirements(current=>current[line.lineId]===required?current:{...current,[line.lineId]:required})}/></div><Button variant="ghost" size="sm" aria-label="Add another appointment" className="pos-repeat-booking mt-2" onClick={()=>{const next={...line,lineId:randomUUID(),qty:1,booking:undefined};phonePaginationAnchor.current=next.lineId;setPhonePage(Math.floor(cart.length/phonePageSize));setCart(current=>[...current,next]);setMobileView('cart');}}>Add another appointment</Button></>}


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

          <nav className="pos-phone-pagination" data-single-page={phonePages===1} aria-label="Cart pages"><Button variant="outline" aria-label="Previous cart page" disabled={safePhonePage===0} onClick={()=>{phonePaginationAnchor.current=null;setPhonePage(safePhonePage-1);}}><ArrowLeft size={16}/></Button><span role="status">{cart.length ? safePhonePage*phonePageSize+1 : 0}–{Math.min((safePhonePage+1)*phonePageSize,cart.length)} of {cart.length} · {safePhonePage+1}/{phonePages}</span><Button variant="outline" aria-label="Next cart page" disabled={safePhonePage>=phonePages-1} onClick={()=>{phonePaginationAnchor.current=null;setPhonePage(safePhonePage+1);}}><ArrowRight size={16}/></Button></nav>
          <p className="pos-cart-scroll-hint">Scroll for more sale items ↓</p>
          <Card className="pos-bill-summary overflow-hidden border-slate-200 bg-white text-slate-950 shadow-sm">
            <CardContent className="space-y-3 p-4">
              <SummaryLine label="Subtotal" value={currency(totals.subtotal)} />
              <SummaryLine label="Tax" value={currency(totals.tax)} />
              <button className="pos-phone-discounts" type="button" onClick={()=>setPhonePanel("discounts")}><Tag size={15}/>Discounts &amp; Coupons<span>›</span></button><details className="pos-desktop-discounts"><summary>Tax, discounts &amp; coupon</summary><div className="space-y-3 py-2">
              <SummaryLine label="Line discount" value={currency(totals.lineDiscount)} />
              <div className="grid grid-cols-[1fr_8rem] items-center gap-3 text-sm">
                <span className="text-slate-500">Bill discount</span>
                <Input aria-label="Bill discount" type="number" min="0" value={billDiscount} onChange={(event) => setBillDiscount(Number(event.target.value) || 0)} className="border-slate-200 bg-slate-50 text-right text-slate-950" />
              </div>
              <div className="grid grid-cols-[1fr_8rem] items-center gap-3 text-sm">
                <span className="text-slate-500">Coupon</span>
                <Input aria-label="Coupon code" value={coupon} onChange={(event) => setCoupon(event.target.value)} placeholder="WELCOME10" className="border-slate-200 bg-slate-50 text-slate-950" />
              </div>
              <SummaryLine label="Coupon discount" value={currency(totals.couponDiscount)} />
              <SummaryLine label="Taxable" value={currency(totals.taxable)} />
              <SummaryLine label="Tax" value={currency(totals.tax)} />
              <SummaryLine label="Round off" value={currency(totals.roundOff)} />
              </div></details>
              <div className="pos-payable-panel rounded-md bg-[#6d49d7] p-4 text-white">
                <span className="block text-xs font-semibold uppercase">Amount payable</span>
                <strong className="text-3xl">{currency(totals.grandTotal)}</strong>
              </div>
<details className="pos-extra-bill"><summary>Sale note &amp; actions</summary>              <Input aria-label="Sale note" value={note} onChange={(event) => setNote(event.target.value)} placeholder="Bill note / delivery instruction" className="border-slate-200 bg-slate-50 text-slate-950" />
              <div className="grid grid-cols-2 gap-2">
                <Button variant="outline" className="border-slate-200 text-slate-700" disabled={selectedPOS || !cart.length} title={selectedPOS?"Held bills are not integrated in this Business Pack POS yet":undefined} onClick={holdCart}><PauseCircle className="h-4 w-4" />Hold</Button>
                <Button variant="outline" onClick={()=>setReadinessOpen(value=>!value)}>Review bill</Button>
              </div>
</details>            </CardContent>
          </Card>
      <footer ref={checkoutFooterRef} className="srm-pos-checkout sticky bottom-0 grid gap-2 border-t border-slate-200 bg-white p-3 shadow-[0_-8px_20px_rgba(15,23,42,0.06)] md:grid-cols-[repeat(3,1fr)_auto_auto_auto] md:items-center">
        <p id="pos-checkout-reason" className="pos-checkout-reason" data-blocked={!online||locked||readiness.length>0} role="status">{!online ? 'Reconnect before collecting payment.' : locked ? 'Finish or recover the pending checkout before starting another.' : !cart.length ? 'Add a product or service to start a sale.' : readiness[0]?.text || 'Ready to collect payment.'}</p>
        <div className="pos-tender-shortcuts">{(["Cash", "UPI", "Card", "Split"] as PaymentMode[]).map(method => <Button key={method} variant="outline" disabled={!cart.length || locked || !online} onClick={() => openPayment(method)}>{method === "Cash" ? <Banknote size={16}/> : method === "Split" ? <Split size={16}/> : method === "UPI" ? <svg className="pos-upi-icon" width="20" height="22" viewBox="0 0 20 24" aria-hidden="true"><path fill="#f28b13" d="M8 1 18 12 2 23Z"/><path fill="#15944c" d="m12 1 8 11-14 11Z"/></svg> : <CreditCard size={16}/>} {method}</Button>)}</div>
        <FooterMetric label="Items" value={String(cart.length)} />
        <FooterMetric label="Quantity" value={String(totals.qty)} />
        <FooterMetric label="Payable" value={operationalPackKey === "pharma" && cart.some(line => line.lotAllocation === "fefo") && !Number.isInteger(totals.grandTotal) ? currency(totals.grandTotal) : shortCurrency(totals.grandTotal)} />
        <Button variant="outline" className="border-slate-200 text-slate-700" disabled={selectedPOS} title={selectedPOS?"Held bills are not integrated in this Business Pack POS yet":undefined} onClick={() => setActiveModal("held")}><RotateCcw className="h-4 w-4" />Recall</Button>
        <Button variant="outline" className="border-slate-200 text-slate-700" disabled={!sales.some(sale=>!!sale.checkoutId) && !lastSale?.checkoutId} onClick={() => printReceipt()}><Printer className="h-4 w-4" />Print Last</Button>
        <Button className="bg-[#6d49d7] text-white hover:bg-[#5934bd]" aria-describedby="pos-checkout-reason" disabled={!cart.length || locked || !online} onClick={() => openPayment("Cash")}><CreditCard className="h-4 w-4" />{cart.some(line => !!line.booking) ? `Collect ${currency(totals.grandTotal)} & Book` : `Collect ${currency(totals.grandTotal)}`}<ArrowRight className="pos-collect-arrow" size={21}/></Button>
      </footer>
        </aside>
      </main>



      {phoneLine && <Overlay title={`Edit ${phoneLine.name}`} onClose={()=>setPhoneLineId(null)}><div className="space-y-3"><div>Rate<div>{displayRate(phoneLine)}</div></div><label className="block">Discount %<Input type="number" min="0" max="50" value={phoneLine.discount} onChange={event=>updateLine(phoneLine.lineId,{discount:Math.min(50,Math.max(0,Number(event.target.value)||0))})}/></label><label className="block">Line note<Input value={phoneLine.note} onChange={event=>updateLine(phoneLine.lineId,{note:event.target.value})}/></label>{phoneLine.booking&&<p>Quantity is fixed at one per appointment. Use Add another appointment for a second booking.</p>}<Button onClick={()=>setPhoneLineId(null)}>Done</Button></div></Overlay>}
      {phonePanel && <Overlay title={phonePanel==='sessions'?'Register session':phonePanel==='actions'?'POS actions':phonePanel==='customer'?'Sale customer':'Discounts & coupons'} onClose={()=>setPhonePanel(null)}>
        {phonePanel==='sessions' && <div className="pos-phone-session space-y-3"><p>{branchName} · {register?.register_name || activeStoreProfile.register}</p><p>Cashier: {cashierName}</p>{register?.id?<><p>Session {register.session_number || register.id} · Open</p><p>Opening cash {currency(Number(register.opening_cash||0))}</p><Button variant="outline" onClick={()=>{setPhonePanel(null);setActiveModal('cash');}}>Cash drawer</Button><Button variant="outline" onClick={()=>{setPhonePanel(null);setActiveModal('close');}}>Close session</Button></>:<form className="space-y-3" onSubmit={event=>{event.preventDefault();void openRegister();}}><p className="text-sm">Open the register before collecting payment.</p><label className="block text-sm">Opening cash<Input aria-label="Mobile POS opening cash" required type="number" min="0" step="0.01" value={openingCash} onChange={event=>setOpeningCash(event.target.value)}/></label><Button type="submit" disabled={locked||opening||!online||activeRegister.isPending||activeRegister.isFetching}>{opening?'Opening register…':'Open POS register'}</Button></form>}{activeRegister.isError&&<Button variant="outline" onClick={()=>void activeRegister.refetch()}>Reload POS register</Button>}</div>}
        {phonePanel==='actions' && <div className="grid grid-cols-2 gap-3"><Button onClick={()=>setPhonePanel("customer")}>Sale customer</Button><Button onClick={()=>{setPhonePanel(null);setActiveModal('cash');}}>Cash drawer</Button><Button onClick={()=>{setPhonePanel(null);setActiveModal('profile');}}>Register settings</Button><Button disabled={!lastSale?.checkoutId&&!sales.some(sale=>!!sale.checkoutId)} onClick={()=>printReceipt()}>Print last receipt</Button><Button disabled={selectedPOS} onClick={()=>{setPhonePanel(null);setActiveModal('held');}}>Recall held bill</Button><Button onClick={()=>{setPhonePanel(null);setReadinessOpen(true);}}>Review bill</Button><Button disabled={!cart.length} onClick={()=>{setPhonePanel(null);setConfirmClear(true);}}>Clear bill</Button></div>}
        {phonePanel==='customer' && <div className="space-y-3"><POSCustomerPicker onOpen={()=>setCustomersRequested(true)} customers={customers} value={customerId} onChange={setCustomerId} loading={customersQuery.isFetching} error={customersQuery.isError}/><POSCustomerIdentity id={customerId} enabled={selectedPOS} pack={operationalPackKey || profile.business_type}/><Button disabled={selectedPOS&&!posFeatures?.customers_register} onClick={()=>{setPhonePanel(null);setQuickAddOpen(true);}}>New customer</Button><Button variant="outline" onClick={()=>setPhonePanel(null)}>Done</Button></div>}
        {phonePanel==='discounts' && <div className="space-y-4"><label className="block">Bill discount<Input aria-label="Mobile bill discount" type="number" min="0" value={billDiscount} onChange={event=>setBillDiscount(Math.max(0,Number(event.target.value)||0))}/></label><label className="block">Coupon code<Input aria-label="Mobile coupon code" value={coupon} onChange={event=>setCoupon(event.target.value)}/></label><SummaryLine label="Discount" value={currency(totals.lineDiscount+totals.couponDiscount)}/><SummaryLine label="Amount payable" value={currency(totals.grandTotal)}/><Button onClick={()=>setPhonePanel(null)}>Apply & close</Button></div>}
      </Overlay>}
      {quickAddOpen && (selectedPOS&&posFeatures?<POSQuickAddCustomer features={posFeatures} onClose={()=>setQuickAddOpen(false)} onCreated={customerCreated}/>:!selectedPOS?<QuickAddCustomer onClose={() => setQuickAddOpen(false)} onCreated={customerCreated}/>:null)}
      {activeModal === "payment" ? (
        <Overlay title="Complete Payment" onClose={() => {if(!nativeBusy)setActiveModal(null);}} wide>
          <div className="pos-payment-layout grid gap-4 lg:grid-cols-[1fr_20rem]">
            <div className="space-y-4">
              <div className="space-y-3 rounded-lg bg-background p-3 text-foreground">
                <>{selectedPOS&&<p className="text-sm text-muted-foreground">For follow-up reminders, open the customer record. Items requiring follow-ups must use a supported checkout workflow.</p>}</><div className="flex flex-wrap items-end gap-2"><label className="flex-1 text-xs">Customer for this sale<NativeSelect loading={customersQuery.isFetching} error={customersQuery.isError} aria-label="Follow-up customer" className="block w-full rounded border bg-background p-2 text-foreground" value={customerId || ""} onChange={e => setCustomerId(Number(e.target.value))}><option value="">Walk-in — select a customer to schedule</option>{customers.filter(c => c.id).map(c => <option key={c.id} value={c.id}>{c.name}{c.phone ? ` · ${c.phone}` : ""}</option>)}</NativeSelect></label><Button type="button" variant="outline" disabled={selectedPOS&&!posFeatures?.customers_register} title={selectedPOS?posFeatures?.registration_unavailable_reason||undefined:undefined} onClick={() => setQuickAddOpen(true)}><Plus size={16}/>Quick add customer</Button></div>
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
                    setPaymentRows(item === "Split" ? [{ id: randomUUID(), mode: "Cash", amount: totals.grandTotal, reference: "" }] : [{ id: randomUUID(), mode: item === "Credit" ? "Credit" : item, amount: item === "Credit" ? 0 : totals.grandTotal, reference: "" }]);
                  }} className={`rounded-md px-3 py-2 text-sm font-medium ${paymentMode === item ? "bg-amber-500 text-slate-950" : "bg-white/5 text-slate-200 hover:bg-white/10"}`}>
                    {item}
                  </button>
                ))}
              </div>
              <div className="space-y-2">
                {paymentRows.map((row) => (
                  <div key={row.id} className="grid gap-2 rounded-lg border border-white/10 bg-slate-950 p-2 md:grid-cols-[10rem_1fr_1fr_auto]">
                    <Select value={row.mode} onValueChange={(value) => setPaymentRows((current) => current.map((item) => item.id === row.id ? { ...item, mode: value as PaymentRow["mode"] } : item))}>
                      <SelectTrigger aria-label="Payment method" className="border-white/15 bg-slate-900 text-white"><SelectValue /></SelectTrigger>
                      <SelectContent>{rowModes.filter(item=>item!=="Wallet").map((item) => <SelectItem key={item} value={item}>{item}</SelectItem>)}</SelectContent>
                    </Select>
                    <Input aria-label="Payment amount" type="number" min="0" value={row.amount} onChange={(event) => setPaymentRows((current) => current.map((item) => item.id === row.id ? { ...item, amount: Number(event.target.value) || 0 } : item))} className="border-white/15 bg-slate-900 text-white" />
                    <Input aria-label="Payment reference" value={row.reference} onChange={(event) => setPaymentRows((current) => current.map((item) => item.id === row.id ? { ...item, reference: event.target.value } : item))} placeholder="Reference" className="border-white/15 bg-slate-900 text-white" />
                    <Button size="icon" variant="ghost" className="text-slate-300 hover:bg-white/10 hover:text-white" aria-label="Remove payment method" onClick={() => setPaymentRows((current) => current.filter((item) => item.id !== row.id))}><X className="h-4 w-4" /></Button>
                  </div>
                ))}
              </div>
              <Button variant="outline" className="border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={() => { setPaymentMode("Split"); setPaymentRows((current) => [...current, { id: randomUUID(), mode: "Cash", amount: 0, reference: "" }]); }}><Plus className="h-4 w-4" />Add payment mode</Button>
            </div>
            <div className="pos-payment-summary space-y-3 rounded-lg bg-slate-950 p-4">
              {paymentError && <p role="alert" className="rounded border border-red-400 p-2 text-sm text-red-200">{paymentError}</p>}
              <SummaryLine label="Amount received" value={currency(received)} />
              <SummaryLine label="Balance due" value={currency(balanceDue)} />
              <SummaryLine label="Change due" value={currency(changeDue)} />
              {paymentMode==="Split"&&explicitCredit>0&&<SummaryLine label="Explicit credit balance" value={currency(explicitCredit)}/>}
              <p className="text-xs text-slate-300">{paymentMode==='Credit' ? 'Save this invoice as unpaid for the selected customer.' : paymentMode==='Split' ? 'Combine supported methods. Only cash can include change.' : 'Confirm the amount received before completing the sale.'}</p>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={printAfterSale} onChange={event=>setPrintAfterSale(event.target.checked)}/>Print receipt after checkout</label>
              <Button disabled={nativeBusy || locked || !online} className="w-full bg-emerald-500 text-slate-950 hover:bg-emerald-400" onClick={() => completeSale(printAfterSale?'print':'done')}>{nativeBusy?'Processing...':'Complete Sale'}</Button>
              <p className="text-xs text-slate-300">Download and sharing options appear after confirmation.</p>




            </div>
          </div>
          <div className="pos-payment-mobile-footer space-y-2 border-t border-white/20 bg-slate-950 p-3">
            <div className="flex justify-between gap-2 text-sm"><strong>Total {currency(totals.grandTotal)}</strong><span>{changeDue>0 ? `Change ${currency(changeDue)}` : `Balance ${currency(balanceDue)}`}</span></div>
            {paymentError && <p role="alert" className="text-sm text-red-200">{paymentError}</p>}
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={printAfterSale} onChange={event=>setPrintAfterSale(event.target.checked)}/>Print receipt after checkout</label>
            <Button disabled={nativeBusy || locked || !online} className="w-full" onClick={()=>completeSale(printAfterSale?'print':'done')}>{nativeBusy?'Processing...':'Complete Sale'}</Button>
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
            {lastSale.checkoutId && <section className="pos-confirmed-sale" aria-label="Confirmed sale summary"><dl><div><dt>Invoice</dt><dd>{lastSale.invoiceNo}</dd></div><div><dt>Paid</dt><dd>{currency(Number(lastSale.paid))}</dd></div><div><dt>Remaining balance</dt><dd>{currency(Number(lastSale.balance))}</dd></div><div><dt>Receipt numbers</dt><dd>{lastSale.receiptNumbers?.join(', ') || 'No payment received'}</dd></div></dl>{lastSale.hasBookings && <><p role="status">Appointments confirmed with this sale.</p><ul>{lastSale.lines?.filter(line=>line.appointment).map((line,index)=><li key={index}><strong>{line.name}</strong> · {line.appointment}</li>)}</ul><Button variant="outline" onClick={()=>navigate('/srm/appointments')}>View confirmed appointments</Button></>}</section>}
            {lastSale.checkoutId&&<details className="mt-4 rounded-lg bg-card p-3 text-left text-foreground"><summary>Payment details &amp; adjustments</summary><ServiceCheckoutBillingPanel checkoutId={lastSale.checkoutId} canCollect={!!paymentCaps.data?.collect} onChanged={()=>{const id=lastSale.checkoutId;void api.get<NativeCheckoutResult>(`/srm/service-checkout/${id}`).then(({data})=>{if(owns())setLastSale(current=>current&&current.checkoutId===id?{...current,paid:data.invoice.paid,balance:data.invoice.balance,receiptNumbers:data.receipts.map(row=>row.number)}:current);}).catch(error=>{if(owns())toast({title:"Checkout refresh failed",description:dealError(error),variant:"destructive"});});void activeRegister.refetch();}}/>{paymentCaps.isError&&<p role="alert">Payment permissions could not load. <Button variant="outline" onClick={()=>void paymentCaps.refetch()}>Reload payment permissions</Button></p>}</details>}
            {lastSale.checkoutId&&operationalPackKey==='retail'&&posFeatures&&'retail_returns' in posFeatures&&posFeatures.retail_returns===true&&<RetailReturnPanel checkoutId={lastSale.checkoutId} sessionId={register?.id||null} onChanged={()=>{void productsQuery.refetch();void activeRegister.refetch();}}/>}
            {!lastSale.checkoutId&&<p className="mt-2 text-xs text-slate-400">Sales order reference. Payment is not confirmed for this older sale.</p>}
            <div className="mt-5 grid gap-2 md:grid-cols-2">
              <Button disabled={!lastSale?.checkoutId} onClick={() => printReceipt(lastSale)}><Printer className="h-4 w-4" />Print Receipt</Button>
              <Button disabled={!lastSale?.checkoutId} variant="outline" onClick={()=>downloadReceipt(lastSale!)}>Download receipt</Button>
              <Button disabled={!lastSale?.checkoutId} variant="outline" onClick={()=>void shareReceipt(lastSale!)}>Share receipt</Button>
              <Button variant="outline" className="border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={() => {setActiveModal(null);setReadinessOpen(false);setScanFeedback('');setMobileView('products');searchRef.current?.focus();}}>New Sale</Button>
              {shareNotice && <p role="status">{shareNotice}</p>}
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
              const fresh=await api.get<unknown>(recovery.pending?'/srm/pos/sessions':'/srm/pos/sessions/active',{_recordSyncBypass:true,headers:{'Cache-Control':'no-cache, no-store'},params:{_cash_intent_probe:randomUUID()}});
              const summary=fresh.data as {session?:{id?:number};cash_intent_version?:number};
              const supported=recovery.pending?Array.isArray(fresh.data)&&fresh.data.some(item=>item?.cash_intent_version===119):summary?.session?.id===sessionId&&summary?.cash_intent_version===119;
              if(!owns()||financialIntentKey('cash_movement',sessionId)!==key||!supported)throw new Error('Cash movement recovery is unavailable in this context. Reload after the server update before collecting cash.');
              if(recovery.pending){const current=readFinancialIntent<CashIntent>(key);if(!current.pending||JSON.stringify(current.payload)!==JSON.stringify(pending))throw new Error('Cash recovery storage changed. Retry before submitting another cash movement.');}
              else if(findPendingCashIntent<CashIntent>().pending)throw new Error('A prior cash movement is awaiting recovery. Save again to recover it first.');
              const payload=recovery.pending?pending!:{session_id:sessionId,movement_type:row.type==='Withdrawal'?'cash_out':'cash_in',amount:row.amount.toFixed(2),reason:row.reason,request_key:randomUUID()};
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
        <Overlay title="POS Settings & Layout" onClose={() => setActiveModal(null)} wide>
          <ProfileSettingsPanel
            activeProfile={activeStoreProfile}
            profiles={posStoreProfiles}
            tileDensity={tileDensity}
            onProfileChange={switchProfile}
            onDensityChange={setTileDensity}
            bookingPresentation={bookingPresentation}
            onBookingPresentationChange={setBookingPresentation}
          />
        </Overlay>
      ) : null}

      {activeModal === "close" ? (
        <Overlay title="Close POS Session" onClose={() => setActiveModal(null)}>
          <div className="space-y-3">
            <SummaryLine label="Opening cash" value={register?currency(Number(register.opening_cash||0)):"No open register"} />
            <SummaryLine label="Cash received" value={registerCashDisplay(activeRegister.isFetching,activeRegister.isError,cashReceived,currency)} />
            <SummaryLine label="Expected closing cash" value={registerCashDisplay(activeRegister.isFetching,activeRegister.isError,expectedCash,currency)} />
            <label className="block text-sm text-slate-400">Actual counted cash<Input value={closingCash} onChange={(event) => setClosingCash(event.target.value)} type="number" className="mt-1 border-white/15 bg-slate-950 text-white" /></label>
            {registerCashReady && Number.isFinite(countedClosingCash) && countedClosingCash >= 0 ? <SummaryLine label="Cash variance" value={currency(countedClosingCash - expectedCash)} /> : null}
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
    <POSReceipt sale={printSale}/>
    {confirmClear && <Overlay title="Clear this bill?" onClose={()=>setConfirmClear(false)}><p className="mb-4">Remove {cart.length} items from the current bill? You can undo this before checkout.</p><div className="flex gap-2"><Button variant="outline" onClick={()=>setConfirmClear(false)}>Keep bill</Button><Button variant="destructive" onClick={()=>{setUndo({lines:cart,message:'Bill cleared',customerId});setCart([]);setCustomerId(0);setCustomerProfile(false);setConfirmClear(false);}}>Clear bill</Button></div></Overlay>}
    {nativeBusy && !uncertain && <section className="fixed inset-x-3 bottom-24 z-[100] rounded border bg-card p-4" role="status">Processing checkout. Please wait; do not start another payment.</section>}
    {opaqueLock && <section className="fixed inset-x-3 bottom-20 z-[100] rounded-lg border bg-card p-4" role="alert">An unresolved checkout requires reconciliation. New checkout is locked; recovery details are unavailable.</section>}
    {uncertain && <section className="fixed inset-x-3 bottom-20 z-[100] space-y-2 rounded-lg border bg-card p-4 shadow-lg" aria-label="Unresolved POS checkout"><p role="status">{nativeBusy ? "Processing saved checkout. Please wait for confirmation before taking another payment." : "Checkout outcome is unresolved. This basket is frozen. Retry the exact saved checkout before starting another transaction; missing records alone do not prove rejection."}</p>{nativeError&&<p role="alert">{nativeError}</p>}<Button disabled={nativeBusy || !canReplay} onClick={()=>void submitNative(uncertainty.current!,true)}>{nativeBusy?'Confirming checkout...':'Retry same checkout'}</Button>{!canReplay && <Button variant="outline" disabled={recoveryAuthority.isFetching} onClick={()=>void recoveryAuthority.refetch()}>Reload checkout permissions</Button>}</section>}
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
      className={active ? "h-8 bg-[#6d49d7] px-2.5 text-white hover:bg-[#5934bd]" : "h-8 border-slate-200 bg-white px-2.5 text-slate-700 hover:bg-slate-50"}
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

function ProductVisual({ product, lowStock, density }: { product: Product; lowStock: boolean; density: "comfortable" | "compact" }) {
  const tone: Record<string, string> = {
    General: "from-indigo-100 to-blue-50 text-indigo-600",
    Stationery: "from-amber-100 to-orange-50 text-amber-700",
    "Office Supplies": "from-emerald-100 to-teal-50 text-emerald-700",
    Electronics: "from-sky-100 to-cyan-50 text-sky-700",
    Pharmacy: "from-rose-100 to-red-50 text-rose-700",
    Garments: "from-violet-100 to-fuchsia-50 text-violet-700",
  };
  const Icon = catalogIcon(product.name, product.category, isService(product));
  return (
    <span className={`pos-product-visual ${isService(product) ? "is-service" : ""} relative flex ${density === "compact" ? "h-14" : "h-20"} items-center justify-center bg-gradient-to-br ${tone[product.category] || "from-slate-100 to-slate-50 text-slate-600"}`}>
      {lowStock ? <span className="absolute right-1.5 top-1.5 rounded-full bg-red-500 px-1.5 py-0.5 text-[10px] font-semibold text-white">Low</span> : null}
      {product.image ? <img src={product.image} alt={product.name} className="h-full w-full object-cover" referrerPolicy="no-referrer" /> : <span className={`${density === "compact" ? "h-9 w-9 text-sm" : "h-12 w-12 text-base"} flex items-center justify-center rounded-full border border-white/80 bg-white/80 font-bold shadow-sm`}><Icon size={density === "compact" ? 24 : 36} aria-hidden="true"/></span>}
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
  const returnFocus=useRef<HTMLElement | null>(document.activeElement instanceof HTMLElement?document.activeElement:null);
  const [dialog, setDialog] = useState<HTMLDivElement | null>(null);
  useLayoutEffect(() => {
    const viewport = window.visualViewport;
    if (!dialog || !viewport) return;
    const updateViewport = () => {
      dialog.style.setProperty('--pos-visible-height', `${viewport.height}px`);
      dialog.style.setProperty('--pos-keyboard-offset', `${Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop)}px`);
    };
    updateViewport();
    viewport.addEventListener('resize', updateViewport);
    viewport.addEventListener('scroll', updateViewport);
    return () => {
      viewport.removeEventListener('resize', updateViewport);
      viewport.removeEventListener('scroll', updateViewport);
    };
  }, [dialog]);
  return (
    <Dialog.Root open onOpenChange={open => { if (!open) onClose(); }}><Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-50 bg-black/70" />
      <Dialog.Content ref={setDialog} onCloseAutoFocus={event=>{event.preventDefault();if(returnFocus.current?.isConnected)returnFocus.current.focus();else document.querySelector<HTMLInputElement>('[aria-label="Search or scan items"]')?.focus();}} aria-describedby={undefined} className={`srm-pos-dialog fixed left-1/2 top-1/2 z-50 max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] -translate-x-1/2 -translate-y-1/2 overflow-auto rounded-lg border border-white/10 bg-slate-900 p-4 text-slate-100 shadow-2xl ${wide ? "max-w-5xl" : "max-w-2xl"}`}>
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
  bookingPresentation,
  onBookingPresentationChange,
}: {
  activeProfile: PosStoreProfile;
  profiles: PosStoreProfile[];
  tileDensity: "comfortable" | "compact";
  onProfileChange: (profileId: string) => void;
  onDensityChange: (density: "comfortable" | "compact") => void;
  bookingPresentation:POSBookingPresentation;
  onBookingPresentationChange:(value:POSBookingPresentation)=>void;
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
          <POSBookingSettings value={bookingPresentation} onChange={onBookingPresentationChange}/>
          <span className="mt-4 block text-xs uppercase text-slate-400">Cashier layout</span>
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
