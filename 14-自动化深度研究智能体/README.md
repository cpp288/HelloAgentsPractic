# 第十四章 自动化深度研究智能体

> 本章是一个完整案例：用「TODO 驱动」的多智能体系统，把开放研究主题变成一份带来源引用的结构化报告。
> 本章为案例讲解，未在本仓库放置练习代码；教材配套工程为 `helloagents-deepresearch`（后端 FastAPI + 前端 Vue3）。
> 运行前提（教材版）：Python ≥ 3.10、Node ≥ 16，`.env` 至少配置 `LLM_PROVIDER` / `LLM_API_KEY` / `SEARCH_API`，后端 8000、前端 5174。

## 0. 一句话记住本章

**把"研究一个开放主题"拆成"规划 3–5 个 TODO → 逐个 搜索 + 总结 + 记笔记 → 汇总成带引用的报告"，三个 Agent 各管一段，SSE 把过程实时播给用户。**

## 1. 整体架构（14.1）

四层结构，职责边界很清楚：

| 层 | 技术 | 负责什么 |
|---|---|---|
| 前端层 | Vue3 + TypeScript | 全屏模态框、任务列表/进度日志、Markdown 报告渲染 |
| 后端层 | FastAPI | 只暴露一个流式端点 `/research/stream`，负责 SSE 推送 |
| 智能体层 | HelloAgents | 三个专职 Agent（规划/总结/报告）+ 两个工具（SearchTool/NoteTool） |
| 外部服务层 | 搜索引擎 + LLM | Tavily / DuckDuckGo / Perplexity…，以及任意 OpenAI 兼容模型 |

一次研究的完整数据流（图 14.2 的 8 步）：

```
用户输入主题
  → 前端 SSE 连接 /research/stream
  → FastAPI 创建研究状态
  → ① 规划：TODO Planner 拆出 3–5 个子任务
  → ② 执行：对每个子任务
        SearchTool 搜索 → Task Summarizer 总结 → NoteTool 落盘
  → ③ 报告：Report Writer 整合所有总结
  → SSE 持续推送进度/任务/报告
  → 前端更新任务状态、进度条、日志、Markdown 报告
```

工程目录（精简）：

```
helloagents-deepresearch/
├── backend/src/
│   ├── agent.py          # 核心协调器 DeepResearchAgent
│   ├── main.py           # FastAPI 入口 + SSE
│   ├── models.py         # TodoItem / SummaryState 等
│   ├── prompts.py        # 三套 Prompt 模板
│   └── services/         # planner / summarizer / reporter / search
└── frontend/src/
    ├── App.vue
    ├── components/ResearchModal.vue
    └── composables/useResearch.ts   # EventSource 封装
```

**设计取舍**：不做多 Agent 并发，而是"线性三段 + 段内串行"。原因是研究任务存在强依赖（必须先有 TODO 才能执行、先有总结才能写报告），并发只会增加协调成本。

## 2. TODO 驱动的研究范式（14.2）

### 2.1 与传统搜索的区别

| | 传统搜索 | TODO 驱动 |
|---|---|---|
| 输入 | 一个关键词 | 一个开放主题 |
| 过程 | 返回 10–20 条链接，人自己点开读 | 自动拆子任务，逐个搜索+总结 |
| 输出 | 碎片信息 | 结构化报告 + 来源引用 |
| 可追溯 | 靠浏览器历史 | 每个子任务都有笔记与 URL |

### 2.2 三个核心角色

1. **智能规划器（TODO Planner）**：把主题拆成 3–5 个子任务（太少覆盖不全，太多冗余），并为每个子任务写搜索 query。
2. **任务执行器（Task Executor）**：搜索 → 提取要点 → 去冗余 → 保留来源。
3. **报告生成器（Report Writer）**：按逻辑排序、合并重复、统一格式、汇总参考文献。

### 2.3 三阶段流程

