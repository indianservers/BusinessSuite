export function wall(instant: number, zone: string) {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(instant);
  const part = (key: string) => parts.find(item => item.type === key)?.value || '';
  return `${part('year')}-${part('month')}-${part('day')}T${part('hour')}:${part('minute')}`;
}
export function candidates(value: string, zone: string) {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) return [];
  const nominal = Date.parse(`${value}:00Z`); if (!Number.isFinite(nominal)) return [];
  try {
    const offsets = new Set<number>();
    for (let hour = -36; hour <= 36; hour += 6) { const sample = nominal + hour * 3600000; offsets.add(Date.parse(`${wall(sample, zone)}:00Z`) - sample); }
    return [...offsets].map(offset => nominal - offset).filter(instant => wall(instant, zone) === value);
  } catch { return []; }
}

