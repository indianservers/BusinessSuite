import { createContext, useContext } from "react";
import { leadsApi } from "./api";
export const LeadRecordContext = createContext({api: leadsApi, potential: false});
export const useLeadRecord = () => useContext(LeadRecordContext);