| 阶段 | 输入 | 输出 | 关键点 |
|---|---|---|---|
| Planning | 研究主题 + 当前日期 | `[{title, intent, query}]` | 数量 3–5、逻辑递进、query 可检索、只返回 JSON |
| Execution | 子任务列表 + 搜索引擎配置 | 每个子任务一份 Markdown 总结 + 来源列表 | 逐条执行，实时推送 `status` / `task` 事件 |
| Reporting | 主题 + 所有子任务总结 | 最终 Markdown 报告 | 标题、概述、分节、总结、参考文献五段式 |

子任务只有三个字段，但各有用途：`title` 用于展示与报告小标题，`intent` 约束"为什么研究这个"，`query` 直接喂给搜索引擎（教材建议用英文 query 提升召回）。

以「Datawhale 是一个什么样的组织？」为例，规划结果通常是：基本信息 / 主要项目 / 社区文化 / 影响力——从"是什么"到"做了什么"再到"价值如何"，形成逻辑闭环。

**规划质量自检**（教材给的 `evaluate_plan` 思路）：数量 <3 扣分、>5 扣分、query 少于 2 个词扣分。这是很实用的低成本质量闸门。

## 3. 三个 Agent 的设计（14.3）

### 3.1 职责与 Prompt 约束

| Agent | 职责 | 输入 | 输出 | Prompt 必须写死的约束 |
|---|---|---|---|---|
| TODO Planner | 主题 → 子任务 | 主题、当前日期 | JSON 任务数组 | 3–5 个、逻辑关系、query 精准、只输出 JSON、带当前日期以便搜最新信息 |
| Task Summarizer | 搜索结果 → 结构化总结 | 任务三字段 + 搜索结果 | Markdown 总结 + `[1][2]` 引用 | 核心观点/关键数据/来源引用三段式、保留数字日期名称、每观点带引用 |
| Report Writer | 多份总结 → 最终报告 | 主题 + 各任务总结与来源 | Markdown 报告 | 按逻辑顺序、消除重复、保留全部引用、五段式结构 |

三个 Prompt 的共同套路：**给角色 + 给上下文 + 给输出格式示例 + 给硬约束**。规划器的"当前日期"是个容易忽略的细节——没有它，模型会拿旧知识编"2024 年最新"。

### 3.2 ToolAwareSimpleAgent：给 Agent 装"行车记录仪"

教材第七章的 `SimpleAgent` 只会"想 → 调工具 → 答"，不暴露工具调用细节。本章扩展出 `ToolAwareSimpleAgent`：

- 继承 `SimpleAgent`，只重写 `_execute_tool_call`；
- 新增 `tool_call_listener` 回调；
- 每次工具调用后回调四个字段：`agent_name` / `tool_name` / `parsed_parameters` / `result`。

```python
def _execute_tool_call(self, tool_name: str, parameters: str) -> str:
    parsed_parameters = self._parse_parameters(parameters)
    result = super()._execute_tool_call(tool_name, parameters)
    if self._tool_call_listener:
        self._tool_call_listener({
            "agent_name": self.name,
            "tool_name": tool_name,
            "parsed_parameters": parsed_parameters,
            "result": result,
        })
    return result
```

价值有四个：调试（看参数对不对）、日志（留痕）、行为分析（统计调了哪些工具）、**实时进度展示**（转成 SSE 的 `tool_call` 事件）。这和第十三章里我们做的"执行追踪"是同一个思路：**可观测性不是附属功能，而是多智能体系统的必备件**。

### 3.3 协作模式：顺序编排

`DeepResearchAgent` 是唯一协调器，`run()` 就是三段直线代码：

```python
def run(self, research_topic: str) -> str:
    todo_list = self.planner.plan_todo_list(research_topic)      # ① 规划
    emit({"type": "tasks", "tasks": todo_list})

    task_summaries = []
    for task in todo_list:                                        # ② 执行
        emit({"type": "status", "message": f"正在研究：{task.title}"})
        results = self.search_service.search(task.query)
        summary = self.summarizer.summarize_task(task, results)
        self.note_service.save_task_summary(task, results, summary)
        task_summaries.append((task, summary))
        emit({"type": "task_completed", "task_id": task.id})

    report = self.reporter.generate_report(research_topic, task_summaries)  # ③ 报告
    emit({"type": "report", "content": report})
    return report
```

