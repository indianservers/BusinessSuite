/** Keep server validation payloads out of React's child renderer. */
export function collectionFormError(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.flatMap(item => {
      if (!item || typeof item !== 'object' || typeof item.msg !== 'string') return [];
      const field = Array.isArray(item.loc) ? item.loc.slice(-1)[0] : undefined;
      return [typeof field === 'string' ? `${field.replace(/_/g, ' ')}: ${item.msg}` : item.msg];
    });
    if (messages.length) return messages.join('. ');
  }
  if (detail && typeof detail === 'object' && 'message' in detail && typeof detail.message === 'string') return detail.message;
  return fallback;
}

export function localReceiptDate(now = new Date()): string {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}
