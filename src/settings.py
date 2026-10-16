"""统一配置加载：环境变量 > config.py > 内置默认值。

- GitHub Actions 上没有 config.py，配置全部来自 Repository Secrets；
- 本地开发仍可保留 config.py，但同名环境变量优先级更高；
- 因此同一份代码既能跑在 CI，也能跑在本地，互不干扰。
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULTS: Dict[str, Any] = {
    # 微信读书官方 Agent API
    "WEREAD_API_KEY": "",
    "WEREAD_SKILL_VERSION": "1.0.5",
    "WEREAD_RATE_LIMIT": 30,
    "WEREAD_REQUEST_DELAY": 0.5,
    # Notion
    "NOTION_TOKEN": "",
    "NOTION_DATABASE_ID": "",
    "NOTION_PARENT_PAGE_ID": "",
    "NOTION_RATE_LIMIT": 3,
    "NOTION_REQUEST_TIMEOUT": 60,
    "NOTION_MAX_RETRIES": 5,
    # 同步范围（默认全量对账，不做过滤）
    "SYNC_FINISHED_BOOKS": True,
    "SYNC_UNFINISHED_BOOKS": True,
    "SYNC_BOOK_COVERS": True,
    "SYNC_BOOK_REVIEWS": True,
    "SYNC_READING_NOTES": True,
    # 缓存与重试
    "BOOK_CACHE_FILE": "logs/book_metadata.json",
    "BOOK_CACHE_TTL": 604800,
    "MAX_RETRIES": 3,
    "RETRY_DELAY": 2,
    # 日志
    "LOG_LEVEL": "INFO",
    "LOG_FILE": "logs/sync.log",
    "LOG_FORMAT": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "LOG_MAX_SIZE": 10 * 1024 * 1024,
    "LOG_BACKUP_COUNT": 5,
}


def _coerce(raw: str, template: Any) -> Any:
    """按默认值的类型把环境变量字符串转成目标类型。"""
    if isinstance(template, bool):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(template, int):
        return int(raw)
    if isinstance(template, float):
        return float(raw)
    return raw


def _load_local_config() -> Dict[str, Any]:
    """读取项目根目录的 config.py（存在才读，格式错误时忽略）。"""
    path = PROJECT_ROOT / "config.py"
    if not path.is_file():
        return {}
    spec = importlib.util.spec_from_file_location("_noread_local_config", path)
    if spec is None or spec.loader is None:
        return {}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {key: getattr(module, key) for key in DEFAULTS if hasattr(module, key)}


def _load() -> Dict[str, Any]:
    global _LOCAL_CONFIG
    values = dict(DEFAULTS)
    _LOCAL_CONFIG = _load_local_config()
    values.update(_LOCAL_CONFIG)

    # 环境变量最后生效：CI 只靠 Secrets，本地可用环境变量临时覆盖 config.py
    for key, template in DEFAULTS.items():
        raw = os.getenv(key)
        if raw is None or raw == "":
            continue
        values[key] = _coerce(raw, template)

    return values


_LOCAL_CONFIG: Dict[str, Any] = {}

globals().update(_load())

# 便于排查：指出关键项的来源（只报来源，不打印敏感值）
SOURCES: Dict[str, str] = {}
for _key in ("WEREAD_API_KEY", "NOTION_TOKEN", "NOTION_DATABASE_ID"):
    if os.getenv(_key):
        SOURCES[_key] = "env"
    elif _LOCAL_CONFIG.get(_key):
        SOURCES[_key] = "config.py"
    else:
        SOURCES[_key] = "missing"
