import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import * as Dropdown from "@radix-ui/react-dropdown-menu";
import {
  Users,
  SquareArrowOutUpRight,
  MoreHorizontal,
  UserRound,
  ClipboardList,
  Mail,
  Shield,
} from "lucide-react";
import { openPerson } from "./peopleTypes";
import { type DirectoryPerson, initials } from "./peopleWorkspace";
import PeopleAction from "./PeopleAction";
export function DirectoryAvatar({
  person,
  size = "normal",
}: {
  person: Pick<DirectoryPerson, "name" | "photo_url">;
  size?: "normal" | "small" | "large";
}) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [person.photo_url]);
  return person.photo_url && !failed ? (
    <img
      className={`pd-avatar ${size}`}
      src={person.photo_url}
      alt={person.name}
      onError={() => setFailed(true)}
    />
  ) : (
    <span aria-label={person.name} className={`pd-avatar pd-initials ${size}`}>
      {initials(person.name)}
    </span>
  );
}
export default function DirectoryPersonCard({
  person,
  selected,
  onSelect,
  onTeam,
  onAssign,
  canTeam,
  canAddWorkspace,
  canAddProject,
  onWorkspace,
  onProject,
  profileHref, onPreview, onDragMembers, onDragEnd, onDestinations,
}: {
  person: DirectoryPerson;
  selected: boolean;
  onSelect: () => void;
  onTeam: () => void;
  onAssign: () => void;
  canTeam: boolean;
  canAddWorkspace?: boolean;
  canAddProject?: boolean;
  onWorkspace?: () => void;
  onProject?: () => void;
  profileHref: string;
  onPreview?: () => void;
  onDestinations?: () => void;
  onDragMembers?: (event: React.DragEvent) => void;
  onDragEnd?: () => void;
}) {
  const active = person.status === "active";
  const tags = [
    person.classification,
    ...person.batches.slice(0, 1).map((b) => b.name),
    ...person.teams.slice(0, 1).map((t) => t.name),
    ...person.skills.slice(0, 1),
    ...(person.department ? [person.department] : []),
  ]
    .filter(Boolean)
    .slice(0, 3);
  return (
    <article className={`pd-person-card ${selected ? "selected" : ""}`} draggable={active} onDragStart={onDragMembers} onDragEnd={onDragEnd}>
      <div className="pd-person-body">
        <Link to={profileHref} onClick={e => { if(onPreview){e.preventDefault();onPreview();} }} className="pd-person-photo">
          <DirectoryAvatar person={person} />
        </Link>
        <div className="pd-person-identity">
          <div>
            <Link to={profileHref} onClick={e => {if(onPreview){e.preventDefault();onPreview();}}}>{person.name}</Link>
            <span className={`pd-status ${active ? "active" : "inactive"}`}>
              <i />
              {active ? "Login enabled" : `Login disabled (${person.status.replace(/_/g, " ")})`}
            </span>
          </div>
          <p title={person.email}>
            {person.classification}
            {person.employee_code ? ` · ${person.employee_code}` : ""} ·{" "}
            {person.email}
          </p>
          <div className="pd-tags">
            {person.employment_status && <span>{person.classification}: {person.employment_status}</span>}
            {tags.map((tag, index) => (
              <span key={`${tag}-${index}`}>{tag}</span>
            ))}
          </div>
        </div>
        <label className="pd-card-select">
          <input
            type="checkbox"
            aria-label={`Select ${person.email}`}
            checked={selected}
            disabled={!active}
            onChange={onSelect}
          />
          <span className="sr-only">Select for bulk actions</span>
        </label>
      </div>
      <div className="pd-membership-summary"><span>Project: {person.projects?.[0]?.name || "No current project"}</span><details><summary>Membership details</summary><p>Workspaces: {person.workspaces?.map(x=>x.name).join(", ") || "None"}</p><p>Teams: {person.teams.map(x=>x.name).join(", ") || "None"}</p>{person.classification.toLowerCase() === "intern" && <p>Intern batches: {person.batches.map(x=>x.name).join(", ") || "None"}</p>}<p>Projects: {person.projects?.map(x=>x.name).join(", ") || "None"}</p></details></div>
      <button className="pd-drag-handle" disabled={!active} onClick={onDestinations} aria-label={`Assign ${person.name} to a destination`} title="Drag this card to a destination, or click to choose one">Drag or assign</button>
      <footer>
        <PeopleAction
          type="button"
          reason={!active ? "Reactivate this account before changing team memberships." : !canTeam ? "Team membership changes require workspace administration access." : undefined}
          disabled={!active || !canTeam}
          title={
            !canTeam
              ? "Team membership changes require a workspace administrator"
              : "Add to a workspace team"
          }
          onClick={onTeam}
        >
          <Users size={14} />
          Add to team
        </PeopleAction>
        <PeopleAction type="button" disabled={!active || !canAddWorkspace} reason={!active ? "Reactivate this account first." : !canAddWorkspace ? "Workspace administration access is required." : undefined} onClick={onWorkspace}>
          <Users size={14} /> Add to workspace
        </PeopleAction>
        <PeopleAction
          type="button"
          reason={!active ? "Reactivate this account before assigning work." : undefined}
          disabled={!active}
          title={
            !active
              ? "Reactivate the account before assigning new work"
              : "Open full-page task creation"
          }
          onClick={onAssign}
        >
          <SquareArrowOutUpRight size={13} />
          Assign task
        </PeopleAction>
        <Dropdown.Root>
          <Dropdown.Trigger
            className="pd-more"
            aria-label={`More actions for ${person.name}`}
          >
            <MoreHorizontal size={17} />
          </Dropdown.Trigger>
          <Dropdown.Portal>
            <Dropdown.Content className="pd-dropdown" sideOffset={5}>
              <Dropdown.Item disabled={!active || !canAddWorkspace} onSelect={onWorkspace}>
                <Users size={15} /> Add to workspace
              </Dropdown.Item>
              <Dropdown.Item disabled={!active || !canAddProject} onSelect={onProject}>
                <ClipboardList size={15} /> Add to project
              </Dropdown.Item>
              <Dropdown.Separator />
              <Dropdown.Item asChild>
                <Link to={profileHref}>
                  <UserRound size={15} />
                  View profile
                </Link>
              </Dropdown.Item>
              <Dropdown.Item asChild>
                <Link to={profileHref + "&tab=tasks"}>
                  <ClipboardList size={15} />
                  View assignments
                </Link>
              </Dropdown.Item>
              <Dropdown.Item asChild>
                <a href={`mailto:${encodeURIComponent(person.email)}`}>
                  <Mail size={15} />
                  Compose email
                </a>
              </Dropdown.Item>
              <Dropdown.Separator />
              {person.can_manage ? (
                <Dropdown.Item
                  className="pd-manage-person"
                  onSelect={() => openPerson({ userId: person.id })}
                >
                  <Shield size={15} />
                  Manage person
                </Dropdown.Item>
              ) : (
                <p className="pd-menu-note">
                  Editing requires permission to manage this person.
                </p>
              )}
            </Dropdown.Content>
          </Dropdown.Portal>
        </Dropdown.Root>
      </footer>
    </article>
  );
}
