"""无 Key 时使用的确定性样例数据，保证全链路可跑通。"""

from __future__ import annotations

from typing import Any

# 城市 -> 景点候选。字段与 Attraction 对齐
_ATTRACTIONS: dict[str, list[dict[str, Any]]] = {
    "北京": [
        {"name": "故宫博物院", "address": "东城区景山前街4号", "visit_duration": "3-4小时",
         "description": "明清两代皇宫，中轴线上的核心建筑群，建议从午门入、神武门出。", "ticket_price": 60,
         "latitude": 39.9163, "longitude": 116.3972},
        {"name": "天安门广场", "address": "东城区东长安街", "visit_duration": "1小时",
         "description": "城市地标广场，清晨可看升旗，周边有人民英雄纪念碑与国家博物馆。", "ticket_price": 0,
         "latitude": 39.9055, "longitude": 116.3976},
        {"name": "颐和园", "address": "海淀区新建宫门路19号", "visit_duration": "3小时",
         "description": "皇家园林代表作，昆明湖与长廊适合慢走，十七孔桥日落出片。", "ticket_price": 30,
         "latitude": 39.9998, "longitude": 116.2755},
        {"name": "天坛公园", "address": "东城区天坛内东里7号", "visit_duration": "2小时",
         "description": "明清皇帝祭天场所，祈年殿与回音壁是必看点位。", "ticket_price": 15,
         "latitude": 39.8822, "longitude": 116.4066},
        {"name": "八达岭长城", "address": "延庆区G6京藏高速58号出口", "visit_duration": "4小时",
         "description": "保存最完好的长城段落，建议早出发避开人流，穿防滑鞋。", "ticket_price": 40,
         "latitude": 40.3565, "longitude": 116.0200},
        {"name": "什刹海", "address": "西城区羊房胡同", "visit_duration": "2小时",
         "description": "胡同与水域交织的老城片区，傍晚沿湖散步、坐三轮车逛胡同。", "ticket_price": 0,
         "latitude": 39.9394, "longitude": 116.3864},
        {"name": "南锣鼓巷", "address": "东城区南锣鼓巷", "visit_duration": "1.5小时",
         "description": "老北京胡同商业街，两侧支巷里的小店比主街更有味道。", "ticket_price": 0,
         "latitude": 39.9372, "longitude": 116.4033},
        {"name": "798艺术区", "address": "朝阳区酒仙桥路4号", "visit_duration": "2小时",
         "description": "由老厂房改造的艺术街区，画廊、展览与咖啡馆密集。", "ticket_price": 0,
         "latitude": 39.9847, "longitude": 116.4953},
        {"name": "中国国家博物馆", "address": "东城区东长安街16号", "visit_duration": "3小时",
         "description": "馆藏从远古到近代，需提前预约，建议只挑两三个专题展厅。", "ticket_price": 0,
         "latitude": 39.9042, "longitude": 116.4012},
        {"name": "北海公园", "address": "西城区文津街1号", "visit_duration": "2小时",
         "description": "最古老的皇家园林之一，白塔与琼华岛是标志景观。", "ticket_price": 10,
         "latitude": 39.9254, "longitude": 116.3892},
        {"name": "恭王府", "address": "西城区前海西街17号", "visit_duration": "2小时",
         "description": "清代王府建筑典范，花园布局精巧，讲解值得听。", "ticket_price": 40,
         "latitude": 39.9378, "longitude": 116.3833},
        {"name": "奥林匹克公园", "address": "朝阳区国家体育场南路1号", "visit_duration": "2小时",
         "description": "鸟巢、水立方夜景灯光好看，适合傍晚到夜间游览。", "ticket_price": 50,
         "latitude": 39.9929, "longitude": 116.3965},
    ],
    "上海": [
        {"name": "外滩", "address": "黄浦区中山东一路", "visit_duration": "1.5小时",
         "description": "万国建筑群与陆家嘴天际线隔江对望，夜景最佳。", "ticket_price": 0,
         "latitude": 31.2397, "longitude": 121.4900},
        {"name": "豫园", "address": "黄浦区福佑路168号", "visit_duration": "2小时",
         "description": "明代江南园林，紧邻城隍庙小吃街。", "ticket_price": 40,
         "latitude": 31.2272, "longitude": 121.4921},
        {"name": "上海博物馆", "address": "黄浦区人民大道201号", "visit_duration": "3小时",
         "description": "青铜器与陶瓷馆藏质量极高，免费需预约。", "ticket_price": 0,
         "latitude": 31.2286, "longitude": 121.4750},
        {"name": "武康路", "address": "徐汇区武康路", "visit_duration": "2小时",
         "description": "梧桐树下的老洋房街区，适合步行与拍照。", "ticket_price": 0,
         "latitude": 31.2088, "longitude": 121.4374},
        {"name": "田子坊", "address": "黄浦区泰康路210弄", "visit_duration": "1.5小时",
         "description": "石库门里弄改造的文创街区，小店密集。", "ticket_price": 0,
         "latitude": 31.2085, "longitude": 121.4689},
        {"name": "陆家嘴", "address": "浦东新区世纪大道", "visit_duration": "2小时",
         "description": "摩天楼群，可登上海中心观光层俯瞰全城。", "ticket_price": 180,
         "latitude": 31.2397, "longitude": 121.5017},
        {"name": "朱家角古镇", "address": "青浦区朱家角镇", "visit_duration": "4小时",
         "description": "江南水乡古镇，放生桥与北大街值得一逛。", "ticket_price": 60,
         "latitude": 31.1088, "longitude": 121.0564},
        {"name": "上海科技馆", "address": "浦东新区世纪大道2000号", "visit_duration": "3小时",
         "description": "适合亲子，展项互动性强。", "ticket_price": 45,
         "latitude": 31.2196, "longitude": 121.5440},
    ],
    "杭州": [
        {"name": "西湖", "address": "西湖区龙井路1号", "visit_duration": "4小时",
         "description": "苏堤、白堤与断桥一线，建议骑行环湖。", "ticket_price": 0,
         "latitude": 30.2447, "longitude": 120.1450},
        {"name": "灵隐寺", "address": "西湖区灵隐路法云弄1号", "visit_duration": "2.5小时",
         "description": "千年古刹与飞来峰石刻，需另购飞来峰门票。", "ticket_price": 75,
         "latitude": 30.2408, "longitude": 120.0994},
        {"name": "西溪湿地", "address": "西湖区天目山路518号", "visit_duration": "4小时",
         "description": "城市湿地，摇橹船穿行芦苇荡，秋季最佳。", "ticket_price": 80,
         "latitude": 30.2707, "longitude": 120.0756},
        {"name": "河坊街", "address": "上城区河坊街", "visit_duration": "1.5小时",
         "description": "老字号与小吃集中的步行街。", "ticket_price": 0,
         "latitude": 30.2419, "longitude": 120.1689},
        {"name": "雷峰塔", "address": "西湖区南山路15号", "visit_duration": "1.5小时",
         "description": "登塔俯瞰西湖全景，黄昏时分光线最好。", "ticket_price": 40,
         "latitude": 30.2317, "longitude": 120.1487},
        {"name": "九溪烟树", "address": "西湖区九溪路", "visit_duration": "2小时",
         "description": "溪谷徒步路线，夏天避暑、秋天看红叶。", "ticket_price": 0,
         "latitude": 30.1967, "longitude": 120.1139},
    ],
    "成都": [
        {"name": "宽窄巷子", "address": "青羊区长顺上街", "visit_duration": "2小时",
         "description": "清代街巷格局，茶馆与川西民居集中。", "ticket_price": 0,
         "latitude": 30.6698, "longitude": 104.0556},
        {"name": "武侯祠", "address": "武侯区武侯祠大街231号", "visit_duration": "2小时",
         "description": "三国文化主题祠庙，与锦里相邻。", "ticket_price": 50,
         "latitude": 30.6428, "longitude": 104.0470},
        {"name": "大熊猫繁育研究基地", "address": "成华区熊猫大道1375号", "visit_duration": "3小时",
         "description": "早晨熊猫最活跃，建议 8 点前入园。", "ticket_price": 55,
         "latitude": 30.7322, "longitude": 104.1444},
        {"name": "锦里古街", "address": "武侯区武侯祠大街231号附1号", "visit_duration": "1.5小时",
         "description": "夜景漂亮，小吃与手工艺品多。", "ticket_price": 0,
         "latitude": 30.6440, "longitude": 104.0457},
        {"name": "人民公园", "address": "青羊区少城路12号", "visit_duration": "1.5小时",
         "description": "鹤鸣茶社喝盖碗茶，体验成都慢生活。", "ticket_price": 0,
         "latitude": 30.6601, "longitude": 104.0645},
        {"name": "都江堰", "address": "都江堰市公园路", "visit_duration": "4小时",
         "description": "两千多年仍在使用的无坝引水工程。", "ticket_price": 80,
         "latitude": 31.0012, "longitude": 103.6155},
    ],
    "西安": [
        {"name": "秦始皇兵马俑", "address": "临潼区秦陵北路", "visit_duration": "3.5小时",
         "description": "一号坑最震撼，建议请讲解或租语音导览。", "ticket_price": 120,
         "latitude": 34.3841, "longitude": 109.2785},
        {"name": "西安城墙", "address": "碑林区南大街2号", "visit_duration": "2小时",
         "description": "可骑行环城，永宁门夜景灯光好看。", "ticket_price": 54,
         "latitude": 34.2583, "longitude": 108.9422},
        {"name": "大雁塔", "address": "雁塔区雁塔路", "visit_duration": "2小时",
         "description": "唐代佛塔，北广场音乐喷泉每晚表演。", "ticket_price": 40,
         "latitude": 34.2186, "longitude": 108.9642},
        {"name": "回民街", "address": "莲湖区北院门", "visit_duration": "1.5小时",
         "description": "清真小吃集中地，建议往小巷深处走。", "ticket_price": 0,
         "latitude": 34.2610, "longitude": 108.9430},
        {"name": "陕西历史博物馆", "address": "雁塔区小寨东路91号", "visit_duration": "3小时",
         "description": "周秦汉唐文物精华，需提前预约。", "ticket_price": 0,
         "latitude": 34.2222, "longitude": 108.9526},
        {"name": "大唐不夜城", "address": "雁塔区慈恩路", "visit_duration": "2小时",
         "description": "夜间步行街，唐风建筑与演艺密集。", "ticket_price": 0,
         "latitude": 34.2192, "longitude": 108.9640},
    ],
}

