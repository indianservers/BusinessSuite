import WorkforceInbox from "@/components/workforce/WorkforceInbox";
import { api } from "@/services/api";
const load = (page: number) => api.get("/project-management/operations/inbox", { params: { page } }).then(r => r.data);
const acknowledge = (id: number) => api.post(`/project-management/operations/inbox/${id}/acknowledge`);
export default function MyNoticesPage() { return <WorkforceInbox load={load} acknowledge={acknowledge} />; }
