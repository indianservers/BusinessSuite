import { useEffect, useMemo, useRef, useState } from "react";
import {
  Banknote,
  Barcode,
  Boxes,
  Calculator,
  CheckCircle2,
  CreditCard,
  DoorClosed,
  Minus,
  Package,
  PauseCircle,
  Plus,
  Printer,
  Receipt,
  RotateCcw,
  Search,
  Settings,
  ShoppingCart,
  Trash2,
  WalletCards,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "@/hooks/use-toast";

type PosMode = "Retail" | "Supermarket" | "Restaurant" | "Services" | "Wholesale" | "Pharmacy" | "Electronics" | "Garments";
type PaymentMode = "Cash" | "Card" | "UPI" | "Wallet" | "Credit" | "Split";

type Product = {
  id: number;
  name: string;
  sku: string;
  barcode: string;
  category: string;
  rate: number;
  mrp: number;
  taxRate: number;
  stock: number;
  reorderLevel: number;
  trackInventory: boolean;
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
  id: string;
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
  name: string;
  mode: PosMode;
  categories: string[];
};

const products: Product[] = [
  { id: 1, name: "Sample Product", sku: "SKU-001", barcode: "890000000001", category: "General", rate: 150, mrp: 175, taxRate: 18, stock: 50, reorderLevel: 10, trackInventory: true },
  { id: 2, name: "School Notebook A4", sku: "STN-A4-100", barcode: "890000000102", category: "Stationery", rate: 64, mrp: 75, taxRate: 12, stock: 112, reorderLevel: 25, trackInventory: true },
  { id: 3, name: "Blue Ball Pen Pack", sku: "PEN-BL-10", barcode: "890000000103", category: "Stationery", rate: 90, mrp: 100, taxRate: 12, stock: 8, reorderLevel: 20, trackInventory: true },
  { id: 4, name: "USB Keyboard", sku: "EL-KBD-USB", barcode: "890000000201", category: "Electronics", rate: 699, mrp: 799, taxRate: 18, stock: 16, reorderLevel: 5, trackInventory: true, serialTracking: true, serials: ["KBD-2401", "KBD-2402", "KBD-2403"] },
  { id: 5, name: "WiFi Router", sku: "EL-RTR-4G", barcode: "890000000202", category: "Electronics", rate: 2499, mrp: 2799, taxRate: 18, stock: 7, reorderLevel: 4, trackInventory: true, serialTracking: true, serials: ["RTR-9101", "RTR-9102"] },
  { id: 6, name: "Printer Paper Bundle", sku: "PPR-A4-500", barcode: "890000000301", category: "Office Supplies", rate: 310, mrp: 350, taxRate: 12, stock: 45, reorderLevel: 12, trackInventory: true },
  { id: 7, name: "Lab Coat", sku: "UNI-LAB-M", barcode: "890000000401", category: "Garments", rate: 540, mrp: 620, taxRate: 5, stock: 22, reorderLevel: 10, trackInventory: true },
  { id: 8, name: "Consultation Service", sku: "SRV-CONSULT", barcode: "SRV-CONSULT", category: "Services", rate: 1200, mrp: 1200, taxRate: 18, stock: 999, reorderLevel: 0, trackInventory: false, decimalAllowed: true },
  { id: 9, name: "Pharmacy First Aid Kit", sku: "MED-FAK-01", barcode: "890000000501", category: "Pharmacy", rate: 420, mrp: 475, taxRate: 5, stock: 18, reorderLevel: 8, trackInventory: true, batchTracking: true, batch: "MED-JUN26" },
];

const customers: Customer[] = [
  { id: 1, name: "Cash Customer", phone: "9999999999", type: "Walk-in", creditLimit: 0, outstanding: 0, loyaltyPoints: 0 },
  { id: 2, name: "Gowthama Main Campus", phone: "9848012345", type: "Credit", creditLimit: 250000, outstanding: 32000, loyaltyPoints: 1400 },
  { id: 3, name: "GreenField Stores", phone: "9000011122", type: "Wholesale", creditLimit: 150000, outstanding: 42000, loyaltyPoints: 820 },
  { id: 4, name: "Walk-in Parent", phone: "9888877776", type: "Retail", creditLimit: 0, outstanding: 0, loyaltyPoints: 80 },
];

const activeStoreProfile: PosStoreProfile = {
  name: "Bookstore Retail",
  mode: "Retail",
  categories: ["General", "Stationery", "Office Supplies"],
};
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
  const mode = activeStoreProfile.mode;
  const [customerId, setCustomerId] = useState(1);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");
  const [cart, setCart] = usePersistedState<CartLine[]>("business-suite-srm-pos-cart", []);
  const [heldBills, setHeldBills] = usePersistedState<HeldBill[]>("business-suite-srm-pos-held", []);
  const [sales, setSales] = usePersistedState<Sale[]>("business-suite-srm-pos-sales", []);
  const [billDiscount, setBillDiscount] = useState(0);
  const [coupon, setCoupon] = useState("");
  const [note, setNote] = useState("");
  const [activeModal, setActiveModal] = useState<"payment" | "held" | "success" | "close" | "cash" | null>(null);
  const [paymentMode, setPaymentMode] = useState<PaymentMode>("Cash");
  const [paymentRows, setPaymentRows] = useState<PaymentRow[]>([]);
  const [lastSale, setLastSale] = useState<Sale | null>(null);
  const [closingCash, setClosingCash] = useState("");
  const [cashMovements, setCashMovements] = usePersistedState<{ id: string; type: string; amount: number; reason: string; createdAt: string }[]>("business-suite-srm-pos-cash", []);
  const searchRef = useRef<HTMLInputElement>(null);

  const customer = customers.find((item) => item.id === customerId) || customers[0];
  const storeProducts = useMemo(() => products.filter((item) => activeStoreProfile.categories.includes(item.category)), []);
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
      return categoryMatch && textMatch;
    });
  }, [category, query, storeProducts]);

  const received = paymentRows.reduce((sum, row) => row.mode === "Credit" ? sum : sum + row.amount, 0);
  const balanceDue = Math.max(totals.grandTotal - received, 0);
  const changeDue = Math.max(received - totals.grandTotal, 0);
  const expectedCash = 5000 + sales.filter((sale) => sale.mode === "Cash" || sale.mode === "Split").reduce((sum, sale) => sum + sale.amount, 0) - cashMovements.filter((row) => row.type === "Withdrawal").reduce((sum, row) => sum + row.amount, 0);

  function addProduct(product: Product) {
    if (product.trackInventory && product.stock <= 0) {
      toast({ title: "Out of stock", description: `${product.name} cannot be added.` });
      return;
    }
    setCart((current) => {
      const existing = current.find((line) => line.id === product.id && !line.serialTracking);
      if (!existing) return [...current, buildCartLine(product)];
      return current.map((line) => line.lineId === existing.lineId ? { ...line, qty: Math.min(line.stock, line.qty + 1) } : line);
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

  function completeSale(after: "done" | "print" | "whatsapp" | "email") {
    if (!cart.length) return;
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
    const sale: Sale = {
      id: uid("sale"),
      invoiceNo: `POS-${String(sales.length + 1).padStart(5, "0")}`,
      customer: customer.name,
      amount: totals.grandTotal,
      mode: paymentMode,
      createdAt: new Date().toISOString(),
      items: cart.length,
    };
    setSales((current) => [sale, ...current].slice(0, 25));
    setLastSale(sale);
    setCart([]);
    setBillDiscount(0);
    setCoupon("");
    setNote("");
    setActiveModal("success");
    toast({ title: "Sale completed", description: `${sale.invoiceNo} posted for ${shortCurrency(sale.amount)}.` });
    if (after === "print") setTimeout(() => window.print(), 150);
    if (after === "whatsapp" || after === "email") {
      toast({ title: "Receipt queued", description: `${after} provider will send after integration credentials are configured.` });
    }
  }

  function holdCart() {
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
    setHeldBills((current) => [held, ...current]);
    setCart([]);
    setNote("");
    toast({ title: "Bill held", description: `${held.holdNo} is ready for recall.` });
  }

  function recallBill(bill: HeldBill) {
    setCart(bill.cart);
    setCustomerId(bill.customerId);
    setHeldBills((current) => current.filter((item) => item.id !== bill.id));
    setActiveModal(null);
    toast({ title: "Bill recalled", description: `${bill.holdNo} restored to cart.` });
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
    <div className="min-h-full bg-slate-950 text-slate-100">
      <header className="border-b border-white/10 bg-slate-900 px-4 py-3">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-amber-500 text-slate-950">
              <ShoppingCart className="h-6 w-6" />
            </span>
            <div>
              <h1 className="text-xl font-semibold">Sales & Inventory POS</h1>
              <p className="text-sm text-slate-300">Main Branch · Main POS Register · Session POS-0001</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs md:flex md:items-center">
            <SessionPill label="Cashier" value="Sales Manager" />
            <SessionPill label="Warehouse" value="POS Warehouse" />
            <SessionPill label="Opening Cash" value={shortCurrency(5000)} />
            <SessionPill label="Expected Cash" value={shortCurrency(expectedCash)} />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" className="border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={holdCart}><PauseCircle className="h-4 w-4" />Hold</Button>
            <Button variant="outline" className="border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={() => setActiveModal("held")}><RotateCcw className="h-4 w-4" />Recall</Button>
            <Button variant="outline" className="border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={() => setActiveModal("cash")}><Banknote className="h-4 w-4" />Cash</Button>
            <Button variant="destructive" onClick={() => setActiveModal("close")}><DoorClosed className="h-4 w-4" />Close</Button>
          </div>
        </div>
      </header>

      <section className="grid gap-3 border-b border-white/10 bg-slate-900/80 p-4 xl:grid-cols-[14rem_18rem_1fr_auto]">
        <div className="rounded-md border border-amber-400/40 bg-amber-500/10 px-3 py-2 text-sm">
          <span className="block text-xs font-medium text-amber-200">Template</span>
          <strong className="text-white">{activeStoreProfile.name}</strong>
        </div>
        <Select value={String(customerId)} onValueChange={(value) => setCustomerId(Number(value))}>
          <SelectTrigger className="border-white/15 bg-slate-950 text-white">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {customers.map((item) => <SelectItem key={item.id} value={String(item.id)}>{item.name}</SelectItem>)}
          </SelectContent>
        </Select>
        <div className="relative">
          <Barcode className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
          <Input
            ref={searchRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") scanSearch();
            }}
            className="border-white/15 bg-slate-950 pl-9 text-white placeholder:text-slate-500"
            placeholder="Scan barcode or search product, SKU, batch, serial [F2]"
          />
        </div>
        <Button className="bg-amber-500 text-slate-950 hover:bg-amber-400" onClick={() => openPayment("Cash")}><CreditCard className="h-4 w-4" />Payment [F7]</Button>
      </section>

      <main className="grid gap-4 p-4 xl:grid-cols-[1fr_27rem]">
        <section className="space-y-4">
          <ModePanel mode={mode} customer={customer} />
          <div className="flex flex-wrap gap-2">
            {categories.map((item) => (
              <button key={item} type="button" onClick={() => setCategory(item)} className={`rounded-md border px-3 py-2 text-sm ${category === item ? "border-amber-400 bg-amber-500 text-slate-950" : "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10"}`}>
                {item}
              </button>
            ))}
          </div>
          <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
            {filteredProducts.map((product) => {
              const qty = cart.filter((line) => line.id === product.id).reduce((sum, line) => sum + line.qty, 0);
              const lowStock = product.trackInventory && product.stock <= product.reorderLevel;
              return (
                <article key={product.id} className={`relative rounded-lg border p-3 transition ${qty ? "border-amber-400 bg-amber-500/10" : "border-white/10 bg-slate-900 hover:border-white/30"}`}>
                  {lowStock ? <Badge variant="destructive" className="absolute right-3 top-3">Low stock</Badge> : null}
                  <button type="button" className="w-full text-left" onClick={() => addProduct(product)}>
                    <span className="flex h-24 items-center justify-center rounded-md bg-slate-800 text-slate-300">
                      <Package className="h-10 w-10" />
                    </span>
                    <span className="mt-3 block pr-20 text-sm font-semibold text-white">{product.name}</span>
                    <span className="mt-1 block text-xs text-slate-400">{product.sku} · {product.barcode}</span>
                    <span className="mt-3 flex items-center justify-between">
                      <strong className="text-lg text-amber-300">{currency(product.rate)}</strong>
                      <span className="text-xs text-slate-400">Stock {product.trackInventory ? product.stock : "Service"}</span>
                    </span>
                  </button>
                  <div className="mt-3 flex items-center justify-between rounded-md bg-slate-950 p-1">
                    <Button size="icon" variant="ghost" className="text-slate-200 hover:bg-white/10 hover:text-white" onClick={() => removeProduct(product.id)} disabled={!qty}><Minus className="h-4 w-4" /></Button>
                    <strong>{qty}</strong>
                    <Button size="icon" variant="ghost" className="text-slate-200 hover:bg-white/10 hover:text-white" onClick={() => addProduct(product)}><Plus className="h-4 w-4" /></Button>
                  </div>
                </article>
              );
            })}
          </div>
        </section>

        <aside className="space-y-4">
          <Card className="border-white/10 bg-slate-900 text-slate-100">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">Active Bill</CardTitle>
              <Button variant="ghost" size="sm" className="text-slate-300 hover:bg-white/10 hover:text-white" onClick={() => setCart([])} disabled={!cart.length}><Trash2 className="h-4 w-4" />Clear</Button>
            </CardHeader>
            <CardContent className="space-y-3">
              {cart.length ? cart.map((line) => (
                <div key={line.lineId} className="rounded-lg border border-white/10 bg-slate-950 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <strong className="text-sm">{line.name}</strong>
                      <p className="text-xs text-slate-400">{line.sku}{line.batchNo ? ` · Batch ${line.batchNo}` : ""}{line.serialNo ? ` · Serial ${line.serialNo}` : ""}</p>
                    </div>
                    <Button size="icon" variant="ghost" className="h-7 w-7 text-slate-300 hover:bg-white/10 hover:text-white" onClick={() => setCart((current) => current.filter((item) => item.lineId !== line.lineId))}><X className="h-4 w-4" /></Button>
                  </div>
                  <div className="mt-3 grid grid-cols-[1fr_1fr_1fr] gap-2">
                    <label className="text-xs text-slate-400">Qty<Input type="number" min="0.001" step={line.decimalAllowed ? "0.001" : "1"} value={line.qty} onChange={(event) => updateLine(line.lineId, { qty: Math.min(line.stock, Math.max(0.001, Number(event.target.value) || 1)) })} className="mt-1 border-white/15 bg-slate-900 text-white" /></label>
                    <label className="text-xs text-slate-400">Rate<Input type="number" min="0" value={line.rate} onChange={(event) => updateLine(line.lineId, { rate: Math.max(0, Number(event.target.value) || 0) })} className="mt-1 border-white/15 bg-slate-900 text-white" /></label>
                    <label className="text-xs text-slate-400">Disc %<Input type="number" min="0" max="50" value={line.discount} onChange={(event) => updateLine(line.lineId, { discount: Math.min(50, Math.max(0, Number(event.target.value) || 0)) })} className="mt-1 border-white/15 bg-slate-900 text-white" /></label>
                  </div>
                  <div className="mt-2 flex items-center justify-between text-sm">
                    <span className="text-slate-400">Tax {line.taxRate}%</span>
                    <strong>{currency(lineTotal(line))}</strong>
                  </div>
                </div>
              )) : (
                <div className="rounded-lg border border-dashed border-white/15 p-8 text-center text-slate-400">
                  <ShoppingCart className="mx-auto mb-3 h-8 w-8" />
                  <strong className="block text-slate-200">Ready for first scan</strong>
                  <span className="text-sm">Scan barcode or tap a product to start billing.</span>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border-white/10 bg-slate-900 text-slate-100">
            <CardContent className="space-y-3 p-4">
              <SummaryLine label="Subtotal" value={currency(totals.subtotal)} />
              <SummaryLine label="Line discount" value={currency(totals.lineDiscount)} />
              <div className="grid grid-cols-[1fr_8rem] items-center gap-3 text-sm">
                <span className="text-slate-400">Bill discount</span>
                <Input type="number" min="0" value={billDiscount} onChange={(event) => setBillDiscount(Number(event.target.value) || 0)} className="border-white/15 bg-slate-950 text-right text-white" />
              </div>
              <div className="grid grid-cols-[1fr_8rem] items-center gap-3 text-sm">
                <span className="text-slate-400">Coupon</span>
                <Input value={coupon} onChange={(event) => setCoupon(event.target.value)} placeholder="WELCOME10" className="border-white/15 bg-slate-950 text-white" />
              </div>
              <SummaryLine label="Coupon discount" value={currency(totals.couponDiscount)} />
              <SummaryLine label="Taxable" value={currency(totals.taxable)} />
              <SummaryLine label="Tax" value={currency(totals.tax)} />
              <SummaryLine label="Round off" value={currency(totals.roundOff)} />
              <div className="rounded-lg bg-amber-500 p-4 text-slate-950">
                <span className="block text-xs font-semibold uppercase">Amount payable</span>
                <strong className="text-3xl">{currency(totals.grandTotal)}</strong>
              </div>
              <Input value={note} onChange={(event) => setNote(event.target.value)} placeholder="Bill note / delivery instruction" className="border-white/15 bg-slate-950 text-white" />
              <div className="grid grid-cols-2 gap-2">
                <Button variant="outline" className="border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={holdCart}><PauseCircle className="h-4 w-4" />Hold</Button>
                <Button className="bg-emerald-500 text-slate-950 hover:bg-emerald-400" onClick={() => openPayment("Cash")}><Calculator className="h-4 w-4" />Pay</Button>
              </div>
            </CardContent>
          </Card>
        </aside>
      </main>

      <footer className="sticky bottom-0 grid gap-2 border-t border-white/10 bg-slate-900 p-3 md:grid-cols-[repeat(3,1fr)_auto_auto_auto] md:items-center">
        <FooterMetric label="Items" value={String(cart.length)} />
        <FooterMetric label="Quantity" value={String(totals.qty)} />
        <FooterMetric label="Payable" value={shortCurrency(totals.grandTotal)} />
        <Button variant="outline" className="border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={() => setActiveModal("held")}><RotateCcw className="h-4 w-4" />Recall</Button>
        <Button variant="outline" className="border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={() => window.print()}><Printer className="h-4 w-4" />Print Last</Button>
        <Button className="bg-emerald-500 text-slate-950 hover:bg-emerald-400" onClick={() => openPayment("Cash")}><CreditCard className="h-4 w-4" />Payment</Button>
      </footer>

      {activeModal === "payment" ? (
        <Overlay title="Complete Payment" onClose={() => setActiveModal(null)} wide>
          <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
            <div className="space-y-4">
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
              <Button className="w-full bg-emerald-500 text-slate-950 hover:bg-emerald-400" onClick={() => completeSale("done")}>Complete Sale</Button>
              <Button variant="outline" className="w-full border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={() => completeSale("print")}>Complete + Print</Button>
              <Button variant="outline" className="w-full border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={() => completeSale("whatsapp")}>Complete + WhatsApp</Button>
              <Button variant="outline" className="w-full border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={() => completeSale("email")}>Complete + Email</Button>
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
                  <p className="text-xs text-slate-500">{bill.notes}</p>
                </div>
                <div className="flex gap-2">
                  <Button onClick={() => recallBill(bill)}>Recall</Button>
                  <Button variant="outline" className="border-white/20 bg-white/5 text-white hover:bg-white/10" onClick={() => setHeldBills((current) => current.filter((item) => item.id !== bill.id))}>Delete</Button>
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
    <span className="rounded-md border border-white/10 bg-white/5 px-3 py-2">
      <small className="block text-slate-400">{label}</small>
      <strong className="text-slate-100">{value}</strong>
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
    <div className="rounded-lg border border-white/10 bg-slate-900 p-3">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <strong>{mode} mode</strong>
          <p className="text-sm text-slate-400">Customer: {customer.name} · Outstanding {shortCurrency(customer.outstanding)} · Points {customer.loyaltyPoints}</p>
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
      <span className="text-slate-400">{label}</span>
      <strong className="text-slate-100">{value}</strong>
    </div>
  );
}

function FooterMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-slate-950 px-3 py-2">
      <span className="block text-xs text-slate-400">{label}</span>
      <strong className="text-slate-100">{value}</strong>
    </div>
  );
}

function Overlay({ title, onClose, children, wide }: { title: string; onClose: () => void; children: React.ReactNode; wide?: boolean }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className={`max-h-[92vh] w-full overflow-auto rounded-lg border border-white/10 bg-slate-900 p-4 text-slate-100 shadow-2xl ${wide ? "max-w-5xl" : "max-w-2xl"}`}>
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">{title}</h2>
          <Button size="icon" variant="ghost" className="text-slate-300 hover:bg-white/10 hover:text-white" onClick={onClose}><X className="h-4 w-4" /></Button>
        </div>
        {children}
      </div>
    </div>
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