_HOTELS: dict[str, list[dict[str, Any]]] = {
    "北京": [
        {"name": "全季酒店（王府井店）", "address": "东城区王府井大街", "price_per_night": 420, "rating": "4.6"},
        {"name": "桔子水晶（西单店）", "address": "西城区西单北大街", "price_per_night": 520, "rating": "4.7"},
        {"name": "亚朵酒店（东直门店）", "address": "东城区东直门外大街", "price_per_night": 480, "rating": "4.5"},
        {"name": "北京前门建国饭店", "address": "西城区永安路175号", "price_per_night": 680, "rating": "4.4"},
    ],
    "上海": [
        {"name": "全季酒店（人民广场店）", "address": "黄浦区西藏中路", "price_per_night": 460, "rating": "4.6"},
        {"name": "桔子水晶（外滩店）", "address": "黄浦区四川中路", "price_per_night": 620, "rating": "4.7"},
    ],
    "杭州": [
        {"name": "全季酒店（西湖湖滨店）", "address": "上城区延安路", "price_per_night": 450, "rating": "4.6"},
        {"name": "亚朵酒店（西湖店）", "address": "西湖区曙光路", "price_per_night": 520, "rating": "4.7"},
    ],
    "成都": [
        {"name": "全季酒店（春熙路店）", "address": "锦江区红星路", "price_per_night": 380, "rating": "4.6"},
        {"name": "亚朵酒店（宽窄巷子店）", "address": "青羊区西大街", "price_per_night": 450, "rating": "4.7"},
    ],
    "西安": [
        {"name": "全季酒店（钟楼店）", "address": "碑林区南大街", "price_per_night": 360, "rating": "4.6"},
        {"name": "桔子水晶（大雁塔店）", "address": "雁塔区雁塔路", "price_per_night": 430, "rating": "4.5"},
    ],
}

