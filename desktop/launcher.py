from __future__ import annotations

import atexit
from dataclasses import dataclass
from datetime import datetime
import html
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


APP_NAME = "明察鼠毫"
APP_TITLE = "明察鼠毫 - 实验动物多模态智能造模与 Agent 辅助决策系统"
FRONTEND_URL = "http://127.0.0.1:8501"
INSTANCE_PORT = 45837


class StartupError(RuntimeError):
    """Raised when a local service cannot be started safely."""


@dataclass(frozen=True)
class ProbeResult:
    ready: bool
    recognized: bool
    detail: str = ""


@dataclass(frozen=True)
class ServiceDefinition:
    key: str
    label: str
    port: int
    health_url: str
    timeout_seconds: float


@dataclass
class ManagedProcess:
    definition: ServiceDefinition
    process: subprocess.Popen[bytes] | None = None
    log_handle: Any | None = None
    owned: bool = False


SERVICES = (
    ServiceDefinition("backend", "研究数据服务", 8000, "http://127.0.0.1:8000/api/health", 40),
    ServiceDefinition("agent", "Agent 辅助决策服务", 8001, "http://127.0.0.1:8001/api/health", 35),
    ServiceDefinition("frontend", "桌面研究工作台", 8501, "http://127.0.0.1:8501/_stcore/health", 60),
)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return Path(__file__).resolve().parents[1]


