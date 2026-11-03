from app.module_registry import build_api_router

api_router = build_api_router()
from app.api.v1.whatsapp_cloud import router as whatsapp_cloud_router
from app.core.route_policy import enforce_private_defaults
enforce_private_defaults(whatsapp_cloud_router)
api_router.include_router(whatsapp_cloud_router)
