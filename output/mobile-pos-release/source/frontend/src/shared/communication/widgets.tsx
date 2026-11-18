import { useCollaboration, CollaborationDetails } from "./collaboration";
import { useNavigate } from "react-router-dom";
export function FollowUpWidget({workspaceId,conversationId}:{workspaceId:number;conversationId:number}){
  const result=useCollaboration(workspaceId,conversationId,true),navigate=useNavigate();
  return <CollaborationDetails wid={workspaceId} rid={conversationId} data={result.data} error={result.error} participants={[]} description="" onJump={message=>navigate(`/pms/messages?workspace=${workspaceId}&conversation=${conversationId}&message=${message}`)} onDownload={async()=>{}} messages={[]} onThread={()=>{}} view="followups" features={{files:false,aiAssistant:false}}/>;
}
