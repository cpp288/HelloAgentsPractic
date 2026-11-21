# Hello-Agents 学习总结

> 本文件用于持续沉淀每一章的学习重点，后续章节的总结直接追加在本文件末尾即可。
> 学习资料：`Hello-Agents-V1.0.3-20260717.pdf`　配套练习代码：`Chapter-XX/`

---

## 第一章　初识智能体

### 1. 什么是智能体（Agent）
能通过**传感器（Sensors）感知环境**，并**自主地通过执行器（Actuators）采取行动（Action）达成目标**的实体。

四个基本要素：**环境 Environment → 感知 Sensors → 决策（自主性 Autonomy）→ 行动 Actuators**，核心是「感知→行动」的闭环。

### 2. 传统智能体的演进（由简单到复杂）
1. **简单反射智能体**：纯「条件-动作」规则，无记忆（如恒温器）
2. **基于模型的反射智能体**：引入内部「世界模型」，有了初级记忆（如隧道中的自动驾驶）
3. **基于目标的智能体**：主动规划达成目标（如 GPS 导航 + A* 搜索）
4. **基于效用的智能体**：多目标权衡，最大化期望效用（如最省时+最省油）
5. **学习型智能体**：通过与环境互动自主学习，代表路径是**强化学习（RL）**，如 AlphaGo Zero

### 3. LLM 驱动的新范式（与传统智能体的本质区别）
| 维度 | 传统智能体 | LLM 智能体 |
|---|---|---|
| 能力来源 | 工程师显式编程 | 海量数据预训练，隐式世界模型 |
| 行为 | 确定、有边界 | 灵活、通用、涌现能力 |
| 输入 | 结构化 | 可直接处理模糊的自然语言指令 |

LLM 智能体的三大能力：**规划与推理（任务分解）→ 工具使用（补全信息缺口）→ 动态修正（根据反馈调整）**。

### 4. 智能体的三种分类维度
- **按内部决策架构**：反射 / 基于模型 / 基于目标 / 基于效用（+ 学习这种元能力）
- **按时间与反应性**：反应式（快但短视）、规划式（深思熟虑但慢）、**混合式**（现代 LLM 智能体 = 「思考-行动-观察」微循环）
- **按知识表示**：符号主义 AI（可解释但脆弱）、亚符号主义/连接主义（强模式识别但黑箱、有幻觉）、**神经符号主义**（融合两者，LLM 智能体是其典型实践，对应卡尼曼「系统1快直觉 / 系统2慢推理」）

### 5. 运行机制：Agent Loop（智能体循环）
**感知 Perception → 思考 Thought → 行动 Action → 观察 Observation → （回到感知）**

- **思考**可细分为：规划（Planning，分解子任务）+ 工具选择（Tool Selection）
- 工程上通过**交互协议**规范 LLM 输出：`Thought: ... Action: function_name(arg="value")`，解析器执行后把结果封装成 `Observation: ...` 反馈给下一轮
- 描述任务环境用 **PEAS 模型**：Performance（性能度量）、Environment、Actuators、Sensors
- LLM 所处的数字环境特点：**部分可观察、随机性、多智能体、序贯且动态**

### 6. 动手实践：智能旅行助手（对应 `Chapter-01/`）
用真实 LLM 从零搭一个能「查天气 → 推荐景点」的 Agent，完整体现 Thought-Action-Observation 循环。代码结构与理论的对应：

| 文件 | 职责 | 对应理论 |
|---|---|---|
| `prompts.py` | 系统提示词 `AGENT_SYSTEM_PROMPT` | 提示工程：定义角色、可用工具、输出格式（Thought/Action/Finish） |
| `tools.py` | `get_weather`（wttr.in）、`get_attraction`（Tavily 搜索） | 执行器 / 外部工具；用环境变量读 API Key |
| `llm_client.py` | `OpenAICompatibleClient`，兼容任意 OpenAI 接口的 LLM | 智能体的「大脑」 |
| `agent.py` | 主循环：拼 Prompt → 调 LLM → 正则解析 Action → 调工具 → 记录 Observation | Agent Loop 的工程实现；`MAX_STEPS` 限制最大循环防死循环 |

关键实现要点：
- 把工具函数放进字典 `available_tools`，按模型输出的函数名动态调用
- 用正则解析模型输出，注意**判空**（模型不按格式输出时不能崩）
- API Key / Base URL / Model ID 走 `.env` + `load_dotenv()`，不硬编码

### 7. 智能体的协作模式与范式
- **作为开发者工具**（增强人类）：GitHub Copilot、Claude Code、Trae、Cursor
- **作为自主协作者**（目标委托）：从「命令-执行」变为「目标-委托」
  - 单智能体自主循环（AgentGPT）
  - 多智能体协作：角色扮演（CAMEL）、组织化工作流（MetaGPT / CrewAI）、灵活对话网络（AutoGen / AgentScope）
  - 高级控制流：LangGraph（状态图，支持循环/分支/回溯/人工介入）

### 8. Workflow vs Agent
- **Workflow**：预先定义的静态流程图，每一步和判断条件都写死（如报销审批），按部就班执行
- **Agent**：以目标为导向，理解环境→推理→规划→动态行动，没有写死的 `if 晴天 then 推荐颐和园`，能根据实时信息自主决策
- 核心理解：**Workflow 是让 AI 按指令执行，Agent 是给 AI 自由度自主达成目标**

### 9. 关键术语速记
- PEAS、Agent Loop、Thought-Action-Observation 协议、Reactivity vs Deliberation、符号主义/连接主义/神经符号主义、系统1/系统2

### 10. 本章练习踩坑记录（Chapter-01）
- 缺包报错：`ModuleNotFoundError: No module named 'dotenv'` → 给运行用的 Python 解释器装 `python-dotenv`（注意本机有多个 Python，要装到实际运行的那个）
- 代码常见坑：模块未导入就使用（`OpenAICompatibleClient`/`os`）、正则括号不匹配导致 `re.error`、`.group(1)` 前没判空、环境变量名前后不一致、顶层代码缺 `if __name__ == "__main__"` 保护
- `__pycache__/` 是字节码缓存，可删、应进 `.gitignore`
