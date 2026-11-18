import type { CatalogLine } from "@/shared/catalog/api";

const cents = (value: number) => Math.round((value + Number.EPSILON) * 100) / 100;
export function salesOrderLineAmounts(line: CatalogLine) {
  const subtotal = cents(line.quantity * line.unit_price);
  const discount = cents(subtotal * line.discount / 100);
  const tax = cents((subtotal - discount) * (line.tax_rate ?? line.item?.tax ?? 0) / 100);
  return { subtotal, discount, tax, total: cents(subtotal - discount + tax) };
}
export function salesOrderInput(order: { title: string; customer_id: string; currency: string; expected_start_date: string; expected_end_date: string; terms: string }, selected: CatalogLine[]) {
  if (!order.title.trim()) throw new Error("Sales order title is required.");
  const customer = Number(order.customer_id);
  if (!Number.isSafeInteger(customer) || customer <= 0) throw new Error("Choose a customer before creating the sales order.");
  if (!selected.length) throw new Error("Select at least one product or service.");
  if (order.expected_start_date && order.expected_end_date && order.expected_start_date > order.expected_end_date) throw new Error("Start date cannot be after end date.");
  const lines = selected.map((line, index) => {
    const label = line.name || `Line ${index + 1}`;
    if (!Number.isSafeInteger(line.item_id) || line.item_id <= 0) throw new Error(`${label}: select a catalog item.`);
    if (!Number.isFinite(line.quantity) || line.quantity <= 0) throw new Error(`${label}: quantity must be greater than zero.`);
    if (!Number.isFinite(line.unit_price) || line.unit_price < 0) throw new Error(`${label}: unit price cannot be negative.`);
    if (!Number.isFinite(line.discount) || line.discount < 0 || line.discount > 100) throw new Error(`${label}: discount must be between 0 and 100.`);
    const rate = line.tax_rate ?? line.item?.tax ?? 0;
    if (!Number.isFinite(rate) || rate < 0 || rate > 100) throw new Error(`${label}: tax must be between 0 and 100.`);
    if ((line.currency || order.currency) !== order.currency) throw new Error(`${label}: choose an item priced in ${order.currency}.`);
    const { discount, tax, total } = salesOrderLineAmounts(line);
    return { product_id: line.item_id, item_code: line.item?.code, description: line.name || line.item?.name || "", service_type: line.kind, quantity: line.quantity, unit_price: line.unit_price, discount_amount: discount, tax_amount: tax, line_total: total };
  });
  const subtotal = cents(lines.reduce((sum, line) => sum + cents(line.quantity * line.unit_price), 0));
  const discount_amount = cents(lines.reduce((sum, line) => sum + line.discount_amount, 0));
  const tax_amount = cents(lines.reduce((sum, line) => sum + line.tax_amount, 0));
  return { title: order.title.trim(), customer_id: customer, currency: order.currency, subtotal, discount_amount, tax_amount, total_amount: cents(subtotal - discount_amount + tax_amount), expected_start_date: order.expected_start_date || undefined, expected_end_date: order.expected_end_date || undefined, terms: order.terms, lines };
}
