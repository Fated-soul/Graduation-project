from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
PAGES = [
    "造模总览",
    "实验动物",
    "造模会话",
    "多模态复核",
    "Agent 辅助决策",
    "数据来源",
    "研究数据",
]
INTERNAL_TERMS = {
    "/api/",
    "mouse_id",
    "device_id",
    "event_type",
    "duration_ms",
    "next_interval_ms",
    "esp32_s3",
    "vital_sensor",
    "environment_sensor",
    "WebSocket",
    "后端 API",
    "Streamlit",
    "Mock",
    "mock",
    "demo",
    "Prototype",
    "演示数据",
}


def _visible_text(app: AppTest) -> list[str]:
    values: list[str] = []
    for collection_name in (
        "markdown",
        "caption",
        "info",
        "warning",
        "error",
        "success",
    ):
        for element in getattr(app, collection_name):
            value = str(element.value)
            if collection_name == "markdown" and value.lstrip().startswith("<style"):
                continue
            values.append(value)

    for dataframe in app.dataframe:
        values.extend(str(column) for column in dataframe.value.columns)
    for selectbox in app.selectbox:
        values.extend(str(option) for option in selectbox.options)
    return values


def test_pages_use_research_language_instead_of_internal_field_names() -> None:
    for page in PAGES:
        # Each page gets an isolated Streamlit state. This mirrors a browser
        # navigation run and avoids retaining removed widget protocol state.
        app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
        navigation = next(button for button in app.button if button.label.endswith(page))
        navigation.click()
        app.run()

        assert not app.exception, f"{page} 页面渲染失败：{app.exception}"
        visible_text = "\n".join(_visible_text(app))
        leaked_terms = sorted(term for term in INTERNAL_TERMS if term in visible_text)
        assert not leaked_terms, f"{page} 页面显示了内部术语：{leaked_terms}"


def test_sidebar_highlights_the_current_page_after_navigation() -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    target = next(button for button in app.button if button.label.endswith("多模态复核"))

    target.click()
    app.run()

    nav_buttons = [button for button in app.button if str(button.key).startswith("nav_")]
    active_buttons = [button for button in nav_buttons if button.proto.type == "primary"]
    assert app.session_state["current_page"] == "多模态复核"
    assert len(active_buttons) == 1
    assert active_buttons[0].label.endswith("多模态复核")


def test_agent_question_shortcut_updates_the_input() -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    navigation = next(
        button for button in app.button if button.label.endswith("Agent 辅助决策")
    )
    navigation.click()
    app.run()

    prompt = "不同模态之间是否相互支持？哪些结论仍需人工复核？"
    shortcut = next(button for button in app.button if button.label == prompt)
    shortcut.click()
    app.run()

    question = next(
        item for item in app.text_area if item.label == "本次希望重点评估什么？"
    )
    assert question.value == prompt
