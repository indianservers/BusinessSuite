import { FormEvent, KeyboardEvent as ReactKeyboardEvent, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { reportsApi } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { getProductForContext } from "@/lib/products";
import { canAccessRoute } from "@/lib/roles";

type Result = { type: string; title: string; subtitle?: string; url: string };

export default function GlobalSearch() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuthStore();
  const product = getProductForContext(location.pathname, user?.role, user?.is_superuser);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const enabled = product.key === "hrms" && open && query.trim().length >= 2;
  const { data } = useQuery({
    queryKey: ["global-search", query],
    queryFn: () => reportsApi.globalSearch(query).then((r) => r.data),
    enabled,
  });
  const staticResults = useMemo<Result[]>(() => {
    if (product.key === "crm") {
      return [
        { type: "Page", title: "CRM Dashboard", url: "/crm" },
        { type: "Page", title: "Leads", subtitle: "Lead capture and qualification", url: "/crm/leads" },
        { type: "Page", title: "Deals", subtitle: "Pipeline and opportunities", url: "/crm/deals" },
        { type: "Page", title: "Contacts", subtitle: "Customer contacts", url: "/crm/contacts" },
        { type: "Page", title: "Reports", subtitle: "Sales analytics", url: "/crm/reports" },
      ];
    }
    if (product.key === "project_management") {
      return [
        { type: "Page", title: "PMS Dashboard", url: "/pms" },
        { type: "Page", title: "Projects", subtitle: "Project portfolio", url: "/pms/projects" },
        { type: "Page", title: "Backlog", subtitle: "Issues and planning", url: "/pms/backlog" },
        { type: "Page", title: "Sprints", subtitle: "Sprint execution", url: "/pms/sprints" },
        { type: "Page", title: "Reports", subtitle: "Delivery analytics", url: "/pms/reports" },
      ];
    }
    if (product.key === "srm") {
      return [
        { type: "Page", title: "SRM Dashboard", url: "/srm" },
        { type: "Page", title: "Sales Orders", subtitle: "CRM won handoffs and order approvals", url: "/srm/sales-orders" },
        { type: "Page", title: "Engagements", subtitle: "CRM, SRM, and PMS lifecycle links", url: "/srm/engagements" },
        { type: "Page", title: "Invoices", subtitle: "Drafts, approvals, sending, and PDF", url: "/srm/invoices" },
        { type: "Page", title: "Collections", subtitle: "Receipts, allocations, aging, reminders", url: "/srm/collections" },
        { type: "Page", title: "Profitability", subtitle: "Margin and cash performance", url: "/srm/profitability" },
      ];
    }
    return [
      { type: "Page", title: "HRMS Dashboard", url: "/hrms" },
      { type: "Page", title: "Payroll", subtitle: "Run, pre-checks, payslips", url: "/hrms/payroll" },
      { type: "Page", title: "ESS Profile", subtitle: "Photo, completeness, change requests", url: "/hrms/profile" },
      { type: "Page", title: "Talent", subtitle: "OKR, 360, competencies", url: "/hrms/performance" },
      { type: "Page", title: "Org Chart", subtitle: "Company hierarchy", url: "/hrms/company" },
    ];
  }, [product.key]);
  const results: Result[] = (enabled ? (data?.results || []) : staticResults).filter((item: Result) =>
    canAccessRoute(item.url, user?.role, user?.is_superuser)
  );

  useEffect(() => {
    setFocusedIndex(-1);
  }, [query]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(true);
      }
      if (event.altKey && event.key.toLowerCase() === "h") navigate(product.homePath);
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate, product.homePath]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const selected = (focusedIndex >= 0 ? results[focusedIndex] : undefined) || results[0];
    if (selected) {
      navigate(selected.url);
      setOpen(false);
    }
  }

  function handleSearchKeyDown(event: ReactKeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setFocusedIndex((current) => (results.length ? (current + 1) % results.length : -1));
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setFocusedIndex((current) => (results.length ? (current <= 0 ? results.length - 1 : current - 1) : -1));
    }
  }

  return (
    <>
      <button
        type="button"
        className="relative hidden max-w-md flex-1 sm:flex"
        onClick={() => setOpen(true)}
      >
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input readOnly value="" placeholder={product.searchPlaceholder} className="cursor-pointer border-0 bg-secondary/50 pl-9 focus-visible:ring-1" />
      </button>
      <button
        type="button"
        className="inline-flex h-9 w-9 items-center justify-center rounded-md border bg-background text-muted-foreground sm:hidden"
        onClick={() => setOpen(true)}
        aria-label="Open search"
        title="Search"
      >
        <Search className="h-4 w-4" />
      </button>
      {open && (
        <div className="fixed inset-0 z-50 bg-black/40 p-4 pt-[12vh]" onClick={() => setOpen(false)}>
          <div className="mx-auto max-w-2xl rounded-lg border bg-background shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <form onSubmit={submit} className="border-b p-3">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input autoFocus value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={handleSearchKeyDown} placeholder="Search anything..." className="border-0 pl-9 text-base focus-visible:ring-0" />
              </div>
            </form>
            <div className="max-h-[420px] overflow-y-auto p-2">
              {results.length ? results.map((item, index) => (
                <button
                  key={`${item.type}-${item.title}-${index}`}
                  className={`flex w-full items-center justify-between rounded-md p-3 text-left hover:bg-muted ${focusedIndex === index ? "bg-accent" : ""}`}
                  onClick={() => {
                    navigate(item.url);
                    setOpen(false);
                  }}
                >
                  <div>
                    <p className="text-sm font-medium">{item.title}</p>
                    <p className="text-xs text-muted-foreground">{item.subtitle || item.type}</p>
                  </div>
                  <span className="rounded bg-muted px-2 py-1 text-[10px] font-semibold uppercase text-muted-foreground">{item.type}</span>
                </button>
              )) : (
                <div className="p-8 text-center text-sm text-muted-foreground">No results found</div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
