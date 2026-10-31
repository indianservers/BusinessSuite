export type OrgPerson = {
  id: number;
  name: string;
  display_name: string;
  email: string;
  job_title: string;
  role: string;
  manager_id: number | null;
  teams: { id: number; name: string }[];
};
export type OrgData = {
  positions?: Record<string, { x: number; y: number }>;
  revision: number;
  can_manage: boolean;
  people: OrgPerson[];
  teams: { id: number; name: string }[];
};
export type OrgNode = {
  person: OrgPerson;
  x: number;
  y: number;
  depth: number;
  children: number[];
};
export const CARD_W = 240,
  CARD_H = 122,
  GAP_X = 32,
  GAP_Y = 70;
export function layoutChart(
  people: OrgPerson[],
  collapsed: Set<number>,
  mode: string,
  team: number,
) {
  const byId = new Map(people.map((p) => [p.id, p]));
  const included = new Set<number>();
  for (const p of people)
    if (!team || p.teams.some((t) => t.id === team)) {
      let cursor: OrgPerson | undefined = p;
      const seen = new Set<number>();
      while (cursor && !seen.has(cursor.id)) {
        included.add(cursor.id);
        seen.add(cursor.id);
        cursor = byId.get(cursor.manager_id!);
      }
    }
  const children = new Map<number, number[]>();
  const roots: number[] = [];
  for (const p of people)
    if (included.has(p.id)) {
      const parent = included.has(p.manager_id!) ? p.manager_id : null;
      if (parent == null) roots.push(p.id);
      else children.set(parent, [...(children.get(parent) || []), p.id]);
    }
  const order: { id: number; depth: number }[] = [];
  const seen = new Set<number>();
  const stack = roots
    .slice()
    .reverse()
    .map((id) => ({ id, depth: 0 }));
  while (stack.length) {
    const n = stack.pop()!;
    if (seen.has(n.id)) continue;
    seen.add(n.id);
    order.push(n);
    if (!collapsed.has(n.id))
      for (const id of [...(children.get(n.id) || [])].reverse())
        stack.push({ id, depth: n.depth + 1 });
  }
  const widths = new Map<number, number>();
  for (const n of [...order].reverse()) {
    const kids = collapsed.has(n.id) ? [] : children.get(n.id) || [];
    widths.set(
      n.id,
      Math.max(
        CARD_W,
        kids.reduce((sum, id) => sum + (widths.get(id) || CARD_W), 0) +
          Math.max(0, kids.length - 1) * GAP_X,
      ),
    );
  }
  let width = Math.max(
    roots.reduce((sum, id) => sum + (widths.get(id) || CARD_W), 0) +
      Math.max(0, roots.length - 1) * GAP_X +
      80,
    400,
  );
  const offsets = new Map<number, number>();
  let left = 40;
  for (const id of roots) {
    offsets.set(id, left);
    left += (widths.get(id) || CARD_W) + GAP_X;
  }
  const nodes: OrgNode[] = [];
  for (const n of order) {
    const w = widths.get(n.id) || CARD_W;
    const x = (offsets.get(n.id) || 40) + (w - CARD_W) / 2;
    nodes.push({
      person: byId.get(n.id)!,
      x,
      y: 40 + n.depth * (CARD_H + GAP_Y),
      depth: n.depth,
      children: children.get(n.id) || [],
    });
    let start = offsets.get(n.id) || 40;
    for (const id of children.get(n.id) || []) {
      offsets.set(id, start);
      start += (widths.get(id) || CARD_W) + GAP_X;
    }
  }
  if (mode === "levels") {
    const levels = new Map<number, OrgNode[]>();
    for (const n of nodes)
      levels.set(n.depth, [...(levels.get(n.depth) || []), n]);
    width = Math.max(
      400,
      ...[...levels.values()].map(
        (row) => row.length * (CARD_W + GAP_X) - GAP_X + 80,
      ),
    );
    for (const row of levels.values()) {
      const start = (width - (row.length * (CARD_W + GAP_X) - GAP_X)) / 2;
      row.forEach((n, i) => (n.x = start + i * (CARD_W + GAP_X)));
    }
  }
  const height = Math.max(300, ...nodes.map((n) => n.y + CARD_H + 70));
  return { nodes, width, height };
}
export function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0])
    .join("")
    .toUpperCase();
}
export const colors = [
  "#7c3aed",
  "#0891b2",
  "#db2777",
  "#059669",
  "#d97706",
  "#2563eb",
];
export function exportFile(content: string, name: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function chartSVG(nodes: OrgNode[], width: number, height: number) {
  const esc = (s: string) =>
    s.replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&apos;",
        })[c]!,
    );
  const map = new Map(nodes.map((n) => [n.person.id, n]));
  const edges = nodes
    .flatMap((n) => {
      const p = map.get(n.person.manager_id!);
      return p
        ? [
            `<path d="M${p.x + 120} ${p.y + CARD_H}V${n.y - 35}H${n.x + 120}V${n.y}" fill="none" stroke="#c4b5fd" stroke-width="2"/>`,
          ]
        : [];
    })
    .join("");
  const cards = nodes
    .map(
      (n) =>
        `<g transform="translate(${n.x} ${n.y})"><rect width="240" height="122" rx="14" fill="white" stroke="#ddd6fe"/><circle cx="30" cy="32" r="18" fill="${colors[n.person.id % colors.length]}"/><text x="30" y="37" text-anchor="middle" fill="white" font-size="12">${esc(initials(n.person.name))}</text><text x="58" y="30" font-size="13" font-weight="bold">${esc(n.person.name.slice(0, 23))}</text><text x="58" y="49" font-size="11" fill="#6b7280">${esc((n.person.job_title || n.person.role).slice(0, 27))}</text><text x="16" y="85" font-size="10" fill="#6b7280">${esc(n.person.email.slice(0, 35))}</text><text x="16" y="108" font-size="10" fill="#7c3aed">${n.children.length} direct reports</text></g>`,
    )
    .join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" font-family="Arial,sans-serif"><rect width="100%" height="100%" fill="#faf9ff"/>${edges}${cards}</svg>`;
}
