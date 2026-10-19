from __future__ import annotations

import streamlit as st

from components.metric_card import render_section_title
from data.public_dataset import format_datetime, format_size, get_source, get_stats, sync_catalog


def render() -> None:
    source = get_source()
    stats = get_stats()

    with st.container(border=True):
        st.markdown("### DANDI 000718 · Offline ensemble co-reactivation links memories across days")
        st.write(
            "本系统使用该公开研究的固定发布版本，整合行为视频、足底电击、冻结行为、"
            "单光子钙成像、细胞分割、睡眠状态、EEG 和 EMG。目录同步只建立会话索引，"
            "会话证据在复核前按需读取，不下载整个 40.6 GB 数据集。"
        )
        cols = st.columns(4)
        cols[0].metric("实验动物", int(stats.get("subject_count", 0)))
        cols[1].metric("造模会话", int(stats.get("session_count", 0)))
        cols[2].metric("公开资产", int((source or {}).get("asset_count") or 20))
        cols[3].metric("原始规模", format_size((source or {}).get("total_size_bytes") or 40_600_000_000))

    if st.button("同步 DANDI 000718 研究目录", type="primary", width="stretch"):
        with st.spinner("正在读取固定版本并建立实验动物、阶段、会话与文件关系……"):
            response = sync_catalog(20)
        if response.get("success") is False:
            st.error(str(response.get("message") or response.get("detail") or "同步失败。"))
        else:
            st.success("研究目录已更新。")
            st.rerun()

    render_section_title("来源与使用边界", "保证造模证据可追溯、版本固定且解释范围明确")
    with st.container(border=True):
        rows = [
            ("研究内容", "恐惧条件化、跨日记忆连接与离线神经集群再激活"),
            ("固定版本", (source or {}).get("version") or "0.260825.1902"),
            ("开放许可", (source or {}).get("license") or "CC-BY-4.0"),
            ("本地状态", "目录可用" if (source or {}).get("status") == "available" else "等待同步"),
            ("最近同步", format_datetime((source or {}).get("last_synced_at"))),
            ("当前用途", "毕业设计中的多模态智能造模评估与 Agent 辅助决策"),
        ]
        for label, value in rows:
            st.markdown(f"**{label}：** {value}")
        left, right = st.columns(2)
        with left:
            st.link_button(
                "查看 DANDI 数据集",
                str((source or {}).get("landing_url") or "https://dandiarchive.org/dandiset/000718"),
                width="stretch",
            )
        with right:
            st.link_button(
                "查看官方数据教程",
                "https://docs.dandiarchive.org/example-notebooks/000718/CaiLab/zaki_2024/000718_demo/",
                width="stretch",
            )
