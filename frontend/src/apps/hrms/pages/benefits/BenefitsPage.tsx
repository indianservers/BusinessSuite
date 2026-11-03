import { NativeSelect } from "@/components/ui/native-select";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Gift, HeartPulse, PiggyBank, Plus, RefreshCw, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { benefitsApi } from "@/services/api";
import { toast } from "@/hooks/use-toast";
import { usePageTitle } from "@/hooks/use-page-title";

type BenefitPlan = {
  id: number;
  name: string;
  plan_type: string;
  provider_name?: string;
  employer_contribution: string | number;
  employee_contribution: string | number;
  taxable: boolean;
};

type BenefitClaim = {
  id: number;
  employee_id: number;
  claim_type: string;
  claim_amount: string | number;
  approved_amount: string | number;
  status: string;
  claim_date: string;
};

type Enrollment = {
  id: number;
  employee_id: number;
  benefit_plan_id: number;
  coverage_level: string;
  status: string;
  start_date: string;
};

type EsopGrant = {
  id: number;
  employee_id: number;
  granted_units: string | number;
  vested_units: string | number;
  status: string;
};

const money = (value: string | number | undefined) =>
  Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });

export default function BenefitsPage() {
  usePageTitle("Benefits");
  const qc = useQueryClient();
  const [showPlanForm, setShowPlanForm] = useState(false);
  const [planForm, setPlanForm] = useState({
    name: "",
    plan_type: "Group Health",
    provider_name: "",
    employer_contribution: "0",
    employee_contribution: "0",
    payroll_component_code: "",
  });

  const { data: plans, isLoading: plansLoading } = useQuery({
    queryKey: ["benefits-plans"],
    queryFn: () => benefitsApi.plans().then((r) => r.data as BenefitPlan[]),
  });
  const { data: enrollments } = useQuery({
    queryKey: ["benefits-enrollments"],
    queryFn: () => benefitsApi.enrollments().then((r) => r.data as Enrollment[]),
  });
  const { data: claims } = useQuery({
    queryKey: ["benefits-claims"],
    queryFn: () => benefitsApi.claims().then((r) => r.data as BenefitClaim[]),
  });
  const { data: esopGrants } = useQuery({
    queryKey: ["benefits-esop-grants"],
    queryFn: () => benefitsApi.esopGrants().then((r) => r.data as EsopGrant[]),
  });

  const createPlan = useMutation({
    mutationFn: () =>
      benefitsApi.createPlan({
        ...planForm,
        employer_contribution: Number(planForm.employer_contribution || 0),
        employee_contribution: Number(planForm.employee_contribution || 0),
        taxable: false,
        is_active: true,
      }),
    onSuccess: () => {
      toast({ title: "Benefit plan created" });
      setShowPlanForm(false);
      setPlanForm({
        name: "",
        plan_type: "Group Health",
        provider_name: "",
        employer_contribution: "0",
        employee_contribution: "0",
        payroll_component_code: "",
      });
      qc.invalidateQueries({ queryKey: ["benefits-plans"] });
    },
    onError: () => toast({ title: "Unable to create benefit plan", variant: "destructive" }),
  });

  const pendingClaims = (claims || []).filter((claim) => claim.status === "Pending");
  const activeEnrollments = (enrollments || []).filter((row) => row.status === "Active");

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 rounded-lg border bg-card p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="page-title">Benefits Administration</h1>
          <p className="page-description">Manage group health, NPS, flexi-benefits, ESOP grants, claims, and payroll deductions.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => qc.invalidateQueries({ queryKey: ["benefits-plans"] })}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button size="sm" onClick={() => setShowPlanForm((value) => !value)}>
            <Plus className="mr-2 h-4 w-4" />
            New Plan
          </Button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { label: "Active Plans", value: plans?.length || 0, icon: HeartPulse },
          { label: "Enrollments", value: activeEnrollments.length, icon: ShieldCheck },
          { label: "Pending Claims", value: pendingClaims.length, icon: Gift },
          { label: "ESOP Grants", value: esopGrants?.length || 0, icon: PiggyBank },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <Card key={item.label}>
              <CardContent className="p-5">
                <Icon className="mb-3 h-5 w-5 text-primary" />
                <p className="text-2xl font-semibold">{item.value}</p>
                <p className="text-sm text-muted-foreground">{item.label}</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {showPlanForm && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Create Benefit Plan</CardTitle>
            <CardDescription>Plan definitions become the source for enrollments and payroll deductions.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label>Plan Name</Label>
              <Input value={planForm.name} onChange={(e) => setPlanForm({ ...planForm, name: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label>Type</Label>
              <NativeSelect className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={planForm.plan_type} onChange={(e) => setPlanForm({ ...planForm, plan_type: e.target.value })}>
                {["Group Health", "NPS", "Insurance", "Flexi", "Wellness"].map((type) => <option key={type}>{type}</option>)}
              </NativeSelect>
            </div>
            <div className="space-y-1.5">
              <Label>Provider</Label>
              <Input value={planForm.provider_name} onChange={(e) => setPlanForm({ ...planForm, provider_name: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label>Employer Contribution</Label>
              <Input type="number" value={planForm.employer_contribution} onChange={(e) => setPlanForm({ ...planForm, employer_contribution: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label>Employee Contribution</Label>
              <Input type="number" value={planForm.employee_contribution} onChange={(e) => setPlanForm({ ...planForm, employee_contribution: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label>Payroll Component</Label>
              <Input value={planForm.payroll_component_code} onChange={(e) => setPlanForm({ ...planForm, payroll_component_code: e.target.value })} placeholder="NPS_EMP" />
            </div>
            <div className="flex gap-2 sm:col-span-3">
              <Button disabled={!planForm.name || createPlan.isPending} onClick={() => createPlan.mutate()}>
                Save Plan
              </Button>
              <Button variant="outline" onClick={() => setShowPlanForm(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Benefit Plans</CardTitle>
            <CardDescription>Configured plans available for employee enrollment.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {plansLoading ? <div className="h-24 rounded-lg bg-muted/40" /> : plans?.length ? plans.map((plan) => (
              <div key={plan.id} className="grid gap-3 rounded-lg border p-4 sm:grid-cols-[1fr_auto] sm:items-center">
                <div>
                  <p className="font-medium">{plan.name}</p>
                  <p className="text-sm text-muted-foreground">{plan.plan_type} {plan.provider_name ? `- ${plan.provider_name}` : ""}</p>
                </div>
                <div className="text-sm text-muted-foreground sm:text-right">
                  <p>Employer INR {money(plan.employer_contribution)}</p>
                  <p>Employee INR {money(plan.employee_contribution)}</p>
                </div>
              </div>
            )) : <p className="rounded-lg border p-4 text-sm text-muted-foreground">No benefit plans configured.</p>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Claims Queue</CardTitle>
            <CardDescription>Latest claims waiting for payroll/HR review.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {(claims || []).slice(0, 6).map((claim) => (
              <div key={claim.id} className="rounded-lg border p-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-medium">{claim.claim_type}</p>
                  <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{claim.status}</span>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">Employee #{claim.employee_id} - INR {money(claim.claim_amount)}</p>
              </div>
            ))}
            {!claims?.length && <p className="rounded-lg border p-4 text-sm text-muted-foreground">No benefit claims yet.</p>}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
