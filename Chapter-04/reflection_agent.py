from typing import List, Dict, Any, Optional
from llm_client import HelloAgentsLLM
from reflection_agent_prompt import INITIAL_PROMPT_TEMPLATE, REFLECT_PROMPT_TEMPLATE, REFINE_PROMPT_TEMPLATE

class Memory:
    """
    一个简单的短期记忆模块，用于存储智能体的行动与反思轨迹
    """
    def __init__(self):
        """
        初始化一个空列表来存储所有记录
        """
        self.records: List[Dict[str, Any]] = []
    
    def add_record(self, record_type: str, content: str):
        """
        向记忆中添加一条新记录

        参数：
        - record_type: 记录类型，例如"action"或"reflection"
        - content: 记录的具体内容（例如生成的代码或反思的反馈）
        """
        record = {"type": record_type, "content": content}
        self.records.append(record)
        print(f"✍️ 记忆已更新，新增一条 '{record_type}' 记录。")
        
    def get_trajectory(self) -> str:
        """
        将所有记忆记录格式化为一个连贯的字符串文本，用于构建提示词。
        """
        trajectory_parts = []
        for record in self.records:
            if record["type"] == "execution":
                trajectory_parts.append(f"--- 上一轮尝试（代码） ---\n{record['content']}")
            elif record["type"] == "reflection":
                trajectory_parts.append(f"--- 评审员反馈 ---\n{record['content']}")
                
        return "\n\n".join(trajectory_parts)
    
    def get_last_execution(self) -> Optional[str]:
        """
        获取最近一次执行的代码（例如最新生成的代码）。
        如果不存在，则返回None。
        """
        for record in reversed(self.records):
            if record["type"] == "execution":
                return record["content"]
        return None

class ReflectionAgent:
    def __init__(self, llm_client, max_iterations=3):
        self.llm_client = llm_client
        self.max_iterations = max_iterations
        self.memory = Memory()

    def run(self, task: str):
        print(f"\n--- 开始处理任务 ---\n任务： {task}")

        # 1. 初始执行
        print("\n--- 正在进行初始尝试 ---")
        initial_prompt = INITIAL_PROMPT_TEMPLATE.format(task=task)
        initial_code = self._get_llm_response(initial_prompt)
        self.memory.add_record("execution", initial_code)
        
        # 2. 迭代循环：反思与优化
        for i in range(self.max_iterations):
            print(f"\n--- 第{i+1}/{self.max_iterations} 轮迭代 ---")
            # 反思
            print("\n-> 正在进行反思...")
            last_code = self.memory.get_last_execution()
            reflect_prompt = REFLECT_PROMPT_TEMPLATE.format(task=task, code=last_code)
            feedback = self._get_llm_response(reflect_prompt)
            self.memory.add_record("reflection", feedback)

            # 检查是否需要停止
            if "无需改进" in feedback:
                print("\n✅ 反思任务代码已无需改进，任务完成。")
                break

            # 优化
            print("\n-> 正在进行优化...")
            refine_prompt = REFINE_PROMPT_TEMPLATE.format(task=task, last_code_attempt=last_code, feedback=feedback)
            refined_code = self._get_llm_response(refine_prompt)
            self.memory.add_record("execution", refined_code)
        
        final_code = self.memory.get_last_execution()
        print(f"\n--- ✅ 任务完成 ---\n最终代码：\n```python\n{final_code}\n```")
        return final_code
    
    def _get_llm_response(self, prompt: str) -> str:
        """
        调用LLM客户端获取响应
        """
        message = [{"role": "user", "content": prompt}]
        return self.llm_client.think(message) or ""

# 测试代码
if __name__ == "__main__":
    try:
        llmClient = HelloAgentsLLM()
        agent = ReflectionAgent(llmClient)
        task = "编写⼀个Python函数，找出1到n之间所有的素数 (prime numbers)。"
        result = agent.run(task)
    except Exception as e:
        print(f"❌ 运行智能体时发生错误: {e}")