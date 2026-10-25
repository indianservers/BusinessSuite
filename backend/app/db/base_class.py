from typing import Any
from sqlalchemy.orm import DeclarativeBase, declared_attr
import re


class Base(DeclarativeBase):
    id: Any

    @property
    def phone_validation_issues(self):
        from app.core.orm_validation import contact_issues
        return contact_issues(self)

    @declared_attr.directive
    def __tablename__(cls) -> str:
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", cls.__name__)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower() + "s"
