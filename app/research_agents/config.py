from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path


@dataclass(frozen=True)
class ResearchConfig:
    app_name: str = "Deep Research Scaffold"
    model: str = "stub"
    max_iterations: int = 2
    enable_memory: bool = True
    memory_top_k: int = 6
    web_search_enabled: bool = True
    local_rag_enabled: bool = True

    @classmethod
    def from_file(cls, path: str | Path) -> "ResearchConfig":
        config_path = Path(path).resolve()
        data: dict = {}
        if config_path.exists():
            data = json.loads(config_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError(f"Config must be a JSON object: {config_path}")
        return cls(
            app_name=_str(data, "app_name", "APP_NAME", cls.app_name),
            model=_str(data, "model", "MODEL", cls.model),
            max_iterations=_int(data, "max_iterations", "MAX_ITERATIONS", cls.max_iterations),
            enable_memory=_bool(data, "enable_memory", "ENABLE_MEMORY", cls.enable_memory),
            memory_top_k=_int(data, "memory_top_k", "MEMORY_TOP_K", cls.memory_top_k),
            web_search_enabled=_bool(data, "web_search_enabled", "WEB_SEARCH_ENABLED", cls.web_search_enabled),
            local_rag_enabled=_bool(data, "local_rag_enabled", "LOCAL_RAG_ENABLED", cls.local_rag_enabled),
        )

    def with_overrides(self, **kwargs) -> "ResearchConfig":
        return replace(self, **{key: value for key, value in kwargs.items() if value is not None})


def _str(data: dict, key: str, env_key: str, default: str) -> str:
    value = os.getenv(env_key)
    if value is not None and value.strip():
        return value.strip()
    raw = data.get(key)
    if raw is not None and str(raw).strip():
        return str(raw).strip()
    return default


def _int(data: dict, key: str, env_key: str, default: int) -> int:
    return int(_str(data, key, env_key, str(default)))


def _bool(data: dict, key: str, env_key: str, default: bool) -> bool:
    value = _str(data, key, env_key, "true" if default else "false").lower()
    return value in {"1", "true", "yes", "on"}

