"""Initialize database: run migrations + seed default tenant."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from uuid import UUID

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alembic import command
from alembic.config import Config

from app.core.config import get_settings
from app.core.database import dispose_engine, init_engine
from app.models import Tenant
from sqlalchemy import select


def run_migrations() -> None:
    cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url_sync)
    command.upgrade(cfg, "head")


async def seed_default_tenant() -> None:
    settings = get_settings()
    init_engine()
    from app.core.database import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        stmt = select(Tenant).where(Tenant.code == settings.default_tenant_code)
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            print(f"Tenant {settings.default_tenant_code} already exists (id={existing.id})")
            return

        tenant = Tenant(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            code=settings.default_tenant_code,
            name="Main Library",
            status="active",
            config={},
        )
        session.add(tenant)
        await session.commit()
        print(f"Created default tenant: {tenant.id}")


async def main() -> None:
    print("Running migrations...")
    run_migrations()
    print("Seeding default tenant...")
    await seed_default_tenant()
    await dispose_engine()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
