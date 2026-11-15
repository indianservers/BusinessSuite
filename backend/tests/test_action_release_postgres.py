"""Release checks use unique disposable databases and never remote/app DBs."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from action_release_postgres import environment


def test_release_evaluations_use_distinct_local_postgres_databases(tmp_path,monkeypatch):
    monkeypatch.setenv('TEST_DATABASE_URL','must-not-be-inherited')
    uri='postgresql+psycopg://synthetic:synthetic@127.0.0.1:6543/application'
    first=environment(tmp_path,'action',uri);second=environment(tmp_path,'action',uri)
    assert first['POSTGRES_TEST_DATABASE']!=second['POSTGRES_TEST_DATABASE']
    assert all(value['POSTGRES_TEST_DATABASE'].startswith('business_suite_') and value['POSTGRES_TEST_DATABASE'].endswith('_test') and len(value['POSTGRES_TEST_DATABASE'])<=63 for value in [first,second])
    assert 'TEST_DATABASE_URL' not in first
    assert first['LOCAL_NLP_MODEL_DIR']==str(tmp_path.resolve())


@pytest.mark.parametrize('uri',['sqlite:///app.db','postgresql://synthetic@remote.example.com/app'])
def test_release_evaluator_rejects_nonlocal_or_nonpostgres_sources(tmp_path,uri):
    with pytest.raises(ValueError):environment(tmp_path,'action',uri)


def test_native_evaluator_passes_disposable_environment_to_test_runner(tmp_path,monkeypatch):
    """Exercise the evaluator entrypoint, not just its environment helper."""
    import json
    from contextlib import nullcontext
    from types import SimpleNamespace
    import evaluate_action_release as evaluator
    for name in ('bundle.json','dialogue.json','dialogue-evaluation.json'):
        (tmp_path/name).write_text('{}',encoding='utf-8')
    sentinel=environment(tmp_path,'action','postgresql+psycopg://synthetic:synthetic@127.0.0.1:6543/application')
    monkeypatch.setattr(evaluator,'isolated_environment',lambda folder,kind,*,fast_disposable_evaluation=False:nullcontext(sentinel if kind=='action' and fast_disposable_evaluation is True else None))
    def run(command,**kwargs):
        assert kwargs['env'] is sentinel
        assert 'run_postgres_tests.py' in command[1]
        report=next(value.split('=',1)[1] for value in command if value.startswith('--junitxml='))
        Path(report).write_text('<testsuites><testsuite tests="141" failures="0" errors="0" skipped="0"/></testsuites>',encoding='utf-8')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(evaluator,'managed_run',run)
    monkeypatch.setattr(sys,'argv',['evaluate_action_release.py','--model-dir',str(tmp_path)])
    evaluator.main()
    assert json.loads((tmp_path/'action-release-evaluation.json').read_text())['tests']==141


def test_release_cluster_is_local_disposable_and_stops_on_failure(tmp_path,monkeypatch):
    from action_release_postgres import isolated_environment
    from sqlalchemy import create_engine,text
    from sqlalchemy.engine import make_url
    monkeypatch.setenv('TEST_DATABASE_URL','must-not-be-inherited')
    with pytest.raises(RuntimeError,match='simulated evaluator failure'):
        with isolated_environment(tmp_path,'action') as env:
            url=make_url(env['DATABASE_URL'])
            assert url.host=='127.0.0.1' and url.database=='postgres'
            assert 'TEST_DATABASE_URL' not in env
            engine=create_engine(env['DATABASE_URL'])
            try:
                with engine.connect() as connection:
                    assert connection.execute(text('select current_user')).scalar()=='qa_suite'
                    assert connection.execute(text('show synchronous_commit')).scalar()=='on'
                    assert connection.execute(text('show fsync')).scalar()=='on'
                    assert connection.execute(text('show full_page_writes')).scalar()=='on'
            finally:engine.dispose()
            raise RuntimeError('simulated evaluator failure')
    roots=list(tmp_path.glob('isolated-action-postgres-*'))
    assert len(roots)==1
    assert (roots[0]/'stop.log').exists()
    assert not (roots[0]/'data/postmaster.pid').exists()


def test_fast_throwaway_mode_preserves_native_constraints_and_rollback(tmp_path):
    from action_release_postgres import isolated_environment
    from sqlalchemy import create_engine,text
    from sqlalchemy.exc import IntegrityError
    with isolated_environment(tmp_path,'action',fast_disposable_evaluation=True) as env:
        engine=create_engine(env['DATABASE_URL'])
        try:
            with engine.begin() as connection:
                assert connection.execute(text('show synchronous_commit')).scalar()=='off'
                assert connection.execute(text('show fsync')).scalar()=='on'
                assert connection.execute(text('show full_page_writes')).scalar()=='on'
                connection.execute(text('CREATE TABLE qa_functional_probe (id integer PRIMARY KEY, quantity integer CHECK (quantity>=0))'))
                connection.execute(text('INSERT INTO qa_functional_probe VALUES (1,1)'))
                for statement in ('INSERT INTO qa_functional_probe VALUES (1,2)','INSERT INTO qa_functional_probe VALUES (2,-1)'):
                    with pytest.raises(IntegrityError):
                        with connection.begin_nested():connection.execute(text(statement))
                assert connection.execute(text('SELECT count(*) FROM qa_functional_probe')).scalar()==1
        finally:engine.dispose()
    roots=list(tmp_path.glob('isolated-action-postgres-*'))
    assert len(roots)==1 and not (roots[0]/'data/postmaster.pid').exists()