顺序协作的三个特征：线性流程、上一步输出即下一步输入、同一时刻只有一个 Agent 在工作。

## 4. 工具系统（14.4）

### 4.1 SearchTool：多引擎统一接口

在第七章 Tavily + SerpApi 的基础上，本章补了 `duckduckgo`、`perplexity`、`searxng`，以及 `advanced`（组合多引擎）。

| 引擎 | 是否需要 Key | 特点 |
|---|---|---|
| DuckDuckGo | 否 | 零配置、易限流，适合本地体验（教材默认） |
| Tavily | 是 | 为 Agent 设计，直接返回摘要，质量稳定 |
| Perplexity | 是 | 额外返回 AI 生成的 `answer` |
| SearXNG | 否（自建） | 可私有化部署，聚合多源 |
| Advanced | 视子引擎 | 多引擎组合，覆盖更全但更慢更贵 |

统一返回结构：`results[]`（title/url/snippet）、`backend`、`answer`（仅 Perplexity）、`notices`（限流/错误提示）。

两类结果治理（很关键，直接决定 token 成本）：

```python
# URL 去重
if source["url"] not in seen_urls: ...

# 单来源限长：1 token ≈ 4 字符，2000 token ≈ 8000 字符
if len(snippet) > max_tokens * 4:
    snippet = snippet[: max_tokens * 4] + "..."
```

### 4.2 NoteTool：把研究过程落盘

`NoteTool`（第九章内置工具）把每个子任务写成一个 Markdown 文件，天然支持"中断后继续"和事后审计：

```
workspace/
├── notes/
│   ├── 1.md      # 任务 1：任务信息 + 搜索结果 + 总结
│   ├── 2.md
│   └── ...
└── reports/
    └── final_report.md
```

笔记内容包含任务意图、查询、原始搜索结果、总结——相当于把"证据链"完整保存，报告里的每个观点都能回溯。

### 4.3 ToolRegistry：工具的统一入口

注册后 Agent 只需生成调用指令，六步完成执行：

```
1. Agent 生成 [TOOL_CALL:search_tool:{"input": "...", "backend": "tavily"}]
2. Registry 解析工具名与参数
3. 按名查找工具
4. 调用 tool.run(params)
5. 工具返回结果
6. 结果格式化为字符串回灌给 Agent
```

**为什么还要 SearchService 中间层？** 教材明确说明：不让 Agent 直接调 SearchTool，而是由服务层先做去重、限长、异常兜底，再把干净结果交给 Agent。这样 Agent 只专注"理解信息"，工程治理留在代码里——**确定性的活交给代码，判断性的活交给模型**。

## 5. 四个核心服务（14.5）

| 服务 | 职责 | 关键实现 |
|---|---|---|
| PlanningService | 构建 Prompt、调规划 Agent、解析并校验 JSON | 正则 `\[.*\]` 提取数组 → 失败再整体 `json.loads` → 校验 title/intent/query 齐全 |
| SummarizationService | 格式化搜索结果、调总结 Agent | 结果编号成 `[1] 标题 / URL / 摘要`，让模型按编号引用 |
| ReportingService | 格式化各任务总结、调报告 Agent | 按 `## 任务 N：标题 + 意图 + 总结 + 来源` 拼装，保证引用不丢 |
| SearchService | 选引擎、执行搜索、治理结果 | 去重 + 限长 + 异常返回空列表；可加本地缓存 |

两个值得抄的工程细节：

1. **JSON 解析要容错**：模型常在 JSON 前后加"好的，我将为您规划…"。先正则抠数组，再退化到整体解析，最后才报错。
2. **搜索缓存**：用 `query + max_results + backend` 做 MD5 当文件名，命中直接读 `cache/search/*.json`，省钱且让调试可复现。

## 6. 前端交互（14.6）

三块：全屏模态框、SSE 实时进度、Markdown 结果渲染。

**全屏模态**：遮罩 + 顶部栏（主题/关闭）+ 进度条 + 内容区 + 底部状态栏；支持 ESC 关闭，768px / 480px 两个断点做响应式。

