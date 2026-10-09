import base64
import json
import logging

from fastapi import Request
from fastapi.responses import Response
from openai import AsyncOpenAI
from starlette.datastructures import UploadFile

from auth import VisionAuth
from common import is_valid_image, vision_url
from handlers.base import add_cors_headers
from manager_api import ManagerApiClient


LOGGER = logging.getLogger(__name__)
MAX_FILE_SIZE = 5 * 1024 * 1024


class VisionHandler:
    def __init__(self, config: dict, manager_api: ManagerApiClient):
        self.config = config
        self.manager_api = manager_api
        self.auth = VisionAuth(config["server"]["auth_key"])

    def _verify(self, request: Request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False, None
        return self.auth.verify_token(auth_header[7:])

    async def post(self, request: Request) -> Response:
        try:
            valid, token_device_id = self._verify(request)
            if not valid:
                return add_cors_headers(
                    Response(
                        json.dumps(
                            {"success": False, "message": "无效的认证token或token已过期"}
                        ),
                        media_type="application/json",
                        status_code=401,
                    )
                )

            device_id = request.headers.get("Device-Id", "")
            client_id = request.headers.get("Client-Id", "")
            if device_id != token_device_id:
                raise ValueError("设备ID与token不匹配")

            form = await request.form()
            question_field = form.get("question")
            if question_field is None or isinstance(question_field, UploadFile):
                raise ValueError("缺少问题字段")
            image_field = form.get("image") or form.get("file")
            if not isinstance(image_field, UploadFile):
                raise ValueError("缺少图片文件")
            image_data = await image_field.read()
            if not image_data:
                raise ValueError("图片数据为空")
            if len(image_data) > MAX_FILE_SIZE:
                raise ValueError("图片大小超过限制，最大允许5MB")
            if not is_valid_image(image_data):
                raise ValueError("不支持的图片格式")

            current_config = self.config
            if self.manager_api.enabled:
                current_config = await self.manager_api.get_agent_models(
                    device_id,
                    client_id,
                    self.config.get("selected_module", {}),
                )

            selected = current_config.get("selected_module", {}).get("VLLM")
            provider = current_config.get("VLLM", {}).get(selected, {})
            if not selected or not provider:
                raise ValueError("您还未设置默认的视觉分析模块")
            if provider.get("type", "openai") != "openai":
                raise ValueError(f"不支持的VLLM类型: {provider.get('type')}")

            client = AsyncOpenAI(
                api_key=provider.get("api_key"),
                base_url=provider.get("base_url") or provider.get("url"),
            )
            completion = await client.chat.completions.create(
                model=provider.get("model_name"),
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"{question_field}(请使用中文回复)"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": "data:image/jpeg;base64,"
                                    + base64.b64encode(image_data).decode("utf-8")
                                },
                            },
                        ],
                    }
                ],
                stream=False,
                max_tokens=int(provider.get("max_tokens") or 500),
                temperature=float(provider.get("temperature") or 0.7),
                top_p=float(provider.get("top_p") or 1.0),
            )
            result = {
                "success": True,
                "action": "RESPONSE",
                "response": completion.choices[0].message.content,
            }
            response = Response(
                json.dumps(result, separators=(",", ":")),
                media_type="application/json",
            )
        except ValueError as error:
            response = Response(
                json.dumps({"success": False, "message": str(error)}),
                media_type="application/json",
            )
        except Exception as error:
            LOGGER.exception("视觉分析处理失败: %s", error)
            response = Response(
                json.dumps({"success": False, "message": "处理请求时发生错误"}),
                media_type="application/json",
            )
        return add_cors_headers(response)

    async def get(self, request: Request) -> Response:
        del request
        message = f"MCP Vision 接口运行正常，视觉解释接口地址是：{vision_url(self.config)}"
        return add_cors_headers(Response(message, media_type="text/plain"))
