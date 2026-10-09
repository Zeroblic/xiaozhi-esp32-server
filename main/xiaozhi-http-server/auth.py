import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class DeviceAuth:
    """生成与 WebSocket 服务兼容的 HMAC Token。"""

    def __init__(self, secret_key: str, expire_seconds: int | None = None):
        self.secret_key = secret_key
        self.expire_seconds = expire_seconds or 60 * 60 * 24 * 30

    def _sign(self, content: str) -> str:
        signature = hmac.new(
            self.secret_key.encode("utf-8"), content.encode("utf-8"), hashlib.sha256
        ).digest()
        return base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")

    def generate_token(self, client_id: str, device_id: str) -> str:
        timestamp = int(time.time())
        return f"{self._sign(f'{client_id}|{device_id}|{timestamp}')}.{timestamp}"


class VisionAuth:
    """验证 xiaozhi-server 为视觉接口生成的 JWT/AES Token。"""

    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"fixed_salt_placeholder",
            iterations=100000,
            backend=default_backend(),
        )
        self.encryption_key = kdf.derive(self.secret_key)

    def _decrypt_payload(self, encrypted_data: str) -> dict:
        data = base64.urlsafe_b64decode(encrypted_data.encode())
        cipher = Cipher(
            algorithms.AES(self.encryption_key),
            modes.GCM(data[:12], data[-16:]),
            backend=default_backend(),
        )
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(data[12:-16]) + decryptor.finalize()
        return json.loads(plaintext.decode())

    def verify_token(self, token: str) -> Tuple[bool, Optional[str]]:
        try:
            outer_payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            inner_payload = self._decrypt_payload(outer_payload["data"])
            if inner_payload["exp"] < time.time():
                return False, None
            return True, inner_payload["device_id"]
        except Exception:
            return False, None

    def generate_token(self, device_id: str) -> str:
        """供兼容性测试和独立调试使用。"""
        payload = {
            "device_id": device_id,
            "exp": (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp(),
        }
        iv = os.urandom(12)
        cipher = Cipher(
            algorithms.AES(self.encryption_key),
            modes.GCM(iv),
            backend=default_backend(),
        )
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(json.dumps(payload).encode()) + encryptor.finalize()
        data = base64.urlsafe_b64encode(iv + encrypted + encryptor.tag).decode()
        return jwt.encode({"data": data}, self.secret_key, algorithm="HS256")
