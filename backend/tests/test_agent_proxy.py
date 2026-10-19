from __future__ import annotations

import importlib
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _load_snapshot_as_backend_package() -> None:
    """backend_7.23 is a snapshot directory; mount it under its import package name."""
    spec = importlib.util.spec_from_file_location(
        "backend",
        BACKEND_ROOT / "__init__.py",
        submodule_search_locations=[str(BACKEND_ROOT)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load backend_7.23 package")
    package = importlib.util.module_from_spec(spec)
    sys.modules["backend"] = package
    spec.loader.exec_module(package)


_load_snapshot_as_backend_package()

from backend.schemas.agent import (  # noqa: E402
    AgentConversationMessageRequest,
    AgentCreateConversationRequest,
)
from backend.services import agent_service  # noqa: E402


class AgentProxyTests(unittest.TestCase):
    def test_create_conversation_forwards_supported_fields(self) -> None:
        request = AgentCreateConversationRequest(
            mouse_id="MOUSE-001",
            llm_provider="doubao",
            model="doubao-seed-1.6-thinking",
        )
        with patch.object(
            agent_service,
            "_request",
            return_value={"success": True, "data": {"session_id": "conversation-1"}},
        ) as proxy:
            result = agent_service.create_conversation(request)

        self.assertEqual(result["data"]["session_id"], "conversation-1")
        proxy.assert_called_once_with(
            "POST",
            "/api/conversations",
            {
                "mouse_id": "MOUSE-001",
                "llm_provider": "doubao",
                "model": "doubao-seed-1.6-thinking",
                "use_llm": True,
                "use_semantic_reasoning": False,
            },
        )

    def test_message_path_and_payload_are_forwarded(self) -> None:
        request = AgentConversationMessageRequest(
            message="为什么认为它存在应激？"
        )
        with patch.object(
            agent_service,
            "_request",
            return_value={"success": True, "data": {"answer": "依据上一轮分析。"}},
        ) as proxy:
            agent_service.send_conversation_message(
                "conversation/id",
                request,
            )

        proxy.assert_called_once_with(
            "POST",
            "/api/conversations/conversation%2Fid/messages",
            {"message": "为什么认为它存在应激？"},
        )

    def test_openapi_contains_all_agent_routes(self) -> None:
        main = importlib.import_module("backend.main")
        paths = main.app.openapi()["paths"]
        expected = {
            "/api/agent/health",
            "/api/agent/analyze/{mouse_id}",
            "/api/agent/conversations",
            "/api/agent/conversations/{session_id}",
            "/api/agent/conversations/{session_id}/messages",
        }
        self.assertFalse(expected - set(paths))


if __name__ == "__main__":
    unittest.main()
