from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.common.models import CommonPerson, CommonProfile
from app.models.user import User


@dataclass(frozen=True)
class IdentitySummary:
    user_id: int
    email: str
    display_name: str
    role: str | None = None
    organization_id: int | None = None
    person_id: int | None = None
    phone_number: str | None = None
    profile_photo_url: str | None = None


class SharedIdentityService:
    """Common identity access for modules.

    Product modules should use their own thin service facade and avoid reaching
    into HRMS employee fields for shared identity concerns.
    """

    @staticmethod
    def _email_display_name(email: str | None) -> str:
        return (email or "user").split("@")[0]

    @classmethod
    def display_name_for_user(cls, user: User) -> str:
        person = getattr(user, "person", None)
        if person and person.display_name:
            return person.display_name
        employee = getattr(user, "employee", None)
        if employee:
            name = " ".join(
                part for part in [getattr(employee, "first_name", None), getattr(employee, "last_name", None)] if part
            ).strip()
            if name:
                return name
        return cls._email_display_name(user.email)

    @classmethod
    def organization_id_for_user(cls, user: User) -> int | None:
        person = getattr(user, "person", None)
        if person and person.organization_id:
            return int(person.organization_id)
        employee = getattr(user, "employee", None)
        branch = getattr(employee, "branch", None) if employee else None
        if branch and getattr(branch, "company_id", None):
            return int(branch.company_id)
        return getattr(user, "company_id", None)

    @classmethod
    def ensure_person_for_user(
        cls,
        db: Session,
        user: User,
        *,
        display_name: str | None = None,
        organization_id: int | None = None,
        phone_number: str | None = None,
        source_module: str | None = None,
        source_record_type: str | None = None,
        source_record_id: int | None = None,
        profile_defaults: dict[str, Any] | None = None,
    ) -> CommonPerson:
        person = (
            db.query(CommonPerson)
            .options(joinedload(CommonPerson.profile))
            .filter(CommonPerson.user_id == user.id)
            .first()
        )
        if not person:
            person = CommonPerson(
                user_id=user.id,
                primary_email=user.email,
                display_name=display_name or cls.display_name_for_user(user),
                organization_id=organization_id,
                phone_number=phone_number,
                source_module=source_module,
                source_record_type=source_record_type,
                source_record_id=source_record_id,
            )
            db.add(person)
            db.flush()
        else:
            person.primary_email = user.email or person.primary_email
            person.display_name = display_name or person.display_name or cls.display_name_for_user(user)
            person.organization_id = organization_id if organization_id is not None else person.organization_id
            person.phone_number = phone_number or person.phone_number
            person.source_module = source_module or person.source_module
            person.source_record_type = source_record_type or person.source_record_type
            person.source_record_id = source_record_id if source_record_id is not None else person.source_record_id

        if not person.profile:
            person.profile = CommonProfile(person_id=person.id, **(profile_defaults or {}))
            db.add(person.profile)
            db.flush()
        elif profile_defaults:
            for key, value in profile_defaults.items():
                if value is not None and hasattr(person.profile, key):
                    setattr(person.profile, key, value)

        return person

    @classmethod
    def sync_from_employee(cls, db: Session, employee: Any, user: User | None = None) -> CommonPerson | None:
        user = user or getattr(employee, "user", None)
        if not user:
            return None
        branch = getattr(employee, "branch", None)
        organization_id = getattr(branch, "company_id", None) if branch else getattr(employee, "organization_id", None)
        display_name = " ".join(
            part for part in [getattr(employee, "first_name", None), getattr(employee, "last_name", None)] if part
        ).strip()
        return cls.ensure_person_for_user(
            db,
            user,
            display_name=display_name or None,
            organization_id=organization_id,
            phone_number=getattr(employee, "phone_number", None),
            source_module="hrms",
            source_record_type="employee",
            source_record_id=getattr(employee, "id", None),
            profile_defaults={
                "preferred_display_name": getattr(employee, "preferred_display_name", None),
                "profile_photo_url": getattr(employee, "profile_photo_url", None),
                "bio": getattr(employee, "bio", None),
                "timezone": getattr(employee, "timezone", None),
                "directory_visibility": getattr(employee, "directory_visibility", None),
            },
        )

    @classmethod
    def summary_for_user(cls, user: User) -> IdentitySummary:
        person = getattr(user, "person", None)
        profile = getattr(person, "profile", None) if person else None
        return IdentitySummary(
            user_id=user.id,
            email=user.email,
            display_name=cls.display_name_for_user(user),
            role=user.role.name if user.role else None,
            organization_id=cls.organization_id_for_user(user),
            person_id=person.id if person else None,
            phone_number=getattr(person, "phone_number", None) if person else None,
            profile_photo_url=getattr(profile, "profile_photo_url", None) if profile else None,
        )

    @classmethod
    def search_users(
        cls,
        db: Session,
        *,
        query: str = "",
        limit: int = 10,
        organization_id: int | None = None,
    ) -> list[IdentitySummary]:
        term = query.strip().lower()
        user_query = (
            db.query(User)
            .options(joinedload(User.role), joinedload(User.person).joinedload(CommonPerson.profile))
            .outerjoin(CommonPerson, CommonPerson.user_id == User.id)
            .filter(User.is_active.is_(True))
        )
        if organization_id is not None:
            user_query = user_query.filter(or_(CommonPerson.organization_id == organization_id, CommonPerson.id.is_(None)))
        users = user_query.order_by(User.email.asc()).limit(250).all()

        results: list[IdentitySummary] = []
        for user in users:
            summary = cls.summary_for_user(user)
            if organization_id is not None and summary.organization_id not in {None, organization_id}:
                continue
            haystack = " ".join([summary.display_name, summary.email or "", summary.role or ""]).lower()
            if term and term not in haystack:
                continue
            results.append(summary)
            if len(results) >= limit:
                break
        return results

    @classmethod
    def contact_for_user(cls, db: Session, user_id: int) -> IdentitySummary | None:
        user = (
            db.query(User)
            .options(joinedload(User.role), joinedload(User.person).joinedload(CommonPerson.profile))
            .filter(User.id == user_id)
            .first()
        )
        return cls.summary_for_user(user) if user else None