def user_data_root() -> Path:
    override = os.getenv("MINGCHA_DESKTOP_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "MingChaShuHao"
    return Path.home() / "AppData" / "Local" / "MingChaShuHao"


def config_path() -> Path:
    return user_data_root() / "config" / ".env"


def ensure_runtime_directories() -> None:
    for path in (
        user_data_root() / "config",
        user_data_root() / "logs",
        user_data_root() / "cache" / "backend",
        user_data_root() / "cache" / "agent",
        user_data_root() / "cache" / "webview",
    ):
        path.mkdir(parents=True, exist_ok=True)


def ensure_user_config() -> Path:
    target = config_path()
    if target.exists():
        return target
    template = resource_root() / "desktop" / ".env.example"
    if template.is_file():
        target.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        target.write_text(
            "IOT_DB_NAME=IOT\n"
            "IOT_DB_USER=postgres\n"
            "IOT_DB_PASSWORD=123\n"
            "IOT_DB_HOST=127.0.0.1\n"
            "IOT_DB_PORT=5432\n"
            "DASHSCOPE_API_KEY=\n"
            "DASHSCOPE_MODEL=deepseek-v4.1-flash\n",
            encoding="utf-8",
        )
    return target


def _read_env_values(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        from dotenv import dotenv_values

        values = dotenv_values(path)
        return {
            str(key): str(value)
            for key, value in values.items()
            if key and value not in (None, "")
        }
    except Exception:
        values: dict[str, str] = {}
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() and value.strip():
                values[key.strip()] = value.strip().strip('"').strip("'")
        return values


def build_runtime_environment() -> dict[str, str]:
    ensure_runtime_directories()
    target_config = ensure_user_config()
    environment = dict(os.environ)
    source_agent_config = resource_root() / "agent" / ".env"
    for key, value in _read_env_values(source_agent_config).items():
        environment.setdefault(key, value)
    environment.update(_read_env_values(target_config))
    environment.update(
        {
            "PYTHONUTF8": "1",
            "PYTHONUNBUFFERED": "1",
            "MINGCHA_API_BASE_URL": "http://127.0.0.1:8000",
            "MINGCHA_BACKEND_API_URL": "http://127.0.0.1:8000",
            "AGENT_API_URL": "http://127.0.0.1:8001",
            "MINGCHA_ENABLE_MOCK_FALLBACK": "0",
            "MINGCHA_BACKEND_CACHE_DIR": str(user_data_root() / "cache" / "backend"),
            "MINGCHA_RAG_CACHE_PATH": str(
                user_data_root() / "cache" / "agent" / "knowledge_index.json"
            ),
        }
    )
    root = str(resource_root())
    existing_python_path = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = (
        root if not existing_python_path else root + os.pathsep + existing_python_path
    )
    return environment


def _service_command(key: str) -> list[str]:
    if is_frozen():
        return [sys.executable, "--service", key]
    return [sys.executable, str(Path(__file__).resolve()), "--service", key]


def _port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(0.35)
        return client.connect_ex(("127.0.0.1", port)) == 0


def _fetch(url: str) -> tuple[int, str]:
    try:
        with urlopen(url, timeout=1.2) as response:
            return int(response.status), response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        return int(exc.code), ""
    except (URLError, TimeoutError, OSError):
        return 0, ""


def probe_service(definition: ServiceDefinition) -> ProbeResult:
    status_code, body = _fetch(definition.health_url)
    if status_code != 200:
        return ProbeResult(False, False, "健康检查暂未响应")
    if definition.key == "frontend":
        recognized = "ok" in body.strip().lower()
        return ProbeResult(recognized, recognized, "桌面界面正在启动")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return ProbeResult(False, False, "端口响应不是本系统服务")
    if definition.key == "backend":
        recognized = isinstance(payload, dict) and "database" in payload
        if not recognized:
            return ProbeResult(False, False, "8000 端口不是明察鼠毫后端")
        if payload.get("database") != "connected":
            return ProbeResult(
                False,
                True,
                "PostgreSQL 未连接，请启动 PostgreSQL 并检查配置文件中的数据库账号与密码。",
            )
        return ProbeResult(True, True)
    data = payload.get("data") if isinstance(payload, dict) else None
    recognized = isinstance(data, dict) and "backend_connected" in data
    if not recognized:
        return ProbeResult(False, False, "8001 端口不是明察鼠毫 Agent 服务")
    return ProbeResult(True, True)


def _tail(path: Path, lines: int = 24) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(content[-lines:])


class ServiceManager:
    def __init__(self) -> None:
        self.processes: list[ManagedProcess] = []
        self._lock = threading.RLock()

    def start(self, definition: ServiceDefinition) -> None:
        with self._lock:
            if _port_is_open(definition.port):
                result = probe_service(definition)
                if result.ready:
                    self.processes.append(ManagedProcess(definition, owned=False))
                    return
                detail = result.detail or f"端口 {definition.port} 已被其他程序占用"
                raise StartupError(detail)

            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            log_path = user_data_root() / "logs" / f"{definition.key}-{stamp}.log"
            log_handle = log_path.open("ab")
            creation_flags = 0
            if os.name == "nt":
                creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                creation_flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            process = subprocess.Popen(
                _service_command(definition.key),
                cwd=str(resource_root()),
                env=build_runtime_environment(),
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )
            managed = ManagedProcess(definition, process, log_handle, True)
            self.processes.append(managed)

        deadline = time.monotonic() + definition.timeout_seconds
        last_detail = ""
        recognized_at: float | None = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise StartupError(f"{definition.label}启动失败。\n\n{_tail(log_path)}")
            result = probe_service(definition)
            if result.ready:
                return
            if result.recognized:
                last_detail = result.detail
                recognized_at = recognized_at or time.monotonic()
                if time.monotonic() - recognized_at >= 3:
                    break
            time.sleep(0.45)

        detail = last_detail or _tail(log_path) or "健康检查超时"
        raise StartupError(f"{definition.label}未能就绪。\n\n{detail}")

    def stop_all(self) -> None:
        with self._lock:
            managed_processes = list(reversed(self.processes))
            self.processes.clear()
        for managed in managed_processes:
            process = managed.process
            if managed.owned and process is not None and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=8)
                except (subprocess.TimeoutExpired, OSError):
                    try:
                        process.kill()
                        process.wait(timeout=3)
                    except (subprocess.TimeoutExpired, OSError):
                        pass
            if managed.log_handle is not None:
                try:
                    managed.log_handle.close()
                except OSError:
                    pass


SPLASH_HTML = """
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  * { box-sizing: border-box; }
  body { margin: 0; background: #f3f5f6; color: #20262b; font-family: "Microsoft YaHei", sans-serif; }
  main { min-height: 100vh; display: grid; place-items: center; padding: 32px; }
  .panel { width: min(620px, 92vw); background: #fff; border: 1px solid #dfe4e6; border-radius: 8px; padding: 42px 46px; box-shadow: 0 16px 40px rgba(25, 45, 54, .09); }
  .brand { display: flex; align-items: center; gap: 18px; }
  .mark { width: 60px; height: 60px; display: grid; place-items: center; border-radius: 8px; background: #128ba8; color: #fff; font-size: 30px; font-weight: 700; }
  h1 { margin: 0 0 6px; font-size: 26px; }
  p { margin: 0; color: #69777e; line-height: 1.7; }
  .progress { margin-top: 34px; height: 5px; overflow: hidden; border-radius: 3px; background: #e7ecee; }
  .progress span { display: block; width: 34%; height: 100%; background: #169cb2; animation: loading 1.25s ease-in-out infinite; }
  #status { margin-top: 18px; color: #3d4d54; font-size: 15px; }
  .path { margin-top: 22px; padding-top: 18px; border-top: 1px solid #edf0f1; font-size: 12px; color: #8a969b; }
  @keyframes loading { 0% { transform: translateX(-110%); } 100% { transform: translateX(300%); } }
</style>
</head>
<body>
<main><section class="panel">
  <div class="brand"><div class="mark">明</div><div><h1>明察鼠毫</h1><p>实验动物多模态智能造模与 Agent 辅助决策系统</p></div></div>
  <div class="progress"><span></span></div>
  <div id="status">正在准备本地运行环境...</div>
  <div class="path">桌面研究工作台正在启动，请稍候</div>
</section></main>
</body>
</html>
"""


def error_html(message: str) -> str:
    escaped_message = html.escape(message).replace("\n", "<br>")
    escaped_config = html.escape(str(config_path()))
    escaped_logs = html.escape(str(user_data_root() / "logs"))
    return f"""
<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><style>
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #f4f5f5; color: #20262b; font-family: "Microsoft YaHei", sans-serif; }}
main {{ min-height: 100vh; display: grid; place-items: center; padding: 32px; }}
.panel {{ width: min(760px, 94vw); background: #fff; border: 1px solid #d9dfe1; border-radius: 8px; padding: 38px 42px; }}
h1 {{ margin: 0 0 12px; font-size: 25px; }}
.message {{ margin: 24px 0; padding: 18px 20px; border-left: 4px solid #c24b4b; background: #fbf3f3; line-height: 1.8; }}
.hint {{ color: #66757c; line-height: 1.8; }}
code {{ color: #38454b; font-family: Consolas, monospace; word-break: break-all; }}
.actions {{ display: flex; gap: 12px; margin-top: 26px; }}
button {{ border: 1px solid #bbc7cb; background: #fff; border-radius: 5px; padding: 10px 18px; color: #28383f; cursor: pointer; font-size: 14px; }}
button:hover {{ background: #f0f4f5; }}
</style></head><body><main><section class="panel">
<h1>系统未能完成启动</h1>
<div class="message">{escaped_message}</div>
<div class="hint">请确认 PostgreSQL 已启动，并核对配置文件：<br><code>{escaped_config}</code><br><br>详细启动日志：<br><code>{escaped_logs}</code></div>
<div class="actions">
  <button onclick="pywebview.api.open_config()">编辑本地配置</button>
  <button onclick="pywebview.api.open_logs()">查看启动日志</button>
</div>
</section></main></body></html>
"""


class DesktopApi:
    def open_config(self) -> bool:
        ensure_user_config()
        os.startfile(config_path())
        return True

    def open_logs(self) -> bool:
        logs = user_data_root() / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        os.startfile(logs)
        return True


def _set_status(window: Any, text: str) -> None:
    script = (
        "document.getElementById('status').textContent = "
        f"{json.dumps(text, ensure_ascii=False)};"
    )
    try:
        window.evaluate_js(script)
    except Exception:
        pass


def _start_services(window: Any, manager: ServiceManager) -> None:
    try:
        for definition in SERVICES:
            _set_status(window, f"正在启动{definition.label}...")
            manager.start(definition)
        _set_status(window, "服务已就绪，正在打开研究工作台...")
        window.load_url(FRONTEND_URL)
    except Exception as exc:
        manager.stop_all()
        window.load_html(error_html(str(exc)))


def _message_box(message: str, title: str = APP_NAME) -> None:
    if os.name == "nt":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
    else:
        print(f"{title}: {message}", file=sys.stderr)


def acquire_instance_lock() -> socket.socket | None:
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", INSTANCE_PORT))
        lock.listen(1)
        return lock
    except OSError:
        lock.close()
        return None


def run_backend_service() -> None:
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
        access_log=False,
    )


