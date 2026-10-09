from fastapi.responses import Response


def add_cors_headers(response: Response) -> Response:
    response.headers["Access-Control-Allow-Headers"] = (
        "client-id, content-type, device-id, authorization"
    )
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response
