# 明察鼠毫后端

本后端服务于“实验动物多模态智能造模与 Agent 辅助决策系统”。系统使用 DANDI 000718
固定发布版本 `0.260825.1902`，将实验动物、造模阶段、刺激与行为事件、钙成像、运动、
EEG、EMG、睡眠状态、人工复核和 Agent 分析统一保存到 PostgreSQL。

## 技术环境

- Python 3.13
- FastAPI、Pydantic、Uvicorn
- PostgreSQL、psycopg2
- h5py、remfile、NumPy（按需读取远程 NWB）
- imageio-ffmpeg（将公开 WMV 行为视频缓存为浏览器兼容的 MP4）

数据库配置集中在 `backend/config.py`：数据库 `IOT`，用户 `postgres`，主机
`localhost`，端口 `5432`。当前密码 `123` 仅用于本地毕业设计环境，可通过环境变量覆盖。

## 核心数据表

- `public_data_sources`：DANDI 数据来源、固定版本、许可和同步状态。
- `dataset_subjects`：公开研究中的实验动物及品系、性别等信息。
- `experiment_sessions`：纵向造模会话、研究阶段及模态覆盖。
- `session_assets`：每次会话关联的 NWB 与行为视频文件。
- `modeling_events`：足底电击、冻结行为、睡眠状态和实验阶段区间。
- `multimodal_signal_windows`：钙活动、运动、EEG、EMG 的固定时间窗摘要。
- `calcium_roi_metrics`：单细胞 ROI 的平均、峰值、波动和活跃比例。
- `session_annotations`：实验人员的时间定位复核记录。
- `session_agent_analyses`：Agent 的问题、证据、建议、可信程度、知识检索来源、检索方式与追问关系。

原有设备采集相关表继续保留用于兼容早期接口，但当前毕业设计主流程不依赖这些表。

## 初始化与启动

在项目根目录执行：

```powershell
python -m pip install -r backend/requirements.txt
```

若数据库尚未创建，先在 PostgreSQL 中执行：

```sql
CREATE DATABASE "IOT";
```

随后初始化表结构并启动后端：

```powershell
python -m backend.database.init_db
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

API 文档：`http://127.0.0.1:8000/docs`

健康检查：`http://127.0.0.1:8000/api/health`

## DANDI 000718 工作流

1. 调用 `POST /api/public-data/sync?limit=20` 建立 2 只实验动物和 12 次会话的目录关系。
2. 调用 `POST /api/public-data/sessions/{会话编号}/import` 按需读取该会话的 NWB。
3. 导入器跳过原始成像帧，只提取刺激、行为区间、处理后的钙活动、运动与生理信号摘要。
4. 调用 `GET /api/public-data/sessions/{会话编号}/timeline` 获取统一时间轴证据。
5. 使用注释和分析接口保存人工复核及 Agent 辅助决策。

行为视频接口 `GET /api/public-data/sessions/{会话编号}/video` 会在首次访问时完成下载和
H.264 MP4 转换，结果缓存在 `backend/cache/videos`。后续播放支持浏览器分段读取，不会
重复下载或转码。原始 WMV 地址仍可通过 `/video/original` 获取。

数据集页面：<https://dandiarchive.org/dandiset/000718>

官方教程：<https://docs.dandiarchive.org/example-notebooks/000718/CaiLab/zaki_2024/000718_demo/>

## FC 与 Offline 会话的真实时间对齐

同一只小鼠的两类会话分开保存、联合展示：

- FC 会话保存足底电击、冻结行为、行为视频、运动与钙活动。
- Offline 会话保存脑电、肌电、活动信号、睡眠状态与钙活动。
- `experiment_sessions.timestamps_reference_at` 保存 NWB 的时间参考点。
- `modeling_events.event_started_at/event_stopped_at` 保存事件的绝对采集时间。
- `multimodal_signal_windows.window_started_at/window_ended_at` 保存信号窗的绝对采集时间。

绝对采集时间按“会话时间参考点 + 会话内秒数”计算。FC 和 Offline 会话可以放在同一真实时间轴上，
但没有采集记录的时间段保持为空，不会把两场会话各自的相同秒数强行视为同一时刻。

查询同一实验动物的 FC 与 Offline 对齐结果：

```text
GET /api/public-data/subjects/{实验动物编号}/aligned-timeline
```

Offline 导入器直接读取 NWB 中的 `EEGSignal`、`EMGSignal`、`ActivitySignal`、`SleepIntervals`
和处理后的钙活动。远程 NWB 数据块缓存在 `backend/cache/nwb`，首次载入可能需要数分钟，后续重复读取会明显加快。

## RAG 辅助决策

Agent 采用“结构化实验数据 + 检索增强生成”的组合方式。当前实验动物、会话、事件和多模态信号由
FastAPI 从 PostgreSQL 读取；DANDI 官方说明、原始论文、数据解释规则和决策边界等知识文档存放在
`agent/knowledge`。分析前先使用百炼 `text-embedding-v4` 检索相关知识片段，再将片段与当前会话证据
共同提交给生成模型。若向量服务不可用，系统会自动退回本地关键词检索，不影响基础分析流程。

每次分析使用的资料会写入 `session_agent_analyses.knowledge_sources`，检索方式写入
`session_agent_analyses.retrieval_mode`。前端据此展示可点击的参考资料。检索资料仅用于解释研究背景和
分析边界，当前实验对象的结论仍以数据库中的真实观测数据为依据。

每条决策记录都保留实际提问。继续追问时调用
`POST /api/public-data/sessions/{会话编号}/analyses/{决策编号}/follow-up`，后端通过
`parent_analysis_id` 关联上一条决策，并把上一条问题、结论、依据和建议作为本轮分析上下文。

