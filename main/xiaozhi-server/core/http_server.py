from contextlib import contextmanager

import uvicorn
from fastapi import FastAPI
from config.logger import setup_logging
from core.api.ota_handler import OTAHandler
from core.api.vision_handler import VisionHandler

TAG = __name__


class EmbeddedUvicornServer(uvicorn.Server):
    """让顶层 app.py 统一负责进程信号和任务生命周期。"""

    @contextmanager
    def capture_signals(self):
        yield


class SimpleHttpServer:
    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logging()
        self.ota_handler = OTAHandler(config)
        self.vision_handler = VisionHandler(config)

    def _get_websocket_url(self, local_ip: str, port: int) -> str:
        """获取websocket地址

        Args:
            local_ip: 本地IP地址
            port: 端口号

        Returns:
            str: websocket地址
        """
        server_config = self.config["server"]
        websocket_config = server_config.get("websocket")

        if websocket_config and "你" not in websocket_config:
            return websocket_config
        else:
            return f"ws://{local_ip}:{port}/xiaozhi/v1/"

    async def start(self):
        try:
            server_config = self.config["server"]
            read_config_from_api = self.config.get("read_config_from_api", False)
            host = server_config.get("ip", "0.0.0.0")
            port = int(server_config.get("http_port", 8003))

            if port:
                app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

                if not read_config_from_api:
                    # 如果没有开启智控台，只是单模块运行，就需要再添加简单OTA接口，用于下发websocket接口
                    app.add_api_route(
                        "/xiaozhi/ota/", self.ota_handler.handle_get, methods=["GET"]
                    )
                    app.add_api_route(
                        "/xiaozhi/ota/", self.ota_handler.handle_post, methods=["POST"]
                    )
                    app.add_api_route(
                        "/xiaozhi/ota/",
                        self.ota_handler.handle_options,
                        methods=["OPTIONS"],
                    )
                    app.add_api_route(
                        "/xiaozhi/ota/download/{filename}",
                        self.ota_handler.handle_download,
                        methods=["GET"],
                    )
                    app.add_api_route(
                        "/xiaozhi/ota/download/{filename}",
                        self.ota_handler.handle_options,
                        methods=["OPTIONS"],
                    )

                app.add_api_route(
                    "/mcp/vision/explain",
                    self.vision_handler.handle_get,
                    methods=["GET"],
                )
                app.add_api_route(
                    "/mcp/vision/explain",
                    self.vision_handler.handle_post,
                    methods=["POST"],
                )
                app.add_api_route(
                    "/mcp/vision/explain",
                    self.vision_handler.handle_options,
                    methods=["OPTIONS"],
                )

                server = EmbeddedUvicornServer(
                    uvicorn.Config(app, host=host, port=port, log_config=None)
                )
                await server.serve()
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"HTTP服务器启动失败: {e}")
            import traceback

            self.logger.bind(tag=TAG).error(f"错误堆栈: {traceback.format_exc()}")
            raise
