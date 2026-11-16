"""Strict control-plane inputs; clients never set pack identity or active state."""
from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StringConstraints

Key = Annotated[str, StringConstraints(strict=True, pattern=r'^[a-z][a-z0-9_]{0,63}$')]
Reason = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=3, max_length=1000)]
PositiveId = Annotated[StrictInt, Field(gt=0)]
Revision = Annotated[StrictInt, Field(ge=0)]
ExistingRevision = Annotated[StrictInt, Field(ge=1)]
NewRevision = Annotated[StrictInt, Field(ge=0, le=0)]


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class DraftActivation(Strict):
    pack_key: Key
    expected_revision: NewRevision
    reason: Reason


class DraftContext(Strict):
    activation_id: PositiveId
    activation_revision: ExistingRevision
    branch_id: PositiveId
    expected_revision: NewRevision
    reason: Reason


class GrantRole(Strict):
    context_revision: ExistingRevision
    role: Key
    active: StrictBool = True
    expected_revision: Revision
    reason: Reason


class Activate(Strict):
    expected_revision: ExistingRevision
    reason: Reason


class ActivateContext(Activate):
    activation_revision: ExistingRevision


class ActivateTheme(Strict):
    pack_key: Key
    expected_selection: Annotated[str, StringConstraints(strict=True, pattern=r'^[0-9a-f]{64}$')]
    reason: Reason


class PreviewActivation(DraftActivation):
    action: Literal['draft_activation']


class PreviewContext(DraftContext):
    action: Literal['draft_context']


class PreviewGrant(GrantRole):
    action: Literal['grant_role']
    context_id: PositiveId
    user_id: PositiveId


class PreviewActivate(Activate):
    action: Literal['activate']
    activation_id: PositiveId


class PreviewActivateContext(ActivateContext):
    action: Literal['activate_context']
    context_id: PositiveId


PreviewInput = Annotated[Union[
    PreviewActivation, PreviewContext, PreviewGrant, PreviewActivate, PreviewActivateContext,
], Field(discriminator='action')]
