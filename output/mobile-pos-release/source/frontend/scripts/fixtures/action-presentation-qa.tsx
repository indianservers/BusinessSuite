import { createRoot } from "react-dom/client";
import { Plus } from "lucide-react";
import { Button } from "../../src/components/ui/button";
import { Badge } from "../../src/components/ui/badge";
import { ActionButton, MoreActionsMenu } from "../../src/components/actions";
import "../../src/index.css";
createRoot(document.getElementById("root")!).render(<main className="flex flex-wrap gap-3 p-6">
  <Button>Add task</Button>
  <Button>+ Add task</Button>
  <Button asChild><a href="#legacy-task">+ Add task</a></Button>
  <Button variant="outline"><Plus aria-hidden="true"/>Add task</Button>
  <Button asChild variant="outline"><a href="#task">Add task</a></Button>
  <ActionButton action="task"/>
  <Button variant="outline">Export</Button>
  <Button variant="outline">Trash</Button>
  <Button variant="outline">Import</Button>
  <Badge>{0}</Badge><Badge>{124}</Badge><Badge variant="success">Completed</Badge>
  <MoreActionsMenu actions={[{id:"copy",kind:"copy"},{id:"export",kind:"download"}]}/>
</main>);
