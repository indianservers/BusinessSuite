"""Trusted read materialization scopes cannot survive errors or nested use."""
from types import SimpleNamespace
import pytest
from app.branches.derived import payroll_read_derivatives


def test_nested_payroll_read_scope_restores_outer_run_and_cleans_up_after_error():
    db = SimpleNamespace(info={})
    with payroll_read_derivatives(db, 10, variance=True):
        outer = db.info['derived_read_parents']
        assert outer == {'payroll_variance_items': frozenset({10})}
        with pytest.raises(RuntimeError):
            with payroll_read_derivatives(db, 20, download=True):
                assert db.info['derived_read_parents'] == {
                    'payroll_variance_items': frozenset({10}),
                    'payroll_run_audit_logs': frozenset({20}),
                }
                raise RuntimeError('Synthetic failure before commit')
        assert db.info['derived_read_parents'] is outer
    assert 'derived_read_parents' not in db.info
