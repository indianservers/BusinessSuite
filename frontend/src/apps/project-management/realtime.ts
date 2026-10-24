import { useEffect, useRef } from "react";
import { create } from "zustand";
import { notificationsMuted } from "@/store/personalStore";
import { toast } from "@/hooks/use-toast";
import { api } from "@/services/api";
import { getApiBaseUrl } from "@/config/runtime";
import { useAuthStore } from "@/store/authStore";

export type PMSRealtimeEvent = {
  id?: string;
  type: string;
  organizationId?: number | null;
  projectId?: number | null;
  taskId?: number | null;
  sprintId?: number | null;
  actor?: { id?: number; name?: string; email?: string } | string;
  action?: string;
  target?: string;
  message?: string;
  entity?: Record<string, unknown>;
  data?: Record<string, unknown>;
  projectIds?: number[];
  taskIds?: number[];
  createdAt: string;
};

type RealtimeState = {
  events: PMSRealtimeEvent[];
  onlineUsers: string[];
  connected: boolean;
  receive: (event: PMSRealtimeEvent) => void;
  publish: (event: { actor: string; action: string; target: string }) => void;
  setConnected: (connected: boolean) => void;
};

const CHANNEL = "karyaflow-realtime";
const channel = typeof window !== "undefined" && "BroadcastChannel" in window ? new BroadcastChannel(CHANNEL) : null;

function actorName(actor: PMSRealtimeEvent["actor"]) {
  return typeof actor === "string" ? actor : actor?.name;
}

export const useRealtimeStore = create<RealtimeState>((set, get) => ({
  events: [],
  onlineUsers: [],
  connected: false,
  receive: (event) => {
    const name = actorName(event.actor);
    const onlineUsers = event.type === "user.presence" && name
      ? Array.from(new Set([name, ...get().onlineUsers])).slice(0, 20)
      : get().onlineUsers;
    const normalized = {
      ...event,
      id: event.id || `${event.type}-${event.createdAt}-${event.taskId || event.projectId || Math.random()}`,
      action: event.action || event.type.replace("task.", "").replace("_", " "),
      target: event.target || event.message || "",
    };
    if (get().events.some(existing => existing.id === normalized.id)) return;
    set({ events: [normalized, ...get().events].slice(0, 50), onlineUsers });
  },
  publish: (event) => {
    const fullEvent: PMSRealtimeEvent = {
      ...event,
      id: crypto.randomUUID(),
      type: "local.activity",
      actor: event.actor,
      message: `${event.actor} ${event.action}`,
      createdAt: new Date().toISOString(),
    };
    set({ events: [fullEvent, ...get().events].slice(0, 50) });
    channel?.postMessage(fullEvent);
  },
  setConnected: (connected) => set({ connected }),
}));

channel?.addEventListener("message", (message) => {
  useRealtimeStore.getState().receive(message.data as PMSRealtimeEvent);
});

function wsUrl(token: string) {
  const apiBase = getApiBaseUrl();
  const base = apiBase.startsWith("http")
    ? apiBase
    : `${window.location.origin}${apiBase.startsWith("/") ? apiBase : `/${apiBase}`}`;
  const url = new URL(`${base.replace(/\/$/, "")}/project-management/realtime`);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.searchParams.set("token", token);
  return url.toString();
}

export function usePMSRealtime({
  projectId,
  taskId,
  onEvent,
  onFallbackPoll,
  pollIntervalMs = 45000,
  showToast = true,
  enabled = true,
}: {
  projectId?: number | null;
  taskId?: number | null;
  onEvent?: (event: PMSRealtimeEvent) => void;
  onFallbackPoll?: () => void;
  pollIntervalMs?: number;
  showToast?: boolean;
  enabled?: boolean;
}) {
  const token = useAuthStore((state) => state.accessToken);
  const onEventRef = useRef(onEvent);
  const pollRef = useRef(onFallbackPoll);

  useEffect(() => {
    onEventRef.current = onEvent;
    pollRef.current = onFallbackPoll;
  }, [onEvent, onFallbackPoll]);

  useEffect(() => {
    if (!token || !enabled) return;
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    let closedByEffect = false;
    let feedTimer: ReturnType<typeof setTimeout> | null = null;
    let feedCursor: number | undefined;
    let feedTicks = 0;

    const subscribe = () => {
      if (!socket || socket.readyState !== WebSocket.OPEN) return;
      socket.send(JSON.stringify({
        action: "subscribe",
        projectIds: projectId ? [projectId] : [],
        taskIds: taskId ? [taskId] : [],
      }));
      if (projectId) {
        socket.send(JSON.stringify({
          action: "presence",
          projectId,
          taskId: taskId || undefined,
          state: "viewing",
          message: taskId ? "Viewing task" : "Viewing project",
        }));
      }
    };

    const startPolling = () => {
      if (!pollRef.current || pollTimer) return;
      pollTimer = setInterval(() => pollRef.current?.(), pollIntervalMs);
    };

    const stopPolling = () => {
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = null;
    };

    const connect = () => {
      try {
        socket = new WebSocket(wsUrl(token));
      } catch {
        startPolling();
        return;
      }
      socket.onopen = () => {
        useRealtimeStore.getState().setConnected(true);
        stopPolling();
        subscribe();
      };
      socket.onmessage = (message) => {
        const event = JSON.parse(message.data) as PMSRealtimeEvent;
        useRealtimeStore.getState().receive(event);
        if (!["connected", "subscribed", "user.presence"].includes(event.type)) {
          onEventRef.current?.(event);
          const name = actorName(event.actor);
          if (showToast && name && !notificationsMuted(useAuthStore.getState().user?.id)) {
            toast({ title: event.message || "PMS updated", description: `By ${name}` });
          }
        }
      };
      socket.onerror = () => {
        useRealtimeStore.getState().setConnected(false);
        startPolling();
      };
      socket.onclose = () => {
        useRealtimeStore.getState().setConnected(false);
        startPolling();
        if (!closedByEffect) reconnectTimer = setTimeout(connect, 5000);
      };
    };

    const pollFeed = async () => {
      try {
        const { data } = await api.get<{ cursor: number; events: PMSRealtimeEvent[] }>("/project-management/realtime/events", {
          params: feedCursor === undefined ? {} : { cursor: feedCursor },
        });
        if (closedByEffect) return;
        feedCursor = data.cursor;
        useRealtimeStore.getState().setConnected(true);
        for (const event of data.events) {
          if (projectId && event.projectId !== projectId) continue;
          if (taskId && event.taskId !== taskId) continue;
          useRealtimeStore.getState().receive(event);
          onEventRef.current?.(event);
        }
        // Also recover from a lost publish, tab suspension or expired retention.
        if (++feedTicks % 5 === 0) pollRef.current?.();
      } catch {
        useRealtimeStore.getState().setConnected(false);
        pollRef.current?.();
      } finally {
        if (!closedByEffect) feedTimer = setTimeout(pollFeed, document.hidden ? 15000 : 3000);
      }
    };
    void api.get<{ transport: string }>("/project-management/realtime/config")
      .then(({ data }) => {
        if (closedByEffect) return;
        if (data.transport === "database") void pollFeed();
        else connect();
      }).catch(() => { if (!closedByEffect) connect(); });

    return () => {
      closedByEffect = true;
      if (feedTimer) clearTimeout(feedTimer);
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (pollTimer) clearInterval(pollTimer);
      socket?.close();
    };
  }, [enabled, pollIntervalMs, projectId, showToast, taskId, token]);
}
