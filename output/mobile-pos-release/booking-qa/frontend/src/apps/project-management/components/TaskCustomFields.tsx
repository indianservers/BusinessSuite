import { RecordCustomFields } from "./CustomFields";
export default function TaskCustomFields({taskId}:{taskId:number;projectId:number}) {return <RecordCustomFields entity="task" id={taskId}/>;}
