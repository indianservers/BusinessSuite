export type Category = 'email' | 'inventory' | 'mail_merge';
import type { BlockType, DesignBlock } from '@/shared/template-design/types';
export type { BlockType } from '@/shared/template-design/types';
export type Block = DesignBlock;
export type Template = { id?: number; name: string; category: Category; document_type: string; module: string; subject: string; folder: string; status: 'draft' | 'ready'; version: number; design: { blocks: Block[]; accent: string; background: string; font: string }; email_template_id?: number };
export type Field = { group: string; key: string; label: string; sample: string };
export type Rendered = { html: string; body: string; blocks: { id: string; html: string }[]; subject: string; unresolved: string[] };
export const categories: { key: Category; label: string; description: string }[] = [
  { key: 'email', label: 'Email', description: 'Welcome messages, follow-ups, reminders, invitations and updates.' },
  { key: 'inventory', label: 'Business documents', description: 'Invoices, quotations, sales orders and purchase orders.' },
  { key: 'mail_merge', label: 'Mail merge', description: 'Letters, agreements, forms, address labels and envelopes.' },
];
export const types: Record<Category, { key: string; label: string }[]> = {
  email: [{ key: 'email', label: 'Email' }],
  inventory: [{ key: 'invoice', label: 'Invoice' }, { key: 'quotation', label: 'Quotation' }, { key: 'sales_order', label: 'Sales order' }, { key: 'purchase_order', label: 'Purchase order' }],
  mail_merge: [{ key: 'letter', label: 'Letter' }, { key: 'agreement', label: 'Agreement' }, { key: 'form', label: 'Form' }, { key: 'label', label: 'Address label' }, { key: 'envelope', label: 'Envelope' }],
};
export const blockLabels: Record<BlockType, string> = { brand: 'Brand header', heading: 'Heading', text: 'Text', image: 'Logo / image', button: 'Button', divider: 'Divider', spacer: 'Spacing', items: 'Line items', totals: 'Totals', signature: 'Signature', columns: 'Columns' };
export function block(type: BlockType, text?: string): Block {
  const defaults: Record<BlockType, string> = { brand: '{{organization.name}}', heading: 'A heading that makes an impression', text: 'Hello {{name}},\nAdd your message here. Use placeholders to personalize each copy.', image: 'Company logo', button: 'Explore more', divider: '', spacer: '', items: '', totals: '', signature: '{{sender}}\n{{sender_title}}', columns: 'Your first highlight\nA useful benefit or next step.\n---\nYour second highlight\nSupporting details for your customer.' };
  return { id: crypto.randomUUID(), type, text: text ?? defaults[type], url: type === 'button' ? 'https://example.com' : '', align: 'left', size: type === 'heading' ? 32 : type === 'brand' ? 18 : 14, color: '#243047', bold: false, padding: 12 };
}
export function starter(category: Category, documentType?: string, name?: string, message?: string): Template {
  const type = documentType || types[category][0].key;
  const title = types[category].find(t => t.key === type)?.label || 'Email';
  let blocks: Block[];
  if (category === 'email') blocks = [block('brand', 'YOUR COMPANY'), block('divider'), block('heading', name || 'Welcome aboard, {{name}}'), block('text', message || 'Hi {{name}},\n\nThank you for choosing us. We look forward to helping {{company}} achieve its goals.\n\nReply to this email whenever you need a hand.'), block('button', 'Get started'), block('text', 'Warm regards,\nYour customer success team')];
  else if (category === 'inventory') blocks = [block('brand'), block('text', '{{organization.address}}\n{{organization.email}} · {{organization.phone}}\nTax / GST: {{organization.tax_id}}'), block('divider'), block('heading', title.toUpperCase()), block('text', 'Reference: {{document.number}}\nIssued: {{document.date}}\nDue / valid until: {{document.due_date}}'), block('text', (type === 'purchase_order' ? 'SUPPLIER' : 'BILL TO') + '\n{{name}}\n{{company}}\n{{address}}'), block('items'), block('totals'), block('text', '{{document.terms}}'), block('signature')];
  else if (type === 'label' || type === 'envelope') blocks = [block('text', 'FROM\n{{organization.name}}\n{{organization.address}}'), block('spacer'), block('heading', '{{name}}'), block('text', '{{company}}\n{{address}}')];
  else blocks = [block('brand'), block('text', '{{organization.address}}\n{{organization.email}}'), block('divider'), block('heading', type === 'agreement' ? 'Service agreement' : type === 'form' ? 'Customer information form' : 'A letter to {{name}}'), block('text', 'Date: {{document.date}}\nTo: {{name}}\n{{company}}\n{{address}}'), block('text', type === 'agreement' ? 'This agreement is between {{organization.name}} and {{company}}, effective {{contract.start_date}} through {{contract.end_date}}.\n\nScope of services: {{product}}\n\nAdd the agreed responsibilities, commercial terms and termination provisions here.' : type === 'form' ? 'Full name: {{name}}\nEmail address: {{email}}\nPhone number: {{phone}}\nCompany: {{company}}\n\nAdditional information: ______________________\n\nConsent / signature: ______________________' : 'Dear {{name}},\n\nThank you for your continued partnership with {{organization.name}}. We are pleased to share this personalized update with you.\n\nAdd the details of your letter here.'), block('signature')];
  return { name: name || (category === 'email' ? 'Welcome email' : `${title} · Modern`), category, document_type: type, module: 'contact', subject: category === 'email' ? 'Welcome, {{name}} — let’s get started' : '', folder: 'General', status: 'draft', version: 1, design: { accent: '#6554c0', background: '#ffffff', font: 'Arial', blocks } };
}
export function presets(category: Category): Template[] {
  if (category !== 'email') return types[category].map(t => starter(category, t.key));
  return [starter('email'),
    starter('email', 'email', 'Sales follow-up', 'Hi {{name}},\n\nIt was lovely speaking with you about the needs of {{company}}. Would you have time this week to discuss the next steps?\n\nLooking forward to hearing from you.'),
    starter('email', 'email', 'Payment reminder', 'Hi {{name}},\n\nA friendly reminder that your payment is due soon. Please contact our accounts team if you need a copy of your invoice.\n\nThank you for your business.'),
    starter('email', 'email', 'Meeting invitation', 'Hi {{name}},\n\nWe would love to meet with the team at {{company}}. Please reply with a suitable time and we will send you an invitation.'),
    starter('email', 'email', 'Thank you', 'Hi {{name}},\n\nThank you for trusting us. We appreciate your partnership and look forward to working together again.'),
    starter('email', 'email', 'Product announcement', 'Hello {{name}},\n\nWe have something new to share with {{company}}. Discover our latest product improvements and tell us what you think.')];
}
export function payload(t: Template) {
  return { name: t.name, category: t.category, document_type: t.document_type, module: t.module, subject: t.subject, folder: t.folder, status: t.status, version: t.version, design: t.design };
}
