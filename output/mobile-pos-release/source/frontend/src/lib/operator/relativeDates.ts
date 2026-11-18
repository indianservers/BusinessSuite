export type DateContext = { now?: Date; timezone?: string };
export function resolveLocalDate(input: string, context: DateContext = {}): string | null {
  const text = input.toLowerCase().trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) {
    const d = new Date(`${text}T00:00:00Z`);
    return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === text ? text : null;
  }
  let parts: Intl.DateTimeFormatPart[];
  try { parts = new Intl.DateTimeFormat('en-CA', { timeZone: context.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone,
    year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(context.now || new Date()); } catch { return null; }
  const part = (type: string) => Number(parts.find(p => p.type === type)?.value);
  const date = new Date(Date.UTC(part('year'), part('month')-1, part('day')));
  const add = (days: number) => { date.setUTCDate(date.getUTCDate()+days); return date.toISOString().slice(0,10); };
  if (text === 'today') return add(0);
  if (text === 'tomorrow') return add(1);
  if (text === 'next week') return add((8-date.getUTCDay()) % 7 || 7);
  let match = text.match(/^in ([1-9]\d{0,2}) (days?|weeks?|business days?)$/);
  if (match) {
    let days = Number(match[1]);
    if (match[2].startsWith('business')) {
      while (days) { add(1); if (![0,6].includes(date.getUTCDay())) days--; }
      return add(0);
    }
    return add(days*(match[2].startsWith('week') ? 7 : 1));
  }
  match = text.match(/^next (sunday|monday|tuesday|wednesday|thursday|friday|saturday)$/);
  if (match) return add((['sunday','monday','tuesday','wednesday','thursday','friday','saturday'].indexOf(match[1])-date.getUTCDay()+7)%7 || 7);
  return null;
}
