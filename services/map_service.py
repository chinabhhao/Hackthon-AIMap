# ============================================================
# services/map_service.py - 地图与天气服务
# 功能：地理编码（地名→经纬度）& 天气查询
# 使用高德后端服务 Key (AMAP_SERVER_KEY) 调用 REST API
# ============================================================

import os
import sys
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import AMAP_SERVER_KEY, is_key_configured

# 禁用系统代理，直连高德 API（避免 ProxyError 导致请求失败）
_NO_PROXY = {"http": None, "https": None}


# ============================================================
#  天气查询
# ============================================================

def get_weather(location: str) -> dict:
    """
    查询指定地点的天气信息（使用高德天气 API + 后端服务 Key）

    参数:
        location: 城市名或 adcode（如 "杭州" 或 "330100"）

    返回:
        {
            "city": "杭州",
            "weather": "晴",
            "temperature": "25",
            "wind": "东南风 2级",
            "humidity": "60%"
        }
    """
    # ========== 真实 API 调用 ==========
    if is_key_configured("AMAP_SERVER_KEY"):
        try:
            # 先通过地理编码获取 adcode
            adcode = _get_adcode(location)

            # 调用高德天气 API
            weather_url = "https://restapi.amap.com/v3/weather/weatherInfo"
            resp = requests.get(weather_url, params={
                "key": AMAP_SERVER_KEY,
                "city": adcode,
                "extensions": "base",
            }, timeout=10, proxies=_NO_PROXY).json()

            if resp.get("lives"):
                live = resp["lives"][0]
                return {
                    "city": live.get("city", location),
                    "weather": live.get("weather", "未知"),
                    "temperature": live.get("temperature", "--"),
                    "wind": f"{live.get('winddirection', '')} {live.get('windpower', '')}级",
                    "humidity": f"{live.get('humidity', '--')}%",
                }
        except Exception as e:
            print(f"[map_service] 天气 API 调用异常: {e}，回退模拟数据")

    # ---------- 模拟数据（API 调用失败时使用） ----------
    return {
        "city": location or "杭州",
        "weather": "晴",
        "temperature": "25",
        "wind": "东南风 2级",
        "humidity": "60%",
    }


# ============================================================
#  地理编码：地名 → 经纬度
# ============================================================

# 杭州西湖周边的预设坐标（缓存 + 兜底）
_PRESET_LOCATIONS = {
    "断桥": {"lng": 120.15193, "lat": 30.25959, "adcode": "330106"},
    "白堤": {"lng": 120.14880, "lat": 30.25720, "adcode": "330106"},
    "岳庙": {"lng": 120.13990, "lat": 30.25780, "adcode": "330106"},
    "曲院风荷": {"lng": 120.13450, "lat": 30.25350, "adcode": "330106"},
    "西湖": {"lng": 120.14870, "lat": 30.24240, "adcode": "330106"},
    "雷峰塔": {"lng": 120.14920, "lat": 30.23150, "adcode": "330106"},
    "苏堤": {"lng": 120.13910, "lat": 30.23500, "adcode": "330106"},
    "灵隐寺": {"lng": 120.10270, "lat": 30.26540, "adcode": "330106"},
    "杭州": {"lng": 120.15507, "lat": 30.27408, "adcode": "330100"},
    "北山街": {"lng": 120.14500, "lat": 30.25900, "adcode": "330106"},
}


def _get_adcode(location: str) -> str:
    """通过地名获取 adcode（行政区划代码），用于天气查询"""
    # 先查预设缓存
    for name, info in _PRESET_LOCATIONS.items():
        if name in location:
            return info.get("adcode", "330100")

    # 调用高德地理编码 API 获取 adcode
    if is_key_configured("AMAP_SERVER_KEY"):
        try:
            url = "https://restapi.amap.com/v3/geocode/geo"
            resp = requests.get(url, params={
                "key": AMAP_SERVER_KEY,
                "address": location,
            }, timeout=10, proxies=_NO_PROXY).json()
            if resp.get("geocodes"):
                return resp["geocodes"][0].get("adcode", "330100")
        except Exception as e:
            print(f"[map_service] 获取 adcode 异常: {e}")

    # 兜底：杭州
    return "330100"


def geo_to_location(address: str) -> dict:
    """
    将地名转换为经纬度坐标（使用高德地理编码 API + 后端服务 Key）

    参数:
        address: 地名（如 "断桥"、"西湖"）

    返回:
        {"lng": 120.15193, "lat": 30.25959, "formatted_address": "浙江省杭州市西湖区断桥"}
    """
    # 先查预设缓存（快速 + 节省 API 配额）
    for name, info in _PRESET_LOCATIONS.items():
        if name in address:
            # 有真实 Key 时尝试 API 获取更精确结果
            if is_key_configured("AMAP_SERVER_KEY"):
                try:
                    result = _call_geo_api(address)
                    if result:
                        return result
                except Exception:
                    pass
            return {
                "lng": info["lng"],
                "lat": info["lat"],
                "formatted_address": f"浙江省杭州市{name}",
            }

    # 非预设地名：调 API
    if is_key_configured("AMAP_SERVER_KEY"):
        try:
            result = _call_geo_api(address)
            if result:
                return result
        except Exception as e:
            print(f"[map_service] 地理编码 API 异常: {e}，回退模拟数据")

    # 兜底：返回西湖中心坐标
    return {
        "lng": 120.14870,
        "lat": 30.24240,
        "formatted_address": f"浙江省杭州市{address}",
    }


def _call_geo_api(address: str) -> dict | None:
    """调用高德地理编码 API 的内部方法"""
    url = "https://restapi.amap.com/v3/geocode/geo"
    resp = requests.get(url, params={
        "key": AMAP_SERVER_KEY,
        "address": address,
    }, timeout=10, proxies=_NO_PROXY).json()

    if resp.get("geocodes"):
        geo = resp["geocodes"][0]
        location_str = geo.get("location", "")
        if location_str:
            lng, lat = location_str.split(",")
            return {
                "lng": float(lng),
                "lat": float(lat),
                "formatted_address": geo.get("formatted_address", address),
            }
    return None


# ============================================================
#  批量地理编码
# ============================================================

def batch_geo_encode(landmarks: list) -> list:
    """
    批量将地标名转为经纬度

    参数:
        landmarks: 地标名列表 ["断桥", "岳庙", ...]

    返回:
        [{"name": "断桥", "lng": 120.15, "lat": 30.26, "formatted_address": "..."}, ...]
    """
    results = []
    for name in landmarks:
        loc = geo_to_location(name)
        results.append({
            "name": name,
            "lng": loc["lng"],
            "lat": loc["lat"],
            "formatted_address": loc["formatted_address"],
        })
    return results
