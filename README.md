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
- 百炼 `text-embedding-v4` 向量检索

## 启动方式

完整的环境配置、数据库初始化和三项服务启动步骤见
[`frontend/README.md`](frontend/README.md)。

本仓库不包含 API 密钥、本地数据库、下载缓存、原始公开数据集副本、视频文件及历史项目存档。
