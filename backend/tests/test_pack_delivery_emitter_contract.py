"""A missing genuine issuer can never turn metadata into delivery authority."""
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.business_packs.delivery_sources import bind_native_emitter,source_identity,_EMITTERS


@pytest.mark.parametrize('metadata',[{}, {'business_pack_scope':object(),'shared_actor':(1,1),'_member_plan':object()}])
def test_unissued_emitter_fails_closed_without_owner_issuer(metadata):
    native=Session();native.info.update(metadata)
    try:
        with pytest.raises(HTTPException):bind_native_emitter(native,object(),parent=Session(),frame=object())
        assert native not in _EMITTERS
        assert native.info==metadata
    finally:native.close()


def test_member_source_uses_actual_canonical_mapper_identity():
    from app.apps.project_management.models import PMSWorkspaceMember
    model,identity=source_identity(PMSWorkspaceMember.__tablename__,'7')
    assert model is PMSWorkspaceMember and identity=={'id':7}
