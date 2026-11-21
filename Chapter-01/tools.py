import requests, os
from tavily import TavilyClient
from dotenv import load_dotenv

# 加载项目根目录下的 .env 环境变量配置
load_dotenv()

def get_weather(city: str) -> str:
    """
    通过调⽤ wttr.in API 查询真实的天⽓信息。
    """
    # API端点，我们请求JSON格式的数据
    url = f"https://wttr.in/{city}?format=j1"

    try:
        # 发起网络请求
        response = requests.get(url)
        # 检查响应是否成功（200）
        response.raise_for_status()
        # 解析返回的JSON数据
        data = response.json()

        # 提取当前天气状况
        current_condition = data["current_condition"][0]
        weather_des = current_condition["weatherDesc"][0]["value"]
        temp_c = current_condition["temp_C"]

        # 格式化成自然语言返回
        return f"当前{city}的天气是{weather_des}，温度是{temp_c}摄氏度。"
    except requests.exceptions.RequestException as e:
        # 处理网络请求异常
        return f"错误:查询天⽓时遇到⽹络问题 - {e}"
    except (KeyError, IndexError) as e:
        # 处理数据解析错误
        return f"错误:解析天⽓数据失败，可能是城市名称⽆效 - {e}"

def get_attraction(city: str, weather: str) -> str:
    """
    根据城市和天气，使用Tavily Search API搜索并返回优化后的景点推荐。
    """
    # 1. 从环境变量中读取API密钥
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "错误:未配置Tavily API密钥，请在环境变量中设置TAVILY_API_KEY"
    
    # 2. 初始化Tavily客户端
    tavily_client = TavilyClient(api_key=api_key)

    # 3. 构建搜索查询
    query = f"'{city}' 在'{weather}'天气下最值得去的旅游景点推荐及理由"

    try:
        # 4. 调用API，include_answer=True会返回一个综合性的回答
        response = tavily_client.search(query, search_depth="basic", include_answer=True)

        # 5. Tavily返回的结果已经非常干净，可以直接使用
        # response["answer"]是一个基于所有搜索结果的综合回答
        if response.get("answer"):
            return response["answer"]
        
        # 如果没有综合性回答，则格式化原始结果
        formatted_results = []
        for result in response.get("results", []):
            formatted_results.append(f"- {result['title']}: {result['content']}")

        if not formatted_results:
            return "抱歉，没有找到相关景点推荐。"

        return "根据搜索，为您找到一下信息：\n" + "\n".join(formatted_results)

    except requests.exceptions.RequestException as e:
        # 处理网络请求异常
        return f"错误:执行Tavily搜索时出现问题 - {e}"

def main():
    print(get_weather("杭州"))
        
if __name__ == "__main__":
    main()