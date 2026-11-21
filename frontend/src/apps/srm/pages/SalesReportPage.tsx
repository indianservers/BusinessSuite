import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { MobileSheet } from "@/components/mobile/MobilePrimitives";
import { useMobile } from "@/components/mobile/useMobile";
import { useRecordScope } from "@/lib/record-scope";
import { api } from "@/services/api";
import { catalogError, money } from "@/shared/catalog/api";
import "@/shared/catalog/catalog.css";

const tabs = [
  { kind: "", label: "All sales" },
  { kind: "product", label: "Products" },
  { kind: "service", label: "Services" },
  { kind: "membership", label: "Memberships" },
  { kind: "subscription", label: "Subscriptions" },
] as const;

const labels = {
  product: "Product", service: "Service", membership: "Membership",
  subscription: "Subscription", bundle: "Bundle", other: "Other",
} as const;

type Report = {
  start: string;
  end: string;
  has_more: boolean;
  totals: { currency: string; gross: string }[];
  items: { kind: keyof typeof labels; name: string; currency: string; quantity: number; tax: string; gross: string }[];
};

export default function SalesReportPage() {
  const scope = useRecordScope();
  return <SalesReport key={scope} scope={scope}/>;
}

function SalesReport({ scope }: { scope: string }) {
  const phone = useMobile(480);
  const [datesOpen, setDatesOpen] = useState(false);
  const [kind, setKind] = useState<(typeof tabs)[number]["kind"]>("");
  const [dates, setDates] = useState({ start: "", end: "" });
  const [draftDates, setDraftDates] = useState<typeof dates | null>(null);
  const [page, setPage] = useState(1);
  const report = useQuery({
    queryKey: ["srm", "offering-sales", scope, kind, dates, page],
    queryFn: async ({ signal }) => {
      const response = await api.get<Report>("/srm/reporting/offering-sales", {
        params: { kind: kind || undefined, start: dates.start || undefined, end: dates.end || undefined, page },
        signal,
        recordCache: false,
      });
      return response.data;
    },
  });

  const fields = draftDates ?? { start: dates.start || report.data?.start || "", end: dates.end || report.data?.end || "" };
  const updateDate = (field: "start" | "end", value: string) => setDraftDates({ ...fields, [field]: value });
  const dateForm = (
    <form className={phone ? "grid gap-3" : "flex flex-wrap items-end gap-3"} onSubmit={event => {
      event.preventDefault();
      setDates(fields);
      setPage(1);
      setDatesOpen(false);
    }}>
      <label className="grid gap-1 text-sm">From<Input type="date" required value={fields.start} max={fields.end || undefined} onChange={event => updateDate("start", event.target.value)}/></label>
      <label className="grid gap-1 text-sm">To<Input type="date" required value={fields.end} min={fields.start || undefined} onChange={event => updateDate("end", event.target.value)}/></label>
      <Button type="submit">Apply dates</Button>
      <Button type="button" variant="outline" onClick={() => { setDraftDates(null); setDates({ start: "", end: "" }); setPage(1); setDatesOpen(false); }}>Last 30 days</Button>
    </form>
  );

  return <div className="sc-page space-y-4">
    <header className="sc-hero">
      <div><h1>Sales Report<span><BarChart3 size={23}/></span></h1><p>Issued invoice lines by offering. Sales amounts include tax.</p></div>
    </header>

    {phone ? (
      <label className="grid gap-1 text-sm font-medium">
        Offering type
        <NativeSelect className="min-h-11 text-base" value={kind} onChange={event => {
          setKind(event.target.value as (typeof tabs)[number]["kind"]);
          setPage(1);
        }}>
          {tabs.map(tab => <option key={tab.kind} value={tab.kind}>{tab.label}</option>)}
        </NativeSelect>
      </label>
    ) : <div className="sc-catalog-bar">
      <div className="sc-tabs" role="group" aria-label="Offering type">
        {tabs.map(tab => <button key={tab.kind} type="button" aria-pressed={kind === tab.kind} onClick={() => {
          setKind(tab.kind);
          setPage(1);
        }}>{tab.label}</button>)}
      </div>
    </div>}

    {phone ? (
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" className="min-h-11" aria-haspopup="dialog" onClick={() => setDatesOpen(true)}>Report dates</Button>
        {report.data && <p className="text-sm text-muted-foreground">{report.data.start} – {report.data.end}</p>}
        <MobileSheet title="Report dates" open={datesOpen} onClose={() => { setDraftDates(null); setDatesOpen(false); }}>{dateForm}</MobileSheet>
      </div>
    ) : dateForm}

    {report.isPending && <p role="status">Loading sales…</p>}
    {report.isError && <div role="alert" className="flex flex-wrap items-center gap-2">
      <span>{catalogError(report.error)}</span>
      <Button variant="outline" onClick={() => void report.refetch()}>Retry</Button>
    </div>}
    {report.data && (report.data.items.length === 0 ? <p>No sales found for this period.</p> : <>
      <div className="flex flex-wrap gap-3" aria-label="Sales totals">
        {report.data.totals.map(total => <div key={total.currency} className="rounded-lg border bg-card px-4 py-2">
          <span className="mr-2 text-sm text-muted-foreground">Total sales · {total.currency}</span>
          <strong>{money(Number(total.gross), total.currency)}</strong>
        </div>)}
      </div>
      {phone ? (
        <ul aria-label="Sales by offering and currency" className="grid gap-2">
          {report.data.items.map((item, index) => (
            <li className="grid min-w-0 gap-2 rounded-lg border bg-card p-3" key={index}>
              <div className="flex flex-wrap justify-between gap-x-3 gap-y-1">
                <h2 className="min-w-0 break-words text-sm font-semibold">{item.name}</h2>
                <strong className="text-sm tabular-nums">{money(Number(item.gross), item.currency)}</strong>
              </div>
              <dl className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                <div><dt className="sr-only">Type and currency</dt><dd>{labels[item.kind]} · {item.currency}</dd></div>
                <div><dt className="inline">Quantity </dt><dd className="inline font-medium text-foreground">{item.quantity.toLocaleString(undefined, { maximumFractionDigits: 10 })}</dd></div>
                <div><dt className="inline">Tax </dt><dd className="inline font-medium text-foreground">{money(Number(item.tax), item.currency)}</dd></div>
              </dl>
            </li>
          ))}
        </ul>
      ) : <div className="overflow-x-auto rounded-lg border bg-card">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Sales by offering and currency</caption>
          <thead><tr className="border-b bg-muted/50">
            {["Offering", "Type", "Currency", "Quantity", "Tax", "Sales"].map(label => <th key={label} scope="col" className="px-3 py-2">{label}</th>)}
          </tr></thead>
          <tbody>{report.data.items.map((item, index) => <tr className="border-b last:border-0" key={index}>
            <th scope="row" className="px-3 py-2 font-medium">{item.name}</th>
            <td className="px-3 py-2">{labels[item.kind]}</td>
            <td className="px-3 py-2">{item.currency}</td>
            <td className="px-3 py-2">{item.quantity.toLocaleString(undefined, { maximumFractionDigits: 10 })}</td>
            <td className="whitespace-nowrap px-3 py-2">{money(Number(item.tax), item.currency)}</td>
            <td className="whitespace-nowrap px-3 py-2 font-semibold">{money(Number(item.gross), item.currency)}</td>
          </tr>)}</tbody>
        </table>
      </div>}
    </>)}
    {report.data && (page > 1 || report.data.has_more) && <nav className="flex items-center gap-3" aria-label="Sales report pages">
      <Button variant="outline" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</Button>
      <span>Page {page}</span>
      <Button variant="outline" disabled={!report.data.has_more || page >= 10000} onClick={() => setPage(page + 1)}>Next</Button>
    </nav>}
  </div>;
}
