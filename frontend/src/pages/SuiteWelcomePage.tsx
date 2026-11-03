import { modules } from "@/lib/moduleCatalog";
import PremiumLauncher from "@/components/suite/PremiumLauncher";
export default function SuiteWelcomePage() {
  return <PremiumLauncher applications={modules} />;
}
