# 明察鼠毫 Agent

Agent 服务使用阿里云百炼 `deepseek-v4.1-flash`，对 Backend 提供的同一实验会话证据
进行解释。服务采用混合 RAG：结构化实验事实来自 Backend/PostgreSQL，研究解释来自
项目知识库；知识片段先使用百炼 `text-embedding-v4` 与中文关键词进行混合召回，再由
`qwen3-rerank` 对候选片段二次排序。向量或重排服务不可用时会自动降级，不影响基础
检索。模型必须区分“当前动物的实验观察”和“公开研究资料”，分析结果及
实际引用来源由 Backend 写入 PostgreSQL。

## 配置

复制 `agent/.env.example` 为 `agent/.env`，填写：

```env
DASHSCOPE_API_KEY=你的百炼密钥
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_MODEL=deepseek-v4.1-flash
MINGCHA_BACKEND_API_URL=http://127.0.0.1:8000
RAG_ENABLED=true
RAG_USE_EMBEDDINGS=true
RAG_EMBEDDING_MODEL=text-embedding-v4
RAG_EMBEDDING_DIMENSIONS=512
RAG_TOP_K=4
RAG_USE_RERANKER=true
RAG_RERANK_MODEL=qwen3-rerank
RAG_RERANK_CANDIDATES=16
```

知识文档位于 `agent/knowledge/`，当前包括：

- DANDI 000718 官方数据说明、固定版本与数据溯源；
- 对应 Nature 原始论文的研究结论、睡眠判读和钙成像处理方法；
- 恐惧条件化、冻结行为及情境回忆判读方法；
- GCaMP 钙信号的生理解释边界；
- EEG、EMG、活动信号与睡眠状态复核规则；
- NWB 多模态时间戳和跨会话真实时间对齐规范；
- ARRIVE 2.0 动物研究设计与报告要点；
- 多模态证据复核规范和 Agent 辅助决策使用边界；
- 行为视频追踪、NWB 文件验证、钙成像 ROI 质控和睡眠分期复核；
- 动物实验随机化、盲法、PREPARE 规划以及 FAIR 数据管理原则。

首次语义检索会调用百炼生成文档向量，并缓存到
`agent/cache/knowledge_index.json`。知识文档修改后会根据内容指纹自动重建索引。
检索时默认先召回 16 个候选片段，再使用百炼 `qwen3-rerank` 选出最相关资料。重排接口
复用 `DASHSCOPE_API_KEY`；业务空间专属地址可通过 `RAG_RERANK_URL` 显式配置。

## 启动

```powershell
python -m pip install -r agent/requirements.txt
python -m uvicorn agent.main:app --host 127.0.0.1 --port 8001
```

健康检查：`http://127.0.0.1:8001/api/health`

公开会话分析：`POST /api/dataset-sessions/{会话编号}/analyze`

知识检索测试：`POST /api/knowledge/search`

请求示例：

```json
{
  "query": "恐惧条件化后应该如何结合冻结行为与钙活动判断？",
  "top_k": 4
}
```

若向量模型暂时不可用，知识检索会自动使用关键词匹配；若重排服务暂时不可用，系统会
保留混合检索原排序；若生成模型不可用，Backend 会
保留基于已载入数据的本地证据结论，不会虚构模型输出。硬件控制建议和旧实验鼠对话接口
仍保留用于兼容。

