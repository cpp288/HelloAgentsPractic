# 第八章　记忆与检索

> 第七章我们搭好了 Agent 的骨架（LLM + Message + Tool 三件套），但跑起来会发现两个硬伤：**对话状态丢失**和**知识有限且过期**。第八章就是补这两块短板——给 Agent 加上记忆和 RAG，让它真正"长记性、懂知识"。
>
> 框架版本：`pip install "hello-agents[all]==0.2.0"`（若遇模型不可用可换 0.2.9），需要额外装 spaCy 中文/英文模型。

---

## 0. 一句话记住本章

**记忆 + RAG = Agent 获得"昨天的对话"和"知识库的知识"**。前者让 Agent 记得你是谁、做过什么；后者让 Agent 能查任何外部文档、回答任何问题，不被训练数据的时间上限卡死。

---

## 1. 认知科学先给答案（8.1）

教材从人类记忆的三层结构讲起——对应到 Agent 的设计直接套用：

| 人类记忆 | Agent 对应 | 特点 |
|---|---|---|
| **感觉记忆**（0.5-3秒，容量巨大） | （本章没直接实现，留给第九章上下文工程） | 暂存一切感官输入 |
| **工作记忆**（15-30秒，7±2项） | **WorkingMemory** | 当前会话的临时上下文，TTL 管理，会话结束即清理 |
| **情景记忆**（经历事件，带时间戳） | **EpisodicMemory** | 存交互事件和学习经历，按时间序列可回溯 |
| **语义记忆**（抽象知识、概念） | **SemanticMemory** | 存用户偏好、领域知识点，用 Qdrant + Neo4j 做知识图谱 |
| **感知记忆**（图像、音频等多模态） | **PerceptualMemory** | 跨模态检索，按模态分独立向量集合 |

**Agent 的两个根本性局限**（加记忆/RAG就是为了解它们）：

| 局限 | 症状 | 解决 |
|---|---|---|
| LLM 无状态 | 重启程序后 Agent 不记得你上次说了什么 | MemoryTool 持久化存储记忆 |
| 知识静态有限 | 2025 年的模型不知道 2026 年的技术 | RAGTool 从外部知识库实时检索 |

---

## 2. 架构设计（8.1.3）

### HelloAgents 记忆系统（四层）

```
hello-agents/
├── hello_agents/memory/
│   ├── base.py          # MemoryItem / MemoryConfig / BaseMemory（基础数据结构）
│   ├── manager.py       # MemoryManager（统一调度四种记忆）
│   ├── embedding.py     # 统一嵌入服务（DashScope / Local Transformer / TFIDF 兜底）
│   ├── types/
│   │   ├── working.py   # 工作记忆（纯内存 + TTL）
│   │   ├── episodic.py  # 情景记忆（SQLite + Qdrant）
│   │   ├── semantic.py  # 语义记忆（Qdrant + Neo4j 图谱）
│   │   └── perceptual.py # 感知记忆（多模态 SQLite + Qdrant）
│   ├── storage/
│   │   ├── qdrant_store.py   # 向量存储（高性能语义检索）
│   │   ├── neo4j_store.py   # 图存储（知识图谱关系推理）
│   │   └── document_store.py # SQLite 文档存储（结构化持久化）
│   └── rag/
│       ├── pipeline.py  # RAG 管道（端到端：载入 → 分块 → 嵌入 → 存库）
│       └── document.py  # 文档处理器（PDF/Word/HTML 多格式解析）
```

**关键设计决策**：记忆和 RAG 都封装成**工具**（第七章确立的"万物皆为工具"理念），Agent 不需要新增任何类就能直接调用——`agent.add_tool(memory_tool)` 搞定。

### 工作流程：模仿人类的记忆形成过程

教材把认知科学的五个阶段一一映射为技术操作：

| 认知阶段 | 技术操作 |
|---|---|
| **编码**（Encoding） | 将对话内容转为 MemoryItem，生成 embedding 向量 |
| **存储**（Storage） | 按记忆类型分发到 SQLite / Qdrant / Neo4j |
| **检索**（Retrieval） | 根据 query 做向量相似度 + 图关系推理 + 重要性加权 |
| **整合**（Consolidation） | 重要性超过阈值的工作记忆 → 情景记忆（短期→长期） |
| **遗忘**（Forgetting） | 三种策略：按重要性删、按时间删、按容量删 |

---

## 3. MemoryTool 详解（8.2.3）

MemoryTool 是记忆系统的**统一入口**，遵循"统一 execute + action 分发"模式：

