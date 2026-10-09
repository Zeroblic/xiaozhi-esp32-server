from typing import Optional

import httpx


class ManagerApiClient:
    def __init__(self, config: dict):
        manager = config.get("manager-api", {})
        self.base_url = manager.get("url", "").rstrip("/")
        self.secret = manager.get("secret", "")
        self.timeout = manager.get("timeout", 30)

    @property
    def enabled(self) -> bool:
        return bool(
            self.base_url
            and self.secret
            and "你" not in self.base_url
            and "你" not in self.secret
        )

    async def _request(self, endpoint: str, json: Optional[dict] = None) -> dict:
        headers = {"Authorization": f"Bearer {self.secret}"}
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout,
            trust_env=False,
        ) as client:
            response = await client.post(endpoint.lstrip("/"), json=json)
            response.raise_for_status()
            result = response.json()
        if result.get("code") != 0:
            raise ValueError(result.get("msg", "manager-api 返回错误"))
        return result.get("data") or {}

    async def get_server_config(self) -> dict:
        return await self._request("/config/server-base")

    async def get_agent_models(
        self, device_id: str, client_id: str, selected_module: dict
    ) -> dict:
        return await self._request(
            "/config/agent-models",
            {
                "macAddress": device_id,
                "clientId": client_id,
                "selectedModule": selected_module,
            },
        )
