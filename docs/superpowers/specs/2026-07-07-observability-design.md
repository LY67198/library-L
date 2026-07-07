# 可观测性 — 设计文档

## 概述

为图书馆智能服务系统增加全链路追踪能力。每个 HTTP 请求自动注入 trace_id，通过 ContextVar 在异步调用链中传递，日志和 LLM 调用自动关联，OpenTelemetry 自动创建 FastAPI span，可选 Jaeger 导出。

## 范围

1. **Trace ID** — UUID7 生成，请求头 `X-Trace-Id` 接收/返回
2. **结构化日志** — JSON 格式，自动注入 trace_id
3. **OpenTelemetry** — FastAPI auto-instrumentation + LLM 调用 span
4. **错误增强** — L4 全局异常处理器响应体自动附带 trace_id
5. **Jaeger exporter** — 可选，通过 `OTEL_EXPORTER_JAEGER_ENABLED=true` 环境变量开启

## 不做什么

- 不做 Prometheus metrics（Phase 4 独立做）
- 不做日志聚合（ELK/Loki 属于部署层，代码不做）
- 不修改现有业务代码（纯中间件层，零侵入）

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| Trace ID 格式 | UUID7 | 时间有序，数据库索引友好，无冲突 |
| 传递机制 | Python `contextvars.ContextVar` | 异步安全，无需修改函数签名 |
| OTel SDK | `opentelemetry-api` + `opentelemetry-instrumentation-fastapi` | 官方自动插桩 |
| 日志格式 | `python-json-logger` | 轻量，生产环境友好 |
| Jaeger protocol | gRPC（`opentelemetry-exporter-jaeger`） | OTel 官方支持 |
| 配置方式 | 环境变量 + `AppSettings` | 遵循现有模式 |

## 详细设计

### 1. TraceMiddleware（纯 ASGI）

```
请求到达
  → 读取 X-Trace-Id header（有 → 复用；无 → UUID7 生成）
  → ContextVar.set(trace_id)
  → 响应头注入 X-Trace-Id
  → 调用下游
```

和 MCP 的 `McpAuthMiddleware` 一样使用纯 ASGI 类，不劫持响应体，兼容 SSE 流。

### 2. 日志增强

```python
# 使用 logging.Filter 自动注入 trace_id
class TraceIdFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = get_trace_id() or "no-trace"
        return True
```

根 logger 配置 JSON 格式，通过 `LOG_FORMAT=json` 环境变量切换（默认 text）。

### 3. OpenTelemetry 初始化

在 `create_app()` 中按条件初始化：

```python
if settings.otel_enabled:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FastAPIInstrumentor.instrument_app(app)
```

Jaeger exporter 通过 `OTEL_EXPORTER_JAEGER_ENABLED=true` 单独控制，不绑定 OTel 开启。

### 4. LLM 调用追踪

`RealLLMClient._call_with_fallback` 中记录每次 LLM 调用的 trace_id、模型名、耗时、是否降级，日志示例：

```json
{"level": "INFO", "trace_id": "0193...", "model": "minimax-M3", "latency_ms": 320, "fallback": false, "msg": "LLM call completed"}
```

### 5. 错误增强

全局 exception handler 响应体追加 trace_id：

```python
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "trace_id": get_trace_id(), "detail": str(exc)}
    )
```

替换当前的 trace_id 占位逻辑（L4 降级已提到 trace_id 但未实现自动注入）。

### 6. AppSettings 新增字段

```python
# .env 新增
OTEL_ENABLED=true
OTEL_EXPORTER_JAEGER_ENABLED=false
OTEL_JAEGER_AGENT_HOST=localhost
OTEL_JAEGER_AGENT_PORT=6831
LOG_FORMAT=text  # text | json
```

## 项目结构

```
app/observability/
├── __init__.py          ← 导出 get_trace_id, setup_observability
├── middleware.py        ← TraceMiddleware（纯 ASGI 类）
└── logging.py           ← JSON formatter + TraceIdFilter
```

修改的文件：
- `app/app_main.py` — 注册 TraceMiddleware + 全局 exception handler
- `app/backend/config/settings.py` — 新增 6 个配置字段
- `app/agents/llm_client/client.py` — LLM 调用日志加 trace_id 字段
- `pyproject.toml` — 新增 `opentelemetry-api`, `opentelemetry-instrumentation-fastapi`, `python-json-logger`

## 测试策略

| 层级 | 数量 | 测什么 |
|------|------|--------|
| 单元 | 8-10 | TraceMiddleware UUID 生成、ContextVar 读写、TraceIdFilter 注入、JSON formatter 输出 |
| 集成 | 2-3 | 请求响应头 X-Trace-Id 往返、SSE 流不受影响 |
| LLM | 2-3 | LLM 调用日志包含 trace_id 字段 |

明确不测：Jaeger exporter 连接、OpenTelemetry span 内容（属于 OTel SDK 内部行为）。

## 扩展路径

- Phase 4 可观测性 v2：Prometheus metrics（请求数、延迟、错误率）
- 数据库查询追踪：SQLAlchemy auto-instrumentation
- 日志聚合：ELK / Loki 由部署层配置，代码层不做
