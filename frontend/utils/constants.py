from __future__ import annotations


APP_NAME = "明察鼠毫"
APP_SUBTITLE = "实验动物多模态智能造模与 Agent 辅助决策系统"
APP_VERSION = "v3.0.0"

DEVICE_TYPE_LABELS: dict[str, str] = {
    "esp32_s3": "刺激控制终端",
    "vital_sensor": "生命体征采集终端",
    "environment_sensor": "环境采集终端",
    "camera": "行为监测摄像头",
}


def device_type_label(value: object) -> str:
    """Convert the stored device type into user-facing research language."""
    key = str(value or "")
    return DEVICE_TYPE_LABELS.get(key, "其他采集终端")

PAGE_DESCRIPTIONS: dict[str, str] = {
    "造模总览": "查看实验动物、造模阶段与多模态证据覆盖",
    "实验动物": "追踪同一实验动物从基线到回忆评估的纵向过程",
    "造模会话": "按阶段组织刺激、行为、钙成像和生理记录",
    "多模态复核": "在统一时间轴核对视频、刺激、冻结行为与神经活动",
    "Agent 辅助决策": "依据当前会话证据形成可追溯的造模评估建议",
    "数据来源": "管理 DANDI 000718 的版本、会话目录和载入状态",
    "研究数据": "查看数据规模、模态覆盖、注释与分析留痕",
}

NAV_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "研究管理",
        [
            ("造模总览", ":material/space_dashboard:"),
            ("实验动物", ":material/pets:"),
            ("造模会话", ":material/science:"),
        ],
    ),
    (
        "证据分析",
        [
            ("多模态复核", ":material/fact_check:"),
            ("Agent 辅助决策", ":material/psychology:"),
        ],
    ),
    (
        "数据管理",
        [
            ("数据来源", ":material/cloud_download:"),
            ("研究数据", ":material/analytics:"),
        ],
    ),
]

NAV_ITEMS: list[tuple[str, str]] = [
    item
    for _, group_items in NAV_GROUPS
    for item in group_items
]

TIME_RANGE_OPTIONS: dict[str, int] = {
    "最近 1 小时": 1,
    "最近 6 小时": 6,
    "最近 24 小时": 24,
}

RISK_COLOR_CLASS: dict[str, str] = {
    "正常": "status-normal",
    "关注": "status-warning",
    "警告": "status-warning",
    "高风险": "status-danger",
    "设备异常": "status-agent",
    "数据异常": "status-muted",
}

EXPERIMENT_STAGES: list[str] = ["准备", "适应", "应激", "行为测试", "观察", "完成"]