**SSE 事件协议**（本章的接口契约）：

| 事件 `type` | 载荷 | 前端动作 |
|---|---|---|
| `progress` | `stage`, `percentage`, `text` | 更新进度条与文案 |
| `plan` | 子任务数组 | 渲染任务列表 |
| `task_summary` | `task_id`, `summary` | 追加到 Markdown |
| `report` | 完整报告 | 整体替换内容区 |
| `error` | `message` | 显示错误并关闭连接 |
| `completed` | — | 关闭连接、结束 loading |

进度分配：规划 10% → 执行 10%~80%（按任务序号线性递增）→ 报告 90% → 完成 100%。

**渲染**：`marked` 配置 `breaks: true`（支持换行）、`gfm: true`（表格/任务列表），再用 `v-html` 输出；参考文献用列表形式分组展示。

## 7. 2025 → 2026：这一块发生了什么（重要补充）

> 教材写于 2025 年，深度研究是过去一年变化最快的赛道之一。以下均按官方文档核对过（截至 2026-11）。

### 7.1 大变化：从"自己搭"到"可以直接调托管 Deep Research"

| 厂商 | 当前形态（2026-11） | 与教材的关系 |
|---|---|---|
| OpenAI | Responses API + `o3-deep-research` / `o4-mini-deep-research`；数据源需至少一个：web search、remote MCP server、file search | 教材"自建三 Agent"是它的低成本替代；官方模型 **已于 2026-07-23 下线**，文档给出的替代是 `gpt-5.6-sol` |
| Google | Gemini Deep Research Agent 处于 preview，**只能通过 Interactions API**（`generate_content` 用不了），`background=True` 异步跑，模型如 `deep-research-preview-04-2026`，另有 `max` 版追求覆盖面 | 教材里"规划→搜索→总结→报告"被封装成一个托管 Agent，客户端只负责发起+轮询/流式接收 |
| LangChain | **Deep Agents**：在 LangGraph 之上提供 planning、虚拟文件系统、子 Agent 派生、长期记忆的 harness；另有托管版 Managed Deep Agents | 教材的三段式顺序编排≈最小 harness；要升级可迁到 Deep Agents，省掉手写状态与笔记层 |

结论：**"必须自己写三个 Agent + SSE"已经不是唯一答案**。学习价值仍在（能定制、可控成本、可接私有数据），但生产选型要先问一句"能不能直接调托管 deep research"。

### 7.2 搜索 API 生态变化

| 项 | 现状 | 对教材的影响 |
|---|---|---|
| Tavily | 免费 1000 credits/月，按量 $0.008/credit；已推出 Tavily Research（`model=mini/pro`，按次计费） | 教材默认 DuckDuckGo，生产建议换 Tavily；`SearchTool` 调用方式不变 |
| Exa | Search 约 $7/1000 次请求，Deep Search $12–15/1000 次 | 可作为 `advanced` 模式的补充引擎 |
| DuckDuckGo | 仍免 Key，但限流明显 | 只适合本地演示，不适合批量研究 |
| Perplexity | 仍提供带 `answer` 的搜索接口，额度和价格以当期文档为准 | 教材的"answer 字段仅 Perplexity"依然成立 |

### 7.3 教材哪些内容需要更新

1. **"o3-deep-research 是最新方案"** → 已过时，2026-07-23 下线，改用 `gpt-5.6-sol` 或自建。
2. **"Deep Research 只能自己搭"** → 已过时，OpenAI / Gemini 都有托管 Agent，Gemini 还只能走 Interactions API。
3. **"手写 EventSource + 自定义事件协议"** → 仍可用，但托管 API 多提供后台任务 + 轮询/流式两种模式，协议设计可参考它们的事件模型。
4. **"规划 3–5 个 TODO 就够"** → 仍然成立；变化在于现在可以让子 Agent 并行检索（Deep Agents 支持 subagents），但强依赖阶段仍需串行。

### 7.4 没变的部分

