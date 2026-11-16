"""Operational employee categories shared across HRMS and service scheduling."""
from typing import Annotated
from pydantic import AfterValidator, Field
import json
from sqlalchemy import cast, String, or_


def normalize_categories(values):
    result = []
    seen = set()
    for value in values:
        name = ' '.join(value.split())
        if not name or len(name) > 80:
            raise ValueError('Employee categories must contain 1 to 80 characters')
        if name.casefold() not in seen:
            result.append(name)
            seen.add(name.casefold())
    return result


WorkCategories = Annotated[list[str], Field(max_length=20), AfterValidator(normalize_categories)]


def category_clause(db, column, categories):
    # Match complete quoted JSON string values, using bound, escaped patterns.
    # This stays inside the canonical employee source accepted by the ORM guard.
    encoded = {json.dumps(name, ensure_ascii=ascii_only) for name in normalize_categories(categories) for ascii_only in (True, False)}
    return or_(*(cast(column, String).icontains(name, autoescape=True) for name in encoded))
