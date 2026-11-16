"""A failed fixture setup must not retain its committed private schema."""
import pytest
from contextlib import contextmanager
from sqlalchemy import text
from sqlalchemy.orm import Session
from tests.test_power_runtime_postgres import durable_store


@pytest.mark.parametrize('stage', ['schema_create', 'seed', 'seed_commit'])
def test_power_fixture_cleans_schema_when_setup_fails(db_engine, monkeypatch, request, stage):
    if db_engine.dialect.name != 'postgresql':
        pytest.skip('Requires real PostgreSQL fixture cleanup')

    def schemas():
        with db_engine.connect() as connection:
            return set(connection.execute(text(
                "SELECT nspname FROM pg_namespace WHERE nspname LIKE 'power_runtime_it_%'"
            )).scalars())

    before = schemas()
    reached = []
    message = 'Intentional private fixture setup failure'
    if stage == 'schema_create':
        original_begin = db_engine.begin
        @contextmanager
        def fail_create_commit():
            with original_begin() as connection:
                yield connection
            if not reached:
                assert len(schemas() - before) == 1
                reached.append(stage)
                raise RuntimeError(message)
        monkeypatch.setattr(db_engine, 'begin', fail_create_commit)
    elif stage == 'seed':
        import test_identity_utils
        def fail_seed(*args, **kwargs):
            reached.append(stage)
            raise RuntimeError(message)
        monkeypatch.setattr(test_identity_utils, 'attach_workflow_branch', fail_seed)
    else:
        original = Session.commit
        def fail_after_commit(session):
            assert 'power_runtime_it_' in session.get_bind().url.query['options']
            original(session)
            assert list(session.execute(text('SELECT email FROM users ORDER BY email')).scalars()) == [
                'runtime-load@example.invalid', 'setup-admin-101@example.test'
            ]
            reached.append(stage)
            raise RuntimeError(message)
        monkeypatch.setattr(Session, 'commit', fail_after_commit)

    with pytest.raises(RuntimeError, match=message):
        request.getfixturevalue('durable_store')
    assert reached == [stage]
    assert schemas() == before
