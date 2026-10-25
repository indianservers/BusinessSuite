import { api } from "./api";
import { useAuthStore } from "@/store/authStore";

/** Real SSE stages/results, not a simulated typewriter or invented progress. */
export async function assistantStream(
  path: string,
  payload: unknown,
  signal: AbortSignal,
  onStage: (stage: string) => void,
) {
  const token = useAuthStore.getState().accessToken;
  const response = await fetch(`${api.defaults.baseURL}${path}`, {
    method: "POST",
    signal,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw { response: { data: error, status: response.status } };
  }
  if (!response.body) throw new Error("Streaming connection unavailable");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: any;
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let boundary: number;
      while ((boundary = buffer.indexOf("\n\n")) >= 0) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const event = block.match(/^event: (.+)$/m)?.[1];
        const raw = block.match(/^data: (.+)$/m)?.[1];
        if (!raw) continue;
        const data = JSON.parse(raw);
        if (event === "status") onStage(data.stage);
        if (event === "failure")
          throw { response: { data, status: data.status } };
        if (event === "result") result = data;
      }
    }
  } finally {
    reader.releaseLock();
  }
  if (!result)
    throw new Error("The connection ended before an action result arrived");
  return { data: result };
}
