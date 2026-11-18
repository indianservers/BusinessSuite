import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import GridTable from "../../src/shared/data-grid/GridTable";
import "../../src/index.css";
const kind=new URLSearchParams(location.search).get("kind")||"crm", native=new URLSearchParams(location.search).has("native");
const field=kind==="hrms"?"Department":kind==="sales"?"Status":"Stage";
const values=kind==="hrms"?["Engineering","Operations","Finance"]:kind==="sales"?["Draft","Approved","Confirmed"]:["New","Contacted","Won"];
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={new QueryClient()}><BrowserRouter><main>
 <GridTable gridId={`grouping-${kind}`}><thead><tr><th>Name</th><th>Priority</th><th>{field}</th><th>Actions</th></tr></thead><tbody>{values.map((value,i)=><tr key={i} data-priority-row data-priority="High"><td>{native?<input type="text" aria-label={`Name ${i}`} defaultValue={`Record ${i}`}/>: `Record ${i}`}</td><td><span data-priority-badge data-priority="High">High</span></td><td>{value}</td><td><button type="button">Open</button></td></tr>)}</tbody></GridTable>
 </main></BrowserRouter></QueryClientProvider>);
