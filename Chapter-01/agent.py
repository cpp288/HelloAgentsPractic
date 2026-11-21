import os
import re

from dotenv import load_dotenv

from llm_client import OpenAICompatibleClient
from prompts import AGENT_SYSTEM_PROMPT
import tools

load_dotenv()

available_tools = {
    "get_weather": tools.get_weather,
    "get_attraction": tools.get_attraction,
}

MAX_STEPS = 5
SEPARATOR = "=" * 40


def main():
    # 1. 配置 LLM 客户端
    llm_client = OpenAICompatibleClient(
        model=os.getenv("LLM_MODEL_ID") or os.getenv("LLM_MODEL"),
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
    )

    # 2. 初始化
    user_prompt = "你好，请帮我查询一下今天杭州的天气，然后根据天气推荐一个合适的旅游景点。"
    prompt_history = [f"用户请求：{user_prompt}"]

    print(f"用户输入：{user_prompt}\n{SEPARATOR}")

    # 3. 运行主循环
    for i in range(MAX_STEPS):
        print(f"--- 循环第{i + 1}轮对话 ---\n")

        # 3.1 构建 Prompt
        full_prompt = "\n".join(prompt_history)

        # 3.2 调用 LLM 进行思考
        llm_output = llm_client.generate(full_prompt, system_prompt=AGENT_SYSTEM_PROMPT)
        # 模型可能输出多对 Thought-Action，截断保留第一对
        match = re.search(
            r"(Thought:.*?Action:.*?)(?=\n\s*(?:Thought:|Action:|Observation:)|\Z)",
            llm_output,
            re.DOTALL,
        )
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
            observation = (
                "错误: 未能解析到 Action 字段。请确保你的回复严格遵循 "
                "'Thought: ... Action: ...' 的格式。"
            )
            observation_str = f"Observation: {observation}"
            print(f"{observation_str}\n{SEPARATOR}")
            prompt_history.append(observation_str)
            continue
        action_str = action_match.group(1).strip()

        if action_str.startswith("Finish"):
            finish_match = re.match(r"Finish\[(.*?)\]", action_str)
            final_answer = finish_match.group(1) if finish_match else action_str
            print(f"任务完成，最终答案：{final_answer}")
            break

        tool_match = re.search(r"(\w+)\(", action_str)
        args_match = re.search(r"\((.*)\)", action_str)
        if not tool_match or not args_match:
            observation = (
                f"错误: 无法解析 Action '{action_str}'，"
                "请使用 function_name(arg=\"value\") 格式。"
            )
        else:
            tool_name = tool_match.group(1)
            args_str = args_match.group(1)
            kwargs = dict(re.findall(r'(\w+)="([^"]*)"', args_str))
            if tool_name in available_tools:
                observation = available_tools[tool_name](**kwargs)
            else:
                observation = f"错误: 未找到工具 {tool_name}。"

        # 3.4 记录观察结果
        observation_str = f"Observation: {observation}"
        print(f"{observation_str}\n{SEPARATOR}")
        prompt_history.append(observation_str)


if __name__ == "__main__":
    main()
