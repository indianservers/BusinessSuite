/** A browser permission prompt must not leave the calling action busy forever. */
export async function writeClipboard(text: string, timeoutMs = 10000): Promise<void> {
  if (!navigator.clipboard?.writeText) {
    throw new Error("Clipboard access is unavailable. Use CSV export instead.");
  }
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    await Promise.race([
      navigator.clipboard.writeText(text),
      new Promise<never>((_, reject) => {
        timer = setTimeout(() => reject(new Error("Clipboard access was not confirmed. Try again or use CSV export.")), timeoutMs);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}
