# 实验动物多模态智能造模与 Agent 辅助决策系统

本项目是面向本科毕业设计的实验动物多模态研究平台。系统以 DANDI 000718 公开数据集为
主要数据来源，将实验会话、行为视频、刺激与冻结事件、钙活动、EEG、EMG、睡眠状态和
人工复核记录统一组织，并通过 RAG Agent 形成带证据来源的辅助决策。

## 项目结构

- `frontend/`：Streamlit 研究平台界面。
- `backend/`：FastAPI 与 PostgreSQL 数据服务。
- `agent/`：百炼大模型、RAG 检索和知识库。
- `.streamlit/`：Streamlit 页面配置。

## 技术栈

- Python 3.13
- Streamlit、Plotly
- FastAPI、Pydantic
- PostgreSQL、psycopg2
- 阿里云百炼 `deepseek-v4.1-flash`
- 百炼 `text-embedding-v4` 混合召回与 `qwen3-rerank` 二次排序

## 新电脑首次部署

仓库包含完整的前端、后端和 Agent 源码，但不包含 API 密钥、本地 PostgreSQL 数据、DANDI
原始文件和视频缓存。首次在新电脑运行时，需要完成以下初始化操作。

### 1. 获取项目

```powershell
git clone https://github.com/Fated-soul/Graduation-project.git
cd Graduation-project
```

### 2. 准备运行环境

安装以下软件：

- Python 3.13
- PostgreSQL
- Git

确认 Python 版本：

```powershell
python --version
```

安装三部分 Python 依赖：

```powershell
python -m pip install -r backend/requirements.txt
python -m pip install -r agent/requirements.txt
python -m pip install -r frontend/requirements.txt
```

建议在 Python 虚拟环境或 Conda 环境中安装依赖，避免与其他项目冲突。

### 3. 创建 PostgreSQL 数据库

启动 PostgreSQL，通过 pgAdmin 或 `psql` 执行：

```sql
CREATE DATABASE "IOT";
```

项目默认数据库配置如下：

```text
database = IOT
user = postgres
password = 123
host = localhost
port = 5432
```

如果本机配置不同，请在启动后端的 PowerShell 窗口中设置：

```powershell
$env:IOT_DB_NAME="IOT"
$env:IOT_DB_USER="postgres"
$env:IOT_DB_PASSWORD="你的数据库密码"
$env:IOT_DB_HOST="localhost"
$env:IOT_DB_PORT="5432"
```

初始化数据库表：

```powershell
python -m backend.database.init_db
```

看到 `database initialized successfully` 表示初始化完成。

### 4. 配置 Agent

复制 Agent 配置模板：

```powershell
Copy-Item agent/.env.example agent/.env
```

打开 `agent/.env`，至少填写百炼 API 密钥：

```env
DASHSCOPE_API_KEY=你的百炼API密钥
DASHSCOPE_MODEL=deepseek-v4.1-flash
MINGCHA_BACKEND_API_URL=http://127.0.0.1:8000
RAG_ENABLED=true
RAG_USE_EMBEDDINGS=true
RAG_EMBEDDING_MODEL=text-embedding-v4
RAG_USE_RERANKER=true
RAG_RERANK_MODEL=qwen3-rerank
RAG_RERANK_CANDIDATES=16
```

`agent/.env` 已被 Git 忽略，不会被提交到仓库。没有 API 密钥时仍可浏览和复核已导入的数据，
但无法使用百炼模型生成完整的 Agent 分析结果。

向量召回或重排接口临时不可用时，系统会依次降级为关键词检索和初排结果，不会阻断已有
研究数据的浏览与复核。若使用百炼业务空间专属域名，可在 `agent/.env` 额外设置
`RAG_RERANK_URL`。

### 5. 启动三个服务

在项目根目录打开三个 PowerShell 窗口，并按以下顺序启动。

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

浏览器访问：<http://127.0.0.1:8501>

服务检查地址：

- 后端健康检查：<http://127.0.0.1:8000/api/health>
- 后端 API 文档：<http://127.0.0.1:8000/docs>
- Agent 健康检查：<http://127.0.0.1:8001/api/health>

### 6. 首次建立研究数据

Git 仓库不保存体积较大的公开数据副本。三个服务正常启动后：

1. 打开左侧“数据来源”。
2. 点击“同步 DANDI 000718 研究目录”。
3. 打开“造模会话”，选择需要分析的会话。
4. 点击“载入该会话证据”，按需读取对应 NWB 数据。
5. 在“多模态复核”中查看视频、行为事件、钙活动、EEG、EMG 和睡眠状态。
6. 在“Agent 辅助决策”中生成带知识来源的分析并继续追问。

同步研究目录只建立实验动物、会话和远程文件的目录关系，不会立即下载整个数据集。首次载入
会话或播放视频时需要访问 DANDI，通常需要几十秒到数分钟。下载及转码结果会缓存在
`backend/cache/`，后续访问会明显加快。

## 日常启动

首次部署完成后，无需重复安装依赖、创建数据库和同步研究目录。启动 PostgreSQL 后，在项目
根目录分别运行以下三个命令即可：

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
python -m uvicorn agent.main:app --host 127.0.0.1 --port 8001
python -m streamlit run frontend/app.py --server.port 8501
```

三个命令需要分别保持运行，不能在同一个未结束的 PowerShell 窗口中依次执行。

## 更多说明

页面职责、公开数据导入流程和常见问题见 [`frontend/README.md`](frontend/README.md)，后端表结构
与数据接口见 [`backend/README.md`](backend/README.md)，RAG 与模型配置见
[`agent/README.md`](agent/README.md)。
