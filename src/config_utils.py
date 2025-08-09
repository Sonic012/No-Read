import os
from typing import Dict, Tuple, Optional


PLACEHOLDER_VALUES: Dict[str, str] = {
    "WEREAD_COOKIE": "your_weread_cookie_here",
    "NOTION_TOKEN": "secret_your_notion_integration_token",
    "NOTION_DATABASE_ID": "your_notion_database_id",
}


def load_dotenv_if_available() -> None:
    """Best-effort 加载 .env 文件（如果安装了 python-dotenv）。"""
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(override=False)
    except Exception:
        # 不强依赖 dotenv；未安装时静默跳过
        pass


def is_placeholder(value: Optional[str], key: str) -> bool:
    """判断配置值是否为占位符。"""
    if value is None:
        return True
    placeholder = PLACEHOLDER_VALUES.get(key)
    if not placeholder:
        return False
    return value.strip() == placeholder


def get_config_value(key: str, fallback_module=None) -> Optional[str]:
    """获取配置值，优先环境变量，其次 fallback_module 中的属性；占位符视为无效。"""
    env_val = os.getenv(key)
    if env_val and not is_placeholder(env_val, key):
        return env_val
    if fallback_module is not None and hasattr(fallback_module, key):
        mod_val = getattr(fallback_module, key)
        if isinstance(mod_val, str) and not is_placeholder(mod_val, key) and mod_val.strip():
            return mod_val
    return None


def validate_required_config(fallback_module=None) -> Tuple[bool, Dict[str, Optional[str]], str]:
    """校验运行所需关键配置。

    Returns:
        ok: 是否通过
        cfg: 解析后的配置映射
        msg: 错误信息（当未通过时）
    """
    base_required = ["WEREAD_COOKIE", "NOTION_TOKEN"]
    optional_or = ["NOTION_DATABASE_ID", "NOTION_PARENT_PAGE_ID"]
    cfg: Dict[str, Optional[str]] = {}

    # 填充必填项
    for key in base_required:
        cfg[key] = get_config_value(key, fallback_module=fallback_module)

    # 填充可二选一项
    for key in optional_or:
        cfg[key] = get_config_value(key, fallback_module=fallback_module)

    missing_base = [k for k in base_required if not cfg.get(k)]
    has_db_id = bool(cfg.get("NOTION_DATABASE_ID"))
    has_parent = bool(cfg.get("NOTION_PARENT_PAGE_ID"))

    if missing_base:
        return False, cfg, (
            "配置缺失/无效: " + ", ".join(missing_base) +
            "。请通过环境变量或有效的 config.py 填写。"
        )

    if not (has_db_id or has_parent):
        return False, cfg, (
            "缺少 NOTION_DATABASE_ID 或 NOTION_PARENT_PAGE_ID（需至少提供其一）。"
        )

    return True, cfg, "OK"


