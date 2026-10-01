"""配置加载：config.yaml + 可选的 .env（手写极简加载，避免额外依赖）。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else PROJECT_ROOT / "config.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"找不到配置文件: {cfg_path}")

    _load_dotenv(PROJECT_ROOT / ".env")

    with cfg_path.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    # 用环境变量覆盖券商密钥（存在则优先）
    alpaca = cfg.setdefault("broker", {}).setdefault("alpaca", {})
    alpaca.setdefault("api_key", os.environ.get("ALPACA_API_KEY", ""))
    alpaca.setdefault("secret_key", os.environ.get("ALPACA_SECRET_KEY", ""))
    return cfg
