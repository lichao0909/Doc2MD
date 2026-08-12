"""应用设置：持久化到项目根目录的 config.json（已 gitignore）。

敏感信息（API Key / Token）优先从环境变量或项目根目录 .env 文件读取，
不写入 config.json，防止泄露到版本控制。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# 尝试加载 .env 文件（开发环境）
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


CONFIG_PATH = _app_dir() / "config.json"

DEFAULTS: dict[str, Any] = {
    "engine": "auto",
    "vision_dpi": 150,
    "vision_jpeg_quality": 85,
    "vision_model": "glm-4v-flash",
    "vision_api_key": "",
    "output_mode": "source",
    "output_dir": "",
    "appearance_mode": "System",
}


def load() -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass

    # 敏感字段：环境变量优先（.env / 系统环境变量）
    _env_override(cfg, "vision_api_key", "VISION_API_KEY")
    _env_override(cfg, "vision_base_url", "VISION_BASE_URL")
    _env_override(cfg, "vision_model", "VISION_MODEL")

    return cfg


def _env_override(cfg: dict[str, Any], cfg_key: str, env_key: str) -> None:
    """若环境变量存在，覆盖 config 中的对应字段。"""
    val = os.getenv(env_key)
    if val:
        cfg[cfg_key] = val


def save(cfg: dict[str, Any]) -> None:
    CONFIG_PATH.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