```python
memory_tool.execute("add",     content="用户张三是 Python 开发者", memory_type="semantic", importance=0.8)
memory_tool.execute("search",  query="前端工程师", limit=3)
memory_tool.execute("forget",  strategy="importance_based", threshold=0.2)
memory_tool.execute("consolidate", from_type="working", to_type="episodic", importance_threshold=0.7)
```

| action | 功能 | 关键参数 |
|---|---|---|
| `add` | 添加记忆 | content, memory_type（working/episodic/semantic/perceptual）, importance(0.0~1.0) |
| `search` | 搜索记忆 | query, limit, memory_type(s), min_importance |
| `summary` | 获取记忆摘要 | 自动汇总长期记忆 |
| `forget` | 遗忘记忆 | strategy：importance_based / time_based / capacity_based |
| `consolidate` | 整合记忆 | from_type → to_type，importance_threshold |
| `update` / `remove` / `clear_all` | 管理操作 | 略 |

### 四种记忆类型的存储后端和检索策略

| 记忆类型 | 存储后端 | 检索/评分核心 |
|---|---|---|
| **WorkingMemory** | 纯内存 + TTL | 时间近因性（最近的最优先），会话结束自动清理 |
| **EpisodicMemory** | SQLite + Qdrant | 向量检索 + 时间近因性（权重 0.2） + 重要性加权 |
| **SemanticMemory** | Qdrant + Neo4j | **向量×0.7 + 图×0.3** 混合检索，再乘重要性权重 |
| **PerceptualMemory** | 多模态独立向量集合 | 同模态精确匹配 + 跨模态语义对齐 |

语义记忆的评分公式值得记一下，很能体现"设计意图"：

```
final_score = (vector_score × 0.7 + graph_score × 0.3) × (0.8 + importance × 0.4)
```

- 向量 0.7 权：语义相似度为主
- 图 0.3 权：关系推理为辅（发现"苹果"和"水果"的关联）
- 重要性范围 [0.8, 1.2]：不让重要性过度绑架相似度

---

## 4. RAG 系统详解（8.3）

RAG 解决的是**知识时效性和领域深度**问题。HelloAgents 的 RAG 分三层：

### 4.1 文档处理层

```
原始 PDF/Word/HTML → MarkItDown 统一转 Markdown → 智能分块 → 向量化 → Qdrant 存储
```

**智能分块策略**（教材的亮点）：
1. MarkItDown 把所有文档转成标准 Markdown（统一格式）
2. 按 `# / ## / ###` 标题层次做结构化分割（保持语义完整）
3. Token 数控制分块大小（默认 1000 token，重叠 200 token）
4. 中英文混合的 Token 估算（CJK 字符按 1 token，英文按空格分词）

### 4.2 三种嵌入方案

| 方案 | 适用场景 | 配置 |
|---|---|---|
| **DashScope API**（百炼） | 云端、效果好 | `EMBED_MODEL_TYPE=dashscope` |
| **Local Transformer**（all-MiniLM-L6-v2） | 离线、隐私 | `EMBED_MODEL_TYPE=local` |
| **TFIDF** | 兜底、轻量 | 自动降级 |

### 4.3 高级检索策略

普通向量检索效果有限，教材介绍了两种进阶方案：

| 策略 | 思路 | 适用场景 |
|---|---|---|
| **MQE（多查询扩展）** | 用 LLM 把用户问题改写成多个同义词查询，每个单独检索后合并结果 | 用词多样性问题 |
| **HyDE（假设文档嵌入）** | 让 LLM 先生成一份"假设的答案文档"，用它的 embedding 去检索真实文档 | 语义鸿沟大的专业领域 |

**建议组合**：一般查询用 MQE；专业领域同时开 MQE + HyDE；性能敏感场景只用基础检索。

---

## 4.4 LLM Wiki：Karpathy 的"编译范式"（前沿补充）

教材写作于 2025 年，彼时 RAG 还是知识库的唯一主流。但 2026 年初 Andrej Karpathy（前 OpenAI 创始团队、特斯拉 AI 负责人）提出了一种**完全不同的知识库架构——LLM Wiki**，在 GitHub 上两个月屠出 5000+ star，被不少人视为 RAG 的"下一代范式"。

### 核心思想：把检索变成编译

RAG 和 LLM Wiki 的本质区别只有一个：**知识工作发生在什么时候**。

