import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from config import load_local_config, resolve_auth_key
from handlers.base import add_cors_headers
from handlers.ota import OtaHandler
from handlers.vision import VisionHandler
from manager_api import ManagerApiClient


def configure_logging(config: dict) -> None:
    level = config.get("log", {}).get("log_level", "INFO")
    logging.basicConfig(
        level=getattr(logging, str(level).upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )


def create_app(initial_config: dict | None = None) -> FastAPI:
    local_config = initial_config or load_local_config()
    manager_api = ManagerApiClient(local_config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config = local_config
        if manager_api.enabled and not initial_config:
            remote_config = await manager_api.get_server_config()
            remote_config["server"] = local_config.get("server", {})
            remote_config["manager-api"] = local_config.get("manager-api", {})
            remote_config["firmware"] = local_config.get("firmware", {})
            remote_config["log"] = local_config.get("log", {})
            remote_config["read_config_from_api"] = True
            config = remote_config

        resolve_auth_key(config)
        configure_logging(config)
        app.state.config = config
        app.state.ota = OtaHandler(config)
        app.state.vision = VisionHandler(config, manager_api)
        app.state.ready = True
        logging.getLogger(__name__).info(
            "HTTP 服务已启动: %s:%s",
            config["server"].get("ip", "0.0.0.0"),
            config["server"].get("http_port", 8003),
        )
        yield
        app.state.ready = False

    app = FastAPI(
        title="Xiaozhi HTTP Server",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.ready = False

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/ready")
    async def ready():
        if not app.state.ready:
            return JSONResponse({"status": "starting"}, status_code=503)
        return {"status": "ready"}

    if not manager_api.enabled:

        @app.get("/xiaozhi/ota/")
        async def ota_get(request: Request):
            return await request.app.state.ota.get(request)

        @app.post("/xiaozhi/ota/")
        async def ota_post(request: Request):
            return await request.app.state.ota.post(request)

        @app.options("/xiaozhi/ota/")
        async def ota_options():
            return add_cors_headers(Response())

        @app.get("/xiaozhi/ota/download/{filename}")
        async def ota_download(request: Request, filename: str):
            return await request.app.state.ota.download(request, filename)

        @app.options("/xiaozhi/ota/download/{filename}")
        async def ota_download_options(filename: str):
            del filename
            return add_cors_headers(Response())

    @app.get("/mcp/vision/explain")
    async def vision_get(request: Request):
        return await request.app.state.vision.get(request)

    @app.post("/mcp/vision/explain")
    async def vision_post(request: Request):
        return await request.app.state.vision.post(request)

    @app.options("/mcp/vision/explain")
    async def vision_options():
        return add_cors_headers(Response())

    return app


app = create_app()


if __name__ == "__main__":
    config = load_local_config()
    uvicorn.run(
        app,
        host=config["server"].get("ip", "0.0.0.0"),
        port=int(config["server"].get("http_port", 8003)),
        log_config=None,
    )
