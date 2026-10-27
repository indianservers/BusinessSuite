// Every suite sign-in opens the authorized application dashboard.
// Legacy return parameters never select a separate module login or destination.
export function loginDestination(_value: string | null): string {
  return "/dashboard";
}
