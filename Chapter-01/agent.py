import re,tools
from dotenv import load_dotenv

AGENT_SYSTEM_PROMPT =  """ 你是⼀个智能旅⾏助⼿。你的任务是分析⽤户的请求，并使⽤可⽤⼯具⼀步步地解决问题。
# 可⽤⼯具: - `get_weather(city: str)`: 查询指定城市的实时天⽓。 - `get_attraction(city: str, weather: str)`: 根据城市和天⽓搜索推荐的旅游景点。
# 输出格式要求: 你的每次回复必须严格遵循以下格式，包含⼀对Thought和Action：
Thought: [你的思考过程和下⼀步计划] Action: [你要执⾏的具体⾏动]
Action的格式必须是以下之⼀： 1. 调⽤⼯具：function_name(arg_name="arg_value") 2. 结束任务：Finish[最终答案]
# 重要提示: - 每次只输出⼀对Thought-Action - Action必须在同⼀⾏，不要换⾏ - 当收集到⾜够信息可以回答⽤户问题时，必须使⽤ Action: Finish[最终答案] 格式结束
请开始吧！ """

load_dotenv()

available_tools = {
    "get_weather": tools.get_weather,
    "get_attraction" : tools.get_attraction,
    }

# 1. 配置LLM客户端

llm_client = OpenAICompatibleClient(
    model=os.getenv("LLM_MODEL"),
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL")
)

# 2. 初始化
user_prompt = "你好，请帮我查询一下今天杭州的天气，然后根据天气推荐一个合适的旅游景点。"
prompt_history = [f"用户请求：{user_prompt}"]

print(f"用户输入：{user_prompt}\n" + "="*40)

# 3. 运行主循环
for i in range(5): # 设置最大循环次数
    print(f"--- 循环第{i+1}轮对话 ---\n")

    # 3.1 构建Prompt
    full_prompt = "\n".join(prompt_history)

    # 3.2 调用LLM进行思考
    llm_output = llm_client.generate(full_prompt, system_prompt=AGENT_SYSTEM_PROMPT)
    # 模型可能会输出多余的Thought-Action，需要截断
    match = re.search(r'Thought:.*?Action:.*?)(?=\n\s* (?:Thought:|Action:|Observation:)|\Z)', llm_output, re.DOTALL)
    if match:
        truncated = match.group(1).strip()
        if truncated != llm_output.strip():
            llm_output = truncated
            print("已截断多余的 Thought-Action 对")
    print(f"模型输出：\n{llm_output}\n")
    prompt_history.append(llm_output)

    # 3.3 解析并执行行动
    action_match = re.search(r"Action: (.*)", llm_output, re.DOTALL)
    if not action_match:
        observation = "错误: 未能解析到 Action 字段。请确保你的回复严格遵循 'Thought: ... Action: ...' 的格式。"
        observation_str = f"Observation: {observation}"
        print(f"{observation_str}\n" + "="*40)
        prompt_history.append(observation_str)
        continue
    action_str = action_match.group(1).strip()

    if action_str.startswith("Finish"):
        final_answer = re.match(r"Finish\[(.*)\]", action_str).group(1)
        print(f"任务完成，最终答案：{final_answer}")
        break

    tool_name = re.search(r"(\w+)\(", action_str).group(1)
    args_str = re.search(r"\((.*)\)", action_str).group(1)
    kwargs = dict(re.findall(r'(\w+)="([^"]*)"', args_str))

    if tool_name in available_tools:
        observation = available_tools[tool_name](**kwargs)
    else:
        observation = f"错误: 未找到⼯具 {tool_name}。"
    
    # 3.4 记录观察结果
    observation_str = f"Observation: {observation}"
    print(f"{observation_str}\n" + "="*40)
    prompt_history.append(observation_str)
    