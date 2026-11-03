from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from app.api.v1.employees import my_profile_completeness


def test_completeness_handles_profile_hidden_by_branch_scope():
    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = None
    user = SimpleNamespace(employee=SimpleNamespace(id=123))
    with pytest.raises(HTTPException) as error:
        my_profile_completeness(db=db, current_user=user)
    assert error.value.status_code == 404
    assert "current branch" in error.value.detail
