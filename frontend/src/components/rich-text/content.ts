import DOMPurify from "dompurify";
import { marked } from "marked";

export const RICH_TEXT_PREFIX = "<!--suite-richtext:v1-->";
export const fontFamilies = ["Inter", "Arial", "Georgia", "Times New Roman", "Courier New"];
export const fontSizes = ["12px", "14px", "16px", "18px", "20px", "24px", "32px", "40px"];
export const safeLink = (url: string) => /^(https?:\/\/|mailto:)[^\s<>]+$/i.test(url);
const allowedTags = ["p","br","h1","h2","h3","h4","h5","h6","strong","b","em","i","u","s","del","span","mark","a","ul","ol","li","blockquote","pre","code","hr","table","thead","tbody","tr","th","td","colgroup","col","label","input"];
export function sanitizeRichHtml(html: string): string {
  const clean = DOMPurify.sanitize(html, { ALLOWED_TAGS: allowedTags,
    ALLOWED_ATTR: ["href","target","rel","style","colspan","rowspan","data-indent","data-note-image","data-type","data-checked","type","checked"],
    ALLOW_DATA_ATTR: false, FORBID_TAGS: ["script","style","iframe","object","embed","img","svg","math"] });
  const template = document.createElement("template"); template.innerHTML = clean;
  template.content.querySelectorAll("[data-note-image]").forEach(element => {
    if (element.tagName !== "P" || !/^[1-9][0-9]*$/.test(element.getAttribute("data-note-image") || "")) element.removeAttribute("data-note-image");
  });
  template.content.querySelectorAll("a").forEach(element => {
    if (!safeLink(element.getAttribute("href") || "")) element.removeAttribute("href");
    element.setAttribute("rel", "noopener noreferrer");
  });
  template.content.querySelectorAll("input").forEach(element => {
    if (element.getAttribute("type") !== "checkbox") element.remove();
    else element.setAttribute("disabled", "");
  });
  template.content.querySelectorAll<HTMLElement>("[style]").forEach(element => {
    const prior = element.style;
    const values: Record<string, string> = {};
    if (["normal","400","500","bold","600","700","800","900"].includes(prior.fontWeight)) values["font-weight"] = prior.fontWeight;
    if (prior.fontStyle === "italic") values["font-style"] = "italic";
    if (["underline","line-through"].includes(prior.textDecorationLine)) values["text-decoration"] = prior.textDecorationLine;
    if (fontFamilies.includes(prior.fontFamily.replace(/["']/g, ""))) values["font-family"] = prior.fontFamily;
    if (fontSizes.includes(prior.fontSize)) values["font-size"] = prior.fontSize;
    for (const key of ["color", "background-color"]) {
      const value = prior.getPropertyValue(key);
      if (/^(#[a-f0-9]{3,8}|rgba?\([\d\s,.%]+\)|[a-z]+)$/i.test(value)) values[key] = value;
    }
    if (["left","center","right","justify"].includes(prior.textAlign)) values["text-align"] = prior.textAlign;
    const indent = Number(element.getAttribute("data-indent"));
    if (Number.isInteger(indent) && indent > 0 && indent <= 6) values["margin-left"] = `${indent * 24}px`;
    element.removeAttribute("style");
    Object.entries(values).forEach(([key,value]) => element.style.setProperty(key,value));
  });
  return template.innerHTML;
}
export function contentToHtml(value = "", legacyFormat: "markdown" | "plain" | "html" = "markdown"): string {
  if (!value) return "";
  if (value.startsWith(RICH_TEXT_PREFIX)) return sanitizeRichHtml(value.slice(RICH_TEXT_PREFIX.length));
  if (legacyFormat === "html") return sanitizeRichHtml(value);
  if (legacyFormat === "plain") {
    const element = document.createElement("div"); element.textContent = value;
    return `<p>${element.innerHTML.replace(/\n/g,"<br>")}</p>`;
  }
  // Legacy Markdown is parsed structurally, never by replacing punctuation.
  return sanitizeRichHtml(marked.parse(value, { gfm: true, breaks: false, async: false }));
}
export function richTextPlainText(value = ""): string {
  const template = document.createElement("template"); template.innerHTML = contentToHtml(value);
  template.content.querySelectorAll("p,h1,h2,h3,h4,li,tr,blockquote,pre").forEach(element => element.append("\n"));
  template.content.querySelectorAll("br").forEach(element => element.replaceWith("\n"));
  return (template.content.textContent || "").replace(/\u00a0/g," ").trim();
}

export function insertRichMention(value: string, name: string): string {
  const template = document.createElement("template"); template.innerHTML = contentToHtml(value);
  const walker = document.createTreeWalker(template.content, NodeFilter.SHOW_TEXT);
  let node: Node | null, last: Node | null = null;
  while ((node = walker.nextNode())) last = node;
  if (last) last.textContent = (last.textContent || "").replace(/@[\w.\-+ ]*$/, `@${name} `);
  return RICH_TEXT_PREFIX + sanitizeRichHtml(template.innerHTML);
}

export function appendRichMarkdown(value: string, markdown: string): string {
  return RICH_TEXT_PREFIX + contentToHtml(value) + contentToHtml(markdown, "markdown");
}

export function downloadRichDocument(value: string, title: string): void {
  const escape = (text: string) => { const element = document.createElement("span"); element.textContent = text; return element.innerHTML; };
  const html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escape(title)}</title><style>body{font:16px/1.65 Arial,sans-serif;max-width:900px;margin:40px auto;padding:20px;color:#172033}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd3df;padding:8px}th{background:#f1f3f8}blockquote{border-left:3px solid #8b5cf6;padding-left:16px}pre{white-space:pre-wrap;background:#f1f3f8;padding:16px}img,table{max-width:100%}</style></head><body><h1>${escape(title)}</h1>${contentToHtml(value)}</body></html>`;
  const url = URL.createObjectURL(new Blob([html], { type: "text/html;charset=utf-8" }));
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = `${(title || "document").replace(/[^a-zA-Z0-9_-]/g,"_").slice(0,80)}.html`; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url),1000);
}
