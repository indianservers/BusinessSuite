import { useEffect, useLayoutEffect } from "react";
import { useLocation, useNavigationType } from "react-router-dom";
import { useMobile } from "./useMobile";
import { useAuthStore } from "@/store/authStore";
import "./mobile-experience.css";

// Only annotate existing controls: React retains their handlers, values and permissions.
export default function MobileExperience() {
  const mobile = useMobile(); const location = useLocation(); const navigation = useNavigationType();
  const user = useAuthStore(state => state.user);
  useLayoutEffect(() => {
    if (!mobile || !/^\/(crm|pms|srm|hrms)(\/|$)/.test(location.pathname)) return;
    document.body.classList.add("mobile-experience");
    const key = `mobile-position:${user?.id}:${user?.access?.companyId}:${location.pathname}${location.search}`;
    let saved: { top: number; left: number } | undefined;
    try { saved = JSON.parse(sessionStorage.getItem(key) || "null") || undefined; } catch { /* Storage can be unavailable in private browsing. */ }
    const scrollElement = () => document.querySelector<HTMLElement>("#suite-main,.mobile-dock-tasks") || document.scrollingElement as HTMLElement;
    let restored = navigation !== "POP" || !saved;
    const restore = () => { if (restored || !saved) return; const element = scrollElement(); if (element) { element.scrollTop = saved.top; element.scrollLeft = saved.left; restored = element.scrollTop >= saved.top - 2; } };
    const annotate = () => {
      document.querySelectorAll<HTMLTableElement>(".kf-main table,.mobile-dock-fullscreen table").forEach(table => {
        if (table.closest('[role="grid"],.recharts-wrapper') || table.dataset.mobileCards === "false") return;
        const headers = Array.from(table.querySelectorAll("thead tr:last-child th")).map(th => th.textContent?.trim() || "Select");
        if (!headers.length) return;
        table.classList.add("mobile-record-table");
        table.querySelectorAll<HTMLTableRowElement>("tbody > tr").forEach(row => Array.from(row.cells).forEach((cell, index) => { const label = cell.colSpan > 1 ? "" : headers[index] || "Details"; if (cell.dataset.mobileLabel !== label) cell.dataset.mobileLabel = label; }));
      });
      document.querySelectorAll<HTMLElement>('form > div:has(> button[type="submit"]),form > footer,.lead-create-footer,.sc-form-footer').forEach(footer => footer.classList.add("mobile-form-actions"));
      restore();
    };
    annotate(); let frame = 0;
    const observer = new MutationObserver(() => { cancelAnimationFrame(frame); frame = requestAnimationFrame(annotate); });
    observer.observe(document.getElementById("root") || document.body, { childList: true, subtree: true });
    return () => { observer.disconnect(); cancelAnimationFrame(frame); const element = scrollElement(); if (element && restored) { try { sessionStorage.setItem(key, JSON.stringify({ top: element.scrollTop, left: element.scrollLeft })); } catch { /* No persistence if browser storage is disabled. */ } } document.body.classList.remove("mobile-experience"); };
  }, [mobile, location.pathname, location.search, navigation, user?.id, user?.access?.companyId]);
  useEffect(() => {
    if (!mobile) return;
    const viewport = window.visualViewport;
    const update = () => { const inset = Math.max(0, innerHeight - (viewport?.height || innerHeight) - (viewport?.offsetTop || 0)); document.documentElement.style.setProperty("--mobile-keyboard-inset", `${inset}px`); document.body.classList.toggle("mobile-keyboard-open", inset > 140); const active = document.activeElement; if (inset > 140 && active instanceof HTMLElement && active.matches("input,textarea,select")) active.scrollIntoView({ block: "nearest" }); };
    const focus = () => window.setTimeout(update, 120);
    viewport?.addEventListener("resize", update); viewport?.addEventListener("scroll", update); document.addEventListener("focusin", focus); update();
    return () => { viewport?.removeEventListener("resize", update); viewport?.removeEventListener("scroll", update); document.removeEventListener("focusin", focus); document.body.classList.remove("mobile-keyboard-open"); document.documentElement.style.removeProperty("--mobile-keyboard-inset"); };
  }, [mobile]);
  return null;
}
