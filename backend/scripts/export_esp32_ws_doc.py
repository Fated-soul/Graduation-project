from __future__ import annotations

from backend.scripts.export_word_docs import (
    PROJECT_ROOT,
    _bullet,
    _code_block,
    _paragraph,
    _table,
    _write_docx,
)


def create_esp32_websocket_doc() -> None:
    title = "ESP32 WebSocket硬件端对接说明"
    blocks = [
        _paragraph(title, "Title"),
        _paragraph(
            "适用对象：负责 ESP32、电击模块、爆闪灯、噪声模块接线和固件开发的同学。"
            "目标是让前端点击按钮后，命令通过 FastAPI WebSocket 实时推送到 ESP32，并由 ESP32 立即执行。"
        ),
        _paragraph("整体流程", "Heading1"),
        _bullet("你这边启动 PostgreSQL、FastAPI 后端和 ngrok http 8000。"),
        _bullet("硬件端 ESP32 连接 WiFi 后，主动连接后端 WebSocket。"),
        _bullet("前端点击“立即电击”“立即爆闪”或“立即噪声”后，后端马上推送控制命令。"),
        _bullet("ESP32 收到命令后控制对应 GPIO，执行完成后回传结果。"),
        _bullet("后端收到 completed 回执后，自动写入 stimulation_events，前端刺激事件表会显示真实执行记录。"),
        _paragraph("他需要填写的服务器配置", "Heading1"),
        _paragraph("假设你这边 ngrok 显示的地址是：https://xxxx.ngrok-free.dev，则硬件端这样配置："),
        _table(
            ["配置项", "示例值", "说明"],
            [
                ("SERVER_HOST", "xxxx.ngrok-free.dev", "只填域名，不要带 https://。"),
                ("SERVER_PORT", "443", "wss/https 默认端口。"),
                ("DEVICE_ID", "ESP32-002", "必须和后端 devices 表里的 device_id 一致。"),
                ("WS_PATH", "/api/ws/devices/ESP32-002", "最后一段改成自己的设备编号。"),
                (
                    "完整 WebSocket 地址",
                    "wss://xxxx.ngrok-free.dev/api/ws/devices/ESP32-002",
                    "如果库支持完整 URL，可以直接使用这一整串。",
                ),
            ],
            [1900, 2900, 4560],
        ),
        _paragraph("ESP32 连接成功后会收到", "Heading1"),
        _code_block(
            """
{
  "type": "connected",
  "device_id": "ESP32-002",
  "message": "device websocket connected"
}
            """
        ),
        _paragraph("ESP32 会收到的控制命令", "Heading1"),
        _paragraph("电击命令示例："),
        _code_block(
            """
{
  "type": "control_command",
  "command_id": "后端生成的唯一命令编号",
  "mouse_id": "MOUSE-002",
  "device_id": "ESP32-002",
  "command_type": "electric_shock",
  "duration_ms": 1500,
  "intensity": null
}
            """
        ),
        _paragraph("爆闪命令示例："),
        _code_block(
            """
{
  "type": "control_command",
  "command_id": "后端生成的唯一命令编号",
  "mouse_id": "MOUSE-002",
  "device_id": "ESP32-002",
  "command_type": "flash",
  "duration_ms": 3000,
  "intensity": null
}
            """
        ),
        _paragraph("噪声命令示例："),
        _code_block(
            """
{
  "type": "control_command",
  "command_id": "后端生成的唯一命令编号",
  "mouse_id": "MOUSE-002",
  "device_id": "ESP32-002",
  "command_type": "noise",
  "duration_ms": 3000,
  "intensity": null
}
            """
        ),
        _paragraph("ESP32 执行后必须回传", "Heading1"),
        _paragraph("执行成功时，通过同一个 WebSocket 发送："),
        _code_block(
            """
{
  "command_id": "原样带回后端发来的 command_id",
  "status": "completed",
  "message": "ok"
}
            """
        ),
        _paragraph("执行失败时发送："),
        _code_block(
            """
{
  "command_id": "原样带回后端发来的 command_id",
  "status": "failed",
  "message": "说明失败原因，例如 relay timeout"
}
            """
        ),
        _paragraph("建议的 ESP32 固件任务", "Heading1"),
        _table(
            ["步骤", "硬件端需要做什么"],
            [
                ("1", "确认 ESP32 可以连接互联网，并能访问你的 ngrok 域名。"),
                ("2", "安装 WebSocket 客户端库和 JSON 解析库，例如 ArduinoWebsockets 与 ArduinoJson。"),
                ("3", "配置 WiFi、SERVER_HOST、SERVER_PORT、DEVICE_ID、WS_PATH。"),
                ("4", "启动后连接 wss:// 域名加 WS_PATH，并在断线后自动重连。"),
                ("5", "收到 command_type=flash 时，拉高爆闪灯控制 GPIO，持续 duration_ms 后关闭。"),
                ("6", "收到 command_type=electric_shock 时，拉高电击模块控制 GPIO，持续 duration_ms 后关闭。"),
                ("7", "收到 command_type=noise 时，拉高噪声模块控制 GPIO，持续 duration_ms 后关闭。"),
                ("8", "无论成功或失败，都把 command_id 和 status 回传给后端。"),
                ("9", "定期发送 heartbeat，或至少保持 WebSocket 循环持续运行。"),
            ],
            [1100, 8260],
        ),
        _paragraph("参考固件伪代码", "Heading1"),
        _code_block(
            r"""
#include <WiFi.h>
#include <ArduinoJson.h>
#include <ArduinoWebsockets.h>

using namespace websockets;

#define WIFI_SSID "你的WiFi名称"
#define WIFI_PASSWORD "你的WiFi密码"
#define SERVER_HOST "xxxx.ngrok-free.dev"
#define DEVICE_ID "ESP32-002"
#define WS_PATH "/api/ws/devices/ESP32-002"

#define FLASH_PIN 18
#define SHOCK_PIN 19
#define NOISE_PIN 20

WebsocketsClient client;

void sendAck(const char* commandId, const char* status, const char* message) {
  StaticJsonDocument<256> ack;
  ack["command_id"] = commandId;
  ack["status"] = status;
  ack["message"] = message;
  String payload;
  serializeJson(ack, payload);
  client.send(payload);
}

void pulsePin(int pin, int durationMs) {
  digitalWrite(pin, HIGH);
  delay(durationMs);
  digitalWrite(pin, LOW);
}

void onMessage(WebsocketsMessage message) {
  StaticJsonDocument<512> doc;
  if (deserializeJson(doc, message.data())) return;

  const char* type = doc["type"] | "";
  if (strcmp(type, "control_command") != 0) return;

  const char* commandId = doc["command_id"] | "";
  const char* commandType = doc["command_type"] | "";
  int durationMs = doc["duration_ms"] | 0;

  if (durationMs <= 0 || durationMs > 10000) {
    sendAck(commandId, "failed", "invalid duration_ms");
    return;
  }

  if (strcmp(commandType, "flash") == 0) {
    pulsePin(FLASH_PIN, durationMs);
    sendAck(commandId, "completed", "flash ok");
  } else if (strcmp(commandType, "electric_shock") == 0) {
    pulsePin(SHOCK_PIN, durationMs);
    sendAck(commandId, "completed", "electric shock ok");
  } else if (strcmp(commandType, "noise") == 0) {
    pulsePin(NOISE_PIN, durationMs);
    sendAck(commandId, "completed", "noise ok");
  } else {
    sendAck(commandId, "failed", "unknown command_type");
  }
}

void setup() {
  pinMode(FLASH_PIN, OUTPUT);
  pinMode(SHOCK_PIN, OUTPUT);
  digitalWrite(FLASH_PIN, LOW);
  digitalWrite(SHOCK_PIN, LOW);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) delay(500);

  client.onMessage(onMessage);
  client.setInsecure();
  String url = String("wss://") + SERVER_HOST + WS_PATH;
  client.connect(url);
}

void loop() {
  if (!client.available()) {
    String url = String("wss://") + SERVER_HOST + WS_PATH;
    client.connect(url);
    delay(1000);
  }
  client.poll();
}
            """
        ),
        _paragraph("硬件保护要求", "Heading1"),
        _bullet("ESP32 上电后，电击、爆闪和噪声 GPIO 必须默认 LOW。"),
        _bullet("ESP32 本地必须限制最大 duration_ms，建议先限制在 10000 ms 以内。"),
        _bullet("电击模块不要由 ESP32 引脚直接供电，应使用继电器、MOSFET、光耦隔离或专用刺激模块。"),
        _bullet("建议加实体急停开关，并确保断网或程序异常时输出自动关闭。"),
        _bullet("前端按钮只是下发命令，真正是否执行以 ESP32 回传 completed 为准。"),
    ]
    output_path = _write_docx(PROJECT_ROOT / "ESP32_WebSocket硬件端对接说明.docx", title, blocks)
    print(output_path)


if __name__ == "__main__":
    create_esp32_websocket_doc()
