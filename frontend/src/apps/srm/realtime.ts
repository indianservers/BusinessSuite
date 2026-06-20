import { useEffect } from "react";
import type { QueryClient } from "@tanstack/react-query";

const CHANNEL_NAME = "business-suite-srm-sync";
const STORAGE_KEY = "business-suite-srm-sync-event";

export type SRMSyncEvent = {
  type: "sales_order_changed" | "inventory_changed" | "pos_sale_completed" | "pos_return_completed";
  at: string;
  source?: string;
  ids?: Record<string, string | number | undefined>;
};

function invalidateSrm(queryClient: QueryClient) {
  queryClient.invalidateQueries({ queryKey: ["srm"] });
}

export function publishSrmSync(event: Omit<SRMSyncEvent, "at"> & { at?: string }) {
  const payload: SRMSyncEvent = { ...event, at: event.at || new Date().toISOString() };
  try {
    const channel = new BroadcastChannel(CHANNEL_NAME);
    channel.postMessage(payload);
    channel.close();
  } catch {
    // BroadcastChannel is optional; storage event below covers older browsers.
  }
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // Local storage can be disabled; same-tab invalidation still happens.
  }
}

export function useSrmRealtimeInvalidation(queryClient: QueryClient, enabled = true) {
  useEffect(() => {
    if (!enabled) return undefined;
    const onStorage = (event: StorageEvent) => {
      if (event.key === STORAGE_KEY && event.newValue) invalidateSrm(queryClient);
    };
    let channel: BroadcastChannel | null = null;
    try {
      channel = new BroadcastChannel(CHANNEL_NAME);
      channel.onmessage = () => invalidateSrm(queryClient);
    } catch {
      channel = null;
    }
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener("storage", onStorage);
      channel?.close();
    };
  }, [enabled, queryClient]);
}

export async function syncSrmNow(queryClient: QueryClient, event: Omit<SRMSyncEvent, "at">) {
  publishSrmSync(event);
  await queryClient.invalidateQueries({ queryKey: ["srm"] });
  await queryClient.refetchQueries({ queryKey: ["srm"], type: "active" });
}
