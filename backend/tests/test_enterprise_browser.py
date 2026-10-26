import os
import pytest
from tests.test_shared_services import shared_setup, access_account


@pytest.mark.skipif(
    os.getenv("RUN_CONTROL_BROWSER") != "1",
    reason="Opt-in real enterprise browser workflow",
)
def test_real_enterprise_browser(
    client, db, shared_setup, superuser_headers, monkeypatch, tmp_path
):
    monkeypatch.setenv("BUSINESSSUITE_BACKUP_DIR", str(tmp_path / "archives"))
    from tests.test_control_browser import test_control_center_real_browser

    monkeypatch.setenv("CONTROL_BROWSER_SCRIPT", "enterprise-live.cjs")
    test_control_center_real_browser(client, db, shared_setup[1], superuser_headers)
