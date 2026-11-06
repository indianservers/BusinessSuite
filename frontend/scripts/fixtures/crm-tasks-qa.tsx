import React from "react";
import ReactDOM from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import Workspace from "../../src/apps/crm/CRMTasksWorkspace";
import { useAuthStore } from "../../src/store/authStore";
import "../../src/index.css";

useAuthStore.setState({ user: {id: 7, email: "me@example.test", name: "Me", role: "admin", is_superuser: true}, accessToken: "qa", isAuthenticated: true });
ReactDOM.createRoot(document.getElementById("root")!).render(<MemoryRouter><Workspace legacyKey="productivity:crm:7:v1" onNotes={() => {}}/></MemoryRouter>);
