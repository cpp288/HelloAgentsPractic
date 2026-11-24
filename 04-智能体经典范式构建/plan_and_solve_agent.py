PLANNER_PROMPT_TEMPLATE = """
你是⼀个顶级的AI规划专家。你的任务是将⽤户提出的复杂问题分解成⼀个由多个简单步骤组成的⾏动计划。
请确保计划中的每个步骤都是⼀个独⽴的、可执⾏的⼦任务，并且严格按照逻辑顺序排列。
你的输出必须是⼀个Python列表，其中每个元素都是⼀个描述⼦任务的字符串。

问题: {question}

请严格按照以下格式输出你的计划,```python与```作为前后缀是必要的: 
```python
["步骤1", "步骤2", "步骤3", ...]
```
"""

from llm_client import HelloAgentsLLM
import ast
import re

class Planner:
    def __init__(self, llmClient):
        self.llmClient = llmClient
    
    def plan(self, question: str) -> list[str]:
        """
        根据用户问题生成一个行动计划
        """
        prompt = PLANNER_PROMPT_TEMPLATE.format(question=question)
        
        message = [
            {"role": "user", "content": prompt},
        ]
        
        print("--- 正在生成计划 ---")
        response_text = self.llmClient.think(message) or ""
        print(f"✅ 计划生成完成：{response_text}")

        # 解析LLM输出的列表字符串
        try:
            # 找到```python和```之间的内容
            match = re.search(r"```(?:python)?\s*(.*?)```", response_text, re.DOTALL)
            plan_str = match.group(1).strip() if match else response_text.strip()
            plan = ast.literal_eval(plan_str)
            return plan if isinstance(plan, list) else []
        except (ValueError, SyntaxError, IndexError) as e:
            print(f"❌ 解析计划时发生错误: {e}")
            return []
        except Exception as e:
            print(f"❌ 未知错误: {e}")
            return []
        
EXECUTOR_PROMPT_TEMPLATE = """
你是⼀位顶级的AI执⾏专家。你的任务是严格按照给定的计划，⼀步步地解决问题。
你将收到原始问题、完整的计划、以及到⽬前为⽌已经完成的步骤和结果。
请你专注于解决“当前步骤”，并仅输出该步骤的最终答案，不要输出任何额外的解释或对话。

# 原始问题: 
{question}

# 完整计划: 
{plan}

# 历史步骤与结果: 
{history}

# 当前步骤: 
{current_step}

请仅输出针对“当前步骤”的回答: 
"""

class Executor:
    def __init__(self, llmClient):
        self.llmClient = llmClient
    
    def execute(self, question: str, plan: list[str]) -> str:
        """
        根据计划，逐步执行并解决问题
        """
        history = "" # 用户存储历史步骤和结果的字符串

        print("--- 正在执行计划 ---")

        for i, step in enumerate(plan):
            print(f"\n-> 正在执行步骤 {i+1}/{len(plan)} : {step}")

            prompt = EXECUTOR_PROMPT_TEMPLATE.format(
                question=question,
                plan=plan,
                history=history if history else "无",
                current_step=step,
            )

            message = [
                {"role": "user", "content": prompt},
            ]

            response_text = self.llmClient.think(message) or ""
            
            # 更新历史记录，为下一步做准备
            history += f"步骤{i+1}：{step}\n结果：{response_text}\n\n"

            print(f"✅ 步骤 {i+1} 执行完成：{response_text}")
            
        # 循环结束后，最后一步的响应就是最终答案
        final_answer = response_text
        return final_answer
            
class PlanAndSolveAgent:
    def __init__(self, llmClient):
        self.llmClient = llmClient
        self.planner = Planner(llmClient)
        self.executor = Executor(llmClient)
    
    def run(self, question: str):
        """
        运行智能体的完整流程：先规划，后执行
        """
        print(f"\n--- 开始处理问题 ---\n问题： {question}")

        # 1. 调用规划器生成计划
        plan = self.planner.plan(question)
        
        if not plan:
            print("\n--- ❌ 任务终止 ---\n无法生成有效的行动计划。")
            return
        
        # 2. 调用执行器执行计划
        final_answer = self.executor.execute(question, plan)
        
        print(f"\n--- 任务完成 ---\n最终答案：{final_answer}")

# 测试代码
if __name__ == "__main__":
    try:
        llmClient = HelloAgentsLLM()
        agent = PlanAndSolveAgent(llmClient)
        
        question = "⼀个⽔果店周⼀卖出了 15 个苹果。周⼆卖出的苹果数量是周⼀的两倍。周三卖出的数量⽐周⼆少了 5 个。请问这三天总共卖出了多少个苹果？"
        agent.run(question)
    except Exception as e:
        print(f"❌ 运行智能体时发生错误: {e}")
        raise e