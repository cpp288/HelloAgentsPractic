# 第十章　智能体通信协议

> 前面九章造的都是"单体智能体"：自己能想、能调工具、有记忆、会管上下文。但真实系统里，Agent 要接外部服务、要跟别的 Agent 协作、要在大规模网络里被找到。这一章就是给 Agent 修三条"路"：**MCP 通向工具、A2A 通向其他 Agent、ANP 通向整个网络**。
>
> 框架版本：`pip install "hello-agents[protocol]==0.2.2"`，另外需要 Node.js（跑 `npx` 启动社区 MCP 服务器）。

---

## 0. 一句话记住本章

**协议就是 Agent 世界的 TCP/IP**。没有协议时，每接一个服务就要手写一个适配器；有了协议，`agent.add_tool(MCPTool(...))` 一行就能接入别人写好的能力。三种协议分工明确：**MCP 管"用工具"，A2A 管"找同伴"，ANP 管"进市场"**。

---

## 1. 为什么需要通信协议（10.1）

第七章的 ReAct Agent 已经能推理、能调工具，但有三个天花板：

| 瓶颈 | 症状 |
|---|---|
| **工具集成困境** | 每接一个服务（GitHub、数据库、天气）就要手写 `XxxTool(BaseTool)`，重复处理 HTTP、认证、错误 |
| **能力扩展瓶颈** | Agent 能力被写死在预定义工具集里，运行时无法发现新服务 |
| **协作缺失** | 多 Agent 协作只能靠手工编排代码，没有标准接口 |

传统写法 vs 协议写法：

```python
# 传统：每个服务一个适配器，N 份重复代码
agent.add_tool(GitHubTool())
agent.add_tool(DatabaseTool())
agent.add_tool(WeatherTool())

# 协议：接入别人写好的标准服务器
agent.add_tool(MCPTool(server_command=["npx", "-y", "@modelcontextprotocol/server-github"]))
agent.add_tool(MCPTool(server_command=["python", "database_mcp_server.py"]))
```

协议带来四件事：**标准化接口、互操作性、动态发现、可扩展**。

### 三种协议的定位

| 协议 | 提出方 | 设计哲学 | 解决什么 | 类比 |
|---|---|---|---|---|
| **MCP** | Anthropic | 上下文共享 | Agent ↔ 工具/数据源 | USB-C 接口 |
| **A2A** | Google | 对等通信 | Agent ↔ Agent 点对点协作 | 同事之间商量事 |
| **ANP** | 开源社区 | 去中心化服务发现 | 大规模网络中发现/路由/负载均衡 | 招聘网站 + 黄页 |

**选型口诀**：要接外部服务选 MCP；几个 Agent 协作选 A2A；要建大规模生态选 ANP。

### HelloAgents 的三层架构

```
协议实现层   protocols/mcp/     基于 FastMCP 2.0
             protocols/a2a/     基于 Google a2a-sdk（可选依赖）
             protocols/anp/     自研轻量实现（概念模拟）

工具封装层   tools/builtin/protocol_tools.py
             MCPTool / A2ATool / ANPTool —— 全部继承 BaseTool，统一 run()

智能体集成层 Agent 只认 Tool System，不关心底层协议
```

这是第七章"万物皆为工具"理念最漂亮的一次复用：**协议再复杂，对 Agent 来说只是一个 Tool**。

---

## 2. MCP 实战（10.2）

### 2.1 架构：Host / Client / Server

以"我桌面上有哪些文档？"为例：

```
用户提问
  → Claude Desktop（Host，管交互体验）
  → Claude 模型判断需要文件信息
  → MCP Client（管协议通信）
  → 文件系统 MCP Server（管具体功能）
  → 扫描目录返回结果
  → 模型生成回答
```

三层关注点分离：**Host 管体验、Client 管通信、Server 管功能**。开发者只需写 Server。

### 2.2 三大能力

| 能力 | 性质 | 说明 |
|---|---|---|
| **Tools** | 主动 | 执行操作，如 `read_file`、`search_code` |
| **Resources** | 被动 | 提供数据，用 URI 标识，如 `file:///path` |
| **Prompts** | 指导性 | 预定义提示模板，如 `code_review` |

### 2.3 工具选择流程（五步全自动）

1. **工具发现**：Client 调 `list_tools()` 拿工具名、描述、参数 schema
2. **上下文构建**：转成 LLM 能懂的格式塞进系统提示
3. **模型推理**：LLM 根据描述判断"要不要调、调哪个"
4. **工具执行**：Client 经 Server 执行
5. **结果整合**：结果回喂 LLM 生成最终回答

