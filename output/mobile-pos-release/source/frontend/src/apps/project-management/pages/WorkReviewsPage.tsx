import "./work-reviews-mobile.css";
import {Link} from "react-router-dom";
import WorkReviewPanel from "../components/WorkReviewPanel";
export default function WorkReviewsPage() {
  return (
    <div className="work-reviews-page space-y-5">
      <div>
        <h1 className="page-title">PMS Work Reviews</h1>
        <p className="page-description">
          Authoritative task submissions, evidence versions, reviewer decisions
          and scores.
        </p>
      </div>
      <div className="rounded-xl border bg-card p-6">
        <nav className="mb-4 flex gap-4 text-primary"><Link to="/pms/batches">Batches</Link><Link to="/pms/batch-tasks">Assign PMS Tasks</Link><Link to="/pms/my-assignments">My Assignments</Link></nav><WorkReviewPanel mobileReview />
      </div>
    </div>
  );
}
