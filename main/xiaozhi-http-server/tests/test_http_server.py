import hashlib
import hmac
import base64
import sys
import unittest
from pathlib import Path

import yaml
from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_DIR = APP_DIR.parents[1]
FIXTURE_DIR = APP_DIR / "tests" / "fixtures"
sys.path.insert(0, str(APP_DIR))

from app import create_app  # noqa: E402
from auth import DeviceAuth, VisionAuth  # noqa: E402
from handlers.ota import is_higher_version  # noqa: E402


def make_config(firmware_dir: str, manager_enabled: bool = False) -> dict:
    return {
        "server": {
            "ip": "127.0.0.1",
            "port": 8000,
            "http_port": 8003,
            "auth_key": "shared-test-secret",
            "websocket": "ws://voice.example/xiaozhi/v1/",
            "public_http_url": "https://http.example",
            "vision_explain": "https://http.example/mcp/vision/explain",
            "timezone_offset": 8,
            "auth": {"enabled": True, "allowed_devices": []},
        },
        "firmware": {"directory": firmware_dir, "cache_ttl": 30},
        "manager-api": (
            {"url": "http://manager.example", "secret": "manager-secret"}
            if manager_enabled
            else {"url": "", "secret": ""}
        ),
        "log": {"log_level": "WARNING"},
        "selected_module": {"VLLM": "test"},
        "VLLM": {"test": {"type": "openai", "api_key": "test"}},
    }


class AuthCompatibilityTest(unittest.TestCase):
    def test_device_token_uses_websocket_signature_format(self):
        auth = DeviceAuth("shared-test-secret")
        token = auth.generate_token("client-1", "device-1")
        signature, timestamp = token.split(".")
        expected = hmac.new(
            b"shared-test-secret",
            f"client-1|device-1|{timestamp}".encode(),
            hashlib.sha256,
        ).digest()
        self.assertEqual(signature, base64.urlsafe_b64encode(expected).decode().rstrip("="))

    def test_vision_token_round_trip(self):
        auth = VisionAuth("shared-test-secret")
        self.assertEqual(auth.verify_token(auth.generate_token("device-1")), (True, "device-1"))


class OtaTest(unittest.TestCase):
    def test_version_comparison(self):
        self.assertTrue(is_higher_version("1.10.0", "1.9.9"))
        self.assertFalse(is_higher_version("1.0", "1.0.0"))

    def test_ota_returns_new_firmware_and_compatible_token(self):
        app = create_app(make_config(str(FIXTURE_DIR)))
        with TestClient(app) as client:
            response = client.post(
                "/xiaozhi/ota/",
                headers={
                    "device-id": "device-1",
                    "client-id": "client-1",
                    "device-model": "esp32",
                    "device-version": "1.0.0",
                },
                json={},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["websocket"]["url"], "ws://voice.example/xiaozhi/v1/")
            self.assertTrue(payload["websocket"]["token"])
            self.assertEqual(payload["firmware"]["version"], "1.2.0")
            self.assertEqual(
                payload["firmware"]["url"],
                "https://http.example/xiaozhi/ota/download/esp32_1.2.0.bin",
            )
            download = client.get("/xiaozhi/ota/download/esp32_1.2.0.bin")
            self.assertEqual(download.content, b"firmware\n")

    def test_manager_mode_does_not_register_simple_ota(self):
        app = create_app(make_config(str(FIXTURE_DIR), manager_enabled=True))
        with TestClient(app) as client:
            self.assertEqual(client.get("/xiaozhi/ota/").status_code, 404)
            self.assertEqual(client.get("/mcp/vision/explain").status_code, 200)

    def test_vision_rejects_missing_token(self):
        app = create_app(make_config(str(FIXTURE_DIR)))
        with TestClient(app) as client:
            response = client.post("/mcp/vision/explain")
            self.assertEqual(response.status_code, 401)


class DeploymentConfigTest(unittest.TestCase):
    def test_compose_files_assign_http_port_to_new_service(self):
        for filename in ("docker-compose.yml", "docker-compose_all.yml"):
            path = REPOSITORY_DIR / "main" / "xiaozhi-server" / filename
            with path.open(encoding="utf-8") as file:
                compose = yaml.safe_load(file)
            services = compose["services"]
            self.assertNotIn("8003:8003", services["xiaozhi-esp32-server"].get("ports", []))
            self.assertIn("8003:8003", services["xiaozhi-http-server"]["ports"])


if __name__ == "__main__":
    unittest.main()
