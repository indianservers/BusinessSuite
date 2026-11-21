import { ArrowUpRight, MessageCircle, UserRound } from "lucide-react";
import { Link } from "react-router-dom";
import { usePageTitle } from "@/hooks/use-page-title";

const destinations = [
  {
    title: "HR messages",
    description: "Open the HR communication workspace and check available channels.",
    href: "/hrms/messages",
    icon: MessageCircle,
  },
  {
    title: "Employee self-service",
    description: "Open leave, attendance, payslips, and other employee services.",
    href: "/hrms/ess",
    icon: UserRound,
  },
];

export default function WhatsAppESSPage() {
  usePageTitle("WhatsApp ESS");

  return (
    <main className="space-y-4">
      <header className="rounded-2xl border bg-gradient-to-br from-primary/10 via-card to-card p-4 sm:p-6">
        <h1 className="page-title">WhatsApp ESS</h1>
        <p className="page-description">Employee support and self-service shortcuts.</p>
      </header>
      <nav aria-label="Employee support" className="grid gap-3 sm:grid-cols-2">
        {destinations.map(({ title, description, href, icon: Icon }) => (
          <Link key={href} to={href} className="group flex min-w-0 gap-3 rounded-xl border bg-card p-4 transition-colors hover:border-primary/50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
              <Icon size={18} aria-hidden="true" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block font-semibold group-hover:text-primary">{title}</span>
              <span className="mt-1 block text-sm text-muted-foreground">{description}</span>
            </span>
            <ArrowUpRight className="shrink-0 text-muted-foreground" size={16} aria-hidden="true" />
          </Link>
        ))}
      </nav>
    </main>
  );
}