- TODO 分解 + 来源引用 + 笔记落盘，依然是"可信研究报告"的三根支柱；
- "确定性逻辑用代码、判断性逻辑用模型"的分层，依然是最稳的工程实践；
- 工具调用可观测（ToolAware 思路），在托管方案里对应 trace/事件流，思路一致。

## 8. 本章速查表

| 主题 | 记住这一句 |
|---|---|
| 研究范式 | 规划 → 执行 → 报告，三段直线，段内串行 |
| TODO 三字段 | title（展示）、intent（为什么）、query（搜什么） |
| 三个 Agent | Planner 拆题、Summarizer 提炼、Writer 成文 |
| ToolAwareSimpleAgent | 重写 `_execute_tool_call` + 回调，换来全链路可观测 |
| 工具治理 | URL 去重 + 单来源 2000 token 上限 |
| NoteTool | 一任务一 Markdown，支持断点续研与审计 |
| SearchService | 中间层做脏活，Agent 只读干净结果 |
| SSE 事件 | progress / plan / task_summary / report / error / completed |
| 2026 变化 | 托管 Deep Research 可用，o3-deep-research 已下线 |

## 附录：大白话理解

**把整个系统想成"带三个实习生的论文小组"。**

- **你**：布置题目「Datawhale 是个什么组织？」。
- **TODO Planner（开题的人）**：不急着搜，先把题目拆成四张小纸条——它是什么、做过什么、什么文化、有什么影响。这就是 TODO 列表。纸条上写清"查什么关键词"（query），免得实习生瞎搜。
- **Task Summarizer（查资料做笔记的人）**：拿着每张纸条去搜索引擎翻资料，读完写成一段带脚注 `[1][2]` 的笔记。**脚注就是来源引用**，防止它胡说。
- **Report Writer（统稿的人）**：把四份笔记按顺序拼成一篇报告，删掉重复内容，最后把脚注统一整理成参考文献。
- **DeepResearchAgent（组长）**：自己不干活，只负责喊"现在开题""现在查第 2 条""现在统稿"，并把进度发到群里。
- **SSE**：群里的实时消息——"正在查第 2 条""第 2 条完成了"，你随时能看到干到哪了。
- **NoteTool**：小组共享的笔记本，每条任务一个 md 文件。中途断电也不怕，翻开笔记本就知道查到哪了。
- **ToolRegistry**：工具箱的借还登记处。谁借了搜索工具、传了什么参数、拿回什么结果，都有记录。
- **ToolAwareSimpleAgent**：给每个实习生配了"行车记录仪"，它一用工具就自动记一笔，组长能把记录实时转发给你。
- **SearchService**：资料预处理员。搜索回来的东西又脏又长，他先去掉重复链接、把超长摘要剪短，再交给实习生，省得实习生被垃圾信息淹没。

**为什么不能三个实习生同时干活？** 因为统稿的人必须等笔记写完，做笔记的人必须等开题的人给纸条——**有先后依赖的事，硬并发只会互相等**。真正能并发的，是"四张纸条同时去查"，这在 2026 年的 Deep Agents 里对应 subagents，但前提仍是先开题。

**一句话**：这套系统的本质，是把"人写论文的流程"翻译成了代码——**先列提纲，再查资料做笔记，最后统稿加引用**；Agent 只是把每一步换成了一个有明确岗位说明书的模型调用。

## 参考来源（2026-11 核对）

- [OpenAI Deep research 指南](https://developers.openai.com/api/docs/guides/deep-research)（含 `o3-deep-research` 下线日期与替代模型）
- [Gemini API: Deep Research Agent](https://ai.google.dev/gemini-api/docs/deep-research?hl=zh-cn)（仅 Interactions API、preview 模型名）
- [LangChain Deep Agents 概览](https://docs.langchain.com/oss/python/deepagents/overview)（planning / 文件系统 / subagents / memory）
- [Tavily Credits & Pricing](https://docs.tavily.com/documentation/api-credits)（credits 与 Research 计费）
- [Exa 定价与能力对比](https://exa.ai/versus/tavily)（Search / Deep Search 单价）
