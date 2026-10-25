import { Link } from 'react-router-dom';
import InternManagementPage from '@/apps/hrms/pages/interns/InternManagementPage';
export default function BatchWorkspacePage({mode='batches'}:{mode?:'batches'|'tasks'}){
 return <><nav className="mb-4 flex flex-wrap gap-4 text-sm text-primary"><Link to="/pms/batches">Batches & Participants</Link><Link to="/pms/batch-tasks">Distribute PMS Tasks</Link><Link to="/pms/my-assignments">My Assignments</Link><Link to="/pms/assignment-controls">Individual Assignment Controls</Link><Link to="/pms/reviews">Review Submissions</Link></nav><InternManagementPage page={mode}/></>
}
