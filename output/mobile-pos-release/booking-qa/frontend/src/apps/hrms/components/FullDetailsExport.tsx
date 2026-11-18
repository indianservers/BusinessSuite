import { useState } from "react";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/store/authStore";
import { api } from "@/services/api";
import { toast } from "@/hooks/use-toast";

export default function FullDetailsExport({ endpoint, params, filename }: {
  endpoint: string; params: Record<string, unknown>; filename: string;
}) {
  const isSuperAdmin = useAuthStore(state => state.user?.is_superuser === true);
  const [busy, setBusy] = useState(false);
  if (!isSuperAdmin) return null;
  return <Button variant="outline" disabled={busy} onClick={async () => {
    setBusy(true);
    try {
      const response = await api.get(endpoint, { params, responseType: "blob", timeout: 300000 });
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      toast({ title: "Full-details export failed", description: "Check your Super Admin access and try again.", variant: "destructive" });
    } finally { setBusy(false); }
  }}><Download className="mr-2 h-4 w-4" />{busy ? "Exporting…" : "Export all details (Excel)"}</Button>;
}