_WEATHER: dict[str, list[dict[str, Any]]] = {
    "北京": [
        {"day_weather": "晴", "night_weather": "晴", "day_temp": 8, "night_temp": -2, "wind": "西北风 3 级"},
        {"day_weather": "多云", "night_weather": "阴", "day_temp": 7, "night_temp": -1, "wind": "北风 2 级"},
        {"day_weather": "阴", "night_weather": "多云", "day_temp": 6, "night_temp": -3, "wind": "西北风 4 级"},
    ],
    "上海": [
        {"day_weather": "多云", "night_weather": "阴", "day_temp": 12, "night_temp": 5, "wind": "东风 2 级"},
        {"day_weather": "小雨", "night_weather": "阴", "day_temp": 11, "night_temp": 6, "wind": "东南风 3 级"},
    ],
    "杭州": [
        {"day_weather": "晴", "night_weather": "多云", "day_temp": 13, "night_temp": 5, "wind": "东北风 2 级"},
        {"day_weather": "多云", "night_weather": "阴", "day_temp": 12, "night_temp": 6, "wind": "东风 2 级"},
    ],
    "成都": [
        {"day_weather": "阴", "night_weather": "小雨", "day_temp": 10, "night_temp": 6, "wind": "微风"},
        {"day_weather": "多云", "night_weather": "阴", "day_temp": 12, "night_temp": 7, "wind": "微风"},
    ],
    "西安": [
        {"day_weather": "晴", "night_weather": "多云", "day_temp": 9, "night_temp": -1, "wind": "东北风 2 级"},
        {"day_weather": "多云", "night_weather": "阴", "day_temp": 8, "night_temp": 0, "wind": "东风 3 级"},
    ],
}