def run_agent_service() -> None:
    import uvicorn

    uvicorn.run(
        "agent.main:app",
        host="127.0.0.1",
        port=8001,
        log_level="info",
        access_log=False,
    )


def run_frontend_service() -> None:
    from streamlit.web import cli as streamlit_cli

    app_path = resource_root() / "frontend" / "app.py"
    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--global.developmentMode=false",
        "--server.address=127.0.0.1",
        "--server.port=8501",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--server.fileWatcherType=none",
    ]
    raise SystemExit(streamlit_cli.main())


def run_service(key: str) -> int:
    os.chdir(resource_root())
    root = str(resource_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    os.environ.update(build_runtime_environment())
    runners = {
        "backend": run_backend_service,
        "agent": run_agent_service,
        "frontend": run_frontend_service,
    }
    runner = runners.get(key)
    if runner is None:
        print(f"unknown service: {key}", file=sys.stderr)
        return 2
    runner()
    return 0


def run_diagnostics() -> int:
    ensure_runtime_directories()
    ensure_user_config()
    dependencies = ("streamlit", "fastapi", "uvicorn", "psycopg2", "webview")
    print(f"resource_root={resource_root()}")
    print(f"user_data_root={user_data_root()}")
    print(f"config={config_path()}")
    missing = []
    for dependency in dependencies:
        available = importlib.util.find_spec(dependency) is not None
        print(f"dependency.{dependency}={'ok' if available else 'missing'}")
        if not available:
            missing.append(dependency)
    for definition in SERVICES:
        result = probe_service(definition) if _port_is_open(definition.port) else None
        state = "closed" if result is None else ("ready" if result.ready else result.detail)
        print(f"service.{definition.key}={state}")
    frontend_app = resource_root() / "frontend" / "app.py"
    knowledge_dir = resource_root() / "agent" / "knowledge"
    resources_ok = frontend_app.is_file() and knowledge_dir.is_dir()
    print(f"resources={'ok' if resources_ok else 'missing'}")
    return 0 if not missing and resources_ok else 1


def run_desktop() -> int:
    instance_lock = acquire_instance_lock()
    if instance_lock is None:
        _message_box("明察鼠毫已经在运行，请切换到现有窗口。")
        return 1
    try:
        import webview
    except ImportError:
        instance_lock.close()
        _message_box(
            "缺少桌面运行依赖。请执行：\n"
            "python -m pip install -r desktop/requirements.txt"
        )
        return 1

    ensure_runtime_directories()
    ensure_user_config()
    manager = ServiceManager()
    atexit.register(manager.stop_all)
    window = webview.create_window(
        APP_TITLE,
        html=SPLASH_HTML,
        js_api=DesktopApi(),
        width=1440,
        height=900,
        min_size=(1100, 700),
        background_color="#f3f5f6",
        text_select=False,
    )
    window.events.closed += manager.stop_all
    try:
        webview.start(
            _start_services,
            (window, manager),
            gui="edgechromium",
            debug=False,
            private_mode=False,
            storage_path=str(user_data_root() / "cache" / "webview"),
        )
    finally:
        manager.stop_all()
        instance_lock.close()
    return 0


def main() -> int:
    multiprocessing.freeze_support()
    arguments = sys.argv[1:]
    if len(arguments) == 2 and arguments[0] == "--service":
        return run_service(arguments[1])
    if arguments == ["--diagnose"]:
        return run_diagnostics()
    return run_desktop()


if __name__ == "__main__":
    raise SystemExit(main())
