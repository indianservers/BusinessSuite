export function dateInputInZone(iso: string, zone: string) {
  try {
    new Intl.DateTimeFormat("en", { timeZone: zone });
  } catch {
    return new Date(iso).toISOString().slice(0, 16);
  }
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: zone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(iso));
  const p = Object.fromEntries(parts.map((x) => [x.type, x.value]));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}
export function dateInputToIso(input: string, zone: string) {
  new Intl.DateTimeFormat("en", { timeZone: zone });
  const target = Date.parse(input + "Z");
  let instant = target;
  for (let i = 0; i < 4; i++) {
    const represented = Date.parse(
      dateInputInZone(new Date(instant).toISOString(), zone) + "Z",
    );
    const delta = target - represented;
    if (!delta) break;
    instant += delta;
  }
  const result = new Date(instant).toISOString();
  if (dateInputInZone(result, zone) !== input)
    throw new Error(
      "This local time does not exist in the selected time zone. Choose another time.",
    );
  return result;
}
