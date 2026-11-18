/** Presentation only; authorization, taxes, stock and scheduling remain server-owned. */
type POSPresentation = { title: string; catalogue: string; bill: string };
const general: POSPresentation = { title: 'POS Terminal', catalogue: 'Products & services', bill: 'Current sale' };
const packs: Record<string, POSPresentation> = {
  general, entrepreneur: general, retail: general, salon: general, saloon: general,
  hospital: { title: 'Billing & POS', catalogue: 'Consultations & services', bill: 'Current bill' },
  pharma: { title: 'POS Terminal', catalogue: 'Medicines & services', bill: 'Current sale' },
  automotive: { title: 'POS Terminal', catalogue: 'Parts & services', bill: 'Current sale' },
  auto_service: { title: 'POS Terminal', catalogue: 'Parts & services', bill: 'Current sale' },
};
export function posPresentation(pack: string | null | undefined): POSPresentation { return packs[pack || 'general'] || general; }
