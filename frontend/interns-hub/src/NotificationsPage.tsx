import WorkforceInbox from "../../src/components/workforce/WorkforceInbox";
import { hub, send } from "./api";
const load = (page: number) => hub(`/operations/inbox?page=${page}`);
const acknowledge = (id: number) => hub(`/operations/inbox/${id}/acknowledge`, send("POST"));
export default function NotificationsPage() { return <WorkforceInbox load={load} acknowledge={acknowledge} />; }