→ 所以**工具描述写得清不清楚，直接决定 Agent 用得好不好**。

### 2.4 MCP vs Function Calling（不是竞争，是互补）

| 维度 | Function Calling | MCP |
|---|---|---|
| 本质 | 模型能力：理解何时调、怎么生成参数 | 工程协议：规定工具如何描述和连接 |
| 跨模型 | 每家格式不同（OpenAI 的 `parameters` vs Claude 的 `input_schema`） | 一套客户端通吃所有支持 MCP 的模型 |
| 工具来源 | 自己实现 | 直接用社区现成服务器 |
| 关系 | "会打电话"的技能 | "全球统一电话标准" |

### 2.5 五种传输方式

MCP 的传输层是无关的，`MCPClient` 支持：

| 传输 | 场景 |
|---|---|
| **Memory** | 单元测试、快速原型（内置演示服务器，不指定参数即用） |
| **Stdio** | 本地开发、Python 脚本服务器、`npx` 社区服务器（最常用） |
| **HTTP** | 生产环境、远程服务、微服务 |
| **SSE** | 实时流式、长连接 |
| **StreamableHTTP** | 双向流式 HTTP |

注意：`MCPTool` 定位是 **Stdio / Memory**；HTTP / SSE / StreamableHTTP 建议直接用底层 `MCPClient`（异步）。

### 2.6 MCPTool 的杀手锏：自动展开

```python
fs_tool = MCPTool(name="fs", server_command=["npx", "-y", "@modelcontextprotocol/server-filesystem", "."])
agent.add_tool(fs_tool)
# 内部：连接服务器 → 发现 14 个工具 → 每个包一层 → 注册为 fs_read_text_file / fs_write_file ...
```

三个要点：

1. **name 会变成前缀**（`name="fs"` → `fs_read_file`），多个服务器必须取不同 name 防冲突
2. **自动类型转换**：Agent 生成 `a=25`（字符串）→ 按 schema 转成 `25.0`（数字）
3. Agent 不用感知 MCP，照常输出 `[TOOL_CALL:fs_read_text_file:path=README.md]`

### 2.7 生态资源

- **Anthropic 官方服务器**：`github.com/modelcontextprotocol/servers`（质量最高）
- **Awesome MCP Servers**：`github.com/punkpeye/awesome-mcp-servers`（社区精选）
- **MCP Servers 网站**：`mcpservers.org`（可搜索筛选）

有意思的组合案例：Playwright 自动网页测试、Obsidian + Perplexity 智能笔记、Jira + GitHub 项目管理、YouTube + Notion + Spotify 内容工作流。

---

## 3. A2A 实战（10.3）

### 3.1 为什么需要（星型拓扑的三个毛病）

传统中央协调器方案：**单点故障**（协调器挂了全挂）、**性能瓶颈**（所有通信过中心）、**扩展困难**（加 Agent 要改中心逻辑）。

A2A 改为**点对点网状拓扑**，两个核心抽象：

| 概念 | 含义 |
|---|---|
| **Task（任务）** | 协作的基本单位，有标准化生命周期 |
| **Artifact（工件）** | 任务的产出物（文档、报告、代码等） |

任务生命周期：创建 → 协商 → 代理 → 执行中 → 完成 / 失败。这使 Agent 能协商、能追踪进度、能处理异常。

请求生命周期四步：**代理发现 → 身份验证 → 发送消息 API → 发送消息流 API**。

### 3.2 A2AServer / A2AClient 用法

```python
# 服务端：用装饰器注册技能
researcher = A2AServer(name="researcher", description="负责搜索和分析资料")
@researcher.skill("research")
def handle_research(text: str) -> str:
    return str({"topic": ..., "findings": ..., "sources": [...]})
researcher.run(host="localhost", port=5000)   # 起服务

# 客户端
client = A2AClient("http://localhost:5000")
resp = client.execute_skill("research", "research AI 在医疗领域的应用")
```

### 3.3 多 Agent 协作实战

教材给了两个完整例子：

**① 研究 → 撰写 → 编辑 流水线**

```
researcher(5000) → writer(5001) → editor(5002)
research(topic) → write(research_data) → edit(article) → 最终稿
```

**② 智能客服系统（更贴近真实业务）**

```
接待员（SimpleAgent）判断问题类型
  ├─ A2ATool → 技术专家（6000）  "你们的 API 如何调用？"
  └─ A2ATool → 销售顾问（6001）  "企业版的价格是多少？"
```

注意这里的设计：**接待员本身是普通 HelloAgents Agent，只是把远端 Agent 当成"工具"挂上来**——A2ATool 就是"另一个 Agent 的遥控器"。

