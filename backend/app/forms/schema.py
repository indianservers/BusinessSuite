from app.core.input_validation import national_phone,calling_code,email_address
import json, math, re
from datetime import date
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

FieldType = Literal[
    "text",
    "textarea",
    "email",
    "phone",
    "url",
    "number",
    "date",
    "select",
    "radio",
    "multiselect",
    "checkbox",
    "rating",
    "section",
    "page",
    "file",
]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Condition(Strict):
    field: str
    operator: Literal["equals", "not_equals", "contains", "not_empty"] = "equals"
    value: str = Field(default="", max_length=500)


class Question(Strict):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_\-]{0,59}$")
    type: FieldType
    label: str = Field(min_length=1, max_length=160)
    help: str = Field(default="", max_length=500)
    placeholder: str = Field(default="", max_length=160)
    required: bool = False
    width: Literal["auto", "full"] = "auto"
    options: list[str] = Field(default_factory=list, max_length=50)
    min: float | None = None
    max: float | None = None
    condition: Condition | None = None
    global_field_id: int | None = Field(default=None, gt=0)


class Workflow(Strict):
    enabled: bool = False
    project_id: int | None = Field(default=None, gt=0)
    title_field: str = ""
    priority: Literal["Low", "Medium", "High", "Urgent"] = "Medium"
    assignee_id: int | None = Field(default=None, gt=0)
    due_days: int | None = Field(default=None, ge=0, le=365)


class Definition(Strict):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    submit_label: str = Field(default="Submit response", min_length=1, max_length=60)
    success_message: str = Field(
        default="Thank you. Your response has been saved.", min_length=1, max_length=500
    )
    accent: str = Field(default="#7c3aed", pattern=r"^#[0-9a-fA-F]{6}$")
    fields: list[Question] = Field(min_length=1, max_length=60)
    workflow: Workflow = Field(default_factory=Workflow)

    @model_validator(mode="after")
    def valid(self):
        if not self.name.strip():
            raise ValueError("Form name is required")
        seen = set()
        for f in self.fields:
            if not f.label.strip() or f.id in seen:
                raise ValueError("Questions need unique IDs and nonempty labels")
            if f.condition and f.condition.field not in seen:
                raise ValueError("Conditions must reference an earlier question")
            if f.condition:
                source = next(q for q in self.fields if q.id == f.condition.field)
                if source.type in {"section", "page"} or (
                    source.type == "file" and f.condition.operator != "not_empty"
                ):
                    raise ValueError(
                        "Conditions must reference an answer field; uploads only support is-answered rules"
                    )
            if f.type in {"select", "radio", "multiselect"} and (
                not f.options
                or any(not x.strip() or len(x) > 160 for x in f.options)
                or len(set(f.options)) != len(f.options)
            ):
                raise ValueError(
                    "Choice fields need unique nonempty options, up to 160 characters"
                )
            if any(v is not None and not math.isfinite(v) for v in [f.min, f.max]) or (
                f.min is not None and f.max is not None and f.min > f.max
            ):
                raise ValueError("Invalid numeric range")
            seen.add(f.id)
        if self.workflow.enabled and (
            not self.workflow.project_id
            or not any(
                f.id == self.workflow.title_field
                and f.type == "text"
                and f.required
                and not f.condition
                for f in self.fields
            )
        ):
            raise ValueError(
                "Task workflows require a project and an unconditional required text title"
            )
        if len(self.model_dump_json()) > 200000:
            raise ValueError("Form definition limit: 200 KB")
        return self


def visible(f, answers):
    c = f.condition
    if not c:
        return True
    value = answers.get(c.field)
    if c.operator == "not_empty":
        return value is not None and value != "" and value != [] and value is not False
    if c.operator == "contains":
        return c.value in value if isinstance(value, (str, list)) else False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            same = float(c.value) == value
        except (ValueError, TypeError):
            same = False
        return same if c.operator == "equals" else not same
    text = (
        ""
        if value is None
        else (
            format(value, "g")
            if isinstance(value, float)
            else (",".join(value) if isinstance(value, list) else str(value))
        )
    )
    same = text.lower() == c.value.lower()
    return same if c.operator == "equals" else not same


def clean_answers(definition, answers):
    if len(json.dumps(answers)) > 20000:
        raise HTTPException(422, "Total response limit: 20,000 characters")
    unknown = set(answers) - {f.id for f in definition.fields} - {f.id+'_country_code' for f in definition.fields if f.type=='phone'}
    if unknown:
        raise HTTPException(422, "Unknown question IDs")
    clean = {}
    for f in definition.fields:
        if f.type in {"section", "page"} or not visible(f, clean):
            continue
        value = answers.get(f.id)
        empty = (
            value is None
            or value == ""
            or value == []
            or (f.type == "checkbox" and value is False)
        )
        if empty:
            if f.required:
                raise HTTPException(422, f"{f.label}: response required")
            continue
        valid = True
        if f.type == "file":
            valid = isinstance(value, str) and bool(
                re.fullmatch(r"file:[a-f0-9]{32}", value)
            )
        elif f.type=='phone':
            try:
                national_phone(value);calling_code(answers.get(f.id+'_country_code'))
                clean[f.id+'_country_code']=answers[f.id+'_country_code']
            except ValueError as exc:raise HTTPException(422,detail=f'{f.label}: {exc}') from None
        elif f.type == "checkbox":
            valid = isinstance(value, bool)
        elif f.type == "multiselect":
            valid = (
                isinstance(value, list)
                and len(value) <= 50
                and all(isinstance(x, str) and x in f.options for x in value)
                and len(set(value)) == len(value)
            )
        elif f.type in {"number", "rating"}:
            try:
                value = (
                    float(value)
                    if not isinstance(value, (bool, list))
                    else float("nan")
                )
                valid = (
                    math.isfinite(value)
                    and (f.min is None or value >= f.min)
                    and (f.max is None or value <= f.max)
                )
                if f.type == "rating":
                    valid = valid and 1 <= value <= 5 and value.is_integer()
            except (TypeError, ValueError):
                valid = False
        else:
            valid = (
                isinstance(value, str)
                and bool(value.strip())
                and len(value) <= (10000 if f.type == "textarea" else 2000)
            )
            if valid:
                value = value if f.type=="email" else value.strip()
                if f.type == "email":
                    try:email_address(value)
                    except ValueError:valid=False
                elif f.type == "url":
                    valid = bool(re.fullmatch(r"https?://[^\s/]+[^\s]*", value))
                elif f.type == "date":
                    try:
                        date.fromisoformat(value)
                    except ValueError:
                        valid = False
                elif f.type in {"select", "radio"}:
                    valid = value in f.options
                elif f.type == "phone":
                    valid = bool(re.fullmatch(r"[+()0-9 .-]{5,40}", value))
        if not valid:
            raise HTTPException(422, f"{f.label}: invalid response")
        clean[f.id] = value
    return clean
