import type { BusinessPackChoice, BusinessPackDiscovery } from './business-pack-types';

/** Navigation hint only. The page rechecks native authority and server capabilities. */
function navigationChoice(discovery: BusinessPackDiscovery | undefined, branch: string | null, selector: string | null): BusinessPackChoice | undefined {
  if (!discovery || discovery.state !== 'ready' || discovery.hasMore !== false
      || discovery.selectionState === 'invalid' || !branch || !/^[1-9][0-9]*$/.test(branch)) return undefined;
  const eligible = discovery.contexts.filter(item => item.branchId === Number(branch));
  const selected = selector === null ? eligible.length === 1 ? eligible[0] : undefined
    : /^[1-9][0-9]*$/.test(selector) && discovery.selectionState === 'verified'
      && discovery.selectedContextId === Number(selector) ? eligible.find(item => item.contextId === Number(selector)) : undefined;
  return selected && [selected.contextId, selected.packVersion, selected.contextRevision, selected.grantRevision, selected.activationRevision]
    .every(value => Number.isSafeInteger(value) && value > 0) ? selected : undefined;
}

export function showRestaurantKitchen(discovery: BusinessPackDiscovery | undefined, branch: string | null, selector: string | null): boolean {
  const selected = navigationChoice(discovery, branch, selector);
  return Boolean(selected?.packKey === 'restaurant'
    && ['chef', 'server', 'cashier', 'restaurant_manager', 'business_owner'].includes(selected.role));
}

export function showAccountsPeriods(discovery: BusinessPackDiscovery | undefined, branch: string | null, selector: string | null): boolean {
  const selected = navigationChoice(discovery, branch, selector);
  return Boolean(selected?.packKey === 'accounting_firm'
    && ['preparer', 'reviewer', 'engagement_manager', 'business_owner'].includes(selected.role));
}

/** Keep the existing unselected suite menu; selected packs expose their own industry pages. */
export function allowConstructionNavigation(discovery: BusinessPackDiscovery | undefined, branch: string | null, selector: string | null): boolean {
  if (!discovery && selector === null) return true;
  if (discovery?.state === 'ready' && discovery.hasMore === false
      && discovery.contexts.length === 0 && discovery.selectorRequired === false
      && discovery.selectionState === 'none' && selector === null) return true;
  return navigationChoice(discovery, branch, selector)?.packKey === 'construction';
}
