import requests

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

        
    