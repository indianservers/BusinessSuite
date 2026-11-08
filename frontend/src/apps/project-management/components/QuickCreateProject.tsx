import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useSmartCreation } from "@/shared/creation/SmartCreationProvider";
import type { PMSProject } from "../types";

type QuickCreateProjectProps = { open: boolean; initialStatus?: PMSProject["status"]; initialWorkspace?: number; onClose: () => void; onCreated: (project: PMSProject) => void };

/** Project creation always uses the full project form, including standalone routes. */
export default function QuickCreateProject(props: QuickCreateProjectProps) {
  const creation = useSmartCreation();
  const navigate = useNavigate();
  const attempted = useRef(false);
  useEffect(() => {
    if (!props.open) { attempted.current = false; return; }
    if (attempted.current) return;
    attempted.current = true;
    const query = new URLSearchParams({ status: props.initialStatus || "Active" });
    if (props.initialWorkspace) query.set("workspace_id", String(props.initialWorkspace));
    const destination = `/pms/projects/new?${query}`;
    const handled = creation?.open(destination, record => { if (record) props.onCreated(record as PMSProject); });
    props.onClose();
    if (!handled) navigate(destination);
  }, [props.open, props.initialStatus, props.initialWorkspace, props.onCreated, props.onClose, creation, navigate]);
  return null;
}
