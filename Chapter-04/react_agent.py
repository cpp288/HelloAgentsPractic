# ReAct 提示词模板 
REACT_PROMPT_TEMPLATE = """ 
请注意，你是⼀个有能⼒调⽤外部⼯具的智能助⼿。

可⽤⼯具如下: 
{tools}

请严格按照以下格式进⾏回应:

Thought: 你的思考过程，⽤于分析问题、拆解任务和规划下⼀步⾏动。 
Action: 你决定采取的⾏动，必须是以下格式之⼀: 
- `{{tool_name}}[{{tool_input}}]`:调⽤⼀个可⽤⼯具。 
- `Finish[最终答案]`:当你认为已经获得最终答案时。 
- 当你收集到⾜够的信息，能够回答⽤户的最终问题时，你必须在Action:字段后使⽤ Finish[最终答案] 来输出最终答案。

现在，请开始解决以下问题: 
Question: {question} 
History: {history}
"""

import re
from typing import Optional

from llm_client import HelloAgentsLLM
from tools import ToolExecutor, search


class ReActAgent:
    def __init__(self, llm_client: HelloAgentsLLM, tool_executor: ToolExecutor, max_steps: int = 5):
        self.llm_client = llm_client
        self.tool_executor = tool_executor
        self.max_steps = max_steps
        self.history = []
    
    def run(self, question: str) -> Optional[str]:
        """
        运行ReAct智能体来回答一个问题。
        """
        self.history = [] # 每次运行时重置历史记录
        current_step = 0

        while current_step < self.max_steps:
            current_step += 1
            print(f"--- 第 {current_step} 步 ---")
            
            # 1. 格式化提示此
            tools_desc = self.tool_executor.getAvailableTools()
            history_str = "\n".join(self.history)
            prompt = REACT_PROMPT_TEMPLATE.format(tools=tools_desc, question=question, history=history_str)

            # 2. 调用LLM进行思考
            messages = [{"role": "user", "content": prompt}]
            response_text = self.llm_client.think(message=messages)

            if not response_text:
                print("❌错误：LLM未能返回有效响应。请检查模型输入是否正确。")
                break

            # 3. 解析LLM的输出
            thought, action = self._parse_output(response_text)
            
            if thought:
                print(f"思考：{thought}")
            
            if not action:
                print("❌警告：LLM未返回有效Action，流程终止。")
                break

            # 4. 执行Action（模型可能用反引号包裹或大小写不一，先归一化）
            action = action.strip().strip("`").strip()

            if action.lower().startswith("finish"):
                final_answer = self._extract_finish_answer(action)
                print(f"🎆 最终答案：{final_answer}")
                return final_answer

            tool_name, tool_input = self._parse_action(action)
            if tool_name is None:
                print("... 处理无效Action格式 ...")
                # 把格式错误写回历史，否则下一轮提示词不变，会重复同样的错误
                self.history.append(f"Action: {action}")
                self.history.append("Observation: ❌ Action 格式无效，请严格使用 `工具名[参数]` 或 `Finish[答案]` 的格式。")
                continue

            print(f"🎬 行动：{tool_name}[{tool_input}]")

            tool_function = self.tool_executor.getTool(tool_name)
            if not tool_function:
                observation = f"❌ 错误：工具 {tool_name} 未注册。"
            else:
                try:
                    observation = tool_function(tool_input)
                except Exception as e:
                    # 工具内部异常不应中断整个 Agent 循环
                    observation = f"❌ 工具 {tool_name} 执行出错: {e}"

            if observation is None:
                observation = "(工具没有返回任何内容)"

            print(f"👀 观察：{observation}")

            # 将本轮的Action和Observation添加到历史记录
            self.history.append(f"Action: {action}")
            self.history.append(f"Observation: {observation}")
        
        # 循环结束
        print("❌ 超过最大步数，流程终止。")
        return None
        
    def _parse_output(self, text: str):
        """
        解析LLM的输出，提取Thought、Action。负责从LLM的完整响应中分离出Thought和Action两个主要部分
        """
        # Thought: 匹配到 Action：或文本末尾
        thought_match = re.search(r"Thought:\s*(.*?)(?:Action:|$)", text, re.DOTALL)
        # Action: 匹配到文本末尾
        action_match = re.search(r"Action:\s*(.*?)$", text, re.DOTALL)
        thought = thought_match.group(1).strip() if thought_match else None
        action = action_match.group(1).strip() if action_match else None
        return thought, action

    def _parse_action(self, action_text: str):
        """
        解析Action字符串，提取工具名称和输入。负责进⼀步解析Action字符串，例如从Search[华为最新⼿机]中提取出⼯具名Search和⼯具输⼊华为最新⼿机。
        """
        # 非贪婪：遇到第一个 ] 就停止，避免把后续多行内容一起吞进来
        match = re.match(r"(\w+)\s*\[(.*?)\]", action_text, re.DOTALL)
        if match:
            return match.group(1), match.group(2).strip()
        return None, None

    def _extract_finish_answer(self, action_text: str) -> str:
        """
        从 Finish[...] 中提取最终答案。
        兼容模型常见的几种不规范写法：多行答案、`Finish: [...]`、缺少右括号、反引号包裹等。
        """
        match = re.search(r"Finish\s*[:：]?\s*\[(.*)\]", action_text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # 兜底：去掉 Finish 前缀和残留括号，直接把剩下的内容当答案，避免抛异常
        return re.sub(r"^Finish\s*[:：]?\s*", "", action_text, flags=re.IGNORECASE).strip("[] \n")

# 测试代码
if __name__ == "__main__":
    try:
        llmClient = HelloAgentsLLM()
        toolExecutor = ToolExecutor()
        # 必须注册工具，否则智能体的可用工具列表为空，无法调用任何工具
        toolExecutor.registerTool(
            "Search",
            "一个网页搜索引擎。当你需要回答关于时事、事实以及在知识库中找不到的信息时，应使用此工具。",
            search,
        )
        reactAgent = ReActAgent(llmClient, toolExecutor)
        
        question = "英伟达最新的GPU型号是什么"
        answer = reactAgent.run(question)
        if answer:
            print(f"✅ 最终答案：{answer}")
        else:
            print("❌ 没有找到有效答案。")
    except Exception as e:
        print(f"❌ 运行ReAct智能体时发生错误: {e}")
        raise e