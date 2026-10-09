import copy
import os
from pathlib import Path

import yaml


PROJECT_DIR = Path(__file__).resolve().parent


def merge_configs(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _read_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def load_local_config(config_path: str | None = None) -> dict:
    config = _read_yaml(PROJECT_DIR / "config.yaml")
    custom_path = Path(
        config_path
        or os.getenv("XIAOZHI_HTTP_CONFIG", str(PROJECT_DIR / "data" / ".config.yaml"))
    ).resolve()
    config = merge_configs(config, _read_yaml(custom_path))

    server = config.setdefault("server", {})
    if os.getenv("XIAOZHI_AUTH_KEY"):
        server["auth_key"] = os.environ["XIAOZHI_AUTH_KEY"]
    if os.getenv("XIAOZHI_WEBSOCKET_URL"):
        server["websocket"] = os.environ["XIAOZHI_WEBSOCKET_URL"]
    if os.getenv("XIAOZHI_HTTP_HOST"):
        server["ip"] = os.environ["XIAOZHI_HTTP_HOST"]
    if os.getenv("XIAOZHI_HTTP_PORT"):
        server["http_port"] = int(os.environ["XIAOZHI_HTTP_PORT"])
    if os.getenv("XIAOZHI_PUBLIC_HTTP_URL"):
        server["public_http_url"] = os.environ["XIAOZHI_PUBLIC_HTTP_URL"].rstrip("/")
    if os.getenv("XIAOZHI_FIRMWARE_DIR"):
        config.setdefault("firmware", {})["directory"] = os.environ[
            "XIAOZHI_FIRMWARE_DIR"
        ]

    config["_config_path"] = str(custom_path)
    return config


def resolve_auth_key(config: dict) -> str:
    server = config.setdefault("server", {})
    candidates = (
        server.get("auth_key", ""),
        config.get("manager-api", {}).get("secret", ""),
    )
    for candidate in candidates:
        if candidate and "你" not in candidate:
            server["auth_key"] = candidate
            return candidate
    raise ValueError(
        "缺少共享认证密钥：请设置 XIAOZHI_AUTH_KEY 或 server.auth_key；"
        "xiaozhi-http-server 与 xiaozhi-server 必须使用相同的值"
    )


def resolve_firmware_dir(config: dict) -> Path:
    configured = config.get("firmware", {}).get("directory", "data/bin")
    path = Path(configured)
    if not path.is_absolute():
        path = PROJECT_DIR / path
    return path.resolve()
