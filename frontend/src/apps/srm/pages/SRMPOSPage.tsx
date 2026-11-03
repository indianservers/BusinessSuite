import CompactActions from "@/components/actions/CompactActions";
import { NativeSelect } from "@/components/ui/native-select";
import { api } from "@/services/api";
import QuickAddCustomer, { type PosCustomerRecord } from "../components/QuickAddCustomer";
import { ScheduleFields, defaultSchedule, type Schedule } from "@/shared/follow-ups/ScheduleFields";
import { RichTextContent } from "@/components/rich-text/RichTextContent";
import { useEffect, useMemo, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import "./srm-pos-mobile.css";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
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
  followUp?: Schedule;
  kind: string;
  duration?: string;
  active?: boolean;
  batchTracking?: boolean;
  serialTracking?: boolean;
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
  qty: number;
  discount: number;
  note: string;
  batchNo?: string;
  serialNo?: string;
};

type HeldBill = {
  id: string | number;
  holdNo: string;
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
};

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
    kind: String(item.product_type === "service" ? "Services" : item.product_type === "package" ? "Packages" : "Products"),
    duration: String((item.metadata_json as Record<string, unknown> | undefined)?.duration || ""),
    active: item.active !== false,
    sku: String(item.sku || ""),
    barcode: String(item.barcode || item.sku || ""),
    category: String(item.category_name || (item.category as SRMRecord | undefined)?.category_name || "General"),
    rate: recordNumber(item.sales_rate),
    mrp: recordNumber(item.mrp, recordNumber(item.sales_rate)),
    taxRate: recordNumber(item.gst_rate),
    stock: recordNumber(item.current_quantity),
    reorderLevel: recordNumber(item.reorder_level),
    trackInventory: item.track_inventory !== false,
    batchTracking: Boolean(item.batch_tracking),
    serialTracking: Boolean(item.serial_tracking),
    decimalAllowed: String(item.unit_code || "").toUpperCase() !== "PCS",
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
    lineId: uid("line"),
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

