"""数据库初始化脚本 — 执行两步流程:运行 Alembic 迁移到最新版本,然后写入默认租户种子数据。"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from uuid import UUID

# 将 backend 目录加入 sys.path,以便以脚本方式运行时能 import app.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alembic import command
from alembic.config import Config

from app.core.config import get_settings
from app.core.database import dispose_engine, init_engine
from app.models import Tenant
from sqlalchemy import select


def run_migrations() -> None:
    """通过 Alembic 将数据库 schema 升级到最新版本。

    加载项目根目录下的 ``alembic.ini``,并使用 settings 中的同步数据库 URL
    覆盖配置中的 ``sqlalchemy.url``,随后调用 ``alembic upgrade head``。

    参数:
        无

    返回值:
        None
    """
    cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url_sync)
    command.upgrade(cfg, "head")


async def seed_default_tenant() -> None:
    """初始化数据库引擎,并按配置写入默认租户种子数据。

    若 ``settings.default_tenant_code`` 对应的租户已存在则跳过;否则以固定
    UUID 创建一条状态为 ``active`` 的默认租户记录。

    参数:
        无

    返回值:
        None
    """
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
    """脚本入口:依次执行迁移与种子数据写入,最后释放引擎资源。

    步骤:
        1. 运行 ``run_migrations`` — Alembic 升级到 head。
        2. 运行 ``seed_default_tenant`` — 写入默认租户。
        3. 释放数据库引擎连接池。

    参数:
        无

    返回值:
        None
    """
    print("Running migrations...")
    run_migrations()
    print("Seeding default tenant...")
    await seed_default_tenant()
    await dispose_engine()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
