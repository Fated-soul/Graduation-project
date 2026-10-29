from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows deployment script")
SCRIPT = Path(__file__).resolve().parents[1] / "install.ps1"


@pytest.fixture
def deployment(tmp_path):
    desktop = tmp_path / "project/desktop"
    desktop.mkdir(parents=True)
    shutil.copy2(SCRIPT, desktop / "install.ps1")
    bundle = desktop / "dist/MingChaShuHao"
    bundle.mkdir(parents=True)
    (bundle / "MingChaShuHao.exe").write_bytes(b"deployment-test-fixture")
    (desktop / ".env.example").write_text("IOT_DB_NAME=IOT\n", encoding="utf-8")
    agent = desktop.parent / "agent"
    agent.mkdir()
    (agent / ".env").write_text("DASHSCOPE_API_KEY=fixture-only\n", encoding="utf-8")
    local = tmp_path / "local"

    def install(*args):
        return subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", str(desktop / "install.ps1"), "-NoShortcuts", *args],
            env=dict(os.environ, LOCALAPPDATA=str(local)),
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    return install, local, agent


def test_first_install_imports_project_configuration(deployment):
    install, local, _ = deployment
    result = install()
    assert result.returncode == 0, result.stdout + result.stderr
    assert (local / "Programs/MingChaShuHao/MingChaShuHao.exe").read_bytes() == b"deployment-test-fixture"
    assert "DASHSCOPE_API_KEY=fixture-only" in (local / "MingChaShuHao/config/.env").read_text(encoding="utf-8")


def test_upgrade_preserves_existing_configuration_without_project_env(deployment):
    install, local, agent = deployment
    config = local / "MingChaShuHao/config/.env"
    config.parent.mkdir(parents=True)
    original = b"IOT_DB_NAME=custom-database\nDASHSCOPE_API_KEY=existing-fixture\n"
    config.write_bytes(original)
    (agent / ".env").unlink()
    result = install()
    assert result.returncode == 0, result.stdout + result.stderr
    assert config.read_bytes() == original
    assert "preserved" in result.stdout


def test_explicit_configuration_refresh_backs_up_the_original(deployment):
    install, local, _ = deployment
    config = local / "MingChaShuHao/config/.env"
    config.parent.mkdir(parents=True)
    original = b"IOT_DB_NAME=custom-database\n"
    config.write_bytes(original)
    result = install("-RefreshConfig")
    assert result.returncode == 0, result.stdout + result.stderr
    backups = list(config.parent.glob(".env.*.bak"))
    assert len(backups) == 1 and backups[0].read_bytes() == original
    assert "DASHSCOPE_API_KEY=fixture-only" in config.read_text(encoding="utf-8")
