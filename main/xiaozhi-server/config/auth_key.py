import os


def resolve_auth_key(config: dict) -> str:
    """解析跨进程共享密钥，禁止为每个进程生成不同的临时值。"""
    server = config.setdefault("server", {})
    candidates = (
        os.getenv("XIAOZHI_AUTH_KEY", ""),
        server.get("auth_key", ""),
        config.get("manager-api", {}).get("secret", ""),
    )
    for candidate in candidates:
        if candidate and "你" not in candidate:
            server["auth_key"] = candidate
            return candidate
    raise ValueError(
        "缺少共享认证密钥：请设置 XIAOZHI_AUTH_KEY 或 server.auth_key；"
        "xiaozhi-server 与 xiaozhi-http-server 必须使用相同的值"
    )
