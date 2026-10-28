import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { getUploadsBaseUrl } from "@/config/runtime";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function assetUrl(path?: string | null): string | undefined {
  if (!path) return undefined;
  if (path.startsWith("http")) return path;
  return `${getUploadsBaseUrl()}${path}`;
}

export function formatCurrency(amount: number, currency = "INR"): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

/** Preserve currency minor units on payroll and expense statements. */
export function formatCurrencyPrecise(amount: number, currency = "INR"): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency }).format(amount);
}

export function formatDate(date: string | Date | null): string {
  if (!date) return "-";
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(date));
}

export function formatDateTime(date: string | Date | null): string {
  if (!date) return "-";
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(date));
}

export function getInitials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

export function statusColor(status: string): string {
  const map: Record<string, string> = {
    Active: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
    Inactive: "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400",
    Pending: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
    Approved: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
    Rejected: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
    Cancelled: "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400",
    Draft: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
    Locked: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400",
    Open: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
    Closed: "bg-gray-100 text-gray-800",
    High: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
    Medium: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
    Low: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
    Critical: "bg-red-200 text-red-900 dark:bg-red-900/50 dark:text-red-300",
    Present: "bg-green-100 text-green-800",
    Absent: "bg-red-100 text-red-800",
    "Half-day": "bg-orange-100 text-orange-800",
    WFH: "bg-blue-100 text-blue-800",
    Holiday: "bg-purple-100 text-purple-800",
    Resigned: "bg-orange-100 text-orange-800",
    Terminated: "bg-red-100 text-red-800",
  };
  return map[status] || "bg-gray-100 text-gray-800";
}

export function calculateAge(dob: string | null): number | null {
  if (!dob) return null;
  const today = new Date();
  const birth = new Date(dob);
  let age = today.getFullYear() - birth.getFullYear();
  const m = today.getMonth() - birth.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) age--;
  return age;
}

export function debounce<T extends (...args: unknown[]) => void>(fn: T, delay: number): T {
  let timer: ReturnType<typeof setTimeout>;
  return ((...args: unknown[]) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  }) as T;
}