**③ Agent 间协商**：提出 proposal → 对方评估 → 接受或返回 counter_proposal（如"deadline 太紧，我要求 7 天"）。

---

## 4. ANP 实战（10.4）

### 4.1 要解决的三个问题

网络里有成百上千个能力各异的 Agent 时：

- **服务发现**：新任务来了，怎么快速找到能干这活的 Agent？
- **智能路由**：多个都能干，选谁？（看负载、成本）
- **动态扩展**：新加入的 Agent 怎么被别人发现？

### 4.2 三步机制

```
1. 发现与匹配：通过公开发现服务，基于语义/功能描述查询
   （发现服务预先爬取各 Agent 的 .well-known/agent-descriptions 建索引）
2. DID 身份验证：请求方用私钥签名 → 对方解析 DID 取公钥验签
3. 标准化执行：按预定义接口和数据格式交换
```

核心是 **DID（去中心化身份）建立信任 + 标准化描述实现动态发现**，不需要中央协调。

### 4.3 实战：分布式任务调度 + 负载均衡

```python
discovery = ANPDiscovery()

# 注册节点，metadata 里带负载、CPU、内存、GPU
register_service(discovery, service_id="compute_node_0", service_type="compute",
                 endpoint="http://node0:8000",
                 metadata={"load": 0.3, "cpu_cores": 8, "gpu": True})

# 按类型发现 + 选负载最低
nlp_services = discover_service(discovery, service_type="nlp")
best = min(nlp_services, key=lambda s: s.metadata.get("load", 1.0))

# 建网络
network = ANPNetwork(network_id="ai_cluster")
network.add_node(...); network.connect_nodes(...)
```

配合 `ANPTool` 挂到 Agent 上，就能让 LLM 按"任务需要 GPU / 高内存 / 轻量"自己挑节点并解释理由。

---

## 5. 构建自定义 MCP 服务器（10.5）

### 5.1 什么时候要自己写

| 动机 | 说明 |
|---|---|
| 封装业务逻辑 | 企业内部流程包装成标准工具 |
| 访问私有数据 | 内网数据库/API 的安全代理 |
| 性能专项优化 | 高频调用、低延迟要求 |
| 功能定制 | 专有算法、特定硬件 |

### 5.2 最小完整示例（天气 MCP）

```python
weather_server = MCPServer(name="weather-server", description="真实天气查询服务")

def get_weather(city: str) -> str:
    """获取指定城市的当前天气"""
    return json.dumps(get_weather_data(city), ensure_ascii=False, indent=2)

def list_supported_cities() -> str: ...
def get_server_info() -> str: ...

weather_server.add_tool(get_weather)
weather_server.add_tool(list_supported_cities)
weather_server.add_tool(get_server_info)

if __name__ == "__main__":
    weather_server.run()
```

关键点：**函数 docstring 就是工具描述**，Agent 靠它决定何时调用——所以描述要写清楚。

### 5.3 发布到 Smithery

写完后可以发布到 Smithery 市场，别人一行就能用：

```python
weather_tool = MCPTool(server_command=["smithery", "run", "weather-mcp-server"])
agent.add_tool(weather_tool)
```

发布成功后会得到唯一标识（如 `@jjyaoao/weather-mcp-server`）、工具列表、以及各语言/环境的接入配置片段。

---

## 6. 本章总结（10.6）

### 三种协议速查

| 协议 | 定位 | 典型场景 |
|---|---|---|
| **MCP** | 智能体与工具的桥梁 | 增强单个 Agent 的能力 |
| **A2A** | 智能体之间的对话系统 | 小规模团队紧密协作 |
| **ANP** | 智能体互联网的基础设施 | 大规模开放网络 |

### 实战经验

1. 优先用成熟社区 MCP 服务，别重复造轮子，**优先选大公司背书的**
2. 按规模选协议：小团队 A2A，大网络 ANP
3. 三者可组合：MCP 接工具 → A2A 串联专家 Agent → ANP 做发现与负载均衡

---

## 7. 2025 → 2026：协议格局发生了什么（重要补充）

教材写于 2025 年上半年，那时协议还处在"春秋战国"。**一年后的今天，这一层的格局已经基本定型**，而且和教材描述有几处关键出入。

### 7.1 最大变化：A2A 赢了，ACP 并入

| 事件 | 时间 | 影响 |
|---|---|---|
| IBM 的 **ACP 合并进 A2A** | 2025-08 | ACP 仓库归档，教材里"ACP"这一支不用再考虑 |
| **A2A 发布 v1.0**（Linux Foundation 治理） | 2026-03 | 24K stars、5 种 SDK 语言、150+ 组织支持，Google / Microsoft / AWS 全线集成 |
| **AGNTCY** 归档自己的 Agent Connect Protocol | — | 转而专做发现/身份/可观测，不再和 A2A 抢协议层 |

