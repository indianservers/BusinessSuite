import {
  FormEvent,
  KeyboardEvent as ReactKeyboardEvent,
  useEffect,
  useMemo,
  useState,
} from "react";

import { useLocation, useNavigate } from "react-router-dom";

import { useQuery } from "@tanstack/react-query";

import { Search } from "lucide-react";

import { Input } from "@/components/ui/input";

import * as Dialog from "@radix-ui/react-dialog";

import { getRoleNav } from "@/lib/roles";

import { modules } from "@/lib/moduleCatalog";

import { api } from "@/services/api";

import { reportsApi } from "@/services/api";

import { useAuthStore } from "@/store/authStore";

import { getProductForContext } from "@/lib/products";

import { canAccessRoute } from "@/lib/roles";

import { getWowFeaturesForContext } from "@/lib/wowFeatures";

type Result = { type: string; title: string; subtitle?: string; url: string };

export default function GlobalSearch() {
  const navigate = useNavigate();

  const location = useLocation();

  const { user } = useAuthStore();

  const product = getProductForContext(
    location.pathname,
    user?.role,
    user?.is_superuser,
  );

  const [open, setOpen] = useState(false);

  const [query, setQuery] = useState("");

  const [debouncedQuery, setDebouncedQuery] = useState("");

  const [focusedIndex, setFocusedIndex] = useState(-1);

  const enabled =
    product.key === "hrms" && open && debouncedQuery.trim().length >= 2;

  const { data } = useQuery({
    queryKey: [
      "global-search",
      user?.id,
      user?.access?.companyId,
      debouncedQuery,
    ],

    queryFn: () => reportsApi.globalSearch(debouncedQuery).then((r) => r.data),

    enabled,
  });

  const staticResults = useMemo<Result[]>(() => {
    const wowResults: Result[] = getWowFeaturesForContext(product.key).map(
      (feature) => ({
        type: feature.impact,

        title: feature.title,

        subtitle: feature.subtitle,

        url: feature.path,
      }),
    );

    if (product.key === "crm") {
      return [
        { type: "Page", title: "CRM Dashboard", url: "/crm" },

        {
          type: "Page",
          title: "Leads",
          subtitle: "Lead capture and qualification",
          url: "/crm/leads",
        },

        {
          type: "Page",
          title: "Deals",
          subtitle: "Pipeline and opportunities",
          url: "/crm/deals",
        },

        {
          type: "Page",
          title: "Contacts",
          subtitle: "Customer contacts",
          url: "/crm/contacts",
        },

        {
          type: "Page",
          title: "Reports",
          subtitle: "Sales analytics",
          url: "/crm/reports",
        },

        ...wowResults,
      ];
    }

    if (product.key === "project_management") {
      return [
        { type: "Page", title: "PMS Dashboard", url: "/pms" },

        {
          type: "Page",
          title: "Projects",
          subtitle: "Project portfolio",
          url: "/pms/projects",
        },

        {
          type: "Page",
          title: "Backlog",
          subtitle: "Issues and planning",
          url: "/pms/backlog",
        },

        {
          type: "Page",
          title: "Sprints",
          subtitle: "Sprint execution",
          url: "/pms/sprints",
        },

        {
          type: "Page",
          title: "Reports",
          subtitle: "Delivery analytics",
          url: "/pms/reports",
        },

        ...wowResults,
      ];
    }

    if (product.key === "srm") {
      return [
        { type: "Page", title: "SRM Dashboard", url: "/srm" },

        {
          type: "Page",
          title: "Sales Orders",
          subtitle: "CRM won handoffs and order approvals",
          url: "/srm/sales-orders",
        },

        {
          type: "Page",
          title: "Engagements",
          subtitle: "CRM, SRM, and PMS lifecycle links",
          url: "/srm/engagements",
        },

        {
          type: "Page",
          title: "Invoices",
          subtitle: "Drafts, approvals, sending, and PDF",
          url: "/srm/invoices",
        },

        {
          type: "Page",
          title: "Collections",
          subtitle: "Receipts, allocations, aging, reminders",
          url: "/srm/collections",
        },

        {
          type: "Page",
          title: "Profitability",
          subtitle: "Margin and cash performance",
          url: "/srm/profitability",
        },

        ...wowResults,
      ];
    }

    if (product.key === "fam") {
      return [
        { type: "Page", title: "FAM Dashboard", url: "/fam" },

        {
          type: "Page",
          title: "Company Financial Settings",
          subtitle: "GST, PAN, books start, statutory settings",
          url: "/fam/settings",
        },

        {
          type: "Page",
          title: "Financial Years",
          subtitle: "Open, close, and lock books periods",
          url: "/fam/financial-years",
        },

        {
          type: "Page",
          title: "Chart of Accounts",
          subtitle: "Ledger groups and ledgers",
          url: "/fam/chart-of-accounts",
        },

        {
          type: "Page",
          title: "Opening Balances",
          subtitle: "Balanced debit and credit opening entries",
          url: "/fam/opening-balances",
        },

        {
          type: "Page",
          title: "Voucher Types",
          subtitle: "Voucher categories and numbering",
          url: "/fam/voucher-types",
        },

        {
          type: "Page",
          title: "Vouchers",
          subtitle: "Draft, post, cancel, reverse, and clone vouchers",
          url: "/fam/vouchers",
        },

        {
          type: "Page",
          title: "Journal",
          subtitle: "Double-entry journal voucher screen",
          url: "/fam/journal",
        },

        {
          type: "Page",
          title: "Day Book",
          subtitle: "Voucher register and debit/credit totals",
          url: "/fam/day-book",
        },

        {
          type: "Page",
          title: "Ledger Entries",
          subtitle: "Immutable ledger postings",
          url: "/fam/ledger-entries",
        },

        {
          type: "Page",
          title: "Customers",
          subtitle: "Customer ledgers, statements, and receivables",
          url: "/fam/customers",
        },

        {
          type: "Page",
          title: "Vendors",
          subtitle: "Vendor ledgers, statements, and payables",
          url: "/fam/vendors",
        },

        {
          type: "Page",
          title: "AR Aging",
          subtitle: "Receivable aging buckets",
          url: "/fam/ar/aging",
        },

        {
          type: "Page",
          title: "AP Aging",
          subtitle: "Payable aging buckets",
          url: "/fam/ap/aging",
        },

        {
          type: "Page",
          title: "Bill References",
          subtitle: "Bill-wise tracking",
          url: "/fam/bill-references",
        },

        {
          type: "Page",
          title: "Bill Allocations",
          subtitle: "Receipt/payment allocations",
          url: "/fam/bill-allocations",
        },

        {
          type: "Page",
          title: "SRM Accounting Integration",
          subtitle: "Post SRM invoices, receipts, allocations, and reversals",
          url: "/fam/integrations/srm",
        },

        {
          type: "Page",
          title: "Posting Jobs",
          subtitle: "SRM to FAM posting queue and retries",
          url: "/fam/posting-jobs",
        },

        {
          type: "Page",
          title: "Posting Rules",
          subtitle: "Ledger rules for SRM accounting postings",
          url: "/fam/posting-rules",
        },

        {
          type: "Page",
          title: "Banking",
          subtitle:
            "Bank accounts, statements, reconciliation, bank book, cash book",
          url: "/fam/banking",
        },

        {
          type: "Page",
          title: "India GST",
          subtitle:
            "GST registrations, rates, HSN/SAC, returns, e-invoice and e-way bill",
          url: "/fam/gst",
        },

        {
          type: "Page",
          title: "Bank Accounts",
          subtitle: "Bank masters linked to FAM ledgers",
          url: "/fam/bank-accounts",
        },

        {
          type: "Page",
          title: "Payment Modes",
          subtitle: "Cash, cheque, NEFT, RTGS, UPI, card, wallet",
          url: "/fam/payment-modes",
        },

        {
          type: "Page",
          title: "Bank Statements",
          subtitle: "Manual CSV import and matching",
          url: "/fam/bank-statements",
        },

        {
          type: "Page",
          title: "Bank Reconciliation",
          subtitle: "Book balance, statement balance, unreconciled items",
          url: "/fam/bank-reconciliation",
        },

        {
          type: "Page",
          title: "Bank Book",
          subtitle: "Bank ledger voucher postings",
          url: "/fam/bank-book",
        },

        {
          type: "Page",
          title: "Cash Book",
          subtitle: "Cash ledger voucher postings",
          url: "/fam/cash-book",
        },

        {
          type: "Page",
          title: "Contra",
          subtitle: "Bank/cash transfers through contra vouchers",
          url: "/fam/contra",
        },

        {
          type: "Page",
          title: "Bank Charges",
          subtitle: "Post bank fees through payment vouchers",
          url: "/fam/bank-charges",
        },

        {
          type: "Page",
          title: "Accounting Audit",
          subtitle: "Setup and chart audit logs",
          url: "/fam/audit",
        },

        ...wowResults,
      ];
    }

    return [
      { type: "Page", title: "HRMS Dashboard", url: "/hrms" },

      {
        type: "Page",
        title: "Payroll",
        subtitle: "Run, pre-checks, payslips",
        url: "/hrms/payroll",
      },

      {
        type: "Page",
        title: "ESS Profile",
        subtitle: "Photo, completeness, change requests",
        url: "/hrms/profile",
      },

      {
        type: "Page",
        title: "Talent",
        subtitle: "OKR, 360, competencies",
        url: "/hrms/performance",
      },

      {
        type: "Page",
        title: "Org Chart",
        subtitle: "Company hierarchy",
        url: "/hrms/company",
      },

      ...wowResults,
    ];
  }, [product.key]);

  const recordSearch = useQuery({
    queryKey: [
      "command-pms",
      user?.id,
      user?.access?.companyId,
      debouncedQuery,
    ],
    enabled:
      open &&
      product.key === "project_management" &&
      debouncedQuery.length >= 2,
    retry: false,

    queryFn: async () => {
      const responses = await Promise.allSettled([
        api.get("/project-management/tasks", {
          params: { search: debouncedQuery, pageSize: 8 },
        }),

        api.get("/project-management/projects"),

        api.get("/project-management/users/search", {
          params: { q: debouncedQuery, limit: 5 },
        }),
      ]);
      const found: Result[] = [];

      const tasks = responses[0];
      if (tasks.status === "fulfilled")
        for (const task of tasks.value.data.items || [])
          found.push({
            type: "Task",
            title: task.title,
            subtitle: task.task_key,
            url: `/pms/tasks/${task.id}`,
          });

      const projects = responses[1];
      if (projects.status === "fulfilled")
        for (const project of projects.value.data
          .filter((p: { name: string; project_key: string }) =>
            `${p.name} ${p.project_key}`
              .toLowerCase()
              .includes(debouncedQuery.toLowerCase()),
          )
          .slice(0, 5))
          found.push({
            type: "Project",
            title: project.name,
            subtitle: project.project_key,
            url: `/pms/projects/${project.id}`,
          });

      const people = responses[2];
      if (people.status === "fulfilled")
        for (const person of people.value.data)
          found.push({
            type: "Person",
            title: person.email,
            url: "/pms/teams",
          });
      return found;
    },
  });

  const pageSources: Result[] = [
    ...[
      { type: "Page", title: "All applications", url: "/dashboard" },
      { type: "Page", title: "Notifications", url: "/notifications" },
      { type: "Page", title: "My account", url: "/account" },
      { type: "Page", title: "Help & support", url: "/help" },
    ],
    ...modules.map((p) => ({ type: "Module", title: p.name, url: p.homePath })),
    ...getRoleNav(user?.role, user?.is_superuser, location.pathname).map(
      (p) => ({ type: "Page", title: p.label, url: p.to }),
    ),
    ...staticResults,
  ];

  const filteredPages = pageSources.filter(
    (item) =>
      !query.trim() ||
      `${item.title} ${item.subtitle || ""}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );

  const results: Result[] = Array.from(
    new Map(
      [
        ...filteredPages,
        ...(enabled ? data?.results || [] : []),
        ...(recordSearch.data || []),
      ]
        .filter((item) =>
          canAccessRoute(item.url, user?.role, user?.is_superuser),
        )
        .map((item) => [item.url + item.title, item]),
    ).values(),
  ).slice(0, 35);

  useEffect(() => {
    setFocusedIndex(-1);
  }, [query]);

  useEffect(() => {
    if (focusedIndex >= 0)
      document
        .getElementById(`suite-command-result-${focusedIndex}`)
        ?.scrollIntoView({ block: "nearest" });
  }, [focusedIndex]);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 300);

    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();

        setOpen(true);
      }

      if (event.altKey && event.key.toLowerCase() === "h")
        navigate(product.homePath);

      if (event.key === "Escape") setOpen(false);
    };

    window.addEventListener("keydown", onKey);

    return () => window.removeEventListener("keydown", onKey);
  }, [navigate, product.homePath]);

  function submit(event: FormEvent) {
    event.preventDefault();

    const selected =
      (focusedIndex >= 0 ? results[focusedIndex] : undefined) || results[0];

    if (selected) {
      navigate(selected.url);

      setOpen(false);
    }
  }

  function handleSearchKeyDown(event: ReactKeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();

      setFocusedIndex((current) =>
        results.length ? (current + 1) % results.length : -1,
      );
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();

      setFocusedIndex((current) =>
        results.length ? (current <= 0 ? results.length - 1 : current - 1) : -1,
      );
    }
  }

  return (
    <>
      <button
        type="button"
        aria-label="Open command palette"
        className="relative hidden max-w-md flex-1 sm:flex"
        onClick={() => setOpen(true)}
      >
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />

        <span className="flex h-10 w-full items-center rounded-lg border border-input bg-muted/40 pl-9 pr-16 text-left text-sm text-muted-foreground">
          <span className="truncate">Search tasks, projects, people…</span>
        </span>
        <kbd
          aria-hidden="true"
          className="absolute right-3 top-3 text-xs text-muted-foreground"
        >
          Ctrl K
        </kbd>
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

      <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
          <Dialog.Content className="kf-command-dialog">
            <Dialog.Title className="px-4 pt-4 text-sm font-semibold">
              Search Business Suite
            </Dialog.Title>
            <p className="px-4 pt-1 text-xs text-muted-foreground">
              Applications and authorized pages · Records in HRMS and PMS
            </p>
            <Dialog.Close
              className="absolute right-2 top-2 grid h-11 w-11 place-items-center rounded-md"
              aria-label="Close search"
            >
              ×
            </Dialog.Close>
            <Dialog.Description className="sr-only">
              Search authorized pages and records. Use arrow keys to choose and
              Enter to open.
            </Dialog.Description>

            <div>
              <form onSubmit={submit} className="border-b p-3">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />

                  <Input
                    autoFocus
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={handleSearchKeyDown}
                    role="combobox"
                    aria-expanded={open}
                    aria-controls="suite-command-results"
                    aria-autocomplete="list"
                    aria-activedescendant={
                      focusedIndex >= 0
                        ? `suite-command-result-${focusedIndex}`
                        : undefined
                    }
                    aria-label="Search authorized applications and pages"
                    placeholder="Search applications, pages, and supported records…"
                    className="border-0 pl-9 text-base focus-visible:ring-0"
                  />
                </div>
              </form>

              {recordSearch.isFetching && (
                <p
                  className="px-4 py-2 text-xs text-muted-foreground"
                  role="status"
                >
                  Searching records…
                </p>
              )}

              <div
                id="suite-command-results"
                role="listbox"
                aria-label="Search results"
                className="max-h-[calc(100dvh-13rem)] overflow-y-auto p-2 sm:max-h-[420px]"
              >
                {results.length ? (
                  results.map((item, index) => (
                    <button
                      key={`${item.type}-${item.title}-${index}`}
                      id={`suite-command-result-${index}`}
                      role="option"
                      aria-selected={focusedIndex === index}
                      className={`flex w-full items-center justify-between rounded-md p-3 text-left hover:bg-muted ${focusedIndex === index ? "bg-accent" : ""}`}
                      onClick={() => {
                        navigate(item.url);

                        setOpen(false);
                      }}
                    >
                      <div>
                        <p className="text-sm font-medium">{item.title}</p>

                        <p className="text-xs text-muted-foreground">
                          {item.subtitle || item.type}
                        </p>
                      </div>

                      <span className="rounded bg-muted px-2 py-1 text-[10px] font-semibold uppercase text-muted-foreground">
                        {item.type}
                      </span>
                    </button>
                  ))
                ) : (
                  <div className="p-8 text-center text-sm text-muted-foreground">
                    No results found
                  </div>
                )}
              </div>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
