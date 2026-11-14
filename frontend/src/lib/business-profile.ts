import catalog from '../../../backend/app/core/business_profiles.json';

export type TermKey = keyof typeof catalog.terms;
export type TermPair = [string, string];
export type ProfileValues = { business_type?: string; terms?: Partial<Record<TermKey, TermPair>> };
export type ResolvedProfile = { business_type: string; terms: Record<TermKey, TermPair> };
export { catalog as businessProfileCatalog };

/** Explicit concept keys only: never replace arbitrary user-authored text. */
export function resolveBusinessProfile(layers: ProfileValues[]): ResolvedProfile {
  let business_type = 'general';
  let overrides: ProfileValues['terms'] = {};
  for (const layer of layers) {
    business_type = layer.business_type ?? business_type;
    overrides = { ...overrides, ...layer.terms };
  }
  const template = catalog.profiles.find(profile => profile.id === business_type) ?? catalog.profiles[0];
  return { business_type, terms: { ...catalog.terms, ...template.terms, ...overrides } as ResolvedProfile['terms'] };
}

export function profileTerm(profile: ResolvedProfile, key: TermKey, plural = false): string {
  return profile.terms[key][plural ? 1 : 0];
}
