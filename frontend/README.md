# 明察鼠毫前端启动说明

系统主题为“实验动物多模态智能造模与 Agent 辅助决策系统”。当前研究数据来自 DANDI
000718，页面围绕基线适应、恐惧条件化造模、记忆回忆评估、离线记忆巩固和跨周随访组织，
不再使用旧的物体识别数据集，也不依赖本地硬件才能运行。

## 一、环境准备

- Python 3.13
- PostgreSQL 已启动
- 已创建数据库 `IOT`

首次使用时，在项目根目录安装依赖：

```powershell
python -m pip install -r backend/requirements.txt
python -m pip install -r agent/requirements.txt
python -m pip install -r frontend/requirements.txt
```

初始化数据库：

```powershell
python -m backend.database.init_db
```

## 二、启动顺序

打开三个 PowerShell 窗口，并都进入项目根目录。

窗口一，启动数据后端：

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

窗口二，启动 Agent 服务：

```powershell
python -m uvicorn agent.main:app --host 127.0.0.1 --port 8001
```

窗口三，启动前端：

```powershell
python -m streamlit run frontend/app.py --server.port 8501
```

浏览器访问：`http://127.0.0.1:8501`

## 三、首次建立研究数据

1. 打开左侧“数据来源”。
2. 点击“同步 DANDI 000718 研究目录”。
3. 系统会建立 2 只实验动物、12 次纵向会话及其原始文件关系，不会下载完整数据集。
4. 打开“造模会话”，选择需要分析的会话并点击“载入本次会话证据”。
5. 首次载入会按需读取远程 NWB，通常需要几十秒到数分钟。
6. 载入完成后，可在“多模态复核”选择基线适应、恐惧条件化、离线巩固、记忆回忆或随访会话，查看视频、行为事件、钙活动和生理信号的统一时间轴。
7. 在“Agent 辅助决策”中选择问题，形成带依据和可信程度的造模评估；每条记录都会显示
   本次问题，并可在记录内继续追问。

建议先载入 `Ca-EEG3-4 · 恐惧条件化造模`，该会话同时包含足底电击、冻结行为、
行为视频、钙活动和运动强度，便于检查完整工作流。

## 四、百炼 Agent 配置

模型默认为 `deepseek-v4.1-flash`。在启动 Agent 服务的 PowerShell 窗口中设置：

```powershell
$env:DASHSCOPE_API_KEY="你的百炼 API Key"
$env:DASHSCOPE_MODEL="deepseek-v4.1-flash"
$env:RAG_ENABLED="true"
$env:RAG_EMBEDDING_MODEL="text-embedding-v4"
$env:RAG_USE_RERANKER="true"
$env:RAG_RERANK_MODEL="qwen3-rerank"
```

Agent 会将 PostgreSQL 中的实验事实与 `agent/knowledge/` 中的数据集说明、原始论文和复核
规范结合。首次检索会建立向量缓存，后续先混合召回候选资料，再通过重排序模型筛选；前端
的决策记录会显示本次实际引用的
研究资料。若未配置 API Key，系统仍可使用后端基于会话证据生成的基础评估，不会影响
数据同步和复核。

## 五、页面职责

- “造模总览”：查看阶段分布、模态覆盖和会话状态。
- “实验动物”：查看同一动物跨阶段的纵向造模轨迹。
- “造模会话”：筛选会话、检查证据完整度并按需载入 NWB。
- “多模态复核”：按真实采集时间浏览全部研究阶段，并在同一屏幕核对视频、事件、信号与人工观察。
- “Agent 辅助决策”：综合当前阶段证据形成造模评估和下一步建议，并围绕任一决策继续追问。
- “数据来源”：管理 DANDI 000718 固定版本及官方来源。
- “研究数据”：查看数据规模、模态覆盖和研究留痕。

## 六、常见问题

后端端口被占用时，可先执行：

```powershell
Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess
Stop-Process -Id 查询到的进程编号
```

DANDI 行为视频原始格式为 WMV。后端会在首次播放时下载该会话视频并转换为浏览器兼容的
MP4，缓存位于 `backend/cache/videos`；首次播放可能需要一至数分钟，之后会直接读取缓存。

公开数据集：<https://dandiarchive.org/dandiset/000718>

官方教程：<https://docs.dandiarchive.org/example-notebooks/000718/CaiLab/zaki_2024/000718_demo/>

## 七、纵向多模态复核

进入“多模态复核”后：

1. 选择实验动物。
2. 在“复核会话”中选择任意基线适应、恐惧条件化、离线巩固、记忆回忆或随访会话。
3. 尚未载入的会话可在当前页面点击“载入该会话证据”。
4. 页面按真实采集时间显示该动物的全部会话、实验事件和信号摘要，中间没有采集的时段会保留空档。
5. 在会话详情中复核该阶段对应的视频、行为、睡眠、神经活动或生理信号，并可保存人工观察。

FC 与 Offline 会话仍依据 NWB 会话开始时间保存在纵向时间轴中。Agent 和后端分析会使用真实
采集先后关系，不会把不同时间采集的脑电、肌电与 FC 电刺激按相同的会话内秒数强行叠加。
