import socket
from urllib.parse import urlsplit, urlunsplit


def get_local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def websocket_url(config: dict) -> str:
    server = config["server"]
    configured = server.get("websocket", "")
    if configured and "你" not in configured:
        return configured
    return f"ws://{get_local_ip()}:{int(server.get('port', 8000))}/xiaozhi/v1/"


def public_http_url(config: dict) -> str:
    server = config["server"]
    configured = server.get("public_http_url", "")
    if configured and "你" not in configured:
        return configured.rstrip("/")

    vision_url = server.get("vision_explain", "")
    if vision_url and "你" not in vision_url and vision_url != "null":
        parts = urlsplit(vision_url)
        return urlunsplit((parts.scheme, parts.netloc, "", "", "")).rstrip("/")

    return f"http://{get_local_ip()}:{int(server.get('http_port', 8003))}"


def vision_url(config: dict) -> str:
    configured = config["server"].get("vision_explain", "")
    if configured and "你" not in configured and configured != "null":
        return configured
    return f"{public_http_url(config)}/mcp/vision/explain"


def is_valid_image(data: bytes) -> bool:
    signatures = (
        b"\xff\xd8\xff",  # JPEG
        b"\x89PNG\r\n\x1a\n",
        b"GIF87a",
        b"GIF89a",
        b"BM",
        b"II*\x00",
        b"MM\x00*",
        b"RIFF",  # WEBP is checked below
    )
    if not any(data.startswith(signature) for signature in signatures):
        return False
    return not data.startswith(b"RIFF") or (len(data) >= 12 and data[8:12] == b"WEBP")
