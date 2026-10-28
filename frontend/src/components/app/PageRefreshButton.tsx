import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "@/hooks/use-toast";
import { refreshPageData, usePageRefreshing } from "@/lib/page-refresh";
import { isRefreshablePage } from "@/lib/refresh-pages";

export default function PageRefreshButton({ compact = false, always = false }: { compact?: boolean; always?: boolean }) {
  const { pathname } = useLocation();
  const client = useQueryClient();
  const busy = usePageRefreshing();
  const [updated, setUpdated] = useState("");
  useEffect(() => setUpdated(""), [pathname]);
  if (!always && !isRefreshablePage(pathname)) return null;
  return <Button type="button" variant="outline" size={compact ? "icon" : "sm"}
    className="shrink-0"
    aria-label={busy ? "Refreshing page data" : "Refresh page data"} aria-busy={busy}
    title={updated ? `Refresh page data · Last refreshed ${updated}` : "Refresh page data"}
    disabled={busy} onClick={async () => {
      try {
        await refreshPageData(client);
        setUpdated(new Date().toLocaleTimeString());
      } catch (error) {
        toast({ title: "Refresh incomplete", description: (error as Error).message, variant: "destructive" });
      }
    }}>
    <RefreshCw aria-hidden="true" className={`h-4 w-4 ${busy ? "animate-spin" : ""}`}/>
    {!compact && <span>{busy ? "Refreshing…" : "Refresh"}</span>}
  </Button>;
}
