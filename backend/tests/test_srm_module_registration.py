from app.module_registry import APP_MODULES, build_api_router, get_installed_app_keys, is_app_enabled


def test_srm_module_is_registered_and_enabled():
    assert "srm" in APP_MODULES
    module = APP_MODULES["srm"]
    assert module.label == "Sales & Inventory Management"
    assert "app.apps.srm.models" in module.model_modules
    assert "app.apps.srm.api.router" in module.router_modules
    assert "srm" in get_installed_app_keys()
    assert is_app_enabled("srm") is True


def test_srm_api_router_prefix_is_available():
    api_router = build_api_router()
    paths = {route.path for route in api_router.routes}
    assert "/srm/module-info" in paths
    assert "/srm/sales-orders" in paths
    assert "/srm/invoices/draft-from-sales-order/{sales_order_id}" in paths
