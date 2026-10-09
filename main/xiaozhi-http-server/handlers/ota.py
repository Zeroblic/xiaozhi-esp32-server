import base64
import glob
import hashlib
import hmac
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Tuple

from fastapi import Request
from fastapi.responses import FileResponse, Response

from auth import DeviceAuth
from common import public_http_url, websocket_url
from config import resolve_firmware_dir
from handlers.base import add_cors_headers


LOGGER = logging.getLogger(__name__)


def parse_version(version: str) -> Tuple[int, ...]:
    parts = re.findall(r"\d+", version)
    return tuple(int(part) for part in parts) if parts else (0,)


def is_higher_version(candidate: str, current: str) -> bool:
    left = parse_version(candidate)
    right = parse_version(current)
    length = max(len(left), len(right))
    return left + (0,) * (length - len(left)) > right + (0,) * (
        length - len(right)
    )


class OtaHandler:
    def __init__(self, config: dict):
        self.config = config
        auth_config = config["server"].get("auth", {})
        self.auth_enabled = auth_config.get("enabled", False)
        self.allowed_devices = set(auth_config.get("allowed_devices", []))
        self.auth = DeviceAuth(
            config["server"]["auth_key"], auth_config.get("expire_seconds")
        )
        self.bin_dir = resolve_firmware_dir(config)
        self.cache: Dict = {
            "updated_at": 0,
            "ttl": config.get("firmware", {}).get(
                "cache_ttl", config.get("firmware_cache_ttl", 30)
            ),
            "files_by_model": {},
        }

    def _refresh_cache(self) -> None:
        now = int(time.time())
        if (
            now - int(self.cache["updated_at"]) < int(self.cache["ttl"])
            and self.cache["files_by_model"]
        ):
            return

        self.bin_dir.mkdir(parents=True, exist_ok=True)
        files_by_model: Dict[str, List[Tuple[str, str]]] = {}
        pattern = str(self.bin_dir / "*.bin")
        for path in glob.glob(pattern):
            filename = os.path.basename(path)
            match = re.match(r"^(.+?)_([0-9][A-Za-z0-9.\-_]*)\.bin$", filename)
            if not match:
                continue
            files_by_model.setdefault(match.group(1), []).append(
                (match.group(2), filename)
            )
        for items in files_by_model.values():
            items.sort(key=lambda item: parse_version(item[0]), reverse=True)
        self.cache.update(updated_at=now, files_by_model=files_by_model)

    @staticmethod
    def _mqtt_password(content: str, secret: str) -> str:
        signature = hmac.new(
            secret.encode("utf-8"), content.encode("utf-8"), hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode("utf-8")

    async def post(self, request: Request) -> Response:
        try:
            raw_body = (await request.body()).decode("utf-8")
            body = json.loads(raw_body) if raw_body else {}
            device_id = request.headers.get("device-id", "")
            client_id = request.headers.get("client-id", "")
            if not device_id or not client_id:
                raise ValueError("device-id 和 client-id 不能为空")

            device_model = next(
                (
                    request.headers.get(header, "").strip()
                    for header in ("device-model", "device_model", "model")
                    if request.headers.get(header)
                ),
                "",
            )
            if not device_model:
                board = body.get("board", {})
                device_model = board.get("type", "") or body.get("model", "default")

            device_version = next(
                (
                    request.headers.get(header, "").strip()
                    for header in (
                        "device-version",
                        "device_version",
                        "firmware-version",
                        "app-version",
                        "application-version",
                    )
                    if request.headers.get(header)
                ),
                "",
            ) or body.get("application", {}).get("version", "0.0.0")

            server = self.config["server"]
            result = {
                "server_time": {
                    "timestamp": int(round(time.time() * 1000)),
                    "timezone_offset": server.get("timezone_offset", 8) * 60,
                },
                "firmware": {"version": device_version, "url": ""},
            }

            mqtt_endpoint = server.get("mqtt_gateway")
            if mqtt_endpoint:
                group_id = f"GID_{device_model}".replace(":", "_").replace(" ", "_")
                safe_device_id = device_id.replace(":", "_")
                mqtt_client_id = f"{group_id}@@@{safe_device_id}@@@{safe_device_id}"
                username = base64.b64encode(
                    json.dumps({"ip": "unknown"}).encode("utf-8")
                ).decode("utf-8")
                signature_key = server.get("mqtt_signature_key", "")
                password = (
                    self._mqtt_password(f"{mqtt_client_id}|{username}", signature_key)
                    if signature_key
                    else ""
                )
                result["mqtt"] = {
                    "endpoint": mqtt_endpoint,
                    "client_id": mqtt_client_id,
                    "username": username,
                    "password": password,
                    "publish_topic": "device-server",
                    "subscribe_topic": f"devices/p2p/{safe_device_id}",
                }
            else:
                token = ""
                if self.auth_enabled and device_id not in self.allowed_devices:
                    token = self.auth.generate_token(client_id, device_id)
                result["websocket"] = {
                    "url": websocket_url(self.config),
                    "token": token,
                }

            self._refresh_cache()
            for version, filename in self.cache["files_by_model"].get(
                device_model, []
            ):
                if is_higher_version(version, device_version):
                    result["firmware"] = {
                        "version": version,
                        "url": f"{public_http_url(self.config)}/xiaozhi/ota/download/{filename}",
                    }
                    break

            response = Response(
                json.dumps(result, separators=(",", ":")),
                media_type="application/json",
            )
        except Exception as error:
            LOGGER.exception("OTA POST 处理失败: %s", error)
            response = Response(
                json.dumps({"success": False, "message": "request error."}),
                media_type="application/json",
            )
        return add_cors_headers(response)

    async def get(self, request: Request) -> Response:
        del request
        message = f"OTA接口运行正常，向设备发送的websocket地址是：{websocket_url(self.config)}"
        return add_cors_headers(Response(message, media_type="text/plain"))

    async def download(self, request: Request, filename: str) -> Response:
        del request
        safe_name = os.path.basename(filename)
        if safe_name != filename or not re.fullmatch(
            r"[A-Za-z0-9.\-_]+\.bin", safe_name
        ):
            return add_cors_headers(Response("invalid filename", status_code=400))

        file_path = (self.bin_dir / safe_name).resolve()
        try:
            file_path.relative_to(self.bin_dir)
        except ValueError:
            return add_cors_headers(Response("forbidden", status_code=403))
        if not file_path.is_file():
            return add_cors_headers(Response("file not found", status_code=404))
        return add_cors_headers(FileResponse(path=Path(file_path)))
