from time import sleep

from serpapi import SerpApiClient
from dotenv import load_dotenv
import os
from typing import List, Dict

load_dotenv()

def search(query: str) -> str:
    """
    一个基于SerpApi的网页搜索引擎工具。
    它会智能的解析搜索结果，优先返回直接答案或知识图谱信息。
    """
    print(f"🔍 正在执行 [SerpApi] 网页搜索： {query}")

    try:
        api_key = os.getenv("SERP_API_KEY")
        if not api_key:
            return "❌错误：SERP_API_KEY 未在 .env 文件中定义。"
        
        params = {
            "engine": "google",
            "q": query,
            "api_key": api_key,
            "gl": "cn",  # 国家代码
            "hl": "zh-CN", # 语言代码
        }

        client = SerpApiClient(params)
        results = client.get_dict()

        # 智能解析：优先寻找最直接的答案
        if "answer_box_list" in results: # 直接答案框
            return "\n".join(results["answer_box_list"])
        if "answer_box" in results and "answer" in results["answer_box"]: # 直接答案框
            return results["answer_box"]["answer"]
        if "knowledge_graph" in results and "description" in results["knowledge_graph"]: # 知识图谱
            return results["knowledge_graph"]["description"]
        if "organic_results" in results and results["organic_results"]: # 有机结果
            # 如果没有直接答案，提取前3个有机结果的标题和摘要
            snippets = [
                f"[{i+1}] {res.get('title', '')} \n{res.get('snippet', '')}"
                for i, res in enumerate(results["organic_results"][:3])
            ]
            return "\n\n".join(snippets)
    except Exception as e:
        return f"❌ 调用 SerpApi 时发生错误: {e}"

class ToolExecutor:
    """
    一个工具执行器，用于调用已注册的工具。
    它会根据模型的指令，选择合适的工具并执行。
    """
    def __init__(self):
        self.tools: Dict[str, Dict[str, Any]] = {}
    
    def registerTool(self, name: str, description: str, func: callable):
        """
        向工具箱中注册一个新工具。
        """
        if name in self.tools:
            print(f"⚠️ 警告：工具 {name} 已存在，将被覆盖。")
        
        self.tools[name] = {
            "description": description,
            "func": func,
        }

        print(f"✅ 工具 {name} 已成功注册。")
    
    def getTool(self, name: str) -> callable:
        """
        获取已注册工具的执行函数。
        """
        return self.tools.get(name, {}).get("func")
    
    def getAvailableTools(self) -> str:
        """
        获取所有已注册工具的格式化描述字符串。
        """
        return "\n".join([f"- {name}: {info['description']}" for name, info in self.tools.items()])

# 测试代码
if __name__ == "__main__":
    toolExecutor = ToolExecutor()
    toolExecutor.registerTool("search", "⼀个⽹⻚搜索引擎。当你需要回答关于时事、事实以及在你的知识库中找不到的信息时，应使⽤此⼯具。", search)

    print("\n--- 可用工具 ---")
    print(toolExecutor.getAvailableTools())

    print("\n--- 执行Action：Search['英伟达最新的GPU型号是什么'] ---")
    tool_name = "search"
    tool_input = "英伟达最新的GPU型号是什么"

    tool_function = toolExecutor.getTool(tool_name)
    if tool_function:
        observation = tool_function(tool_input)
        print("--- 观察（Observation）---")
        print(observation)
    else:
        print(f"❌ 错误：工具 {tool_name} 未注册。")
