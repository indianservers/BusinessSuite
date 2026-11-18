/** Business meaning takes precedence over priority, IDs, dates and monetary columns. */
export type BusinessColumn = {id: string; title: string; groupable?: boolean};
export function businessGroupColumn<T extends BusinessColumn>(columns: T[], scope: string): T | undefined {
  const available = columns.filter(column => column.groupable !== false && !/priority/i.test(column.title));
  const preferred = /(?:^|[/:])hrms(?:[/:]|$)|apps\/hrms/i.test(scope)
    ? [/^department(?: name)?$/i, /^(status|employment status|approval status)$/i, /^type$/i]
    : /(?:leads|crm)/i.test(scope)
      ? [/^(stage|lead stage|pipeline stage)$/i, /^status$/i, /^department$/i]
      : [/^(status|state|approval status|billing status)$/i, /^stage$/i, /^department$/i];
  for (const pattern of [...preferred, /^(category|type|team|group|module)$/i, /^(owner|assignee|assigned to)$/i]) {
    const column = available.find(column => pattern.test(column.title.trim()));
    if (column) return column;
  }
}
export function initialBusinessGroups(columns: BusinessColumn[], scope: string, grouping: string[] | undefined, migrated: boolean): string[] {
  const preferred = businessGroupColumn(columns, scope);
  if (!preferred || migrated) return grouping || [];
  if (!grouping?.length || grouping.every(id => /priority/i.test(columns.find(column => column.id === id)?.title || ""))) return [preferred.id];
  return grouping;
}