| 维度 | RAG（教材 8.3 的方案） | LLM Wiki（Karpathy 范式） |
|---|---|---|
| **综合发生时机** | 查询时（query time） | 导入时（ingestion time） |
| **知识状态** | 无状态——每次查询都重新检索原始片段 | 持久化——导入时"编译"成结构化 Wiki，后续查询直接查 Wiki |
| **知识形态** | 一堆独立文档 + 向量索引 | 互联的 Markdown 页面 + 双向链接（`[[概念名]]`） |
| **跨引用** | 隐式（靠 embedding 相似度"碰巧"关联） | 显式（每个概念页主动链接相关页） |
| **随时间复利** | 不会——每次查询从零开始 | 会——Wiki 越维护越聪明，像"滚雪球" |
| **计算成本** | 每次查询都要跑检索 + 拼接 + 生成 | 一次性编译，后续查询只查 Wiki |
| **维护成本** | 几乎零（导入完就不用管了） | 需要定期重新编译（更新知识、修复错误链接） |
| **最大瓶颈** | 查询时间（长文档、复杂检索会慢） | Wiki 体积（超过 LLM 上下文窗口就需要分层） |

### LLM Wiki 怎么工作

```
[原始文档]── 编译阶段 ──▶ [LLM 编译] ──▶ [结构化 Wiki]
  PDF/论文/笔记                                │
                                             │
                                             ▼
[用户提问] ──▶ [查 Wiki（向量检索或直接读文件）] ──▶ [LLM 回答]
```

**编译阶段**（一次性或增量更新时）：
1. LLM 读入原始文档
2. 提取核心概念、实体、关系
3. 每个概念生成一页 Markdown，开头写概念定义、要点、引用来源
4. 页面内用 `[[相关概念]]` 链接互相关联
5. 记录来源追溯（每段编译后的内容能定位回原文第几页）

**查询阶段**：
1. 直接查 Wiki 页面（可以用向量检索找相关页，也可以让 LLM 直接读）
2. 把相关 Wiki 页喂给 LLM 回答
3. 比直接检索原始文档**信息密度高得多**——Wiki 是"LLM 先消化过一遍"的结果

### 那 LLM Wiki 能取代 RAG 吗？

**不能互相取代，是互补关系**：

| 场景 | 选谁 | 原因 |
|---|---|---|
| 知识**需要持续更新**（新闻、实时数据） | RAG | Wiki 编译成本高，实时性差 |
| 知识**相对稳定**（论文、技术文档、个人笔记） | LLM Wiki | 一次编译、终身受益，回答质量更高 |
| 问题**很简单**（直接事实查询） | RAG 或直接查 Wiki | 都能搞定，RAG 更省时间 |
| 问题**很复杂**（跨概念综合、对比分析） | LLM Wiki | Wiki 的显式链接让 LLM 更容易发现概念间关系 |
| 需要**引用来源** | 都行 | LLM Wiki 每段带追溯，RAG 可附带原始片段 |
| 资源**有限**（不想买向量数据库） | LLM Wiki | 就是一堆 Markdown 文件，零基础设施成本 |

HelloAgents 教材里的 RAGTool 目前是**纯 RAG 模式**（检索原始文档片段），但架构上很容易扩展 LLM Wiki——只需在"分块 → 向量化"之间加一个 LLM 编译步骤，把原始片段变成 Wiki 页面后再入库。这是一个值得动手试试的扩展方向。

### 当前可用工具（2026 年）

| 工具 | 类型 | 特点 |
|---|---|---|
| **Karpathy Gist**（原始范式） | prompt + 手动维护 | 最简单，把 prompt 喂给 Claude Code / Cursor 让它自己建 Wiki |
| **llm-wiki**（Tauri 桌面应用） | 成品应用 | Rust + React，支持自动编译、双链互联、增量更新 |
| **Obsidian + Cursor + prompt** | 工作流 | 用 Obsidian 存 Wiki，Cursor 做编译，自由控制 |
| **HelloAgents 自行扩展** | 框架层 | 给 RAGTool 加一个"编译模式"，在 8.3.4 的嵌入前插入 LLM 编译步骤 |

### 一句话总结 LLM Wiki

**RAG 让 LLM "开卷考试"，LLM Wiki 让 LLM "先把书读一遍做笔记，考试时翻自己的笔记"**。笔记比课本薄、结构化、写了重点，自然答得更好——但前提是你得花时间做笔记（编译）。这就是为什么 Karpathy 说它"知识第一次能像代码一样利滚利"。

---

## 5. 实战案例：智能文档问答助手（8.4）

教材用一个基于 Gradio 的 PDF 问答助手把 Memory + RAG 串了一遍。

### 五步闭环流程

