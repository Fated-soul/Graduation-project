from __future__ import annotations

from datetime import datetime

import streamlit as st


def initialize_session_state() -> None:
    """集中初始化所有页面共享状态，避免跨页面访问缺失 key。"""
    defaults = {
        "current_page": "造模总览",
        "selected_mouse": "MOUSE-001",
        "selected_time_range": "最近 6 小时",
        "monitor_mouse": "MOUSE-001",
        "agent_selected_mouse": "MOUSE-001",
        "agent_context_mouse": "MOUSE-001",
        "agent_session_id": None,
        "agent_session_mouse": None,
        "agent_messages": [],
        "agent_pending_prompt": None,
        "agent_history_restored": False,
        "agent_llm_provider": "bailian",
        "agent_model": "deepseek-v4.1-flash",
        "agent_semantic_reasoning": True,
        "agent_confirmed_recommendations": set(),
        "selected_experiment": "EXP-001",
        "selected_dataset_session": None,
        "review_subject_id": None,
        "review_primary_session": None,
        "control_logs": [],
        "data_refresh_count": 0,
        "last_refresh_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    page_migrations = {
        "智能总览": "造模总览",
        "研究总览": "造模总览",
        "研究对象": "实验动物",
        "实验会话": "造模会话",
        "造模实验": "造模会话",
        "实时监测": "多模态复核",
        "Agent 智能分析": "Agent 辅助决策",
        "异常预警": "多模态复核",
        "设备管理": "数据来源",
        "数据中心": "研究数据",
        "智能造模": "造模会话",
        "多模态监测": "多模态复核",
        "Agent 证据分析": "Agent 辅助决策",
        "风险评估": "多模态复核",
        "采集终端": "数据来源",
        "同步回放": "多模态复核",
        "同步复核": "多模态复核",
        "证据复核": "多模态复核",
        "数据源管理": "数据来源",
    }
    st.session_state.current_page = page_migrations.get(
        st.session_state.current_page,
        st.session_state.current_page,
    )

