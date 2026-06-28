"""可观测性模块 — OpenTelemetry 追踪 / 指标 / 日志的初始化与关闭入口。

当前 Plan 01 阶段为占位实现,完整接入留待 Plan 04。
"""
from __future__ import annotations

from app.core.config import get_settings


def init_observability() -> None:
    """初始化 OpenTelemetry 追踪。

    Plan 04 才会接入 TracerProvider、 MeterProvider 与自动插桩,当前为
    保持应用可启动的 no-op 实现。

    返回值:
        None: 无返回值。
    """
    settings = get_settings()
    # TODO(plan-04): 配置 OTel TracerProvider、 MeterProvider 与自动插桩
    _ = settings  # 避免未使用告警


def shutdown_observability() -> None:
    """关闭 OpenTelemetry Provider 并刷新剩余数据(Plan 04 完整实现)。

    返回值:
        None: 无返回值。
    """
    pass