```
[1] 加载 PDF → RAGTool.add_document（MarkItDown + 智能分块 + 向量化）
                 + MemoryTool.add（情景记忆：加载事件）
[2] 用户提问 → RAGTool.ask（MQE + HyDE 高级检索）
                 + MemoryTool.add（工作记忆：问题本身）
[3] 回答生成 → 基于检索片段 + 记忆上下文
                 + MemoryTool.add（情景记忆：问答事件）
[4] 写笔记  → MemoryTool.add（语义记忆：概念笔记）
[5] 报告生成 → 汇总所有记忆和 RAG 统计 → JSON 报告
```

关键设计点：
- **user_id** 隔离不同用户的记忆空间
- **rag_namespace** 隔离不同用户的 RAG 知识库
- **session_id** 追踪单次会话完整过程，便于回顾

### 核心代码骨架

```python
class PDFLearningAssistant:
    def __init__(self, user_id="default_user"):
        self.memory_tool = MemoryTool(user_id=user_id)
        self.rag_tool = RAGTool(rag_namespace=f"pdf_{user_id}")

    def load_document(self, pdf_path):
        # 一行搞定：MarkItDown → 分块 → 向量化 → Qdrant
        self.rag_tool.execute("add_document", file_path=pdf_path,
                              chunk_size=1000, chunk_overlap=200)
        # 同时记录到记忆系统
        self.memory_tool.execute("add", content=f"加载了《{文件名}》",
                                  memory_type="episodic", importance=0.9)

    def ask(self, question):
        # 工作记忆记问题
        self.memory_tool.execute("add", content=f"提问:{question}",
                                  memory_type="working")
        # RAG 高级检索
        answer = self.rag_tool.execute("ask", question=question,
                                        enable_mqe=True, enable_hyde=True)
        return answer
```

完整代码在 `code/chapter8/11_Q&A_Assistant.py`，启动 `http://localhost:7860` 即可体验。

---

## 6. 依赖清单

本章比前几章重很多，完整 `.env` 需要：

| 类型 | 依赖 | 获取方式 |
|---|---|---|
| **向量数据库** | Qdrant Cloud 或本地 Docker | cloud.qdrant.io（免费） |
| **图数据库** | Neo4j Aura Cloud 或本地 Docker | neo4j.com/cloud/aura |
| **嵌入服务** | 阿里云百炼 DashScope / Local Transformer / TFIDF 兜底 | dashscope.aliyun.com |
| **LLM** | 沿用之前的 OpenAI 兼容 API | 已有 |
| **spaCy** | 中英文分词模型 | `python -m spacy download zh_core_web_sm en_core_web_sm` |
| **文档处理** | MarkItDown | pip 依赖已包含 |

---

## 附录：大白话理解

### 记忆系统 = Agent 的大脑

四种记忆就是 Agent 大脑里不同的脑区：

| 脑区 | 对应 | 什么时候用 |
|---|---|---|
| **前额叶**（短期，正在想的） | WorkingMemory | 聊天时"我正在和张三聊 Python 函数" |
| **海马体**（经历过的事） | EpisodicMemory | "上次张三说他刚学完基础语法" |
| **皮层**（抽象知识） | SemanticMemory | "Python 是解释型面向对象语言" |
| **视觉皮层**（图像/音频） | PerceptualMemory | "张三上传了一张代码截图" |

### 遗忘不是 bug，是 feature

如果让 Agent 把每次对话都永远存着，几个月后知识库会膨胀到检索变慢、甚至引入噪声。所以三种遗忘策略都是在**主动清理不重要的记忆**：
- 不重要的（importance < 0.2）直接删
- 太久的（30天以上）删
- 存不下了（容量到顶）删最不重要的

### RAG = Agent 的外挂知识库

把"PDF / Word / HTML"塞给 RAGTool，它自动转 Markdown、自动分块、自动生成向量存进 Qdrant。你提问时它自动从知识库找最相关的片段、喂给 LLM 回答。

这套流程和我们平时查 PDF 是一样的：
1. 把 PDF 放进内存 → `rag_tool.execute("add_document", ...)`
2. 提问 "这里讲了什么" → `rag_tool.execute("ask", question=...)`
3. 拿到答案（附带参考来源和相似度）

**MQE 就是"用不同措辞问同一个问题，哪个检索结果好用哪个"**，HyDE 就是"先让模型瞎猜一个答案，拿这个猜测的向量去找真实答案"——都是提升检索召回率的工程 trick。

### 本章最值钱的工程经验

Memory 和 RAG 在框架里**都只是 Tool**。这意味着以后你想加"多模态视频记忆"、"实时网页 RAG"，本质上都只是**新增一个 Tool 类**，Agent 代码一行不用改。这就是第七章"万物皆为工具"这个设计理念的真正威力——它让后续所有高级功能都成了"可选插件"，而非"必须重写 Agent"。
