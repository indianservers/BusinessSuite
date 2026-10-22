"""Run migrations and bootstrap once, before enabling serverless traffic.

Set DATABASE_URL to the direct Neon URL in a secure shell. This command does not
create/drop a database. Repeating it uses the existing idempotent bootstrap.
"""
import asyncio
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings


async def provision():
    if settings.SEED_DEMO_DATA:
        raise RuntimeError("Deployment provisioning must not seed demo data")
    if not settings.BOOTSTRAP_ADMIN_PASSWORD:
        raise RuntimeError("Set BOOTSTRAP_ADMIN_PASSWORD before provisioning")
    settings.SERVERLESS = False
    settings.DATABASE_AUTO_MIGRATE = True
    settings.ENVIRONMENT = "provisioning"
    from app.main import app, lifespan
    async with lifespan(app):
        pass
    print("Schema migrated and bootstrap complete. No demo data seeded.")


if __name__ == "__main__":
    asyncio.run(provision())