export default function SRMPOSPage() {
  const queryClient = useQueryClient();
  useSrmRealtimeInvalidation(queryClient);
  const [activeProfileId, setActiveProfileId] = usePersistedState("business-suite-srm-pos-profile", defaultStoreProfile.id);
  const [tileDensity, setTileDensity] = usePersistedState<"comfortable" | "compact">("business-suite-srm-pos-density", "comfortable");
  const [productView, setProductView] = usePersistedState<ProductViewMode>("business-suite-srm-pos-product-view", "tiles");
  const activeStoreProfile = useMemo(() => posStoreProfiles.find((profile) => profile.id === activeProfileId) || defaultStoreProfile, [activeProfileId]);
  const mode = activeStoreProfile.mode;
  const [customerId, setCustomerId] = useState(0);
  const [quickAddOpen, setQuickAddOpen] = useState(false);
  const customersQuery = useQuery<Customer[]>({ queryKey: ["srm", "posCustomers"], queryFn: async () => {
    const items: Customer[] = [];
    let after: number | null = 0;
    while (after !== null) {
      const { data }: { data: { items: PosCustomerRecord[]; next: number | null } } = await api.get("/srm/business/customers", { params: { after }, progress: false });
      items.push(...data.items.map(savedCustomer));
      after = data.next;
    }
    return items;
  } });
  const customers = [walkInCustomer, ...(customersQuery.data || [])];
  function customerCreated(record: PosCustomerRecord) {
    queryClient.setQueryData<Customer[]>(["srm", "posCustomers"], current => [...(current || []).filter(c => c.id !== record.id), savedCustomer(record)]);
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
  const [cart, setCart] = usePersistedState<CartLine[]>("business-suite-srm-pos-cart", []);
  const [localHeldBills, setLocalHeldBills] = usePersistedState<HeldBill[]>("business-suite-srm-pos-held", []);
  const [sales, setSales] = usePersistedState<Sale[]>("business-suite-srm-pos-sales", []);
  const [billDiscount, setBillDiscount] = useState(0);
  const [coupon, setCoupon] = useState("");
  const [note, setNote] = useState("");
  const [activeModal, setActiveModal] = useState<"payment" | "held" | "success" | "close" | "cash" | "profile" | null>(null);
  const [paymentMode, setPaymentMode] = useState<PaymentMode>("Cash");
  const [paymentRows, setPaymentRows] = useState<PaymentRow[]>([]);
  const [lastSale, setLastSale] = useState<Sale | null>(null);
  const [closingCash, setClosingCash] = useState("");
  const [cashMovements, setCashMovements] = usePersistedState<{ id: string; type: string; amount: number; reason: string; createdAt: string }[]>("business-suite-srm-pos-cash", []);
  const searchRef = useRef<HTMLInputElement>(null);
  const productsQuery = useQuery({ queryKey: ["srm", "inventoryItems", "pos"], queryFn: async () => {
    const items:SRMRecord[]=[];let page=1,total=Infinity;
    while(items.length<total){const response=await api.get("/srm/inventory/items",{params:{page,per_page:200},progress:false});items.push(...response.data.items);total=response.data.total;if(!response.data.items.length)break;page++;}
    return {items,total};
  }, refetchInterval: 30000, refetchIntervalInBackground: true, refetchOnWindowFocus: true });
  const heldBillsQuery = useQuery({ queryKey: ["srm", "posHeldBills"], queryFn: () => srmApi.posHeldBills(), refetchInterval: 5000, refetchIntervalInBackground: true, refetchOnWindowFocus: true });

  const followUpOptions = useQuery({queryKey:["follow-up-options"],queryFn:()=>api.get("/follow-ups/options").then(r=>r.data)});
  const [checkoutKey, setCheckoutKey] = useState(() => crypto.randomUUID());
  const checkoutBusy = useRef(false);
  const customer = customers.find((item) => item.id === customerId) || customers[0];
  const serverHeldBills = useMemo(() => listItems(heldBillsQuery.data).map(heldBillFromRecord), [heldBillsQuery.data]);
  const heldBills = useMemo(() => [...serverHeldBills, ...localHeldBills], [localHeldBills, serverHeldBills]);
  const dbProducts = useMemo(() => listItems(productsQuery.data).map(productFromRecord).filter((item) => item.active !== false), [productsQuery.data]);
  const productSource = dbProducts;
  const storeProducts = productSource;
  const [catalogTab, setCatalogTab] = useState("All");
  const [catalogSort, setCatalogSort] = useState("name");
  const [recentIds, setRecentIds] = usePersistedState<number[]>("pos-recent-catalog", []);
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
    const grandTotal = Math.max(Math.round(unrounded), 0);
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
    };
  }, [billDiscount, cart, couponDiscount]);

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
  const expectedCash = 5000 + sales.filter((sale) => sale.mode === "Cash" || sale.mode === "Split").reduce((sum, sale) => sum + sale.amount, 0) - cashMovements.filter((row) => row.type === "Withdrawal").reduce((sum, row) => sum + row.amount, 0);
  const lowStockCount = storeProducts.filter((product) => product.trackInventory && product.stock <= product.reorderLevel).length;

  function addProduct(product: Product) {
    setRecentIds(current => [product.id, ...current.filter(id => id !== product.id)].slice(0, 50));
    if (product.trackInventory && product.stock <= 0) {
      toast({ title: "Out of stock", description: `${product.name} cannot be added.` });
      return;
    }
    setCart((current) => {
      const existing = current.find((line) => line.id === product.id && !line.serialTracking);
      if (!existing) return [...current, buildCartLine(product)];
      return current.map((line) => line.lineId === existing.lineId ? { ...line, qty: line.trackInventory ? Math.min(line.stock, line.qty + 1) : line.qty + 1 } : line);
    });
  }

  function removeProduct(productId: number) {
    setCart((current) => {
      const existing = current.find((line) => line.id === productId);
      if (!existing) return current;
      if (existing.qty <= 1) return current.filter((line) => line.lineId !== existing.lineId);
      return current.map((line) => line.lineId === existing.lineId ? { ...line, qty: line.qty - 1 } : line);
    });
  }

  function updateLine(lineId: string, patch: Partial<CartLine>) {
    setCart((current) => current.map((line) => line.lineId === lineId ? { ...line, ...patch } : line));
  }

  function switchProfile(profileId: string) {
    if (profileId === activeStoreProfile.id) return;
    if (cart.length) {
      toast({ title: "Clear cart before changing template", description: "Template changes are locked while a bill is active." });
      return;
    }
    setActiveProfileId(profileId);
    setCategory("All");
  }

  function openPayment(nextMode: PaymentMode = "Cash") {
    if (!cart.length) {
      toast({ title: "Cart is empty", description: "Scan or select an item before checkout." });
      return;
    }
    setPaymentMode(nextMode);
    setPaymentRows(nextMode === "Split"
      ? [{ id: uid("pay"), mode: "Cash", amount: totals.grandTotal, reference: "" }]
      : [{ id: uid("pay"), mode: nextMode === "Credit" ? "Credit" : nextMode, amount: nextMode === "Credit" ? 0 : totals.grandTotal, reference: "" }]);
    setActiveModal("payment");
  }

  async function completeSale(after: "done" | "print" | "whatsapp" | "email") {
    if (!cart.length) return;
    if (customerId && customer.id !== customerId) {
      toast({ title: "Select a customer", description: "The selected customer is unavailable. Reload customers or select another customer.", variant: "destructive" });
      return;
    }
    if (paymentMode === "Credit" && customer.type === "Walk-in") {
      toast({ title: "Customer required", description: "Credit sale needs a registered customer." });
      return;
    }
    if (paymentMode !== "Credit" && received < totals.grandTotal) {
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
    if (checkoutBusy.current) return;
    if (cart.some(line=>line.followUp?.required) && !customerId) {toast({title:"Select a registered follow-up customer",variant:"destructive"});return;}
    checkoutBusy.current = true;
    const sale: Sale = {
      id: checkoutKey,
      invoiceNo: `POS-${String(sales.length + 1).padStart(5, "0")}`,
      customer: customer.name,
      amount: totals.grandTotal,
      mode: paymentMode,
      createdAt: new Date().toISOString(),
      items: cart.length,
    };
    try {
      const activeSession = await srmApi.activePosSession();
      const posSession = (activeSession as { session?: { id?: number } | null })?.session || null;
      const postedOrder = await srmApi.createSalesOrder({
        order_number: `POS-${checkoutKey}`,
        title: `POS sale - ${customer.name}`,
        customer_id: customer.id || undefined,
        currency: "INR",
        subtotal: totals.subtotal,
        discount_amount: totals.lineDiscount + totals.billDiscount + totals.couponDiscount,
        tax_amount: totals.tax,
        total_amount: totals.grandTotal,
        terms: note || `Created from ${activeStoreProfile.name}`,
        metadata_json: {
          source: "pos",
          pos_sale_id: sale.id,
          pos_session_id: posSession?.id,
          payment_mode: paymentMode,
          register: activeStoreProfile.register,
          branch: activeStoreProfile.branch,
          cashier: "Sales Manager",
        },
        lines: cart.map((line) => ({
          product_id: line.id,
          item_code: line.sku,
          description: line.name,
          service_type: line.trackInventory ? "product" : "service",
          quantity: line.qty,
          unit_price: line.rate,
          discount_amount: lineDiscount(line),
          tax_amount: lineTax(line),
          line_total: lineTotal(line),
          metadata_json: {
            barcode: line.barcode,
            category: line.category,
            batch_no: line.batchNo,
            serial_no: line.serialNo,
            note: line.note,
            follow_up: line.followUp,
          },
        })),
      });
      await syncSrmNow(queryClient, {
        type: "pos_sale_completed",
        source: "pos-terminal",
        ids: { sales_order_id: Number((postedOrder as SRMRecord).id || 0) || undefined },
      });
    } catch (error) {
      checkoutBusy.current = false;
      toast({
        title: "Sale not completed",
        description: "Could not post the sale to SRM. Stock, session, or permissions may need attention.",
        variant: "destructive",
      });
      return;
    }
    checkoutBusy.current = false;
    setCheckoutKey(crypto.randomUUID());
    await Promise.all([productsQuery.refetch(), heldBillsQuery.refetch()]);
    setSales((current) => [sale, ...current].slice(0, 25));
    setLastSale(sale);
    setCart([]);
    setBillDiscount(0);
    setCoupon("");
    setNote("");
    setActiveModal("success");
    toast({ title: "Sale completed", description: `${sale.invoiceNo} posted for ${shortCurrency(sale.amount)}.${cart.some(line=>line.followUp?.required)?" Customer follow-ups scheduled.":""}` });
    if (after === "print") setTimeout(() => window.print(), 150);
    if (after === "whatsapp" || after === "email") {
      toast({ title: "Receipt queued", description: `${after} provider will send after integration credentials are configured.` });
    }
  }

  async function holdCart() {
    if (!cart.length) {
      toast({ title: "Cart is empty", description: "Add items before holding a bill." });
      return;
    }
    const held: HeldBill = {
      id: uid("hold"),
      holdNo: `HOLD-${String(heldBills.length + 1).padStart(4, "0")}`,
      customerId,
      notes: note || `${customer.name} counter bill`,
      cart,
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
        cart_json: cart,
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
    setNote("");
    toast({ title: "Bill held", description: `${held.holdNo} is ready for recall.` });
  }

  async function recallBill(bill: HeldBill) {
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
    setCart(recalled.cart);
    setCustomerId(recalled.customerId);
    setLocalHeldBills((current) => current.filter((item) => item.id !== bill.id));
    setActiveModal(null);
    toast({ title: "Bill recalled", description: `${bill.holdNo} restored to cart.` });
  }

  async function deleteHeldBill(bill: HeldBill) {
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
    <div className={`srm-pos srm-pos-view-${mobileView} min-h-full bg-[linear-gradient(135deg,#eef7f2_0%,#f7f4ee_48%,#eef2ff_100%)] text-slate-950`}>
      <header className="border-b border-white/70 bg-white/85 px-4 py-3 shadow-sm backdrop-blur">
        <div className="flex flex-col gap-3 2xl:flex-row 2xl:items-center 2xl:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-[#3157d8] text-white shadow-sm">
              <ShoppingCart className="h-6 w-6" />
            </span>
            <div className="min-w-0">
              <h1 className="truncate text-xl font-semibold">Sales & Inventory POS</h1>
              <p className="text-sm text-slate-500">{activeStoreProfile.branch} / {activeStoreProfile.register} / Session POS-0001</p>
            </div>
          </div>
          <button type="button" className="srm-pos-session-toggle" aria-expanded={sessionDetailsOpen} aria-controls="pos-session-details" onClick={() => setSessionDetailsOpen(value => !value)}><Settings size={18} />Session & actions<span aria-hidden="true">{sessionDetailsOpen ? "−" : "+"}</span></button>
          <div id="pos-session-details" className={`srm-pos-session-details ${sessionDetailsOpen ? "is-open" : ""}`}>
          <div className="grid grid-cols-2 gap-2 text-xs md:flex md:items-center">
            <SessionPill label="Template" value={activeStoreProfile.name} />
            <SessionPill label="Cashier" value="Sales Manager" />
            <SessionPill label="Opening cash" value={shortCurrency(5000)} />
            <SessionPill label="Expected cash" value={shortCurrency(expectedCash)} />
          </div>
          <CompactActions className="flex flex-wrap gap-2">
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
          <Button type="button" variant="outline" className="h-11 shrink-0 border-slate-200 bg-white text-slate-950" onClick={() => setQuickAddOpen(true)}><Plus size={16}/>Quick add</Button>
        </div>{customersQuery.isError && <p role="alert" className="mt-1 text-xs text-red-700">Unable to load customers. <button type="button" className="underline" onClick={() => void customersQuery.refetch()}>Retry</button></p>}</div>
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
          <div className="grid gap-3 md:grid-cols-3">
            <StatusTile label="Products" value={String(storeProducts.length)} detail={`${filteredProducts.length} visible`} />
            <StatusTile label="Low stock" value={String(lowStockCount)} detail="Reorder watch" />
            <StatusTile label="Cart quantity" value={String(totals.qty)} detail={`${cart.length} lines`} />
          </div>
          <ModePanel mode={mode} customer={customer} />
          <div className="flex flex-col gap-3 rounded-2xl border border-white bg-white p-3 shadow-sm md:flex-row md:items-center md:justify-between">
            <div>
              <strong className="text-sm text-slate-950">Products</strong>
              <p className="text-xs text-slate-500">{filteredProducts.length} eligible products & services</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button asChild variant="outline"><Link to="/srm/inventory/products">Manage products & services</Link></Button>
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
          {productsQuery.isError && <p role="alert">Unable to load the catalog. <button type="button" className="underline" onClick={() => void productsQuery.refetch()}>Retry</button></p>}
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
                    <label className="text-xs text-slate-500">Qty<Input type="number" min="0.001" step={line.decimalAllowed ? "0.001" : "1"} value={line.qty} onChange={(event) => updateLine(line.lineId, { qty: Math.min(line.stock, Math.max(0.001, Number(event.target.value) || 1)) })} className="mt-1 border-slate-200 bg-slate-50 text-slate-950" /></label>
                    <label className="text-xs text-slate-500">Rate<Input type="number" min="0" value={line.rate} onChange={(event) => updateLine(line.lineId, { rate: Math.max(0, Number(event.target.value) || 0) })} className="mt-1 border-slate-200 bg-slate-50 text-slate-950" /></label>
                    <label className="text-xs text-slate-500">Disc %<Input type="number" min="0" max="50" value={line.discount} onChange={(event) => updateLine(line.lineId, { discount: Math.min(50, Math.max(0, Number(event.target.value) || 0)) })} className="mt-1 border-slate-200 bg-slate-50 text-slate-950" /></label>
                  </div>
                  <div className="mt-2 flex items-center justify-between text-sm">
                    <span className="text-slate-400">Tax {line.taxRate}%</span>
                    <strong>{currency(lineTotal(line))}</strong>
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
                <Button variant="outline" className="border-slate-200 text-slate-700" onClick={holdCart}><PauseCircle className="h-4 w-4" />Hold</Button>
                <Button className="bg-[#3157d8] text-white hover:bg-[#2748b8]" onClick={() => openPayment("Cash")}><Calculator className="h-4 w-4" />Pay</Button>
              </div>
            </CardContent>
          </Card>
        </aside>
      </main>

      <footer className="srm-pos-checkout sticky bottom-0 grid gap-2 border-t border-slate-200 bg-white p-3 shadow-[0_-8px_20px_rgba(15,23,42,0.06)] md:grid-cols-[repeat(3,1fr)_auto_auto_auto] md:items-center">
        <FooterMetric label="Items" value={String(cart.length)} />
        <FooterMetric label="Quantity" value={String(totals.qty)} />
        <FooterMetric label="Payable" value={shortCurrency(totals.grandTotal)} />
        <Button variant="outline" className="border-slate-200 text-slate-700" onClick={() => setActiveModal("held")}><RotateCcw className="h-4 w-4" />Recall</Button>
        <Button variant="outline" className="border-slate-200 text-slate-700" onClick={() => window.print()}><Printer className="h-4 w-4" />Print Last</Button>
        <Button className="bg-[#3157d8] text-white hover:bg-[#2748b8]" onClick={() => openPayment("Cash")}><CreditCard className="h-4 w-4" />Payment</Button>
      </footer>

      {quickAddOpen && <QuickAddCustomer onClose={() => setQuickAddOpen(false)} onCreated={customerCreated}/>}
      {activeModal === "payment" ? (
        <Overlay title="Complete Payment" onClose={() => setActiveModal(null)} wide>
          <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
            <div className="space-y-4">
              <div className="space-y-3 rounded-lg bg-background p-3 text-foreground">
                <div className="flex flex-wrap items-end gap-2"><label className="flex-1 text-xs">Customer for this sale & follow-ups<NativeSelect loading={customersQuery.isFetching} error={customersQuery.isError} aria-label="Follow-up customer" className="block w-full rounded border bg-background p-2 text-foreground" value={customerId || ""} onChange={e => setCustomerId(Number(e.target.value))}><option value="">Walk-in — select a customer to schedule</option>{customers.filter(c => c.id).map(c => <option key={c.id} value={c.id}>{c.name}{c.phone ? ` · ${c.phone}` : ""}</option>)}</NativeSelect></label><Button type="button" variant="outline" onClick={() => setQuickAddOpen(true)}><Plus size={16}/>Quick add customer</Button></div>
                {cart.map(line=><details key={line.lineId}><summary className="cursor-pointer text-sm">{line.name} · {line.followUp?.required?`${line.followUp.interval_days} day follow-up`:"Configure follow-up"}</summary><ScheduleFields template value={line.followUp||defaultSchedule} employees={followUpOptions.data?.employees} teams={followUpOptions.data?.teams} onChange={value=>setCart(current=>current.map(l=>l.lineId===line.lineId?{...l,followUp:value}:l))}/></details>)}
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
                    setPaymentRows(item === "Split" ? [{ id: uid("pay"), mode: "Cash", amount: totals.grandTotal, reference: "" }] : [{ id: uid("pay"), mode: item === "Credit" ? "Credit" : item, amount: item === "Credit" ? 0 : totals.grandTotal, reference: "" }]);
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
                    <Input type="number" min="0" value={row.amount} onChange={(event) => setPaymentRows((current) => current.map((item) => item.id === row.id ? { ...item, amount: Number(event.target.value) || 0 } : item))} className="border-white/15 bg-slate-900 text-white" />
                    <Input value={row.reference} onChange={(event) => setPaymentRows((current) => current.map((item) => item.id === row.id ? { ...item, reference: event.target.value } : item))} placeholder="Reference" className="border-white/15 bg-slate-900 text-white" />
                    <Button size="icon" variant="ghost" className="text-slate-300 hover:bg-white/10 hover:text-white" onClick={() => setPaymentRows((current) => current.filter((item) => item.id !== row.id))}><X className="h-4 w-4" /></Button>
                  </div>
                ))}
              </div>
              <Button variant="outline" className="border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={() => { setPaymentMode("Split"); setPaymentRows((current) => [...current, { id: uid("pay"), mode: "Cash", amount: 0, reference: "" }]); }}><Plus className="h-4 w-4" />Add payment mode</Button>
            </div>
            <div className="space-y-3 rounded-lg bg-slate-950 p-4">
              <SummaryLine label="Amount received" value={currency(received)} />
              <SummaryLine label="Balance due" value={currency(balanceDue)} />
              <SummaryLine label="Change due" value={currency(changeDue)} />
              <CompactActions><Button className="w-full bg-emerald-500 text-slate-950 hover:bg-emerald-400" onClick={() => completeSale("done")}>Complete Sale</Button>
<Button variant="outline" className="w-full border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={() => completeSale("print")}>Complete + Print</Button>
<Button variant="outline" className="w-full border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={() => completeSale("whatsapp")}>Complete + WhatsApp</Button>
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
        <Overlay title="Sale Completed" onClose={() => setActiveModal(null)}>
          <div className="text-center">
            <CheckCircle2 className="mx-auto h-14 w-14 text-emerald-400" />
            <h2 className="mt-3 text-2xl font-semibold">{lastSale.invoiceNo}</h2>
            <p className="text-slate-400">{lastSale.customer} · {currency(lastSale.amount)} · {lastSale.mode}</p>
            <div className="mt-5 grid gap-2 md:grid-cols-2">
              <Button onClick={() => window.print()}><Printer className="h-4 w-4" />Print Receipt</Button>
              <Button variant="outline" className="border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={() => setActiveModal(null)}>New Sale</Button>
            </div>
          </div>
        </Overlay>
      ) : null}

      {activeModal === "cash" ? (
        <Overlay title="Cash Drawer Movement" onClose={() => setActiveModal(null)}>
          <CashMovementForm onSave={(row) => {
            setCashMovements((current) => [row, ...current]);
            setActiveModal(null);
            toast({ title: "Cash movement recorded", description: `${row.type} ${currency(row.amount)}` });
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
            <SummaryLine label="Opening cash" value={currency(5000)} />
            <SummaryLine label="Cash sales" value={currency(sales.filter((sale) => sale.mode === "Cash" || sale.mode === "Split").reduce((sum, sale) => sum + sale.amount, 0))} />
            <SummaryLine label="Expected closing cash" value={currency(expectedCash)} />
            <label className="block text-sm text-slate-400">Actual counted cash<Input value={closingCash} onChange={(event) => setClosingCash(event.target.value)} type="number" className="mt-1 border-white/15 bg-slate-950 text-white" /></label>
            {closingCash ? <SummaryLine label="Cash variance" value={currency((Number(closingCash) || 0) - expectedCash)} /> : null}
            <Button className="w-full" variant="destructive" onClick={() => {
              toast({ title: "Z-report prepared", description: `Expected cash ${currency(expectedCash)}. Session close captured.` });
              setActiveModal(null);
            }}>Close Session & View Z-report</Button>
          </div>
        </Overlay>
      ) : null}
    </div>
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

function Overlay({ title, onClose, children, wide }: { title: string; onClose: () => void; children: React.ReactNode; wide?: boolean }) {
  return (
    <Dialog.Root open onOpenChange={open => { if (!open) onClose(); }}><Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-50 bg-black/70" />
      <Dialog.Content aria-describedby={undefined} className={`srm-pos-dialog fixed left-1/2 top-1/2 z-50 max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] -translate-x-1/2 -translate-y-1/2 overflow-auto rounded-lg border border-white/10 bg-slate-900 p-4 text-slate-100 shadow-2xl ${wide ? "max-w-5xl" : "max-w-2xl"}`}>
        <div className="mb-4 flex items-center justify-between gap-3">
          <Dialog.Title className="text-lg font-semibold">{title}</Dialog.Title>
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

function CashMovementForm({ onSave }: { onSave: (row: { id: string; type: string; amount: number; reason: string; createdAt: string }) => void }) {
  const [type, setType] = useState("Withdrawal");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
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
      <Button className="w-full" onClick={() => {
        const parsed = Number(amount);
        if (!parsed || parsed <= 0 || !reason.trim()) {
          toast({ title: "Amount and reason required" });
          return;
        }
        onSave({ id: uid("cash"), type, amount: parsed, reason, createdAt: new Date().toISOString() });
      }}>Record Movement</Button>
    </div>
  );
}
