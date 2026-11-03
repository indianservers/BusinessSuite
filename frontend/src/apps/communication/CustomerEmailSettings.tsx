import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";

export default function CustomerEmailSettings() {
  const { toast } = useToast();
  const [form, setForm] = useState<Record<
    string,
    string | number | boolean
  > | null>(null);
  const query = useQuery({
    queryKey: ["customer-comms", "email-connection"],
    queryFn: () =>
      api.get("/communication/customers/email-connection").then((r) => r.data),
    retry: false,
  });
  const mutation = useMutation({
    mutationFn: (values: Record<string, string | number | boolean>) =>
      api.put("/communication/customers/email-connection", {
        ...values,
        password: values.password || null,
        reply_to: values.reply_to || null,
      }),
    onSuccess: () => {
      setForm(null);
      void query.refetch();
      toast({ title: "Business email connection saved" });
    },
    onError: () =>
      toast({
        title: "Could not save email connection",
        description:
          "Check the SMTP values and your administrator permissions.",
        variant: "destructive",
      }),
  });
  if (query.isError)
    return (
      <p className="text-sm text-muted-foreground">
        CRM administrator permission is required to configure business email.
      </p>
    );
  if (!query.data) return <p className="text-sm">Loading email connection…</p>;
  const values: Record<string, string | number | boolean> = form ?? {
    host: query.data.host ?? "",
    port: query.data.port ?? 587,
    username: query.data.username ?? "",
    password: "",
    from_email: query.data.from_email ?? "",
    from_name: query.data.from_name ?? "",
    reply_to: query.data.reply_to ?? "",
    active: query.data.active ?? true,
  };
  return (
    <div className="space-y-3 border-t pt-4">
      <h3 className="font-semibold">Business email connection</h3>
      <p className="text-sm text-muted-foreground">
        Current transport: {query.data.source} ·{" "}
        {query.data.configured ? "configured" : "not configured"}. SMTP
        credentials are encrypted. Use a provider-verified sender address.
      </p>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate(values);
        }}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          {[
            ["host", "SMTP host"],
            ["port", "TLS port (465 or 587)"],
            ["username", "SMTP username"],
            [
              "password",
              query.data.credentials_configured
                ? "New password (optional)"
                : "SMTP password",
            ],
            ["from_email", "Sender email"],
            ["from_name", "Sender name"],
            ["reply_to", "Reply-to email (optional)"],
          ].map(([key, title]) => (
            <label key={key} className="grid gap-1 text-sm">
              <span>{title}</span>
              <Input
                required={!["password", "reply_to"].includes(key)}
                type={
                  key === "password"
                    ? "password"
                    : key.includes("email") || key === "reply_to"
                      ? "email"
                      : key === "port"
                        ? "number"
                        : "text"
                }
                autoComplete={key === "password" ? "new-password" : "off"}
                value={String(values[key])}
                onChange={(e) =>
                  setForm({
                    ...values,
                    [key]:
                      key === "port" ? Number(e.target.value) : e.target.value,
                  })
                }
              />
            </label>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={Boolean(values.active)}
            onChange={(e) => setForm({ ...values, active: e.target.checked })}
          />
          Enable business SMTP connection
        </label>
        <Button disabled={mutation.isPending}>Save email connection</Button>
      </form>
      <Button
        variant="outline"
        onClick={async () => {
          try {
            const { data } = await api.post(
              "/communication/customers/email-connection/receiver-secret",
              {},
            );
            await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
            toast({
              title: "Email receiver credentials copied",
              description:
                "Configure your receiving-service adapter with these credentials. This replaces the previous secret.",
            });
          } catch {
            toast({
              title: "Could not configure email receiver",
              description: "Save an active business SMTP connection first.",
              variant: "destructive",
            });
          }
        }}
      >
        Generate / rotate email receiver credentials
      </Button>
    </div>
  );
}