结论：**Agent 与 Agent 之间怎么通信，这件事已经有标准答案了——A2A v1.0**。教材"ANP 与 A2A 并列候选"的描述已经过时。

### 7.2 MCP 本身也大改了（2026-07-28 规范）

这是教材完全不可能覆盖的部分：

| 变化 | 说明 |
|---|---|
| **无状态核心（stateless）** | 摆脱有状态会话，可以直接跑在普通 HTTP 基础设施上水平扩展 |
| **Multi Round-Trip Requests** | 一次请求可多次往返，支持需要中间确认的复杂工具 |
| **基于 header 的路由** | 网关/负载均衡可按 header 分发 |
| **可缓存的 list 结果** | `list_tools` 等可缓存，降低开销 |
| **授权强化** | 更贴近 OAuth 2.1 资源服务器模型 |
| **正式扩展框架** | 官方扩展机制，不再靠"土办法" |
| **MCP Apps 扩展** | 服务器可渲染 UI（把交互界面也变成协议的一部分） |
| **Tasks 扩展** | 支持长时运行任务 |
| **加入 Agentic AI Foundation** | Anthropic 把 MCP 捐给 Linux Foundation 下的新基金会，厂商中立 |
| **MCP Registry 上线** | 官方开放目录 + API，用来发现公开 MCP 服务器 |

**对本章实践的影响**：

- 教材用的 FastMCP 2.0 写法目前仍能跑，但新规范建议关注无状态部署与扩展机制
- 找 MCP 服务器时，除了 Awesome 列表，现在还有官方 **MCP Registry** 可查
- 如果要做生产部署，"每条连接一个有状态子进程"的老模式要逐步换成无状态 + HTTP

### 7.3 协议栈已经分层（比教材的"三件套"更完整）

2026 年的共识是一张五层图，教材只讲了其中两层：

```
┌──────────────────────────────────────────────┐
│ USERS    AG-UI        Agent ↔ 用户/前端界面   │  ← 教材没有
├──────────────────────────────────────────────┤
│ EDITORS  Zed ACP      Agent ↔ 编辑器/IDE      │  ← 教材没有
├──────────────────────────────────────────────┤
│ AGENTS   A2A          Agent ↔ Agent          │  ← 教材有
├──────────────────────────────────────────────┤
│ TOOLS    MCP          Agent ↔ 工具/数据       │  ← 教材有
├──────────────────────────────────────────────┤
│ NETWORK  AGNTCY       发现/身份/可观测/SLIM   │  ← 教材用 ANP 代指
└──────────────────────────────────────────────┘
```

| 层 | 标准 | 一句话 |
|---|---|---|
| Agent↔工具 | **MCP** | 教材讲了，且已大改 |
| Agent↔Agent | **A2A v1.0** | 教材讲了，现在已定局 |
| Agent↔用户 | **AG-UI**（CopilotKit） | 16 种标准事件，走 SSE/WebSocket，做流式聊天和生成式 UI |
| Agent↔编辑器 | **Zed ACP**（Zed + JetBrains） | 号称"Agent 界的 LSP"，JSON-RPC 2.0 |
| 底层基础设施 | **AGNTCY**（Cisco 开源，Linux Foundation） | 去中心化 Agent 目录、可验证身份、可观测 SDK、SLIM 消息 |

