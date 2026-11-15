import { createContext, useContext } from "react";

export const OperationPanelContext = createContext(true);
export const OperationWorkspaceContext = createContext(false);
// True only around a manager already rendered inside an operation panel.
// A shared URL host alone does not provide the operation tabs or selected panel.
export const OperationContentContext = createContext(false);
export const useOperationPanelActive = () => useContext(OperationPanelContext);
