import os
import pytest
from tests.test_shared_services import shared_setup, access_account


@pytest.mark.skipif(os.getenv("RUN_CONTROL_BROWSER")!="1",reason="Opt-in real shared-service browser workflow")
def test_real_shared_workflow_editor_and_delivery(client,db,shared_setup,superuser_headers,monkeypatch):
    from tests.test_control_browser import test_control_center_real_browser
    monkeypatch.setenv("CONTROL_BROWSER_SCRIPT","shared-live.cjs")
    test_control_center_real_browser(client,db,shared_setup[1],superuser_headers)
