import type { CRMApiRecord } from "../api";

const missing = (value: unknown) => value === "" || value === undefined || value === null;
export function changeDealCompany(draft: CRMApiRecord, companyId: string): CRMApiRecord {
  if (String(draft.companyId || "") === companyId) return draft;
  return { ...draft, companyId, contactId: "", related_contacts: [] };
}
export function fillEmptyDealFields(draft: CRMApiRecord, suggestions: CRMApiRecord): CRMApiRecord {
  const next = { ...draft };
  for (const [key, value] of Object.entries(suggestions)) if (missing(next[key]) && !missing(value)) next[key] = value;
  return next;
}
export function prefillDealCompany(draft: CRMApiRecord, company: CRMApiRecord): CRMApiRecord {
  if (String(draft.companyId) !== String(company.id)) return draft;
  const contacts = Array.isArray(company.contacts) ? company.contacts as CRMApiRecord[] : [];
  const primary = company.primaryContactId || company.primary_contact_id || (contacts.length === 1 ? contacts[0].id : undefined);
  return fillEmptyDealFields(draft, { name: company.name ? `${company.name} opportunity` : undefined, industry: company.industry, contactId: primary });
}
export function prefillDealLead(draft: CRMApiRecord, lead: CRMApiRecord, companies: CRMApiRecord[], contacts: CRMApiRecord[]): CRMApiRecord {
  const companyName = String(lead.company_name || lead.companyName || lead.company || "");
  const companyMatches = companies.filter(company => String(company.name || "").trim().toLocaleLowerCase() === companyName.trim().toLocaleLowerCase());
  const email = String(lead.email || "").trim().toLocaleLowerCase();
  const contactMatches = email ? contacts.filter(contact => String(contact.email || "").trim().toLocaleLowerCase() === email) : [];
  const companyId = lead.converted_company_id || lead.convertedCompanyId || (companyName && companyMatches.length === 1 ? companyMatches[0].id : undefined);
  const contact = contacts.find(contact => String(contact.id) === String(lead.converted_contact_id || lead.convertedContactId)) || (contactMatches.length === 1 ? contactMatches[0] : undefined);
  const effectiveCompany = draft.companyId || companyId || contact?.companyId || contact?.company_id;
  const contactCompany = contact?.companyId || contact?.company_id;
  return fillEmptyDealFields(draft, {
    name: `${companyName || lead.full_name || lead.fullName || lead.name || "New"} opportunity`,
    companyId: effectiveCompany,
    contactId: contact && (!effectiveCompany || !contactCompany || String(effectiveCompany) === String(contactCompany)) ? contact.id : undefined,
    source: lead.source || lead.lead_source, industry: lead.industry,
    amount: lead.estimated_value ?? lead.estimatedValue,
    expectedCloseDate: String(lead.expected_close_date || lead.expectedCloseDate || "").slice(0, 10),
    description: lead.notes || lead.description,
  });
}