**ANP 的现状要泼点冷水**：教材把它当"第三种主流协议"，但到 2026 年中，ANP 1.1 虽发布了身份/发现/消息/**支付**能力，但元协议仍是草案，约 1.3K stars，主要走 W3C Community Group 路线——属于**研究级**，不是生产主流。它解决的问题（去中心化身份、跨组织持久状态）是真实的，但现在实际用 AGNTCY 的更多。

### 7.4 更新后的选型建议

| 你的需求 | 2025 教材答案 | 2026 建议 |
|---|---|---|
| 接外部工具/数据 | MCP | **MCP**（优先官方 Registry / 大厂服务器） |
| 多个 Agent 协作 | A2A | **A2A v1.0**（唯一事实标准，SDK 成熟） |
| 做 Agent 聊天界面 | 没提 | **AG-UI** |
| 让 Agent 进 IDE | 没提 | **Zed ACP** |
| 大规模发现/身份/可观测 | ANP | **AGNTCY**（ANP 仅研究参考） |
| 企业内多 Agent 编排 | 没提 | 框架层：LangGraph 1.0 / CrewAI / Microsoft Agent Framework（AutoGen 已进维护模式） |

### 7.5 一句话总结这一节

教材教你的是**协议的设计思想和三种典型实现**——这部分完全不过时；但**具体选谁、版本到哪、还有哪些层**——这些必须以 2026 年的现状为准。协议层现在已经从"选边站"变成了"分层协作"，这正是好事：你不需要押注，只要在每层用对的协议。

---

## 附录：大白话理解

### 三种协议 = 三种"社交关系"

| 协议 | 大白话 |
|---|---|
| **MCP** | 你和**工具**的关系。就像你手机上装了一堆 App，每个 App 都要一套登录、支付、权限——MCP 就是那个"统一账号 + 统一接口"，装什么插件都长一个样 |
| **A2A** | 你和**同事**的关系。两个平级的同事，谁都能找谁帮忙，不用事事都请示领导（中央协调器） |
| **ANP** | 你和**整个行业**的关系。你要找一个"会做 3D 建模、报价 500 以内、现在有空"的外包，靠的不是挨个打电话，而是一个能搜索、能看评价、能验身份的平台 |

### 为什么 MCP 叫"USB-C"

以前（Function Calling 时代）：每个模型厂商的接口格式都不一样，OpenAI 用 `parameters`，Claude 用 `input_schema`。你写一个 GitHub 搜索工具，换模型就得重写一遍。

MCP 之后：工具服务器按 MCP 标准写一次，任何支持 MCP 的模型/客户端都能用。**就像 USB-C——不管你是苹果、安卓还是笔记本，一根线通吃**。

所以：**Function Calling 是"模型会打电话的技能"，MCP 是"全球统一的电话标准"**。技能和标准不是竞争关系，缺一不可。

### MCPTool 的"自动展开"有多香

你挂上一个文件系统 MCP 服务器，本来它内部有 14 个工具。你不用写 14 个类，框架自动帮你拆成 `fs_read_file`、`fs_write_file`……Agent 看到的就是 14 个普通工具。

类比：**你买了一个瑞士军刀（MCP 服务器），框架自动帮你把每一把小刀、开瓶器、剪刀都摆到桌上（展开成独立工具），你用的时候直接拿对应那件**，不用先"打开军刀"再"选择刀片"。

`name` 参数就是给这套工具贴标签——两个军刀都放桌上，得写"红色军刀的开瓶器"还是"黑色军刀的开瓶器"，否则会拿混。

### A2A 的点对点好在哪

中央协调器就像**公司里所有事都要经过一个项目经理**：他请假，全组停摆（单点故障）；所有人都找他，他忙不过来（性能瓶颈）；新来一个人，得重新给他排工位、教流程（扩展困难）。

点对点就是**同事之间直接对接**：研究员直接把结果给撰写员，撰写员直接给编辑，不用中间过一手。

代价也有：没人统一记账，出问题不好追责——所以 A2A 才定义了 **Task 生命周期**（创建→协商→执行→完成/失败），相当于给每次协作都开了个工单。

### ANP 为什么是"招聘网站"

一个 Agent 网络里有 1000 个 Agent。你要做"中文情感分析"，怎么找？

- 去发现服务搜"nlp / 情感分析"→ 出来 3 个
- 看它们的"简历"（metadata）：负载 0.3 / 报价 0.01 / 版本 1.0
- 选负载最低那个
- 用 DID 验一下身份，确认不是冒充的

这就是**招聘网站 + 背调**的完整流程。ANP 就是这套"人才市场"的规则。

### 2026 年为什么说"协议战争结束了"

2025 年大家都在猜："最后是 A2A 赢还是 ACP 赢还是 ANP 赢？"

2026 年的答案是：**大家不抢了，改成分层合作**——

```
MCP 管工具      （已经赢了这一层）
A2A 管 Agent    （ACP 投降并入，赢了这一层）
AG-UI 管界面    （新冒出来的）
Zed ACP 管编辑器 （新冒出来的）
AGNTCY 管基础设施（新冒出来的）
```

就像互联网：没人问"TCP 和 HTTP 谁赢"，因为它们在不同层、干不同的事。**协议也一样——你不需要选边，只需要在每一层选对的那一个**。

### 本章最值钱的工程经验

**协议 = 可插拔的能力**。回头看第七章那句"万物皆为工具"，到这一章才真正兑现：

```python
agent.add_tool(MCPTool(...))   # 接一个工具生态
agent.add_tool(A2ATool(...))   # 接一个外部 Agent
agent.add_tool(ANPTool(...))   # 接一个服务市场
```

Agent 的代码一行不改，能力边界却能无限扩展。**这就是协议的价值：把"集成"从写代码变成配参数**。
