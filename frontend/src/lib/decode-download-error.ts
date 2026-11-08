/** Axios blob responses also wrap JSON errors; retain their recovery message. */
export async function decodeDownloadError(error: unknown): Promise<unknown> {
  const response = (error as { response?: { data?: unknown } } | null)?.response;
  if (typeof Blob !== "undefined" && response?.data instanceof Blob) {
    try {
      const data: unknown = JSON.parse(await response.data.text());
      return { response: { ...response, data } };
    } catch { /* Fall back to the caller's normal network-error formatter. */ }
  }
  return error;
}
