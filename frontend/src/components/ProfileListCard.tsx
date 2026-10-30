import { useState, type ReactNode } from "react";
import { assetUrl, getInitials } from "@/lib/utils";
import "./profile-list-card.css";

export function ProfileAction({ children, href, onClick, label }: {
  children: ReactNode; href?: string; onClick?: () => void; label?: string;
}) {
  return href ? <a className="profile-list-action" href={href} aria-label={label} data-context-action={label}>{children}</a>
    : <button type="button" className="profile-list-action" onClick={onClick} aria-label={label} data-context-action={label}>{children}</button>;
}

export default function ProfileListCard({ name, photoUrl, location, subtitle, tags = [], actions, onOpen, status, children }: {
  name: string; photoUrl?: string | null; location?: string | null; subtitle?: ReactNode;
  tags?: Array<string | { label: string; onClick?: () => void }>;
  actions?: ReactNode; onOpen?: () => void;
  status?: { label: string; tone?: "positive" | "muted" | "warning" };
  children?: ReactNode;
}) {
  const [failedPhoto, setFailedPhoto] = useState<string | null>(null);
  const photo = photoUrl ? assetUrl(photoUrl) : undefined;
  const portrait = <span className="profile-list-avatar">{photo && failedPhoto !== photo
    ? <img src={photo} alt="" loading="lazy" onError={() => setFailedPhoto(photo)} />
    : <span aria-hidden="true">{getInitials(name) || "?"}</span>}</span>;
  return <article className="profile-list-card" data-context-record={name}>
    {onOpen ? <button type="button" className="profile-list-portrait" onClick={onOpen} aria-label={`View ${name}'s profile`}>{portrait}</button>
      : <span className="profile-list-portrait">{portrait}</span>}
    <div className="profile-list-content">
      <div className="profile-list-heading"><h3>{onOpen ? <button type="button" onClick={onOpen} className="profile-list-name">{name}</button> : <span className="profile-list-name">{name}</span>}
        {location && <span className="profile-list-location"><span aria-hidden="true"> · </span>{location}</span>}</h3>
        {status && <span className={`profile-list-status profile-list-status--${status.tone || "muted"}`}><span aria-hidden="true" />{status.label}</span>}
      </div>
      {subtitle && <div className="profile-list-subtitle">{subtitle}</div>}
      {!!tags.length && <div className="profile-list-tags">{tags.map((tag, index) => {
        const label = typeof tag === "string" ? tag : tag.label;
        return typeof tag !== "string" && tag.onClick ? <button type="button" key={`${label}-${index}`} onClick={tag.onClick} className="profile-list-tag">{label}</button>
          : <span key={`${label}-${index}`} className="profile-list-tag">{label}</span>;
      })}</div>}
      {actions && <div className="profile-list-actions">{actions}</div>}
      {children}
    </div>
  </article>;
}
