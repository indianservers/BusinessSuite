"""Fresh ordinary app import and actual private native financial producer."""
import os,subprocess,sys
from pathlib import Path


def test_fresh_app_then_actual_accounts_producer_has_stable_listener_order(tmp_path):
    url='sqlite:///'+str(tmp_path/'owned-fresh-delivery.db')
    env={**os.environ,'DATABASE_URL':url,'FAST_TEST_PASSWORD_HASHES':'1'}
    env.pop('TEST_DATABASE_URL',None)
    result=subprocess.run([sys.executable,'-m','pytest','-p','tests.delivery_startup_guard',
        'tests/test_accounts_private_delivery_compatibility.py::test_accounts_billing_collection_does_not_abort_or_launder_private_mail','-q'],
        cwd=Path(__file__).parents[1],env=env,capture_output=True,text=True,timeout=120)
    assert result.returncode==0,result.stdout+result.stderr
    assert '1 passed' in result.stdout
