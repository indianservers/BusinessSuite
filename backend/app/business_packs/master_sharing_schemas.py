from typing import Literal
from pydantic import StrictBool
from .schemas import Strict, PositiveId, Revision, ExistingRevision, Reason, GrantRole

MasterKind = Literal['employees', 'customers', 'products', 'warehouses']


class ShareMaster(Strict):
    kind: MasterKind
    id: PositiveId
    active: StrictBool
    expected_context_revision: ExistingRevision
    expected_revision: Revision
    reason: Reason


class GrantPreview(GrantRole):
    user_id: PositiveId
