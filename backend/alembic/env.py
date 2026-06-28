"""Alembic 迁移环境 — 加载应用 settings、用同步 URL 覆盖配置,并触发模型 import 以注册 metadata。

本模块在 ``alembic`` 命令执行时被加载,主要完成三件事:
    1. 调用 :func:`app.core.config.get_settings` 读取应用配置,并将同步数据库 URL
       写回 ``sqlalchemy.url``,覆盖 ``alembic.ini`` 中的占位值。
    2. ``import app.models.Base`` 会触发所有 ORM 模型的导入,从而将 ``Base.metadata``
       注册到 Alembic 的 ``target_metadata``,autogenerate 才能识别到全部表。
    3. 根据 ``--sql`` / 在线模式分支,执行 :func:`run_migrations_offline`
       或 :func:`run_migrations_online`。
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# 导入 settings 与 Base:Base 的导入会级联触发所有 ORM 模型,
# 从而把它们的 Table 注册到 Base.metadata,Alembic 才能识别。
from app.core.config import get_settings
from app.models import Base  # noqa: F401 - 故意 import 以触发模型注册

config = context.config

# 用应用配置中的同步数据库 URL 覆盖 alembic.ini 中的 sqlalchemy.url
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """以离线模式运行迁移:仅生成 SQL 脚本,不连接数据库。

    从配置中读取 ``sqlalchemy.url``,并将 SQLAlchemy 对象字面量直接渲染进
    生成的脚本(``literal_binds=True``)。

    参数:
        无

    返回值:
        None
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """以在线模式运行迁移:创建真实数据库连接并执行迁移。

    使用 :class:`sqlalchemy.pool.NullPool` 避免迁移过程中持有连接;
    通过 ``connectable.connect()`` 拿到连接后,在同一事务中调用
    :func:`context.run_migrations` 完成全部 DDL。

    参数:
        无

    返回值:
        None
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
