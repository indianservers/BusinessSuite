export function schedulingPhone(phone?: string, country?: string) {
  if (!phone) return '';
  const local = phone.replace(/\D/g,'');
  if (country?.replace(/\D/g,'')==='91' && local.length===10) return `+91 ${local.slice(0,5)} ${local.slice(5)}`;
  return phone.startsWith('+') ? phone : [country,phone].filter(Boolean).join(' ');
}