def _generic_attractions(city: str) -> list[dict[str, Any]]:
    templates = [
        ("城市博物馆", "了解当地历史脉络，建议预留半天。", 0, 30),
        ("老城历史街区", "步行逛老建筑与小店，适合傍晚。", 1.5, 0),
        ("中央公园", "当地人日常休闲的城市绿地。", 2, 0),
        ("滨江/滨河步道", "沿水岸散步，日落时分视野最好。", 1.5, 0),
        ("城市美术馆", "常设展与临展结合，雨天备选。", 2, 40),
        ("本地美食街", "集中体验地方小吃，注意错峰。", 1.5, 0),
        ("观景台", "俯瞰城市天际线，夜间灯光更佳。", 1.5, 60),
        ("大学老校区", "校园建筑与周边书店、咖啡馆氛围好。", 2, 0),
    ]
    return [
        {
            "name": f"{city}{name}",
            "address": f"{city}市中心",
            "visit_duration": f"{duration}小时",
            "description": desc,
            "ticket_price": price,
            "latitude": None,
            "longitude": None,
        }
        for name, desc, duration, price in templates
    ]


def mock_attractions(city: str) -> list[dict[str, Any]]:
    return _ATTRACTIONS.get(city) or _generic_attractions(city)


def mock_hotels(city: str) -> list[dict[str, Any]]:
    return _HOTELS.get(city) or [
        {"name": f"{city}中心商务酒店", "address": f"{city}市中心", "price_per_night": 380, "rating": "4.5"},
        {"name": f"{city}精品民宿", "address": f"{city}老城区", "price_per_night": 320, "rating": "4.6"},
    ]


def mock_weather(city: str, dates: list[str]) -> list[dict[str, Any]]:
    base = _WEATHER.get(city) or [
        {"day_weather": "多云", "night_weather": "阴", "day_temp": 15, "night_temp": 6, "wind": "微风"}
    ]
    return [{**base[i % len(base)], "date": d} for i, d in enumerate(dates)]
