# Xiaozhi HTTP Server

独立承载简单 OTA、固件下载和视觉分析接口。该应用不会导入 `xiaozhi-server` 的代码或音频依赖。

## 配置

复制 `config.yaml` 到 `data/.config.yaml` 并修改。`xiaozhi-http-server` 与
`xiaozhi-server` 必须使用相同的 `server.auth_key`。也可以在两个进程中设置相同的
`XIAOZHI_AUTH_KEY`。

常用环境变量：

- `XIAOZHI_HTTP_CONFIG`：自定义配置文件绝对路径。
- `XIAOZHI_AUTH_KEY`：两个服务共享的认证密钥。
- `XIAOZHI_WEBSOCKET_URL`：下发给设备的 WebSocket 地址。
- `XIAOZHI_PUBLIC_HTTP_URL`：固件下载使用的公网 HTTP 根地址。
- `XIAOZHI_FIRMWARE_DIR`：固件目录。
- `XIAOZHI_HTTP_HOST`、`XIAOZHI_HTTP_PORT`：监听地址和端口。

## 启动

```bash
pip install -r requirements.txt
python app.py
```

健康检查为 `/health`，就绪检查为 `/ready`。启用 manager-api 配置时，保持原有行为：
简单 OTA 路由不注册，视觉接口继续提供服务。
