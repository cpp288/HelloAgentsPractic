# 第七章　构建你的 Agent 框架

> 前六章都是"用"——用别人写好的范式、平台、框架。这一章反过来：**从零构建一个你自己的 Agent 框架 HelloAgents**，作为后续八~十六章所有高级功能的统一底座。
>
> 框架代码仓库：[github.com/jjyaoao/helloagents](https://github.com/jjyaoao/helloagents)，可直接 `pip install hello-agents==0.1.1` 体验，也可以跟着教材从零实现每一个组件。

---

## 0. 一句话记住本章

**框架 = 第四章的范式代码 + 解耦 + 抽象 + 工程化**。不是重新发明范式，是把散在第四章里的"能用代码"整理成"可复用的组件"。

---

## 1. 为什么自建框架（7.1.1）

教材给了三条理由，每条都戳中我们用 AgentScope/LangChain 时踩过的坑：

| 市面框架的局限 | 我们真实遇到过吗 |
|---|---|
| **过度抽象**（LangChain 链式调用、十几个概念才能完成一个简单任务） | ✅ AgentScope 2.x 的 Msg.content 必须是 list[TextBlock]、Credential 必须用 model_validate |
| **快速迭代不稳定**（API 频繁变更、升级即报错） | ✅ AgentScope 1.x → 2.x 的 MsgHub/FanoutPipeline/DialogAgent 全没了 |
| **黑盒化**（核心逻辑封装太严，改不了） | ✅ structured_schema 模式下 reply.content 被占位符替换，想拿自然语言只能翻源码挖 reply_stream |
| **依赖臃肿**（安装包大、和别的库冲突） | 这条没太踩到，但也是实情 |

**自建框架的价值**：从"使用者"跃升到"构建者"——每一行代码你都能改，遇到问题能直接定位到自己写的代码，而不是翻文档等社区回复。

---

## 2. HelloAgents 的四个设计理念（7.1.2）

这四个理念是整个框架的灵魂：

| 理念 | 含义 | 解决什么问题 |
|---|---|---|
| **轻量级与教学友好** | 核心代码按章节可区分，任何有基础的开发者都能在合理时间内读完；极简依赖（只引 OpenAI SDK + 必要基础库） | 解决"为了用一个功能不得不理解十几个抽象层" |
| **基于标准 API** | 所有 LLM 调用基于 OpenAI 兼容 API，不重新发明一套 | 解决"换个模型提供商就得重学 API" |
| **渐进式学习路径** | 每章的代码可 pip 下载历史版本，每一步升级都是自然而然的 | 解决"概念跳跃、跟不上" |
| **万物皆为工具** | 除核心 Agent 类，Memory、RAG、MCP 等**统统抽象为 Tool** | 彻底贯彻轻量级，消除不必要的抽象层 |

最后这个"万物皆为工具"是最激进也最巧妙的设计——后续章节的所有高级功能都能被 Agent 当作工具调用，不用再学习新概念。

---

## 3. 架构蓝图与目录结构（7.1.3）

```
hello-agents/
├── hello_agents/
│   ├── core/              # 核心框架层（Agent 的骨架）
│   │   ├── agent.py       # Agent 基类
│   │   ├── llm.py         # HelloAgentsLLM 统一接口
│   │   ├── message.py     # 消息系统
│   │   ├── config.py      # 配置管理
│   │   └── exceptions.py  # 异常体系
│   ├── agents/            # Agent 实现层（四种范式）
│   │   ├── simple_agent.py
│   │   ├── react_agent.py
│   │   ├── reflection_agent.py
│   │   └── plan_solve_agent.py
│   └── tools/             # 工具系统层
│       ├── base.py        # 工具基类
│       ├── registry.py    # 工具注册机制
│       ├── chain.py       # 工具链管理
│       ├── async_executor.py  # 异步工具执行器
│       └── builtin/       # 内置工具（calculator / search ...）
```

三层分工清晰：**core 定义"Agent 是什么"，agents 实现"四种怎么工作"，tools 扩展"Agent 能做什么"**。

---

## 4. 核心模块实现

### 4.1 HelloAgentsLLM（7.2）

第四章手写的 `llm_client.py` 升级为**多提供商 + 本地模型 + 自动检测**的统一接口：

| 功能 | 说明 |
|---|---|
| **多提供商** | 通过继承 `HelloAgentsLLM` 重写 `__init__`，拦截特定 provider 做特殊处理，其他交给 `super()` |
| **本地模型** | VLLM（高性能推理服务）+ Ollama（更易用），两者都遵循 OpenAI 兼容 API，接入时只改 provider 名称 |
| **自动检测** | `_auto_detect_provider()` 按优先级推断：①特定环境变量（MODELSCOPE_API_KEY 等）→ ②LLM_BASE_URL 域名/端口匹配 → ③API Key 格式分析 |

**继承扩展示例**（添加 ModelScope）：

```python
class MyLLM(HelloAgentsLLM):
    def __init__(self, provider="auto", **kwargs):
        if provider == "modelscope":
            # 拦截 modelscope，自定义凭证和默认值
            self.api_key = os.getenv("MODELSCOPE_API_KEY")
            self.base_url = "https://api-inference.modelscope.cn/v1/"
            self.model = os.getenv("LLM_MODEL_ID") or "Qwen/Qwen2.5-VL-72B-Instruct"
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        else:
            super().__init__(provider=provider, **kwargs)  # 其他交给父类
```

这种"拦截 + 委托"的重写模式**不会修改原始库源码**，升级时不丢定制功能。

### 4.2 Message 消息系统（7.3.1）

用 Pydantic `BaseModel` 统一数据验证：

```python
from pydantic import BaseModel

class Message(BaseModel):
    role: str          # "system" / "user" / "assistant"
    content: str       # 消息正文
    name: str = ""     # 可选，角色名
```

相比 AgentScope 2.x 的 Msg.content 必须是 `list[TextBlock]`，HelloAgents 更简洁——content 就是纯字符串，Agent 的对话历史就是 `List[Message]`。

### 4.3 Config 配置管理（7.3.2）

**单例模式**：整个框架共享一份配置，避免多处初始化不一致。

### 4.4 Agent 基类（7.3.3）

**模板方法模式**：公开接口 `run()` 调用抽象方法 `_execute()`，子类只需要实现"Agent 怎么思考"。

```python
class Agent:
    def run(self, user_input: str) -> str:
        """公开接口：接收输入 → 调用 _execute → 返回结果"""
        # 1. 消息预处理
        # 2. 调用 LLM / 执行工具
        # 3. 返回结果
        return self._execute(user_input)  # 抽象方法，子类实现

    def _execute(self, user_input: str) -> str:
        raise NotImplementedError("子类必须实现")
```

### 4.5 四种 Agent 范式框架化（7.4）

把第四章手写的四个范式，套进 `Agent` 基类的 `_execute` 里：

| Agent | `_execute` 做什么 |
|---|---|
| **SimpleAgent** | 最朴素的对话：构造消息 → `llm.think()` → 返回 |
| **ReActAgent** | 循环：推理 → 调工具 → 把工具结果塞回上下文 → 直到模型说"我答完了" |
| **ReflectionAgent** | 循环：执行 → LLM 给自己打分反思 → 反思意见也喂回上下文 → 直到质量达标 |
| **PlanAndSolveAgent** | 先让 LLM 输出 JSON 计划 → 按步骤逐个执行（可并发、可跳过失败项）→ 汇总成最终答案 |

---

## 5. 工具系统（7.5）

### 5.1 三层架构

| 层 | 组件 | 职责 |
|---|---|---|
| **基类** | `BaseTool` | 统一接口：所有工具都必须实现 `execute(input: str) -> str` |
| **注册** | `ToolRegistry` | 管理所有工具的注册和查找：`registry.register(calculator)` → `registry.execute_tool("calculator", "2+3")` |
| **内置** | `CalculatorTool`, `SearchTool` | 开箱即用的示例工具 |

### 5.2 工具链（ToolChain）

让工具按固定顺序串联执行，步骤之间通过变量模板 `{step_X_result}` 传递数据：

```python
chain = ToolChain("research_and_calculate")
chain.add_step("search", input_template="{input}", output_key="search_result")
chain.add_step("calculator", input_template="根据以下信息计算:{search_result}")
# 执行：chain.execute(registry, input="Python 最新版本号是多少？")
```

### 5.3 异步工具执行器（AsyncToolExecutor）

用 `ThreadPoolExecutor` + `asyncio.gather` 并行跑多个耗时工具：

```python
executor = AsyncToolExecutor(registry)
results = await executor.execute_tools_parallel([
    {"tool_name": "search", "input_data": "Python 编程"},
    {"tool_name": "search", "input_data": "机器学习"},
])
```

---

## 6. 本章的工程价值

第七章的重点不是"写了多少行代码"，而是**把第四章的教学代码升级成了能被后续章节复用的框架**：

| 之前（第四章） | 之后（第七章） |
|---|---|
| `llm_client.py` 是孤立的 | 被 `HelloAgentsLLM` 统一封装，支持多 provider / 本地模型 / 自动检测 |
| `Message` 就是个 dict | 被 Pydantic BaseModel 标准化 |
| Agent 的实现各不相同 | 统一继承 `Agent` 基类，`run()` 公开接口 + `_execute()` 抽象方法 |
| 工具是零散函数 | 有了 `ToolRegistry` + `ToolChain` + `AsyncToolExecutor` |

后续章节的所有功能（第八章 Memory/RAG、第九章上下文工程、第十章协议）**都会基于这个框架继续扩展**，框架的扩展性设计在第 7.5 节专门留了扩展点。

---

## 附录：大白话理解

### 为什么这一章这么重要？

打个比方：前六章是**菜谱和饭店实习**——你学会了怎么做宫保鸡丁（ReActAgent）、红烧肉（ReflectionAgent），也在别人的饭店（AgentScope/LangChain）帮过厨。

第七章是**开一家你自己的饭馆**：
- `HelloAgentsLLM` = 统一采购原料的供应商接口（不管你买的是国产还是进口，都按同一套流程入库）
- `Message` = 标准化的菜单和订单
- `Agent` 基类 = 统一的"做一道菜"流程：接单 → 找配方 → 做菜 → 上桌
- 四种 Agent 范式 = 四种菜系：粤菜师傅（ReAct）、川菜师傅（Reflection）各有各的做法
- `ToolRegistry` = 后厨工具架，刀具、炒锅、烤箱统一摆放
- `ToolChain` = 流水线：切菜 → 调味 → 热锅 → 翻炒 → 装盘，每步之间自动传半成品

**万物皆为工具**的好处是什么？想象一下：你想把"老顾客的偏好记录"加到后厨流程里——在别的饭馆里这可能要在菜单系统、收银系统、后厨系统各改一处。但在你自己的饭馆里，你只需要让它变成一个"偏好查询工具"，就能被任何一个厨师调用。这就是框架统一抽象的威力。

### 那框架和第六章的 AgentScope 到底什么关系？

AgentScope 是**别人的饭馆**，盘子大、流程复杂、出了问题不好改。HelloAgents 是**你自己的小馆子**，菜单精简、流程透明、每样东西你都敢动。

不是谁比谁好——做大规模标准化生产选 AgentScope，想把 Agent 原理学透、想精耕细作做定制化产品，HelloAgents 这条路更扎实。而且框架代码才几百行，翻一遍你就彻底搞懂了 Agent 的所有核心组件。
