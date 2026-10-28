import { safeSuiteDestination } from "./suiteNavigation";

export function loginDestination(value: string | null): string {
  return safeSuiteDestination(value) || "/dashboard";
}
