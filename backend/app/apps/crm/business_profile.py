"""Customer services and market classification shared by CRM write surfaces."""
import re
from fastapi import HTTPException


def normalize_profile_list(value, field):
    if value is None:
        return []
    if isinstance(value, str):
        value = re.split(r"[,\n]", value)
    if not isinstance(value, list) or len(value) > 100:
        raise HTTPException(422, f"{field} must be a list of at most 100 entries")
    result = []
    seen = set()
    for item in value:
        if not isinstance(item, str):
            raise HTTPException(422, f"{field} entries must be text")
        item = item.strip()
        if not item:
            continue
        if field == "business_types":
            item = item.upper()
            if item not in {"B2B", "B2C", "B2G"}:
                raise HTTPException(422, "Business types must be B2B, B2C or B2G")
        if len(item) > 120:
            raise HTTPException(422, "Service names must be at most 120 characters")
        if item.casefold() not in seen:
            seen.add(item.casefold())
            result.append(item)
    return result


def merge_business_profile(target, source):
    for field in ("services_offered", "business_types"):
        setattr(target, field, normalize_profile_list(
            [*(getattr(target, field) or []), *(getattr(source, field) or [])], field))
