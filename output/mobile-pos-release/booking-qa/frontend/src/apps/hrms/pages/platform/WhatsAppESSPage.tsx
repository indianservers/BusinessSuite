import { MessageCircle } from "lucide-react";
import { usePageTitle } from "@/hooks/use-page-title";
import ModuleShell from "@/components/ModuleShell";

export default function WhatsAppESSPage() {
  usePageTitle("WhatsApp ESS");
  return (
    <ModuleShell
      title="WhatsApp ESS"
      description="WhatsApp self-service configuration, opt-ins, templates, inbound messages, and delivery callbacks."
      icon={MessageCircle}
      metrics={[
        { label: "Templates", value: "Ready" },
        { label: "Opt-ins", value: "Tracked" },
        { label: "Messages", value: "Queued" },
      ]}
      items={[
        { title: "Business configuration", description: "Configure WhatsApp sender and webhook settings", status: "Active" },
        { title: "Employee opt-ins", description: "Maintain employee consent and phone mapping", status: "Active" },
        { title: "ESS messages", description: "Route leave, payslip, attendance, and policy requests", status: "Active" },
      ]}
    />
  );
}
