# ============================================================
# app.py - Dy灵动地图 主程序（移动端定宽）
# 主题概念：山有脉，海有流，路有灵
# 运行方式: streamlit run app.py
# ============================================================

import streamlit as st
import streamlit.components.v1 as components
import json
import os
import re
import time
import random
import copy
from datetime import datetime
from urllib.parse import urlparse
import base64
import html as _html

from services.province_detector import detect_province, normalize_province_input

# ---- 导入项目模块 ----
from config import (
    AMAP_WEB_KEY, AMAP_WEB_SECURITY,
    is_key_configured, TEMP_DIR,
)
from services.map_service import get_weather, geo_to_location
from services import local_db
from services import itinerary


# ============================================================
#  色彩体系
#  主色：珊瑚落日粉 #ff6b6b / 渐变 #ff2442→#ff6b6b
#  辅助：海雾蓝 #7eb8da / 山黛青 #4a6741 / 沙滩米 #faf6f0 / 礁石灰 #9ca3af
# ============================================================

# CSS 变量常量（Python 端使用）
CORAL = "#ff6b6b"
CORAL_DARK = "#ff2442"
CORAL_LIGHT = "#ffd1d1"


def _query_params_get() -> dict:
    if hasattr(st, "query_params"):
        try:
            qp = st.query_params
            raw = qp.to_dict() if hasattr(qp, "to_dict") else dict(qp)
            out = {}
            for k, v in raw.items():
                if isinstance(v, list):
                    out[k] = [str(x) for x in v]
                else:
                    out[k] = [str(v)]
            return out
        except Exception:
            return {}
    if hasattr(st, "experimental_get_query_params"):
        try:
            return st.experimental_get_query_params()
        except Exception:
            return {}
    return {}


def _query_params_clear() -> None:
    if hasattr(st, "query_params"):
        try:
            st.query_params.clear()
            return
        except Exception:
            pass
    if hasattr(st, "experimental_set_query_params"):
        try:
            st.experimental_set_query_params()
        except Exception:
            pass


def _query_params_set(**params) -> None:
    if hasattr(st, "query_params"):
        try:
            st.query_params.clear()
            for k, v in params.items():
                if v is None:
                    continue
                st.query_params[k] = v
            return
        except Exception:
            pass
    if hasattr(st, "experimental_set_query_params"):
        try:
            st.experimental_set_query_params(**params)
        except Exception:
            pass
SEA_FOG_BLUE = "#7eb8da"
SEA_FOG_BLUE_LIGHT = "#d4e8f5"
MOUNTAIN_GREEN = "#4a6741"
MOUNTAIN_GREEN_LIGHT = "#d4e8d0"
SAND_BEIGE = "#faf6f0"
SAND_BEIGE_DARK = "#f0ebe3"
REEF_GRAY = "#9ca3af"


# ============================================================
#  知识库数据结构 & Demo 数据
#  结构：{ 城市: { 博主: { spots, food, transport, tips } } }
# ============================================================

def get_demo_knowledge_base():
    """返回 Demo 模式的完整知识库（使用真实数据）"""
    base_path = os.path.join(os.path.dirname(__file__), "picture", "json")
    kb = {}
    
    try:
        for filename in ["hangzhou_daming.json", "hangzhou_yuanzi.json", "chengdu_youzi.json"]:
            filepath = os.path.join(base_path, filename)
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                city = data.get("city", "未知城市")
                blogger = data.get("blogger", "未知博主")
                if city not in kb:
                    kb[city] = {}
                kb[city][blogger] = data
    except Exception as e:
        pass
    
    return kb or {}


def get_demo_catalog():
    """返回 Demo 目录"""
    kb = get_demo_knowledge_base()
    catalog = []
    for city, bloggers in kb.items():
        for blogger, data in bloggers.items():
            catalog.append({
                "city": city,
                "blogger": blogger,
                "label": f"{city} · {data.get('video_title', '')[:15]}{'...' if len(data.get('video_title', '')) > 15 else ''} ({blogger})",
                "transit_city": city
            })
    return catalog


# ============================================================
#  Demo 解析结果（兼容旧接口）
# ============================================================

def get_demo_parse_result(city: str = "杭州西湖", blogger_name: str = "小鹿旅行🦌"):
    """从知识库生成旧格式的解析结果"""
    kb = get_demo_knowledge_base()
    blogger = kb[city][blogger_name]
    points = []
    for i, spot in enumerate(blogger["spots"]):
        points.append({
            "point_id": f"pt_{i+1:03d}",
            "timestamp_start": i * 10,
            "timestamp_end": (i + 1) * 10,
            "coordinates": {"lng": spot["lng"], "lat": spot["lat"]},
            "content": {
                "speech": spot["speech"],
                "landmarks": [spot["name"]],
                "signs": spot.get("signs", []),
                "environment": spot["environment"],
            },
        })
    return {
        "video_id": f"vid_demo_{city}_{blogger_name}",
        "video_metadata": {
            "title": blogger["video_title"],
            "author": blogger_name,
            "duration": blogger["video_duration"],
            "platform": blogger["platform"],
        },
        "points": points,
    }


def get_demo_map_points(city: str = "杭州西湖", blogger_name: str = "小鹿旅行🦌"):
    """从知识库生成地图标注点"""
    kb = get_demo_knowledge_base()
    blogger = kb[city][blogger_name]
    route_image_dir = ""
    for s in blogger.get("spots", []):
        imgs = s.get("images") or []
        if isinstance(imgs, list) and imgs:
            route_image_dir = os.path.dirname(str(imgs[0])).replace("\\", "/")
            break
    points = []
    for spot in blogger["spots"]:
        weather = get_weather(spot["name"])
        points.append({
            "name": spot["name"],
            "lng": spot["lng"],
            "lat": spot["lat"],
            "weather": f"{weather['weather']} {weather['temperature']}°C",
            "recommendation": spot.get("recommendation", ""),
            "speech": spot.get("speech", ""),
            "environment": spot.get("environment", ""),
            "signs": spot.get("signs", []),
            "visit_duration": spot.get("visit_duration", ""),
            "best_time": spot.get("best_time", ""),
            "ticket": spot.get("ticket", ""),
            "tag": spot.get("tag", "城市"),
            "mood": spot.get("mood", ""),
            "images": spot.get("images", []),
            "_route_image_dir": route_image_dir,
            "_city": city,
            "_blogger": blogger_name,
        })
    return points


def get_demo_map_segments(city: str = "杭州西湖", blogger_name: str = "小鹿旅行🦌"):
    """从知识库生成地图路线段（含交通方式，用于路线规划）"""
    kb = get_demo_knowledge_base()
    blogger = kb[city][blogger_name]
    spots = blogger["spots"]
    transport = {f"{t['from']}→{t['to']}": t for t in blogger.get("transport", [])}

    segments = []
    for i in range(len(spots) - 1):
        from_spot = spots[i]
        to_spot = spots[i + 1]
        key = f"{from_spot['name']}→{to_spot['name']}"
        t_info = transport.get(key, {})
        mode = t_info.get("mode", "步行")

        if mode == "步行":
            route_type = "walking"
        elif mode == "公交":
            route_type = "transit"
        elif mode in ("游船", "船"):
            route_type = "driving"
        else:
            route_type = "driving"

        segments.append({
            "from": {"name": from_spot["name"], "lng": from_spot["lng"], "lat": from_spot["lat"]},
            "to": {"name": to_spot["name"], "lng": to_spot["lng"], "lat": to_spot["lat"]},
            "mode": mode,
            "route_type": route_type,
            "desc": t_info.get("desc", ""),
            "duration": t_info.get("duration", ""),
            "cost": t_info.get("cost", ""),
        })
    return segments


# ============================================================
#  山海成就系统
# ============================================================

ACHIEVEMENTS = [
    {"id": "wave_rider", "name": "逐浪者", "desc": "完成 3 次滨水路线", "icon": "🌊", "condition": "water_routes >= 3"},
    {"id": "peak_climber", "name": "登高者", "desc": "打卡 5 个高点/观景点", "icon": "⛰️", "condition": "mountain_checkins >= 5"},
    {"id": "sunset_chaser", "name": "追霞人", "desc": "完成 2 次日落路线", "icon": "🌅", "condition": "sunset_routes >= 2"},
    {"id": "food_collector", "name": "风物收藏家", "desc": "收集 10 个本地美食点", "icon": "🍜", "condition": "food_spots >= 10"},
    {"id": "dual_scene", "name": "山海连游达人", "desc": "一天内完成「登高 + 临水」双场景", "icon": "🏔️", "condition": "dual_scene"},
]

def _calc_achievement_progress(checkins: list, stops: list) -> dict:
    """计算成就进度"""
    water_tags = {"海"}
    mountain_tags = {"山"}
    water_count = sum(1 for s in stops if s.get("tag") in water_tags)
    mountain_checkin_count = sum(1 for c in checkins for s in stops if s["name"] == c and s.get("tag") in mountain_tags)
    food_count = len([s for s in stops if any(kw in s.get("name", "") for kw in ["美食", "小吃", "餐厅"])])
    has_dual = any(s.get("tag") in mountain_tags for s in stops) and any(s.get("tag") in water_tags for s in stops)

    return {
        "water_routes": water_count,
        "mountain_checkins": mountain_checkin_count,
        "sunset_routes": 0,  # 需要时间数据支撑
        "food_spots": food_count,
        "dual_scene": has_dual,
    }

def _get_user_personality(checkins: list, stops: list) -> str:
    """推断用户山海人格"""
    if not checkins:
        return "待探索"
    tags = []
    for c in checkins:
        for s in stops:
            if s["name"] == c and s.get("tag"):
                tags.append(s["tag"])
    if not tags:
        return "自由行者"
    mountain_ratio = tags.count("山") / len(tags)
    water_ratio = tags.count("海") / len(tags)
    if mountain_ratio > 0.5:
        return "⛰️ 山行者"
    elif water_ratio > 0.5:
        return "🌊 浪迹者"
    else:
        return "🏔️‍🌊 山海客"


# ============================================================
#  移动端定宽样式（山海主题）
# ============================================================

def inject_mobile_css():
    """注入手机定宽 + 山海主题 CSS"""
    st.markdown("""
    <style>
        /* ===== 强制手机定宽居中 ===== */
        .stApp {
            max-width: 375px !important;
            margin: 0 auto !important;
            padding: 0 !important;
            background: #F9F7F2 !important;
        }
        .block-container {
            max-width: 375px !important;
            padding-left: 12px !important;
            padding-right: 12px !important;
            padding-top: 0px !important;
            padding-bottom: calc(120px + env(safe-area-inset-bottom, 0px)) !important;
        }

        /* 隐藏 Streamlit 默认元素 */
        header {visibility: hidden !important;}
        footer {visibility: hidden !important;}
        [data-testid="collapsedControl"] {display: none !important;}
        [data-testid="stSidebar"] {display: none !important;}
        
        /* 确保地图组件容器样式正确 */
        [data-testid="stHtml"] iframe {
            border-radius: 48px !important;
            overflow: hidden !important;
        }

        /* ===== 山海主题色 ===== */
        :root {
            --mountain-ink: #25B4E1;
            --mountain-mist: #A8D1D1;
            --sand-beach: #F2E6CE;
            --natural-bg: #F9F7F2;
            --natural-card: #ffffff;
            --natural-text: #2C3E50;
            --natural-muted: #7F8C8D;
            --radius-natural: 24px;
        }

        html, body, [class*="css"]  {
            font-family: Inter, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", system-ui, -apple-system, BlinkMacSystemFont, sans-serif !important;
            color: var(--natural-text) !important;
        }

        .mountain-sea-gradient {
            background: linear-gradient(135deg, var(--mountain-ink) 0%, var(--mountain-mist) 100%) !important;
        }

        .ld-header {
            position: sticky;
            top: 0;
            z-index: 9998;
            margin: 0 -12px;
            padding: calc(6px + env(safe-area-inset-top, 0px)) 14px 10px 14px;
            background: rgba(249, 247, 242, 0.92);
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            border-bottom: 1px solid rgba(168, 209, 209, 0.18);
        }
        .ld-logo {
            width: 34px;
            height: 34px;
            border-radius: 12px;
            background: rgba(255,255,255,0.78);
            border: 1px solid rgba(0,0,0,0.04);
            box-shadow: 0 12px 34px -20px rgba(0,0,0,0.35);
            display: inline-flex;
            align-items: center;
            justify-content: center;
        }
        .ld-header-title {
            font-size: 13px;
            font-weight: 900;
            letter-spacing: -0.2px;
            line-height: 1.1;
            color: var(--natural-text);
        }
        .ld-header-sub {
            display: block;
            margin-top: 2px;
            font-size: 8px;
            font-weight: 800;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            color: rgba(127, 140, 141, 0.9);
        }
        .ld-header-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 10px;
            border-radius: 999px;
            background: rgba(255,255,255,0.65);
            border: 1px solid rgba(0,0,0,0.05);
            box-shadow: 0 6px 20px -14px rgba(0,0,0,0.25);
            font-size: 11px;
            font-weight: 800;
            color: rgba(44,62,80,0.85);
        }

        /* ===== 底部导航栏（小红书风格·固定底部·Streamlit 组件） ===== */
        .shanhai-bottom-nav-anchor {
            height: 0;
            visibility: hidden;
        }
        .shanhai-bottom-nav-anchor + [data-testid="stHorizontalBlock"] {
            position: fixed !important;
            bottom: 18px !important;
            left: 50% !important;
            transform: translateX(-50%) !important;
            width: 351px !important;
            max-width: 100vw !important;
            height: 64px !important;
            background: rgba(255,255,255,0.85) !important;
            backdrop-filter: blur(18px) !important;
            -webkit-backdrop-filter: blur(18px) !important;
            border: 1px solid rgba(255,255,255,0.4) !important;
            z-index: 9999 !important;
            padding: 8px 8px !important;
            margin: 0 !important;
            gap: 0 !important;
            display: flex !important;
            flex-direction: row !important;
            align-items: center !important;
            border-radius: 32px !important;
            box-shadow: 0 15px 60px -15px rgba(0,0,0,0.15) !important;
        }
        .sh-bottom-nav-fixed {
            position: fixed !important;
            bottom: 18px !important;
            left: 50% !important;
            transform: translateX(-50%) !important;
            width: 351px !important;
            max-width: 100vw !important;
            height: 64px !important;
            background: rgba(255,255,255,0.85) !important;
            backdrop-filter: blur(18px) !important;
            -webkit-backdrop-filter: blur(18px) !important;
            border: 1px solid rgba(255,255,255,0.4) !important;
            z-index: 9999 !important;
            padding: 8px 8px !important;
            margin: 0 !important;
            gap: 0 !important;
            display: flex !important;
            flex-direction: row !important;
            align-items: center !important;
            border-radius: 32px !important;
            box-shadow: 0 15px 60px -15px rgba(0,0,0,0.15) !important;
        }
        .shanhai-bottom-nav-anchor + [data-testid="stHorizontalBlock"] > div {
            gap: 0 !important;
            flex: 1 1 0 !important;
            min-width: 0 !important;
        }
        .sh-bottom-nav-fixed > div {
            gap: 0 !important;
            flex: 1 1 0 !important;
            min-width: 0 !important;
        }
        .shanhai-bottom-nav-anchor + [data-testid="stHorizontalBlock"] [data-testid="column"],
        .sh-bottom-nav-fixed [data-testid="column"] {
            flex: 1 1 0 !important;
            width: 25% !important;
            min-width: 0 !important;
        }
        .shanhai-bottom-nav-anchor + [data-testid="stHorizontalBlock"] button {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 6px 0 !important;
            margin: 0 !important;
            border-radius: 18px !important;
            line-height: 1.3 !important;
            font-size: 10px !important;
            color: var(--natural-muted) !important;
            font-weight: 900 !important;
            white-space: pre-line !important;
            width: 100% !important;
            opacity: 0.65 !important;
            transition: transform 0.25s ease, opacity 0.25s ease, color 0.25s ease, background 0.25s ease !important;
        }
        .sh-bottom-nav-fixed button {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 6px 0 !important;
            margin: 0 !important;
            border-radius: 18px !important;
            line-height: 1.3 !important;
            font-size: 10px !important;
            color: var(--natural-muted) !important;
            font-weight: 900 !important;
            white-space: pre-line !important;
            width: 100% !important;
            opacity: 0.65 !important;
            transition: transform 0.25s ease, opacity 0.25s ease, color 0.25s ease, background 0.25s ease !important;
        }
        .shanhai-bottom-nav-anchor + [data-testid="stHorizontalBlock"] button:hover:not(:disabled) {
            background: rgba(37, 180, 225, 0.06) !important;
            opacity: 0.9 !important;
        }
        .sh-bottom-nav-fixed button:hover:not(:disabled) {
            background: rgba(37, 180, 225, 0.06) !important;
            opacity: 0.9 !important;
        }
        .shanhai-bottom-nav-anchor + [data-testid="stHorizontalBlock"] button:disabled {
            opacity: 1 !important;
            color: var(--mountain-ink) !important;
            transform: scale(1.08) !important;
        }
        .sh-bottom-nav-fixed button:disabled {
            opacity: 1 !important;
            color: var(--mountain-ink) !important;
            transform: scale(1.08) !important;
        }


        /* 内容区底部留白已在 .block-container padding-bottom 中处理 */


        /* ===== 山脊线装饰（页面顶部） ===== */
        .mountain-ridge {
            height: 0px;
            background: linear-gradient(90deg,
                transparent 0%,
                #d4e8d0 15%,
                #7eb8da 35%,
                #4a6741 50%,
                #7eb8da 65%,
                #d4e8d0 85%,
                transparent 100%);
            border-radius: 0 0 2px 2px;
            margin: 0;
            opacity: 0.5;
        }

        /* ===== 海浪渐变装饰（页面底部） ===== */
        .sea-wave-footer {
            height: 3px;
            background: linear-gradient(90deg,
                transparent 0%,
                #d4e8f5 20%,
                #7eb8da 50%,
                #d4e8f5 80%,
                transparent 100%);
            border-radius: 2px 2px 0 0;
            margin: 4px -12px 0 -12px;
            opacity: 0.4;
        }

        /* ===== 山海卡片（等高线/波纹纹理） ===== */
        .sh-card {
            background: #fff;
            border-radius: 14px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            overflow: hidden;
            margin: 8px 0;
            position: relative;
        }
        /* 等高线纹理 - 右下角 */
        .sh-card::after {
            content: '';
            position: absolute;
            right: -10px;
            bottom: -10px;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            border: 1px solid rgba(126,184,218,0.12);
            pointer-events: none;
        }
        .sh-card-cover {
            width: 100%;
            height: 120px;
            background: linear-gradient(135deg, #d4e8f5 0%, #d4e8d0 50%, #ffd1d1 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 40px;
            position: relative;
        }
        .sh-card-cover .card-badge {
            position: absolute;
            top: 8px;
            left: 8px;
            background: linear-gradient(135deg, #ff2442, #ff6b6b);
            color: white;
            font-size: 10px;
            padding: 2px 8px;
            border-radius: 10px;
            font-weight: 600;
        }
        .sh-card-body {
            padding: 10px 12px;
        }
        .sh-card-title {
            font-size: 14px;
            font-weight: 600;
            color: #333;
            margin: 0 0 4px 0;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        .sh-card-meta {
            font-size: 11px;
            color: #9ca3af;
        }

        /* ===== 山海标签系统 ===== */
        .tag-mountain {
            display: inline-block;
            background: #d4e8d0;
            color: #4a6741;
            font-size: 10px;
            padding: 1px 6px;
            border-radius: 8px;
            margin: 1px;
            font-weight: 500;
        }
        .tag-sea {
            display: inline-block;
            background: #d4e8f5;
            color: #5b8fb9;
            font-size: 10px;
            padding: 1px 6px;
            border-radius: 8px;
            margin: 1px;
            font-weight: 500;
        }
        .tag-city {
            display: inline-block;
            background: #ffd1d1;
            color: #d44060;
            font-size: 10px;
            padding: 1px 6px;
            border-radius: 8px;
            margin: 1px;
            font-weight: 500;
        }
        .tag-weather {
            display: inline-block;
            background: #f0ebe3;
            color: #8b7355;
            font-size: 10px;
            padding: 1px 6px;
            border-radius: 8px;
            margin: 1px;
        }
        .tag-mood {
            display: inline-block;
            background: #f5f0ff;
            color: #7c5cbf;
            font-size: 10px;
            padding: 1px 6px;
            border-radius: 8px;
            margin: 1px;
        }
        .tag-ticket {
            display: inline-block;
            background: #fff7e6;
            color: #d48806;
            font-size: 10px;
            padding: 1px 6px;
            border-radius: 8px;
            margin: 1px;
        }

        /* ===== 珊瑚粉按钮 ===== */
        .stButton > button {
            border-radius: 24px !important;
            font-weight: 900 !important;
            font-size: 13px !important;
            padding: 8px 0 !important;
            transition: all 0.3s ease !important;
        }
        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, var(--mountain-ink) 0%, var(--mountain-mist) 100%) !important;
            border: none !important;
            box-shadow: 0 18px 40px -18px rgba(0,0,0,0.35) !important;
        }
        .stButton > button[kind="primary"]:hover {
            box-shadow: 0 22px 46px -18px rgba(0,0,0,0.38) !important;
            transform: translateY(-1px);
        }

        /* ===== 潮汐分割线 ===== */
        .tide-divider {
            height: 1px;
            background: linear-gradient(90deg,
                transparent 0%,
                #d4e8f5 20%,
                #7eb8da 50%,
                #d4e8f5 80%,
                transparent 100%);
            margin: 12px 0;
            opacity: 0.6;
        }

        /* ===== Demo 横幅（山海主题） ===== */
        .demo-banner {
            background: linear-gradient(135deg, var(--mountain-ink) 0%, var(--mountain-mist) 100%);
            color: white;
            text-align: center;
            padding: 5px 10px;
            border-radius: 16px;
            font-size: 11px;
            font-weight: 900;
            margin: 4px 0;
        }

        /* ===== 轨迹点列表（山海风格） ===== */
        .point-item {
            background: #fff;
            border-radius: 12px;
            padding: 10px 12px;
            margin: 5px 0;
            box-shadow: 0 1px 4px rgba(0,0,0,0.04);
            border-left: 3px solid #7eb8da;
            position: relative;
        }
        .point-item h4 {
            margin: 0 0 3px 0;
            color: #333;
            font-size: 14px;
        }
        .point-item p {
            margin: 2px 0;
            color: #666;
            font-size: 12px;
        }

        /* ===== 知识库城市卡片 ===== */
        .kb-city-card {
            background: #fff;
            border-radius: 14px;
            padding: 12px;
            margin: 6px 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }
        .kb-city-icon {
            width: 44px;
            height: 44px;
            border-radius: 12px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
            flex-shrink: 0;
        }
        .kb-city-name { font-size: 15px; font-weight: 700; color: #333; }
        .kb-city-sub { font-size: 11px; color: #9ca3af; margin-top: 2px; }

        /* ===== 美食卡片 ===== */
        .food-item {
            background: #fff;
            border-radius: 10px;
            padding: 8px 10px;
            margin: 4px 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            border-left: 3px solid #ff6b6b;
        }
        .food-item h4 { margin: 0 0 2px 0; color: #333; font-size: 13px; }
        .food-item p { margin: 1px 0; color: #666; font-size: 11px; }

        /* ===== 交通卡片 ===== */
        .transport-item {
            background: #fff;
            border-radius: 10px;
            padding: 8px 10px;
            margin: 4px 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            border-left: 3px solid #7eb8da;
        }
        .transport-item h4 { margin: 0 0 2px 0; color: #333; font-size: 13px; }
        .transport-item p { margin: 1px 0; color: #666; font-size: 11px; }

        /* ===== 旅行行程卡片（山海主题） ===== */
        .trip-stop {
            background: #fff;
            border-radius: 12px;
            padding: 10px 12px;
            margin: 5px 0;
            box-shadow: 0 1px 4px rgba(0,0,0,0.04);
            position: relative;
        }
        .trip-stop-number {
            position: absolute;
            top: 10px;
            left: -14px;
            width: 26px;
            height: 26px;
            background: linear-gradient(135deg, #ff2442 0%, #ff6b6b 100%);
            color: white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: 700;
        }
        .trip-stop h4 { margin: 0 0 3px 20px; color: #333; font-size: 14px; }
        .trip-stop p { margin: 1px 0 1px 20px; color: #666; font-size: 11px; }

        /* ===== 个人页头像（山海主题） ===== */
        .profile-header {
            text-align: center;
            padding: 16px 0;
        }
        .profile-avatar {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: linear-gradient(135deg, #d4e8d0 0%, #7eb8da 50%, #ffd1d1 100%);
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            margin-bottom: 6px;
            box-shadow: 0 3px 12px rgba(126,184,218,0.3);
        }
        .profile-name { font-size: 16px; font-weight: 700; color: #333; }
        .profile-bio { font-size: 11px; color: #9ca3af; margin-top: 2px; }

        /* ===== 配置状态条 ===== */
        .config-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 6px 0;
            border-bottom: 0.5px solid #f0f0f0;
        }
        .config-row:last-child { border-bottom: none; }
        .config-name { font-size: 12px; color: #333; }
        .config-status { font-size: 11px; padding: 1px 6px; border-radius: 8px; }
        .config-ok { background: #d4e8d0; color: #4a6741; }
        .config-no { background: #f0f0f0; color: #9ca3af; }

        /* ===== 输入框样式 ===== */
        .stTextInput > div > div > input {
            border-radius: 24px !important;
            border: 2px solid transparent !important;
            font-size: 13px !important;
            padding: 14px 16px !important;
            background: rgba(255,255,255,0.9) !important;
        }
        .stTextInput > div > div > input:focus {
            border-color: rgba(168, 209, 209, 0.6) !important;
            box-shadow: 0 0 0 4px rgba(168,209,209,0.18) !important;
        }

        /* ===== Switch ===== */
        .stToggle > label > div { font-size: 12px !important; }

        /* ===== 旅行方案卡片（山海主题） ===== */
        .trip-card {
            background: #fff;
            border-radius: 14px;
            padding: 12px;
            margin: 6px 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            border-left: 3px solid #7eb8da;
        }
        .trip-card h4 { margin: 0 0 4px 0; color: #333; font-size: 14px; font-weight: 600; }
        .trip-card p { margin: 2px 0; color: #666; font-size: 11px; }

        /* ===== 景点打钩选项卡 ===== */
        .spot-check-item {
            background: #fff;
            border-radius: 12px;
            padding: 8px 10px;
            margin: 4px 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .spot-check-item .spot-name {
            font-size: 13px;
            font-weight: 600;
            color: #333;
        }
        .spot-check-item .spot-info {
            font-size: 10px;
            color: #9ca3af;
        }
        .spot-check-item .spot-ticket {
            font-size: 10px;
            color: #d48806;
            background: #fff7e6;
            padding: 1px 5px;
            border-radius: 6px;
        }

        /* ===== 成就徽章 ===== */
        .badge-card {
            background: #fff;
            border-radius: 12px;
            padding: 10px 12px;
            margin: 4px 0;
            box-shadow: 0 1px 4px rgba(0,0,0,0.04);
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .badge-icon {
            width: 36px;
            height: 36px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            flex-shrink: 0;
        }
        .badge-icon.earned {
            background: linear-gradient(135deg, #ffd1d1, #d4e8f5);
        }
        .badge-icon.locked {
            background: #f0f0f0;
            filter: grayscale(1);
            opacity: 0.5;
        }
        .badge-name { font-size: 13px; font-weight: 600; color: #333; }
        .badge-desc { font-size: 10px; color: #9ca3af; }
        .badge-progress { font-size: 10px; color: #7eb8da; font-weight: 500; }

        /* ===== 解析步骤条 ===== */
        .parse-steps {
            display: flex;
            flex-direction: column;
            gap: 6px;
            margin: 8px 0;
        }
        .parse-step {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 8px;
            border-radius: 10px;
            font-size: 12px;
        }
        .parse-step.active {
            background: #d4e8f5;
            color: #5b8fb9;
            font-weight: 600;
        }
        .parse-step.done {
            background: #d4e8d0;
            color: #4a6741;
        }
        .parse-step.pending {
            background: #f5f5f5;
            color: #bbb;
        }

        /* ===== 潮水进度条 ===== */
        .tide-progress {
            height: 6px;
            border-radius: 3px;
            background: #e8f4f8;
            overflow: hidden;
            margin: 6px 0;
        }
        .tide-progress-bar {
            height: 100%;
            border-radius: 3px;
            background: linear-gradient(90deg, #7eb8da 0%, #4a6741 50%, #ff6b6b 100%);
            transition: width 0.5s ease;
        }

        /* ===== 情绪地图标签 ===== */
        .mood-label {
            display: inline-flex;
            align-items: center;
            gap: 2px;
            font-size: 10px;
            padding: 1px 6px;
            border-radius: 8px;
        }

        /* ===== 山海人格卡片 ===== */
        .personality-card {
            background: linear-gradient(135deg, #d4e8d0 0%, #d4e8f5 50%, #ffd1d1 100%);
            border-radius: 14px;
            padding: 14px;
            text-align: center;
            margin: 8px 0;
        }
        .personality-icon { font-size: 32px; }
        .personality-title { font-size: 16px; font-weight: 700; color: #333; margin-top: 4px; }
        .personality-desc { font-size: 11px; color: #666; margin-top: 2px; }
    </style>
    """, unsafe_allow_html=True)


def inject_swipe_nav_js():
    st.html(
        """
        <script>
        (function () {
          const doc = window.parent.document;
          const win = window.parent;

          try {
            if (!win.__shanhai_demo_load_listener_added) {
              win.__shanhai_demo_load_listener_added = true;
              win.addEventListener('message', function (event) {
                const data = event && event.data ? event.data : null;
                if (!data || data.type !== 'demo_load_done') return;
                try {
                  const btn = findDemoDoneButton();
                  if (btn) {
                    btn.click();
                    return;
                  }
                } catch (e) {}
                try {
                  const url = new URL(win.location.href);
                  url.searchParams.set('demo_load_done', '1');
                  win.location.href = url.toString();
                } catch (e2) {}
              });
            }
          } catch (e) {}

          function findDemoDoneButton() {
            const anchor = doc.getElementById('demo-load-done-anchor');
            if (anchor) {
              let node = anchor;
              for (let i = 0; i < 12 && node; i += 1) {
                node = node.nextElementSibling;
                if (!node) break;
                const btn = node.querySelector ? node.querySelector('button') : null;
                if (btn && (btn.innerText || '').trim() === 'DEMO_LOAD_DONE') return btn;
              }
            }
            const buttons = Array.from(doc.querySelectorAll('button'));
            for (const b of buttons) {
              if ((b.innerText || '').trim() === 'DEMO_LOAD_DONE') return b;
            }
            return null;
          }

          function hideDemoDoneButton() {
            const btn = findDemoDoneButton();
            if (!btn) return;
            const wrap = btn.closest ? btn.closest('[data-testid="stButton"]') : null;
            if (wrap) {
              wrap.style.display = 'none';
              return;
            }
            const p = btn.parentElement;
            if (p) p.style.display = 'none';
            btn.style.display = 'none';
          }

          function findNavBlock() {
            const anchor = doc.getElementById('shanhai-bottom-nav-anchor');
            if (anchor) {
              let node = anchor;
              for (let i = 0; i < 12 && node; i += 1) {
                const next = node.nextElementSibling;
                if (next && next.matches && next.matches('[data-testid="stHorizontalBlock"]')) return next;
                node = node.parentElement;
              }
            }
            const blocks = Array.from(doc.querySelectorAll('[data-testid="stHorizontalBlock"]'));
            const labels = ['寻迹', '地图', '旅行', '我的'];
            for (const block of blocks) {
              const text = block && block.innerText ? block.innerText : '';
              let hit = 0;
              for (const l of labels) {
                if (text.indexOf(l) !== -1) hit += 1;
              }
              if (hit === labels.length) return block;
            }
            return null;
          }

          function pinNavBlock(block) {
            if (!block) return;
            block.classList.add('sh-bottom-nav-fixed');
          }

          function getNavButtons() {
            const block = findNavBlock();
            if (!block) return [];
            return Array.from(block.querySelectorAll('button'));
          }

          function getActiveIndex(buttons) {
            const idx = buttons.findIndex((b) => b.disabled);
            return idx >= 0 ? idx : 0;
          }

          function switchTab(offset) {
            const buttons = getNavButtons();
            if (buttons.length < 2) return;
            const cur = getActiveIndex(buttons);
            const next = (cur + offset + buttons.length) % buttons.length;
            buttons[next].click();
          }

          function tick() {
            pinNavBlock(findNavBlock());
            hideDemoDoneButton();
          }

          let startX = null;
          let startY = null;
          let startAt = null;

          tick();
          setInterval(tick, 500);

          doc.addEventListener(
            'touchstart',
            function (e) {
              if (!e.touches || e.touches.length !== 1) return;
              const target = e.target;
              if (
                target &&
                target.closest &&
                target.closest('input, textarea, [contenteditable="true"], [data-baseweb="input"]')
              ) {
                return;
              }
              startX = e.touches[0].clientX;
              startY = e.touches[0].clientY;
              startAt = Date.now();
            },
            { passive: true }
          );

          doc.addEventListener(
            'touchend',
            function (e) {
              if (startX === null || startY === null || startAt === null) return;
              const dt = Date.now() - startAt;
              const touch = e.changedTouches && e.changedTouches[0];
              const endX = touch ? touch.clientX : null;
              const endY = touch ? touch.clientY : null;
              const dx = endX === null ? 0 : endX - startX;
              const dy = endY === null ? 0 : endY - startY;
              startX = null;
              startY = null;
              startAt = null;

              if (dt > 500) return;
              if (Math.abs(dx) < 70) return;
              if (Math.abs(dy) > 45) return;

              if (dx < 0) switchTab(1);
              else switchTab(-1);
            },
            { passive: true }
          );
        })();
        </script>
        """,
        unsafe_allow_javascript=True,
    )


# ============================================================
#  生成高德地图 HTML（山海主题 · 流动路线）
# ============================================================

def generate_map_html(
    points: list,
    segments: list = None,
    transit_city: str = "杭州",
    immersive_geojson: dict | None = None,
    immersive_sprite_uri: str = "",
) -> str:
    """生成嵌入高德地图的 HTML 代码（375px 定宽移动端·山海主题）"""
    key = AMAP_WEB_KEY
    security_code = AMAP_WEB_SECURITY
    points_json = json.dumps(points, ensure_ascii=False)
    segments_json = json.dumps(segments, ensure_ascii=False) if segments else "[]"
    immersive_json = json.dumps(immersive_geojson, ensure_ascii=False) if immersive_geojson else "null"
    immersive_sprite_json = json.dumps(immersive_sprite_uri, ensure_ascii=False)
    center_lng = points[0]["lng"] if points else 120.14870
    center_lat = points[0]["lat"] if points else 30.24240
    has_segments = segments and len(segments) > 0

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <style>
            html, body {{ margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background: #F9F7F2; font-family: Inter, "PingFang SC", "Microsoft YaHei", system-ui, -apple-system, BlinkMacSystemFont, sans-serif; }}
            #wrap {{ width: 100%; max-width: 375px; height: 100%; border-radius: 48px; overflow: hidden; border: 4px solid #fff; box-shadow: 0 22px 60px -30px rgba(0,0,0,0.35); background: #eaeced; position: relative; margin: 0 auto; }}
            #container {{ width: 100%; height: 100%; }}
            .ld-top-actions {{ position: absolute; top: 12px; right: 12px; z-index: 50; display:flex; gap:10px; }}
            .ld-chip {{ border: 1px solid rgba(255,255,255,0.7); background: rgba(255,255,255,0.86); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); border-radius: 999px; padding: 8px 12px; font-size: 10px; font-weight: 900; color: rgba(44,62,80,0.88); box-shadow: 0 14px 50px -26px rgba(0,0,0,0.35); user-select: none; }}
            .ld-immersive-sub {{ position:absolute; left:14px; right:78px; top:12px; z-index:55; pointer-events:none; display:none; }}
            .ld-immersive-sub.show {{ display:block; }}
            .ld-immersive-sub-inner {{ background: rgba(0,0,0,0.36); border: 1px solid rgba(255,255,255,0.12); border-radius: 18px; padding: 10px 12px; color: #fff; font-size: 12px; line-height: 1.45; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
            .ld-immersive-end {{ position:absolute; left:14px; right:14px; top:50%; transform: translateY(-50%); z-index:70; display:none; background: rgba(255,255,255,0.94); border: 1px solid rgba(255,255,255,0.78); border-radius: 22px; padding: 16px 14px; }}
            .ld-immersive-end.show {{ display:block; }}
            .ld-immersive-end h3 {{ margin:0; font-size:16px; font-weight:900; color:#2C3E50; }}
            .ld-immersive-end p {{ margin:8px 0 0 0; font-size:12px; color:rgba(44,62,80,0.75); line-height:1.45; }}
            .ld-immersive-end .btns {{ margin-top: 12px; display:flex; gap: 10px; }}
            .ld-immersive-end .btn {{ flex:1; border:0; border-radius:16px; padding:10px 12px; font-size:12px; font-weight:900; }}
            .ld-immersive-end .go {{ background:linear-gradient(135deg,#0D8BF2,#0052CC); color:#fff; }}
            .ld-immersive-end .more {{ background:rgba(44,62,80,0.10); color:#2C3E50; }}
            @keyframes ld-bob {{ 0% {{ transform: translateY(0) scale(1.0); }} 50% {{ transform: translateY(-2px) scale(1.03); }} 100% {{ transform: translateY(0) scale(1.0); }} }}
            .ld-sprite {{ width: 54px; height: 54px; background: transparent; box-shadow: none; display:flex; align-items:center; justify-content:center; animation: ld-bob 0.22s ease-in-out infinite; }}
            .ld-sprite img {{ width: 54px; height: 54px; display:block; }}
            .ld-sheet {{ position: absolute; left: 14px; right: 14px; bottom: 14px; z-index: 60; background: rgba(255,255,255,0.94); border: 1px solid rgba(255,255,255,0.75); border-radius: 32px; padding: 16px; box-shadow: 0 26px 70px -30px rgba(0,0,0,0.42); backdrop-filter: blur(22px); -webkit-backdrop-filter: blur(22px); transform: translateY(120%); opacity: 0; transition: transform 260ms ease, opacity 260ms ease; max-height: 42%; overflow: hidden; }}
            .ld-sheet.show {{ transform: translateY(0); opacity: 1; }}
            .ld-sheet-title {{ display:flex; align-items:center; justify-content:space-between; gap:10px; }}
            .ld-sheet-name {{ font-size: 16px; font-weight: 900; color: #2C3E50; letter-spacing: -0.2px; }}
            .ld-sheet-close {{ width: 30px; height: 30px; border-radius: 999px; background: rgba(0,0,0,0.06); color: rgba(0,0,0,0.55); display:flex; align-items:center; justify-content:center; font-size: 16px; font-weight: 900; }}
            .ld-quote {{ margin-top: 10px; background: rgba(249,247,242,0.7); border: 1px solid rgba(0,0,0,0.04); padding: 12px 14px; border-radius: 20px; color: rgba(44,62,80,0.92); font-size: 12px; line-height: 1.55; font-style: italic; max-height: 120px; overflow: auto; -webkit-overflow-scrolling: touch; }}
            .ld-meta {{ margin-top: 10px; display:flex; flex-wrap:wrap; gap:6px; }}
            .ld-pill {{ display:inline-flex; align-items:center; gap:4px; padding: 4px 8px; border-radius: 999px; font-size: 10px; font-weight: 800; background: rgba(37,180,225,0.10); color: rgba(37,180,225,0.95); border: 1px solid rgba(37,180,225,0.10); }}
            .ld-cta {{ margin-top: 12px; width: 100%; border-radius: 20px; padding: 12px 14px; border: 0; color: #fff; font-size: 12px; font-weight: 900; letter-spacing: 0.02em; background: linear-gradient(135deg, #25B4E1 0%, #A8D1D1 100%); box-shadow: 0 18px 40px -22px rgba(0,0,0,0.45); }}
            .ld-cta:active {{ transform: scale(0.98); }}
        </style>
    </head>
    <body>
        <div id="wrap">
          <div id="container"></div>
          <div class="ld-immersive-sub" id="ld-sub"><div class="ld-immersive-sub-inner" id="ld-subtxt"></div></div>
          <div class="ld-top-actions">
            <div class="ld-chip" id="ld-reset">全景复位</div>
            <div class="ld-chip" id="ld-replay" style="display:none;">重播</div>
          </div>
          <div class="ld-immersive-end" id="ld-end">
            <h3 id="ld-end-title"></h3>
            <p id="ld-end-text"></p>
            <div class="btns">
              <button class="btn go" id="ld-go">现在出发</button>
              <button class="btn more" id="ld-more">导入更多素材</button>
            </div>
          </div>
          <div class="ld-sheet" id="ld-sheet">
            <div class="ld-sheet-title">
              <div style="display:flex;align-items:center;gap:10px;">
                <div style="width:6px;height:22px;border-radius:999px;background:rgba(168,209,209,0.85);"></div>
                <div class="ld-sheet-name" id="ld-name"></div>
              </div>
              <div class="ld-sheet-close" id="ld-close">×</div>
            </div>
            <div class="ld-quote" id="ld-quote"></div>
            <div class="ld-meta" id="ld-meta"></div>
            <button class="ld-cta" id="ld-cta">获取博主精华视角</button>
          </div>
        </div>
        <script type="text/javascript">
            window._AMapSecurityConfig = {{ securityJsCode: '{security_code}' }};
        </script>
        <script type="text/javascript" src="https://webapi.amap.com/maps?v=2.0&key={key}&plugin=AMap.Walking,AMap.Driving,AMap.Transfer"></script>
        <script type="text/javascript">
            var map = new AMap.Map('container', {{
                zoom: 13, center: [{center_lng}, {center_lat}],
                mapStyle: 'amap://styles/whitesmoke', resizeEnable: true,
            }});
            var points = {points_json};
            var segments = {segments_json};
            var hasSegments = {str(has_segments).lower()};
            var immersiveGeo = {immersive_json};
            var immersiveSpriteUri = {immersive_sprite_json};
            var immersiveEnabled = immersiveGeo && immersiveGeo.features && immersiveGeo.features.length > 1;

            if (points.length === 0) {{
                var info = new AMap.InfoWindow({{ content: '<div style="padding:10px;font-size:13px;color:#666;">🗺️ 解析视频后生成山海路线</div>', offset: new AMap.Pixel(0, 0) }});
                info.open(map, map.getCenter());
            }} else {{
                var markers = [];
                // 路线颜色 - 山海流动渐变
                var ROUTE_COLOR_DIM = '#A8D1D1';
                var ROUTE_COLOR_HL = '#25B4E1';
                var routeIcons = {{ 'walking': '🚶', 'driving': '🚗', 'transit': '🚌' }};
                var routeLabels = {{ 'walking': '步行', 'driving': '驾车/游船', 'transit': '公交' }};
                var routeCssClass = {{ 'walking': 'walk', 'driving': 'drive', 'transit': 'bus' }};

                var segmentPolylines = [];
                var currentHighlight = [];
                var focusedIndex = -1;
                var suppressMapClickUntil = 0;
                var autoFitLocked = false;
                var focusSeq = 0;

                var sheet = document.getElementById('ld-sheet');
                var sheetName = document.getElementById('ld-name');
                var sheetQuote = document.getElementById('ld-quote');
                var sheetMeta = document.getElementById('ld-meta');
                var btnReset = document.getElementById('ld-reset');
                var btnClose = document.getElementById('ld-close');
                var btnCta = document.getElementById('ld-cta');
                var subWrap = document.getElementById('ld-sub');
                var subText = document.getElementById('ld-subtxt');
                var btnReplay = document.getElementById('ld-replay');
                var endCard = document.getElementById('ld-end');
                var endTitle = document.getElementById('ld-end-title');
                var endText = document.getElementById('ld-end-text');
                var btnGo = document.getElementById('ld-go');
                var btnMore = document.getElementById('ld-more');
                var lastSpeech = '';

                function haversine(aLng, aLat, bLng, bLat) {{
                    var R = 6371000;
                    var toRad = function(d) {{ return d * Math.PI / 180; }};
                    var dLat = toRad(bLat - aLat);
                    var dLng = toRad(bLng - aLng);
                    var lat1 = toRad(aLat);
                    var lat2 = toRad(bLat);
                    var x = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
                    return 2 * R * Math.asin(Math.min(1, Math.sqrt(x)));
                }}

                function speak(text) {{
                    lastSpeech = text || '';
                    try {{
                        if (subWrap) subWrap.classList.add('show');
                        if (subText) subText.textContent = text || '';
                        if (!text) return;
                        if (!('speechSynthesis' in window)) return;
                        window.speechSynthesis.cancel();
                        var u = new SpeechSynthesisUtterance(text);
                        u.rate = 1.0;
                        u.pitch = 1.0;
                        u.lang = 'zh-CN';
                        window.speechSynthesis.speak(u);
                    }} catch (err) {{}}
                }}

                if (btnReplay) {{
                    btnReplay.addEventListener('click', function(e) {{
                        e.stopPropagation();
                        if (lastSpeech) speak(lastSpeech);
                    }});
                }}
                if (btnGo) btnGo.addEventListener('click', function(e) {{ e.stopPropagation(); window.open('https://www.amap.com/', '_blank'); }});
                if (btnMore) btnMore.addEventListener('click', function(e) {{ e.stopPropagation(); location.reload(); }});

                function highlightSegments(idxs) {{
                    for (var i = 0; i < segmentPolylines.length; i++) {{
                        if (segmentPolylines[i]) {{
                            segmentPolylines[i].setOptions({{
                                strokeColor: ROUTE_COLOR_DIM,
                                strokeWeight: 3,
                                strokeOpacity: 0.4,
                                strokeStyle: 'solid',
                            }});
                        }}
                    }}
                    if (!idxs || !idxs.length) {{
                        currentHighlight = [];
                        return;
                    }}
                    for (var j = 0; j < idxs.length; j++) {{
                        var idx = idxs[j];
                        if (idx >= 0 && idx < segmentPolylines.length && segmentPolylines[idx]) {{
                            segmentPolylines[idx].setOptions({{
                                strokeColor: ROUTE_COLOR_HL,
                                strokeWeight: 6,
                                strokeOpacity: 1.0,
                                strokeStyle: 'solid',
                            }});
                        }}
                    }}
                    currentHighlight = idxs.slice(0);
                }}

                function showSheet(p) {{
                    if (!sheet) return;
                    sheetName.textContent = p.name || '';
                    var quote = p.speech || p.recommendation || p.environment || '';
                    quote = quote ? ('“' + quote + '”') : '“在这里按下快门，山海会替你记住风。”';
                    sheetQuote.textContent = quote;
                    var items = [];
                    if (p.weather) items.push('🌤️ ' + p.weather);
                    if (p.visit_duration) items.push('⏱ ' + p.visit_duration);
                    if (p.ticket) items.push('🎫 ' + p.ticket);
                    if (p.best_time) items.push('🕐 ' + p.best_time);
                    sheetMeta.innerHTML = items.map(function(t) {{ return '<span class="ld-pill">' + t + '</span>'; }}).join('');
                    sheet.classList.add('show');
                    sheet.style.transform = 'translateY(0)';
                    sheet.style.opacity = '1';
                }}

                function hideSheet() {{
                    if (!sheet) return;
                    sheet.classList.remove('show');
                    sheet.style.transform = 'translateY(120%)';
                    sheet.style.opacity = '0';
                }}

                function setMarkerActive(idx) {{
                    for (var i = 0; i < markers.length; i++) {{
                        var el = markers[i] && markers[i].getContent && markers[i].getContent();
                        if (el && el.firstChild && el.firstChild.style) {{
                            el.firstChild.style.transform = (i === idx) ? 'scale(1.15)' : 'scale(1.0)';
                            el.firstChild.style.boxShadow = (i === idx) ? '0 16px 40px -18px rgba(0,0,0,0.50)' : '0 10px 28px -18px rgba(0,0,0,0.35)';
                            el.firstChild.style.opacity = (idx >= 0 && i !== idx) ? '0.35' : '1';
                            el.firstChild.style.filter = (idx >= 0 && i !== idx) ? 'blur(0.6px)' : 'none';
                        }}
                    }}
                }}

                function clearFocus() {{
                    focusedIndex = -1;
                    hideSheet();
                    setMarkerActive(-1);
                    highlightSegments([]);
                }}

                function resetView() {{
                    autoFitLocked = false;
                    clearFocus();
                    map.setFitView(markers, false, [40, 40, 40, 40]);
                }}

                function suppressNextMapClicks(ms) {{
                    suppressMapClickUntil = Date.now() + (ms || 700);
                }}

                function focusAt(idx) {{
                    if (idx === focusedIndex) {{
                        clearFocus();
                        return;
                    }}
                    autoFitLocked = true;
                    var token = ++focusSeq;
                    focusedIndex = idx;
                    var p = points[idx];
                    showSheet(p);
                    setMarkerActive(idx);
                    if (hasSegments) {{
                        var ids = [];
                        if (idx > 0) ids.push(idx - 1);
                        if (idx < segments.length) ids.push(idx);
                        highlightSegments(ids);
                    }}
                }}

                btnReset.addEventListener('click', function(e) {{ e.stopPropagation(); resetView(); }});
                btnClose.addEventListener('click', function(e) {{ e.stopPropagation(); autoFitLocked = true; clearFocus(); }});
                btnCta.addEventListener('click', function(e) {{
                    e.stopPropagation();
                    if (focusedIndex < 0) return;
                    var p = points[focusedIndex];
                    var extra = [];
                    if (p.signs && p.signs.length) extra.push('路牌：' + p.signs.join(' / '));
                    if (p.environment) extra.push('环境：' + p.environment);
                    if (p.recommendation) extra.push('推荐：' + p.recommendation);
                    if (!extra.length) return;
                    sheetQuote.textContent = '“' + extra.join(' · ') + '”';
                }});

                points.forEach(function(p, index) {{
                    var pos = new AMap.LngLat(p.lng, p.lat);
                    var mc = document.createElement('div');
                    mc.innerHTML = '<div style="background:linear-gradient(135deg,#25B4E1 0%,#A8D1D1 100%);color:white;border-radius:22px;width:40px;height:40px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:900;box-shadow:0 10px 28px -18px rgba(0,0,0,0.35);border:4px solid rgba(255,255,255,0.95);transition:transform 240ms ease, opacity 240ms ease, filter 240ms ease, box-shadow 240ms ease;cursor:pointer;">' + (index + 1) + '</div>';
                    var marker = new AMap.Marker({{ position: pos, content: mc, offset: new AMap.Pixel(-20, -20), title: p.name, extData: {{ idx: index }} }});

                    function onMarkerActivate(e) {{
                        autoFitLocked = true;
                        suppressNextMapClicks(1500);
                        focusAt(index);
                    }}

                    marker.on('click', onMarkerActivate);
                    marker.on('tap', onMarkerActivate);
                    marker.on('touchend', onMarkerActivate);

                    markers.push(marker); map.add(marker);
                }});

                var segmentNavPaths = [];
                var immersiveStarted = false;

                function toNavCoord(p) {{
                    if (!p) return null;
                    if (typeof p.getLng === 'function' && typeof p.getLat === 'function') {{
                        return {{ lng: p.getLng(), lat: p.getLat() }};
                    }}
                    if (typeof p.lng === 'number' && typeof p.lat === 'number') {{
                        return {{ lng: p.lng, lat: p.lat }};
                    }}
                    return null;
                }}

                function toPathForPolyline(navPath) {{
                    return (navPath || []).map(function(p) {{ return new AMap.LngLat(p.lng, p.lat); }});
                }}

                function drawFallbackLine(segIdx, from, to) {{
                    var nav = [{{ lng: from.getLng(), lat: from.getLat() }}, {{ lng: to.getLng(), lat: to.getLat() }}];
                    segmentNavPaths[segIdx] = nav;
                    var polyline = new AMap.Polyline({{
                        path: toPathForPolyline(nav), strokeColor: ROUTE_COLOR_DIM, strokeWeight: 3,
                        strokeOpacity: 0.4, strokeStyle: 'dashed', lineJoin: 'round', lineCap: 'round',
                    }});
                    map.add(polyline);
                    segmentPolylines[segIdx] = polyline;
                }}

                function maybeStartImmersive() {{
                    if (!immersiveEnabled || immersiveStarted) return;
                    if (hasSegments) {{
                        for (var i0 = 0; i0 < segments.length; i0++) {{
                            if (!segmentNavPaths[i0] || !segmentNavPaths[i0].length) return;
                        }}
                    }}
                    immersiveStarted = true;
                    startImmersive();
                }}

                // 绘制路线（山海渐变色）
                if (hasSegments && segments.length > 0) {{
                    var completedCount = 0;
                    var totalSegments = segments.length;

                    function onRouteComplete() {{
                        completedCount++;
                        if (completedCount >= totalSegments) {{
                            if (!autoFitLocked) map.setFitView(markers, false, [40, 40, 40, 40]);
                            maybeStartImmersive();
                        }}
                    }}

                    segments.forEach(function(seg, idx) {{
                        var origin = new AMap.LngLat(seg.from.lng, seg.from.lat);
                        var dest = new AMap.LngLat(seg.to.lng, seg.to.lat);
                        var routeType = seg.route_type || 'walking';

                        if (routeType === 'walking') {{
                            var walking = new AMap.Walking({{
                                autoFitView: false, hideMarkers: true,
                            }});
                            walking.search(origin, dest, function(status, result) {{
                                walking.clear();
                                if (status === 'complete' && result.routes && result.routes.length > 0) {{
                                    var rawPath = [];
                                    result.routes[0].steps.forEach(function(step) {{ rawPath = rawPath.concat(step.path); }});
                                    var navPath = rawPath.map(toNavCoord).filter(function(x) {{ return x; }});
                                    if (navPath.length >= 2) {{
                                        segmentNavPaths[idx] = navPath;
                                        var polyline = new AMap.Polyline({{
                                            path: toPathForPolyline(navPath), strokeColor: ROUTE_COLOR_DIM, strokeWeight: 3, strokeOpacity: 0.4,
                                            lineJoin: 'round', lineCap: 'round', showDir: true,
                                            borderWeight: 1, borderColor: '#d4e8f5',
                                        }});
                                        map.add(polyline);
                                        segmentPolylines[idx] = polyline;
                                    }} else {{ drawFallbackLine(idx, origin, dest); }}
                                }} else {{ drawFallbackLine(idx, origin, dest); }}
                                onRouteComplete();
                            }});
                        }} else if (routeType === 'transit') {{
                            var transfer = new AMap.Transfer({{
                                autoFitView: false, hideMarkers: true, city: '{transit_city}',
                            }});
                            transfer.search(origin, dest, function(status, result) {{
                                transfer.clear();
                                if (status === 'complete' && result.plans && result.plans.length > 0) {{
                                    var rawPath = [];
                                    result.plans[0].segments.forEach(function(segment) {{
                                        if (segment.transit_mode === 'WALK' && segment.walking && segment.walking.steps) {{
                                            segment.walking.steps.forEach(function(step) {{ rawPath = rawPath.concat(step.path); }});
                                        }} else if (segment.transit_path && segment.transit_path.path) {{
                                            rawPath = rawPath.concat(segment.transit_path.path);
                                        }}
                                    }});
                                    var navPath = rawPath.map(toNavCoord).filter(function(x) {{ return x; }});
                                    if (navPath.length >= 2) {{
                                        segmentNavPaths[idx] = navPath;
                                        var polyline = new AMap.Polyline({{
                                            path: toPathForPolyline(navPath), strokeColor: ROUTE_COLOR_DIM, strokeWeight: 3, strokeOpacity: 0.4,
                                            lineJoin: 'round', lineCap: 'round', showDir: true,
                                            borderWeight: 1, borderColor: '#d4e8f5',
                                        }});
                                        map.add(polyline);
                                        segmentPolylines[idx] = polyline;
                                    }} else {{ drawFallbackLine(idx, origin, dest); }}
                                }} else {{ drawFallbackLine(idx, origin, dest); }}
                                onRouteComplete();
                            }});
                        }} else {{
                            var driving = new AMap.Driving({{
                                autoFitView: false, hideMarkers: true,
                            }});
                            driving.search(origin, dest, function(status, result) {{
                                driving.clear();
                                if (status === 'complete' && result.routes && result.routes.length > 0) {{
                                    var rawPath = [];
                                    result.routes[0].steps.forEach(function(step) {{ rawPath = rawPath.concat(step.path); }});
                                    var navPath = rawPath.map(toNavCoord).filter(function(x) {{ return x; }});
                                    if (navPath.length >= 2) {{
                                        segmentNavPaths[idx] = navPath;
                                        var polyline = new AMap.Polyline({{
                                            path: toPathForPolyline(navPath), strokeColor: ROUTE_COLOR_DIM, strokeWeight: 3, strokeOpacity: 0.4,
                                            lineJoin: 'round', lineCap: 'round', showDir: true,
                                            borderWeight: 1, borderColor: '#d4e8f5',
                                        }});
                                        map.add(polyline);
                                        segmentPolylines[idx] = polyline;
                                    }} else {{ drawFallbackLine(idx, origin, dest); }}
                                }} else {{ drawFallbackLine(idx, origin, dest); }}
                                onRouteComplete();
                            }});
                        }}
                    }});

                    setTimeout(function() {{ if (!autoFitLocked) map.setFitView(markers, false, [40, 40, 40, 40]); }}, 3000);
                }} else {{
                    var navPath = points.map(function(p) {{ return {{ lng: p.lng, lat: p.lat }}; }});
                    if (navPath.length >= 2) {{
                        map.add(new AMap.Polyline({{
                            path: toPathForPolyline(navPath), strokeColor: '#A8D1D1', strokeWeight: 3, strokeOpacity: 0.4,
                            lineJoin: 'round', lineCap: 'round', showDir: true, borderWeight: 1, borderColor: '#d4e8f5',
                        }}));
                    }}
                    if (!autoFitLocked) map.setFitView(markers, false, [40, 40, 40, 40]);
                    maybeStartImmersive();
                }}

                function startImmersive() {{
                    if (!immersiveEnabled) return;
                    if (btnReplay) btnReplay.style.display = 'inline-flex';
                    if (endCard) endCard.classList.remove('show');
                    if (subWrap) subWrap.classList.add('show');
                    speak('沉浸旅程开始');

                    var pois = immersiveGeo.features.filter(function(f) {{ return f.geometry && f.geometry.type === 'Point'; }});
                    var reached = {{}};
                    var noteByName = {{}};
                    for (var np = 0; np < pois.length; np++) {{
                        var nName = (pois[np].properties && pois[np].properties.name) ? pois[np].properties.name : '';
                        if (nName) noteByName[nName] = pois[np].properties.note || '';
                    }}

                    var path = [];
                    var legEnds = [];
                    if (hasSegments && segmentNavPaths.length) {{
                        var running = 0;
                        for (var li = 0; li < segmentNavPaths.length; li++) {{
                            var leg = segmentNavPaths[li] || [];
                            if (!leg.length) continue;
                            for (var pj = 0; pj < leg.length; pj++) {{
                                if (path.length > 0 && pj === 0) continue;
                                path.push(leg[pj]);
                            }}
                            for (var lk = 0; lk < leg.length - 1; lk++) {{
                                running += haversine(leg[lk].lng, leg[lk].lat, leg[lk+1].lng, leg[lk+1].lat);
                            }}
                            legEnds.push(running);
                        }}
                    }} else {{
                        path = points.map(function(p) {{ return {{ lng: p.lng, lat: p.lat }}; }});
                    }}
                    if (path.length < 2) return;

                    var segLens = [];
                    var total = 0;
                    for (var s = 0; s < path.length - 1; s++) {{
                        var d = haversine(path[s].lng, path[s].lat, path[s+1].lng, path[s+1].lat);
                        segLens.push(d);
                        total += d;
                    }}

                    var spriteEl = document.createElement('div');
                    spriteEl.className = 'ld-sprite';
                    if (immersiveSpriteUri) {{
                        var spImg = document.createElement('img');
                        spImg.src = immersiveSpriteUri;
                        spImg.alt = 'sprite';
                        spriteEl.appendChild(spImg);
                    }} else {{
                        spriteEl.textContent = '🧚';
                    }}
                    var sprite = new AMap.Marker({{
                        position: new AMap.LngLat(path[0].lng, path[0].lat),
                        content: spriteEl,
                        offset: new AMap.Pixel(-27, -27),
                        zIndex: 120,
                    }});
                    map.add(sprite);

                    var speed = 14.0;
                    var traveled = 0;
                    var lastT = performance.now();
                    var legAnnounced = {{}};

                    function positionAtDistance(dist) {{
                        var left = dist;
                        for (var i2 = 0; i2 < segLens.length; i2++) {{
                            var seg = segLens[i2];
                            if (left <= seg) {{
                                var t = seg ? (left / seg) : 0;
                                var a = path[i2], b = path[i2 + 1];
                                return {{ lng: a.lng + (b.lng - a.lng) * t, lat: a.lat + (b.lat - a.lat) * t }};
                            }}
                            left -= seg;
                        }}
                        return path[path.length - 1];
                    }}

                    function tick(now) {{
                        var dt = (now - lastT) / 1000;
                        lastT = now;
                        traveled += speed * dt;
                        if (traveled > total) traveled = total;

                        var cur = positionAtDistance(traveled);
                        sprite.setPosition(new AMap.LngLat(cur.lng, cur.lat));

                        if (hasSegments && legEnds.length) {{
                            for (var li2 = 0; li2 < legEnds.length; li2++) {{
                                if (legAnnounced[li2]) continue;
                                if ((legEnds[li2] - traveled) <= 140) {{
                                    legAnnounced[li2] = true;
                                    var nextName = (points[li2 + 1] && points[li2 + 1].name) ? points[li2 + 1].name : '下一站';
                                    var segInfo = segments[li2] || {{}};
                                    var routeMode = segInfo.route_type || 'walking';
                                    var traffic = routeMode === 'driving' ? '驾车/打车' : (routeMode === 'transit' ? '公交/地铁' : '步行');
                                    if (segInfo.duration) traffic += '，约' + segInfo.duration;
                                    if (segInfo.cost) traffic += '，费用' + segInfo.cost;
                                    var caution = noteByName[nextName] || ((points[li2 + 1] && points[li2 + 1].recommendation) ? points[li2 + 1].recommendation : '注意安全，留意人流');
                                    speak('即将到达 ' + nextName + '。推荐交通：' + traffic + '。注意事项：' + caution);
                                }}
                            }}
                        }}

                        for (var k = 0; k < pois.length; k++) {{
                            var pf = pois[k];
                            var name = (pf.properties && pf.properties.name) ? pf.properties.name : '';
                            if (!name || reached[name]) continue;
                            var pc = pf.geometry.coordinates;
                            var dist = haversine(cur.lng, cur.lat, pc[0], pc[1]);
                            if (dist <= 50) {{
                                reached[name] = true;
                                var note = (pf.properties && pf.properties.note) ? pf.properties.note : '';
                                var stay = (pf.properties && pf.properties.stay_min) ? pf.properties.stay_min : 0;
                                var msg = '到达 ' + name;
                                if (note) msg += '，注意：' + note;
                                if (stay) msg += '。建议停留 ' + stay + ' 分钟';
                                speak(msg);
                            }}
                        }}

                        if (traveled >= total) {{
                            map.remove(sprite);
                            if (endCard) endCard.classList.add('show');
                            if (endTitle) endTitle.textContent = '旅程完成';
                            if (endText) endText.textContent = '您刚刚走完了现实中 3 小时的行程，期待你的到来';
                            return;
                        }}
                        requestAnimationFrame(tick);
                    }}
                    requestAnimationFrame(tick);
                }}

                if (immersiveEnabled) {{
                    startImmersive();
                }}

                function onMapBackgroundTap(e) {{
                    if (e && e.target && e.target.getExtData) {{
                        var ext = e.target.getExtData();
                        if (ext && typeof ext.idx === 'number') {{
                            suppressNextMapClicks(1500);
                            autoFitLocked = true;
                            focusAt(ext.idx);
                            return;
                        }}
                    }}
                    if (Date.now() < suppressMapClickUntil) return;
                    autoFitLocked = true;
                    clearFocus();
                }}

                map.on('click', onMapBackgroundTap);
                map.on('tap', onMapBackgroundTap);
            }}
        </script>
    </body>
    </html>
    """
    return html


# ============================================================
#  AI 推荐语生成
# ============================================================

def generate_recommendation(point: dict, weather: dict) -> str:
    name = point.get("name", "此地")
    env = point.get("environment", "")
    weather_text = f"{weather['weather']}{weather['temperature']}°C"
    templates = [
        f"{name}，{weather_text}，值得一游！",
        f"推荐前往{name}，{env}，令人流连忘返。",
        f"{name}风景如画，{weather_text}正适合出行！",
        f"不可错过的{name}，{env}，快来打卡吧！",
    ]
    return templates[hash(name) % len(templates)]


# ============================================================
#  处理解析结果 → 地图标注点
# ============================================================

def process_parse_result(result: dict) -> list:
    points = []
    for pt in result.get("points", []):
        content = pt.get("content", {})
        coords = pt.get("coordinates", {})
        landmarks = content.get("landmarks", [])
        primary_landmark = landmarks[0] if landmarks else None

        if primary_landmark:
            location = geo_to_location(primary_landmark)
            name = primary_landmark
        else:
            location = {"lng": coords.get("lng", 120.14870), "lat": coords.get("lat", 30.24240)}
            name = content.get("environment", "未知地点")[:10]

        weather = get_weather(name)
        point_info = {"name": name, "environment": content.get("environment", "")}
        recommendation = generate_recommendation(point_info, weather)

        points.append({
            "name": name,
            "lng": location["lng"] if "lng" in location else coords.get("lng", 120.14870),
            "lat": location["lat"] if "lat" in location else coords.get("lat", 30.24240),
            "weather": f"{weather['weather']} {weather['temperature']}°C",
            "recommendation": recommendation,
            "speech": content.get("speech", ""),
            "environment": content.get("environment", ""),
            "signs": content.get("signs", []),
            "tag": "城市",
            "mood": "",
        })
    return points


def process_api_result(result: dict) -> list:
    """将后端 /analyze_video_link 返回的新格式 JSON 转为地图点位列表"""
    import requests as _req
    points = []
    city = result.get("city", "")
    DEFAULT_LNG, DEFAULT_LAT = 120.14870, 30.24240

    for spot in result.get("spots", []):
        name = spot.get("name", "未知地点")
        lng = spot.get("lng")
        lat = spot.get("lat")

        # 如果后端没有给坐标，尝试高德地理编码
        if lng is None or lat is None:
            try:
                loc_query = f"{city}{name}" if city else name
                location = geo_to_location(loc_query)
                lng = location.get("lng", DEFAULT_LNG)
                lat = location.get("lat", DEFAULT_LAT)
            except Exception:
                lng, lat = DEFAULT_LNG, DEFAULT_LAT

        # 天气（用城市名查，避免每个点都请求）
        weather_info = get_weather(city or name)
        weather_str = f"{weather_info.get('weather', '')} {weather_info.get('temperature', '')}°C".strip()

        recommendation = spot.get("recommendation", "") or spot.get("speech", "")

        # 注入城市和博主名，供 voice_to_data_uri 查找声音文件
        blogger = result.get("blogger", "") or ""
        # 从博主名中提取纯名（去掉 emoji 等）
        import re as _re
        clean_blogger = _re.sub(r"[\U0001F300-\U0001F9FF]", "", blogger).strip()
        # 城市名去掉"市"字（声音文件夹格式：杭州-博主名）
        clean_city = city.replace("市", "").strip()

        points.append({
            "name": name,
            "lng": lng,
            "lat": lat,
            "weather": weather_str,
            "recommendation": recommendation,
            "speech": spot.get("speech", ""),
            "environment": spot.get("environment", ""),
            "signs": spot.get("signs", []),
            "tag": spot.get("tag", "城市"),
            "mood": spot.get("mood", ""),
            "visit_duration": spot.get("visit_duration", ""),
            "best_time": spot.get("best_time", ""),
            "ticket": spot.get("ticket", ""),
            "images": spot.get("images", []),
            # voice_to_data_uri 会读取这两个字段
            "_city": clean_city,
            "_blogger": clean_blogger,
        })
    return points


def call_backend_analyze(video_link: str) -> dict:
    raise RuntimeError("Demo 模式不支持导入网络视频")


# ============================================================
#  页面配置 & 初始化
# ============================================================

st.set_page_config(
    page_title="灵动地图 AI",
    page_icon="🏔️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_mobile_css()
inject_swipe_nav_js()

# Session State
if "current_tab" not in st.session_state:
    st.session_state.current_tab = "寻迹"
elif st.session_state.current_tab == "解析":
    st.session_state.current_tab = "寻迹"
if "parse_result" not in st.session_state:
    st.session_state.parse_result = None
if "map_points" not in st.session_state:
    st.session_state.map_points = []
if "map_segments" not in st.session_state:
    st.session_state.map_segments = []
if "map_city" not in st.session_state:
    st.session_state.map_city = "杭州"
if "map_province" not in st.session_state:
    st.session_state.map_province = "浙江省"
if "knowledge_base" not in st.session_state:
    st.session_state.knowledge_base = {}
if "demo_mode" not in st.session_state:
    st.session_state.demo_mode = True
st.session_state.demo_mode = True
if "demo_choice" not in st.session_state:
    st.session_state.demo_choice = "hz_xihu_lu"
if "demo_loading" not in st.session_state:
    st.session_state.demo_loading = None
if "trip_plan" not in st.session_state:
    st.session_state.trip_plan = None
if "visited_provinces" not in st.session_state:
    st.session_state.visited_provinces = set()  # 记录已访问过的省份，用于首次欢迎弹窗
if "api_loading" not in st.session_state:
    st.session_state.api_loading = None  # API 解析完成后的漫画展示状态
if "trip_emergency" not in st.session_state:
    st.session_state.trip_emergency = None
if "saved_trips" not in st.session_state:
    st.session_state.saved_trips = []
if "dev_mode" not in st.session_state:
    st.session_state.dev_mode = False
if "all_checkins" not in st.session_state:
    st.session_state.all_checkins = []  # 全局打卡记录
if "virtual_tour_mode" not in st.session_state:
    st.session_state.virtual_tour_mode = False
if "local_db_path" not in st.session_state:
    st.session_state.local_db_path = local_db.get_default_db_path(TEMP_DIR)
if "user_id" not in st.session_state:
    local_db.ensure_user_id(st.session_state)

try:
    db_path = st.session_state.local_db_path
    user_id = st.session_state.user_id
    if isinstance(db_path, str) and isinstance(user_id, str):
        st.session_state.all_checkins = list(dict.fromkeys(local_db.list_checkins(db_path, user_id)))
        if not st.session_state.saved_trips:
            st.session_state.saved_trips = local_db.list_trips(db_path, user_id)
except Exception:
    pass


# ============================================================
#  底部导航（山海主题）
# ============================================================

def render_header():
    st.markdown(
        """
        <div class="ld-header">
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;">
            <div style="display:flex;flex-direction:column;gap:6px;">
              <div class="ld-logo" aria-label="灵动地图AI logo">
                <svg width="22" height="22" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" role="img" aria-hidden="true">
                  <defs>
                    <linearGradient id="g1" x1="0" y1="0" x2="1" y2="1">
                      <stop offset="0" stop-color="#25B4E1"/>
                      <stop offset="1" stop-color="#A8D1D1"/>
                    </linearGradient>
                  </defs>
                  <path d="M12 40c7-9 12-14 20-14s13 5 20 14v10H12V40z" fill="url(#g1)" opacity="0.28"/>
                  <path d="M12 44c7-7 13-10 20-10s13 3 20 10" fill="none" stroke="#25B4E1" stroke-width="4" stroke-linecap="round" opacity="0.55"/>
                  <path d="M16 36l12-14 10 11 10-15 12 18" fill="none" stroke="#2C3E50" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" opacity="0.85"/>
                  <path d="M32 56c9-10 14-17 14-24a14 14 0 1 0-28 0c0 7 5 14 14 24z" fill="url(#g1)" opacity="0.92"/>
                  <circle cx="32" cy="32" r="6.5" fill="#ffffff" opacity="0.95"/>
                </svg>
              </div>
              <div style="display:flex;flex-direction:column;gap:1px;">
              <div class="ld-header-title">灵动地图 AI</div>
              <div class="ld-header-sub">山海寻迹 · 灵感萃取</div>
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_bottom_nav():
    """渲染固定底部导航栏（小红书风格·固定底部·横向按钮）"""
    current = st.session_state.current_tab
    nav_items = [
        ("寻迹", "🧭"),
        ("地图", "🗺️"),
        ("旅行", "💬"),
        ("我的", "👤"),
    ]

    st.markdown('<div id="shanhai-bottom-nav-anchor" class="shanhai-bottom-nav-anchor"></div>', unsafe_allow_html=True)

    cols = st.columns(4)
    next_tab = None
    for i, (tab_id, icon) in enumerate(nav_items):
        with cols[i]:
            is_active = tab_id == current
            btn_label = f"{icon}\n{tab_id}"
            if st.button(
                btn_label,
                key=f"_nav_btn_{tab_id}",
                use_container_width=True,
                disabled=is_active,
            ):
                next_tab = tab_id

    if next_tab and next_tab != current:
        st.session_state.current_tab = next_tab
        st.rerun()


# ============================================================
#  山脊线装饰
# ============================================================

def render_mountain_ridge():
    st.markdown('<div class="mountain-ridge"></div>', unsafe_allow_html=True)

def render_sea_wave_footer():
    st.markdown('<div class="sea-wave-footer"></div>', unsafe_allow_html=True)

def render_tide_divider():
    st.markdown('<div class="tide-divider"></div>', unsafe_allow_html=True)


def _province_to_asset_key(province: str) -> str:
    mapping = {
        "浙江省": "zhejiang",
        "四川省": "sichuan",
    }
    normalized = normalize_province_input(province) or province
    return mapping.get(normalized, "zhejiang")


def _load_province_illustrations(province: str) -> list[str]:
    key = _province_to_asset_key(province)
    manifest_path = os.path.join(os.path.dirname(__file__), "assets", "illustrations", key, "manifest.json")
    if not os.path.exists(manifest_path):
        manifest_path = os.path.join(os.path.dirname(__file__), "assets", "illustrations", "zhejiang", "manifest.json")
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        images = data.get("images", [])
        if isinstance(images, list) and images:
            base_dir = os.path.dirname(manifest_path)
            out = []
            for item in images[:30]:
                rel = str(item)
                if rel.startswith("data:"):
                    out.append(rel)
                    continue
                local_path = os.path.join(base_dir, rel)
                if not os.path.exists(local_path):
                    continue
                with open(local_path, "rb") as imf:
                    blob = imf.read()
                b64 = base64.b64encode(blob).decode("ascii")
                out.append(f"data:image/webp;base64,{b64}")
            if out:
                return out
    except Exception:
        pass
    return []


def _load_sprite_gif_data_uri() -> str:
    sprite_path = os.path.join(os.path.dirname(__file__), "picture", "images", "精灵动图.gif")
    if not os.path.exists(sprite_path):
        return ""
    try:
        with open(sprite_path, "rb") as f:
            blob = f.read()
        b64 = base64.b64encode(blob).decode("ascii")
        return f"data:image/gif;base64,{b64}"
    except Exception:
        return ""


def _extract_filename_hint(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return ""
    try:
        parsed = urlparse(s)
        if parsed.scheme and parsed.netloc:
            base = os.path.basename(parsed.path)
            return base or s
    except Exception:
        pass
    return s


def _duration_to_minutes(value: str) -> int:
    if not value:
        return 0
    s = str(value).strip()
    if not s:
        return 0
    total = 0
    m = re.search(r"(\d+)\s*小时", s)
    if m:
        total += int(m.group(1)) * 60
    m = re.search(r"(\d+)\s*分钟", s)
    if m:
        total += int(m.group(1))
    if total:
        return total
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else 0


def _geojson_from_map_points(points: list[dict]) -> dict:
    coords = []
    features = []
    for p in points:
        try:
            lng = round(float(p.get("lng")), 6)
            lat = round(float(p.get("lat")), 6)
        except Exception:
            continue
        note = (p.get("recommendation") or "").strip()
        if not note:
            note = (p.get("environment") or "").strip()
        if not note:
            signs = p.get("signs") or []
            if isinstance(signs, list) and signs:
                note = "路牌：" + " / ".join([str(x) for x in signs[:3] if x])
        note = note.replace("\n", " ").strip()
        if len(note) > 70:
            note = note[:70] + "…"
        coords.append([lng, lat])
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lng, lat]},
                "properties": {
                    "name": p.get("name") or "",
                    "tts_url": p.get("tts_url") or "",
                    "stay_min": _duration_to_minutes(p.get("visit_duration") or ""),
                    "note": note,
                },
            }
        )
    line = {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": {"name": "旅行轨迹"},
    }
    return {"type": "FeatureCollection", "features": [line] + features}


def _sample_geojson(province: str) -> dict:
    normalized = normalize_province_input(province) or province
    if normalized == "浙江省":
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [120.155050, 30.251650],
                            [120.160200, 30.252900],
                            [120.168500, 30.252000],
                            [120.172600, 30.246900],
                            [120.166400, 30.243600],
                            [120.158900, 30.244300],
                            [120.149200, 30.231500],
                        ],
                    },
                    "properties": {
                        "name": "西湖慢游线",
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [120.155050, 30.251650]},
                    "properties": {"name": "湖滨", "tts_url": "", "stay_min": 20},
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [120.158900, 30.244300]},
                    "properties": {"name": "花港观鱼", "tts_url": "", "stay_min": 45},
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [120.149200, 30.231500]},
                    "properties": {"name": "雷峰塔", "tts_url": "", "stay_min": 60},
                },
            ],
        }
    if normalized == "四川省":
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [104.053730, 30.671930],
                            [104.060200, 30.662400],
                            [104.080300, 30.657300],
                            [104.082900, 30.656700],
                            [104.055400, 30.650900],
                        ],
                    },
                    "properties": {"name": "成都CityWalk"},
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [104.053730, 30.671930]},
                    "properties": {"name": "宽窄巷子", "tts_url": "", "stay_min": 60},
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [104.060200, 30.662400]},
                    "properties": {"name": "人民公园", "tts_url": "", "stay_min": 90},
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [104.080300, 30.657300]},
                    "properties": {"name": "春熙路", "tts_url": "", "stay_min": 60},
                },
            ],
        }
    return _sample_geojson("浙江省")


def _render_flipbook(images: list[str], province_label: str):
    safe_images = json.dumps(images, ensure_ascii=False)
    html = f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8"/>
      <meta name="viewport" content="width=375, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"/>
      <style>
        html,body{{margin:0;padding:0;width:375px;height:100%;overflow:hidden;background:#F9F7F2;}}
        #stage{{position:relative;width:375px;height:420px;margin:0 auto;}}
        #canvas{{width:375px;height:420px;display:block;border-radius:26px;background:#fff;box-shadow:0 18px 50px -26px rgba(0,0,0,0.30);}}
        #skip{{position:absolute;top:10px;right:10px;z-index:4;background:rgba(255,255,255,0.88);border:1px solid rgba(0,0,0,0.05);border-radius:999px;padding:8px 10px;font-size:11px;font-weight:900;color:#2C3E50;}}
        #status{{position:absolute;left:12px;right:72px;top:12px;z-index:4;background:rgba(255,255,255,0.82);border:1px solid rgba(0,0,0,0.05);border-radius:999px;padding:8px 12px;font-size:11px;font-weight:900;color:#2C3E50;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:flex;align-items:center;gap:8px;}}
        .ring{{width:14px;height:14px;border-radius:999px;border:2px solid rgba(37,180,225,0.25);border-top-color:#25B4E1;animation:spin 0.8s linear infinite;flex:0 0 auto;}}
        @keyframes spin{{to{{transform:rotate(360deg);}}}}
        #dots{{position:absolute;left:0;right:0;bottom:10px;display:flex;justify-content:center;gap:6px;z-index:4;}}
        .dot{{width:7px;height:7px;border-radius:999px;background:rgba(0,0,0,0.18);}}
        .dot.active{{background:#25B4E1;}}
        #corner{{position:absolute;right:10px;bottom:10px;width:44px;height:44px;border-radius:14px;z-index:5;}}
      </style>
    </head>
    <body>
      <div id="stage">
        <canvas id="canvas" width="750" height="840"></canvas>
        <div id="status"></div>
        <div id="skip">跳过</div>
        <div id="dots"></div>
        <div id="corner"></div>
      </div>
      <script>
        const images = {safe_images};
        const province = {json.dumps(province_label, ensure_ascii=False)};
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        const dots = document.getElementById('dots');
        const corner = document.getElementById('corner');
        const skip = document.getElementById('skip');
        const status = document.getElementById('status');
        let index = 0;
        let flipping = false;
        let t0 = 0;
        let hover = false;

        const steps = ['正在解析文本…','正在解析语音…','正在解析图片信息…'];
        let si = 0;
        status.innerHTML = '<span class="ring"></span><span id="stxt"></span>';
        const stxt = document.getElementById('stxt');
        stxt.textContent = steps[0];
        setInterval(()=>{{ stxt.textContent = steps[(si++) % steps.length]; }}, 650);

        const loaded = new Map();
        function load(i){{
          const src = images[i % images.length];
          if (loaded.has(src)) return loaded.get(src);
          const img = new Image();
          const p = new Promise((resolve)=>{{ img.onload=()=>resolve(img); img.onerror=()=>resolve(null); }});
          img.src = src;
          loaded.set(src, p);
          return p;
        }}

        function renderDots(){{
          dots.innerHTML = '';
          for (let i=0;i<images.length;i++) {{
            const d = document.createElement('div');
            d.className = 'dot' + (i===index ? ' active' : '');
            d.addEventListener('click', ()=>{{ index=i; draw(); }});
            dots.appendChild(d);
          }}
        }}

        function drawImageFit(img){{
          const w = canvas.width, h = canvas.height;
          ctx.clearRect(0,0,w,h);
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(0,0,w,h);
          if (!img) {{
            ctx.fillStyle = '#2C3E50';
            ctx.font = 'bold 44px system-ui, -apple-system, "PingFang SC"';
            ctx.fillText(province, 42, 96);
            ctx.fillStyle = 'rgba(44,62,80,0.55)';
            ctx.font = '28px system-ui, -apple-system, "PingFang SC"';
            ctx.fillText('插画加载中…', 42, 148);
            return;
          }}
          const iw = img.naturalWidth, ih = img.naturalHeight;
          const s = Math.max(w/iw, h/ih);
          const dw = iw*s, dh = ih*s;
          const dx = (w-dw)/2, dy = (h-dh)/2;
          ctx.drawImage(img, dx, dy, dw, dh);
          ctx.fillStyle = 'rgba(0,0,0,0.22)';
          ctx.fillRect(0,0,w,90);
          ctx.fillStyle = '#fff';
          ctx.font = '900 30px system-ui, -apple-system, "PingFang SC"';
          ctx.fillText(province + ' · 等待插画', 36, 58);
        }}

        async function draw(){{
          renderDots();
          const img = await load(index);
          drawImageFit(img);
          if (!flipping) {{
            const w=canvas.width,h=canvas.height;
            ctx.save();
            ctx.globalAlpha = hover ? 0.35 : 0.18;
            ctx.fillStyle = '#25B4E1';
            ctx.beginPath();
            ctx.moveTo(w-120,h);
            ctx.quadraticCurveTo(w,h,w,h-120);
            ctx.lineTo(w,h);
            ctx.closePath();
            ctx.fill();
            ctx.restore();
          }}
        }}

        function animateFlip(){{
          if (flipping) return;
          flipping = true;
          const start = performance.now();
          const from = index;
          const to = (index + 1) % images.length;
          Promise.all([load(from), load(to)]).then(([a,b])=>{{
            function step(now){{
              const t = Math.min(1, (now-start)/350);
              const w=canvas.width,h=canvas.height;
              ctx.clearRect(0,0,w,h);
              if (a) drawImageFit(a);
              ctx.save();
              ctx.globalCompositeOperation = 'source-atop';
              const fold = w * (0.15 + 0.85*t);
              ctx.beginPath();
              ctx.moveTo(w-fold, 0);
              ctx.lineTo(w, 0);
              ctx.lineTo(w, h);
              ctx.lineTo(w-fold, h);
              ctx.closePath();
              ctx.fillStyle = 'rgba(255,255,255,' + (0.05 + 0.65*t) + ')';
              ctx.fill();
              ctx.restore();
              if (b) {{
                ctx.save();
                ctx.globalAlpha = t;
                ctx.drawImage(b, 0, 0, w, h);
                ctx.restore();
              }}
              if (t < 1) {{
                requestAnimationFrame(step);
              }} else {{
                index = to;
                flipping = false;
                draw();
              }}
            }}
            requestAnimationFrame(step);
          }});
        }}

        function insideCorner(clientX, clientY){{
          const r = corner.getBoundingClientRect();
          return clientX>=r.left && clientX<=r.right && clientY>=r.top && clientY<=r.bottom;
        }}

        canvas.addEventListener('mousemove', (e)=>{{ hover = insideCorner(e.clientX,e.clientY); draw(); }});
        canvas.addEventListener('click', (e)=>{{ if (insideCorner(e.clientX,e.clientY)) animateFlip(); }});
        let touchStartX = null;
        canvas.addEventListener('touchstart', (e)=>{{ if (!e.touches||!e.touches.length) return; touchStartX = e.touches[0].clientX; }}, {{passive:true}});
        canvas.addEventListener('touchend', (e)=>{{
          if (touchStartX == null) return;
          const x = (e.changedTouches && e.changedTouches.length) ? e.changedTouches[0].clientX : touchStartX;
          const dx = x - touchStartX;
          touchStartX = null;
          if (Math.abs(dx) >= 40) animateFlip();
        }}, {{passive:true}});
        skip.addEventListener('click', ()=>{{ document.getElementById('stage').style.display='none'; }});
        draw();
      </script>
    </body>
    </html>
    """
    components.html(html, height=440, scrolling=False)


def _render_virtual_tour(geojson: dict):
    payload = json.dumps(geojson, ensure_ascii=False)
    html = f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8"/>
      <meta name="viewport" content="width=375, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"/>
      <style>
        html,body{{margin:0;padding:0;width:375px;height:100%;overflow:hidden;background:#0b1020;}}
        #wrap{{position:relative;width:375px;height:520px;border-radius:26px;overflow:hidden;background:#0b1020;box-shadow:0 22px 60px -30px rgba(0,0,0,0.45);}}
        #gl{{position:absolute;left:0;top:0;width:375px;height:520px;}}
        #hud{{position:absolute;left:12px;right:12px;top:12px;z-index:4;display:flex;justify-content:space-between;gap:10px;}}
        .chip{{background:rgba(255,255,255,0.10);border:1px solid rgba(255,255,255,0.14);backdrop-filter: blur(12px);-webkit-backdrop-filter: blur(12px);color:#fff;border-radius:999px;padding:8px 10px;font-size:11px;font-weight:900;}}
        #sub{{position:absolute;left:12px;right:12px;bottom:12px;z-index:4;background:rgba(0,0,0,0.35);border:1px solid rgba(255,255,255,0.12);border-radius:18px;padding:10px 12px;color:#fff;font-size:12px;line-height:1.45;min-height:44px;}}
        #end{{position:absolute;left:12px;right:12px;top:50%;transform:translateY(-50%);z-index:6;display:none;background:rgba(255,255,255,0.92);border-radius:22px;padding:16px 14px;}}
        #end h3{{margin:0;font-size:16px;font-weight:900;color:#2C3E50;}}
        #end p{{margin:8px 0 0 0;font-size:12px;color:rgba(44,62,80,0.75);line-height:1.45;}}
        #end .btns{{margin-top:12px;display:flex;gap:10px;}}
        #end button{{flex:1;border:0;border-radius:16px;padding:10px 12px;font-size:12px;font-weight:900;}}
        #go{{background:linear-gradient(135deg,#0D8BF2,#0052CC);color:#fff;}}
        #more{{background:rgba(44,62,80,0.10);color:#2C3E50;}}
      </style>
    </head>
    <body>
      <div id="wrap">
        <canvas id="gl" width="750" height="1040"></canvas>
        <div id="hud">
          <div class="chip" id="title">虚拟旅程</div>
          <div class="chip" id="replay">重播语音</div>
        </div>
        <div id="sub"></div>
        <div id="end">
          <h3 id="endTitle"></h3>
          <p id="endText"></p>
          <div class="btns">
            <button id="go">现在出发</button>
            <button id="more">导入更多素材</button>
          </div>
        </div>
      </div>
      <script>
        const geo = {payload};
        const canvas = document.getElementById('gl');
        const ctx = canvas.getContext('2d');
        const subtitle = document.getElementById('sub');
        const end = document.getElementById('end');
        const endTitle = document.getElementById('endTitle');
        const endText = document.getElementById('endText');
        const replay = document.getElementById('replay');

        function haversine(a,b){{
          const R=6371000;
          const toRad=(d)=>d*Math.PI/180;
          const dLat=toRad(b[1]-a[1]);
          const dLng=toRad(b[0]-a[0]);
          const lat1=toRad(a[1]), lat2=toRad(b[1]);
          const x=Math.sin(dLat/2)**2 + Math.cos(lat1)*Math.cos(lat2)*Math.sin(dLng/2)**2;
          return 2*R*Math.asin(Math.min(1,Math.sqrt(x)));
        }}

        const line = geo.features.find(f=>f.geometry && f.geometry.type==='LineString');
        const pois = geo.features.filter(f=>f.geometry && f.geometry.type==='Point');
        const coords = line ? line.geometry.coordinates : [];
        const bounds = coords.reduce((acc,c)=>{{
          acc.minX=Math.min(acc.minX,c[0]); acc.maxX=Math.max(acc.maxX,c[0]);
          acc.minY=Math.min(acc.minY,c[1]); acc.maxY=Math.max(acc.maxY,c[1]);
          return acc;
        }},{{minX:1e9,maxX:-1e9,minY:1e9,maxY:-1e9}});

        function project(c){{
          const w=canvas.width,h=canvas.height;
          const pad=90;
          const x = (c[0]-bounds.minX)/Math.max(1e-9,(bounds.maxX-bounds.minX));
          const y = (c[1]-bounds.minY)/Math.max(1e-9,(bounds.maxY-bounds.minY));
          return [pad + x*(w-2*pad), h - (pad + y*(h-2*pad))];
        }}

        const pts = coords.map(project);
        const poiState = new Set();
        let segLens = [];
        let total = 0;
        for (let i=0;i<coords.length-1;i++){{
          const d = haversine(coords[i], coords[i+1]);
          segLens.push(d);
          total += d;
        }}
        const speed = 4000/3600;
        let traveled = 0;
        let last = performance.now();
        let lastSpeech = '';

        function speak(text){{
          lastSpeech = text;
          subtitle.textContent = text;
          try {{
            const u = new SpeechSynthesisUtterance(text);
            u.rate = 1.0;
            u.pitch = 1.0;
            u.lang = 'zh-CN';
            window.speechSynthesis.cancel();
            window.speechSynthesis.speak(u);
          }} catch (e) {{}}
        }}
        replay.addEventListener('click', ()=>{{ if (lastSpeech) speak(lastSpeech); }});

        function draw(t){{
          const w=canvas.width,h=canvas.height;
          ctx.clearRect(0,0,w,h);
          const grd = ctx.createLinearGradient(0,0,w,h);
          grd.addColorStop(0,'#0D8BF2');
          grd.addColorStop(1,'#0052CC');
          ctx.lineCap='round';
          ctx.lineJoin='round';
          ctx.strokeStyle='rgba(255,255,255,0.08)';
          ctx.lineWidth=22;
          ctx.beginPath();
          pts.forEach((p,i)=>{{ if(i===0) ctx.moveTo(p[0],p[1]); else ctx.lineTo(p[0],p[1]); }});
          ctx.stroke();
          ctx.strokeStyle=grd;
          ctx.lineWidth=10;
          ctx.beginPath();
          pts.forEach((p,i)=>{{ if(i===0) ctx.moveTo(p[0],p[1]); else ctx.lineTo(p[0],p[1]); }});
          ctx.stroke();

          ctx.fillStyle='rgba(255,255,255,0.92)';
          pois.forEach(p=>{{
            const xy = project(p.geometry.coordinates);
            ctx.beginPath();
            ctx.arc(xy[0],xy[1],7,0,Math.PI*2);
            ctx.fill();
          }});
        }}

        function posAtDistance(d){{
          if (coords.length < 2) return coords[0] || [0,0];
          let left = d;
          for (let i=0;i<segLens.length;i++){{
            const seg = segLens[i];
            if (left <= seg) {{
              const t = seg ? left/seg : 0;
              const a = coords[i], b = coords[i+1];
              return [a[0] + (b[0]-a[0])*t, a[1] + (b[1]-a[1])*t];
            }}
            left -= seg;
          }}
          return coords[coords.length-1];
        }}

        function tick(now){{
          const dt = (now-last)/1000;
          last = now;
          traveled += speed*dt;
          if (traveled > total) traveled = total;
          draw(now);
          const cur = posAtDistance(traveled);
          const xy = project(cur);
          ctx.save();
          ctx.fillStyle='#fff';
          ctx.shadowColor='rgba(0,0,0,0.35)';
          ctx.shadowBlur=14;
          ctx.beginPath();
          ctx.arc(xy[0],xy[1],10,0,Math.PI*2);
          ctx.fill();
          ctx.restore();

          pois.forEach(p=>{{
            const name = p.properties && p.properties.name ? p.properties.name : '';
            if (!name) return;
            if (poiState.has(name)) return;
            const dist = haversine(cur, p.geometry.coordinates);
            if (dist <= 50) {{
              poiState.add(name);
              speak('到达 ' + name);
            }}
          }});

          if (traveled >= total) {{
            end.style.display='block';
            endTitle.textContent = '旅程完成';
            endText.textContent = '您刚刚走完了现实中 3 小时的行程，期待你的到来。';
            return;
          }}
          requestAnimationFrame(tick);
        }}

        document.getElementById('go').addEventListener('click', ()=>{{ window.open('https://www.amap.com/', '_blank'); }});
        document.getElementById('more').addEventListener('click', ()=>{{ location.reload(); }});

        requestAnimationFrame(tick);
      </script>
    </body>
    </html>
    """
    components.html(html, height=540, scrolling=False)


def _load_cartoon_uris(province: str) -> list[str]:
    province = (province or "").strip()
    prefix = "浙江" if ("浙江" in province or province == "浙江省") else "四川" if ("四川" in province or province == "四川省") else ""
    if not prefix:
        return []
    base_dir = os.path.join(os.path.dirname(__file__), "picture", "cartoon")
    if not os.path.exists(base_dir):
        return []
    items = []
    for fn in os.listdir(base_dir):
        if not fn.startswith(prefix):
            continue
        ext = os.path.splitext(fn)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        # 提取文件名中的数字序号，按数字排序（如 四川_01 → 1）
        try:
            num_part = int(fn.replace(prefix, "").split(".")[0].strip("_"))
        except Exception:
            num_part = 0
        full = os.path.join(base_dir, fn)
        try:
            with open(full, "rb") as f:
                blob = f.read()
            b64 = base64.b64encode(blob).decode("ascii")
            mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png" if ext == ".png" else "image/webp"
            items.append((num_part, f"data:{mime};base64,{b64}"))
        except Exception:
            continue
    items.sort(key=lambda x: x[0])  # 按数字序号排序（1→8）
    return [item[1] for item in items]


def _render_demo_loading_cartoon(images: list[str], duration_sec: int = 20):
    duration_ms = int(max(1, duration_sec) * 1000)
    min_interval_ms = 6000
    max_interval_ms = 7000
    images_json = json.dumps(images, ensure_ascii=False)
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <style>
        html, body {{ margin:0; padding:0; background: transparent; }}
        .wrap {{
          width: 100%;
          border-radius: 18px;
          overflow: hidden;
          background: rgba(255,255,255,0.95);
          border: 1px solid rgba(242,230,206,0.7);
          box-shadow: 0 18px 50px -26px rgba(0,0,0,0.22);
          font-family: Inter, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
        }}
        .bar {{
          height: 6px;
          background: rgba(17,24,39,0.10);
          overflow:hidden;
        }}
        .bar > div {{
          height: 100%;
          width: 0%;
          background: linear-gradient(90deg, #ff6b6b, #25b4e1);
          transition: width 0.25s ease;
        }}
        .stage {{
          position: relative;
          width: 100%;
          height: 420px;
          background: #0a0a0f;
          cursor: pointer;
          -webkit-tap-highlight-color: transparent;
        }}
        .nav {{
          position: absolute;
          top: 0; bottom: 0;
          width: 56px;
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 5;
          cursor: pointer;
          user-select: none;
          -webkit-tap-highlight-color: transparent;
          background: linear-gradient(to right, rgba(0,0,0,0.35), rgba(0,0,0,0.0));
          opacity: 0.65;
          transition: opacity 0.2s ease;
        }}
        .nav:hover {{ opacity: 0.9; }}
        .nav.right {{
          right: 50px; left: auto;
          background: linear-gradient(to left, rgba(0,0,0,0.35), rgba(0,0,0,0.0));
        }}
        .nav.left {{ left: 0; right: auto; }}
        .nav span {{
          width: 38px; height: 38px;
          border-radius: 999px;
          display: flex; align-items: center; justify-content: center;
          background: rgba(255,255,255,0.16);
          border: 1px solid rgba(255,255,255,0.18);
          color: rgba(255,255,255,0.92);
          font-size: 18px; font-weight: 900;
          backdrop-filter: blur(8px);
        }}
        .stage img {{
          position: absolute; inset: 0;
          width: 100%; height: 100%;
          object-fit: contain;
          opacity: 0;
          transform: translateX(100%);
          transition: opacity 0.45s ease, transform 0.45s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        .stage img.show {{ opacity: 1; transform: translateX(0); }}
        .stage img.exit-left {{ opacity: 0; transform: translateX(-30%); transition: opacity 0.35s ease, transform 0.35s cubic-bezier(0.4, 0, 0.2, 1); }}
        /* 右上角跳过漫画按钮（悬浮在漫画上） */
        #skip {{
          position: absolute;
          top: 12px; right: 12px;
          z-index: 10;
          background: rgba(0,0,0,0.55);
          border: 1px solid rgba(255,255,255,0.18);
          border-radius: 999px;
          padding: 7px 14px;
          font-size: 12px; font-weight: 900;
          color: rgba(255,255,255,0.90);
          cursor: pointer;
          backdrop-filter: blur(8px);
          -webkit-backdrop-filter: blur(8px);
          transition: background 0.2s;
          user-select: none;
          -webkit-tap-highlight-color: transparent;
        }}
        #skip:hover {{ background: rgba(0,0,0,0.78); }}
        #page-info {{
          position: absolute;
          bottom: 12px; right: 60px;
          z-index: 10;
          font-size: 11px; font-weight: 700;
          color: rgba(255,255,255,0.50);
          user-select: none;
        }}
        .nav-arrow.disabled {{ opacity: 0.15; pointer-events: none; }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="bar"><div id="p"></div></div>
        <div class="stage" id="stage">
          <div class="nav left" id="prev" title="上一张"><span>‹</span></div>
          <div class="nav right disabled" id="next" title="下一张"><span>›</span></div>
          <img id="imgA" />
          <img id="imgB" />
          <div id="page-info"></div>
          <div id="skip">跳过漫画 ✕</div>
        </div>
      </div>
      <script>
        const images = {images_json};
        const DURATION = {duration_ms};
        const total = images.length;
        const imgA = document.getElementById('imgA');
        const imgB = document.getElementById('imgB');
        const p = document.getElementById('p');
        const skipBtn = document.getElementById('skip');
        const stage = document.getElementById('stage');
        const prevBtn = document.getElementById('prev');
        const nextBtn = document.getElementById('next');
        const pageInfo = document.getElementById('page-info');
        let idx = 0;
        let showingA = true;
        let animating = false;
        const started = Date.now();
        let finished = false;
        let finishTimer = null;

        function redirectToMap() {{
          try {{ window.parent.postMessage({{ type: 'demo_load_done' }}, '*'); }} catch (e) {{
            try {{ window.top.postMessage({{ type: 'demo_load_done' }}, '*'); }} catch (e2) {{}}
          }}
        }}

        function finish(mode) {{
          if (finished) return;
          finished = true;
          if (finishTimer) clearTimeout(finishTimer);
          skipBtn.style.opacity = '0.4';
          skipBtn.style.pointerEvents = 'none';
          stage.style.opacity = '0';
          stage.style.transition = 'opacity 0.5s ease';
          finishTimer = setTimeout(redirectToMap, mode === 'skip' ? 300 : 600);
        }}

        function updateNav() {{
          prevBtn.classList.toggle('disabled', idx <= 0);
          nextBtn.classList.toggle('disabled', idx >= total - 1);
          if (pageInfo) pageInfo.textContent = (idx + 1) + '/' + total;
        }}

        function renderPage() {{
          if (!images.length || animating) return;
          animating = true;
          const showEl = showingA ? imgA : imgB;
          const hideEl = showingA ? imgB : imgA;
          hideEl.classList.remove('show', 'exit-left');
          showEl.src = images[idx];
          showEl.classList.remove('exit-left');
          void showEl.offsetWidth;
          showEl.classList.add('show');
          hideEl.classList.add('exit-left');
          showingA = !showingA;
          updateNav();
          setTimeout(() => {{
            hideEl.classList.remove('exit-left', 'show');
            animating = false;
          }}, 450);
        }}

        function goNext() {{
          if (idx >= total - 1) {{ finish('done'); return; }}
          idx++;
          renderPage();
        }}

        function goPrev() {{
          if (idx <= 0) return;
          idx--;
          renderPage();
        }}

        function tick() {{
          const elapsed = Date.now() - started;
          const pct = Math.max(0, Math.min(100, Math.round(elapsed / DURATION * 100)));
          p.style.width = pct + '%';
          if (elapsed >= DURATION) {{
            finish('done');
          }} else {{
            requestAnimationFrame(tick);
          }}
        }}

        skipBtn.addEventListener('click', (e) => {{ e.stopPropagation(); finish('skip'); }});
        stage.addEventListener('click', (e) => {{
          if (e.target === skipBtn || e.target.closest('#prev') || e.target.closest('#next')) return;
          goNext();
        }});
        prevBtn.addEventListener('click', (e) => {{ e.stopPropagation(); goPrev(); }});
        nextBtn.addEventListener('click', (e) => {{ e.stopPropagation(); goNext(); }});
        renderPage();
        requestAnimationFrame(tick);
      </script>
    </body>
    </html>
    """
    components.html(html, height=440, scrolling=False)


def _render_api_cartoon(images: list[str], province: str, is_first_visit: bool = False):
    """
    流程：
    1. 欢迎面板（进度条 + 欢迎弹窗）同时出现
    2. 欢迎弹窗淡出后 → 整个欢迎面板消失
    3. 漫画面板独立出现（无进度条），手动翻页，末页自动淡出
    4. 跳过时若加载已完成（URL param 已设）立即跳转
    """
    images_json = json.dumps(images, ensure_ascii=False)
    display_name = province.replace("省", "").replace("市", "").replace("自治区", "").replace("壮族", "").replace("回族", "").strip()
    total = len(images) if images else 0
    # 欢迎面板最少显示 3000ms（进度条跑完）
    WELCOME_DURATION = 3000
    WELCOME_FADE_START = 2000  # 文字淡出时机
    WELCOME_HIDE_AFTER = 2600 # 欢迎面板消失时机

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        html, body {{ width: 100%; background: transparent; font-family: Inter, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; }}

        /* === 欢迎面板（进度条 + 欢迎弹窗，同一整体） === */
        #welcome-panel {{
          width: 100%;
          border-radius: 18px;
          overflow: hidden;
          background: linear-gradient(160deg, rgba(13,139,242,0.96) 0%, rgba(37,180,225,0.93) 100%);
          box-shadow: 0 18px 50px -26px rgba(0,0,0,0.22);
          transition: opacity 0.6s ease, transform 0.6s ease;
          margin-bottom: 8px;
        }}
        #welcome-panel.hidden {{ opacity: 0; transform: scale(0.97); pointer-events: none; display: none; }}

        .wp-prog {{
          height: 5px;
          background: rgba(255,255,255,0.15);
          overflow: hidden;
        }}
        .wp-prog > div {{
          height: 100%;
          width: 0%;
          background: rgba(255,255,255,0.7);
          transition: width 0.3s linear;
        }}
        #wp-body {{
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: 420px;
        }}
        #wp-icon {{ font-size: 52px; margin-bottom: 14px; animation: bounceIn 0.5s ease; }}
        #wp-title {{ font-size: 26px; font-weight: 900; color: #fff; letter-spacing: 0.04em; text-align: center; line-height: 1.3; transition: opacity 0.5s ease; }}
        #wp-sub {{ margin-top: 10px; font-size: 13px; color: rgba(255,255,255,0.75); text-align: center; transition: opacity 0.5s ease; }}
        @keyframes bounceIn {{ 0% {{ transform: scale(0.4); opacity: 0; }} 70% {{ transform: scale(1.1); opacity: 1; }} 100% {{ transform: scale(1); }} }}

        /* === 漫画面板（独立，无进度条） === */
        #cartoon-wrap {{
          width: 100%;
          border-radius: 18px;
          overflow: hidden;
          background: #0a0a0f;
          box-shadow: 0 18px 50px -26px rgba(0,0,0,0.22);
          opacity: 0;
          transform: scale(0.97) translateY(8px);
          transition: opacity 0.5s ease, transform 0.5s cubic-bezier(0.4,0,0.2,1);
          pointer-events: none;
        }}
        #cartoon-wrap.show {{ opacity: 1; transform: scale(1) translateY(0); pointer-events: all; }}

        #stage {{
          position: relative;
          width: 100%;
          height: 480px;
          background: #0a0a0f;
          overflow: hidden;
          cursor: pointer;
          -webkit-tap-highlight-color: transparent;
        }}
        #stage img {{
          position: absolute; inset: 0;
          width: 100%; height: 100%;
          object-fit: contain;
          opacity: 0;
          transform: translateX(100%);
          transition: opacity 0.45s ease, transform 0.45s cubic-bezier(0.4,0,0.2,1);
        }}
        #stage img.show {{ opacity: 1; transform: translateX(0); }}
        #stage img.exit-left {{ opacity: 0; transform: translateX(-30%); transition: opacity 0.35s ease, transform 0.35s cubic-bezier(0.4,0,0.2,1); }}

        /* 左下角省份标签 */
        #province-tag {{
          position: absolute;
          bottom: 12px; left: 12px;
          z-index: 20;
          background: rgba(0,0,0,0.5);
          border: 1px solid rgba(255,255,255,0.18);
          border-radius: 999px;
          padding: 6px 13px;
          font-size: 12px; font-weight: 900;
          color: rgba(255,255,255,0.88);
          backdrop-filter: blur(8px);
          -webkit-backdrop-filter: blur(8px);
          user-select: none;
        }}

        /* 右下角页码（放在右箭头左侧） */
        #page-info {{
          position: absolute;
          bottom: 12px; right: 56px;
          z-index: 20;
          font-size: 11px; font-weight: 700;
          color: rgba(255,255,255,0.50);
          user-select: none;
        }}

        /* 右上角跳过 */
        #skip-btn {{
          position: absolute;
          top: 12px; right: 12px;
          z-index: 25;
          background: rgba(0,0,0,0.55);
          border: 1px solid rgba(255,255,255,0.18);
          border-radius: 999px;
          padding: 7px 14px;
          font-size: 12px; font-weight: 900;
          color: rgba(255,255,255,0.90);
          cursor: pointer;
          backdrop-filter: blur(8px);
          -webkit-backdrop-filter: blur(8px);
          transition: background 0.2s;
          user-select: none;
          -webkit-tap-highlight-color: transparent;
        }}
        #skip-btn:hover {{ background: rgba(0,0,0,0.78); }}

        /* === spinner 条（位于漫画上方，纵向位置） === */
        #spinner-bar {{
          width: 100%;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 14px 0 10px;
          opacity: 0;
          transition: opacity 0.4s ease;
          pointer-events: none;
        }}
        #spinner-bar.show {{ opacity: 1; }}
        .spin-ring {{
          width: 36px; height: 36px;
          border: 3px solid rgba(255,255,255,0.15);
          border-top-color: #25b4e1;
          border-radius: 50%;
          animation: spinR 0.85s linear infinite;
        }}
        @keyframes spinR {{ to {{ transform: rotate(360deg); }} }}
        #spinner-txt {{
          margin-top: 8px;
          font-size: 12px; font-weight: 700;
          color: rgba(255,255,255,0.75);
          letter-spacing: 0.03em;
        }}

        /* === spinner 叠加层（保留，仅用于 done 前的遮罩） === */
        #spinner-overlay {{
          position: absolute;
          inset: 0;
          z-index: 30;
          opacity: 0;
          pointer-events: none;
        }}

        /* === "解析完毕" 横幅（在 spinner 条位置） === */
        #done-banner {{
          width: 100%;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 10px 0 4px;
          opacity: 0;
          transition: opacity 0.4s ease;
          pointer-events: none;
        }}
        #done-banner.show {{ opacity: 1; }}
        #done-banner span {{
          background: rgba(37,180,225,0.92);
          border-radius: 999px;
          padding: 8px 24px;
          font-size: 14px; font-weight: 900;
          color: #fff;
          letter-spacing: 0.05em;
          box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }}

        /* 左右箭头 — 关于图片中心对称 */
        .nav-arrow {{
          position: absolute;
          top: 0; bottom: 0;
          width: 50px;
          display: flex; align-items: center; justify-content: center;
          z-index: 15;
          cursor: pointer;
          user-select: none;
          -webkit-tap-highlight-color: transparent;
          opacity: 0.55;
          transition: opacity 0.2s;
        }}
        .nav-arrow:hover {{ opacity: 0.9; }}
        .nav-arrow.disabled {{ opacity: 0.15; pointer-events: none; }}
        .nav-arrow.left {{ left: 0; background: linear-gradient(to right, rgba(0,0,0,0.32), transparent); }}
        .nav-arrow.right {{ right: 0; background: linear-gradient(to left, rgba(0,0,0,0.32), transparent); }}
        .nav-arrow span {{
          width: 36px; height: 36px;
          border-radius: 999px;
          display: flex; align-items: center; justify-content: center;
          background: rgba(255,255,255,0.12);
          border: 1px solid rgba(255,255,255,0.15);
          color: rgba(255,255,255,0.88);
          font-size: 20px; font-weight: 900;
          backdrop-filter: blur(6px);
        }}
      </style>
    </head>
    <body>

      <!-- 面板1：欢迎（进度条 + 欢迎弹窗，同一整体） -->
      <div id="welcome-panel">
        <div class="wp-prog"><div id="prog-w"></div></div>
        <div id="wp-body">
          <div id="wp-icon">🏔️</div>
          <div id="wp-title">欢迎您来到<br/>{display_name}</div>
          <div id="wp-sub">正在为您加载山海路线…</div>
        </div>
      </div>

      <!-- 面板2：漫画（独立，无进度条） -->
      <div id="cartoon-wrap">
        <!-- spinner 条（在漫画上方，纵向位置） -->
        <div id="spinner-bar">
          <div class="spin-ring"></div>
          <div id="spinner-txt">AI 正在寻迹萃取…</div>
        </div>
        <!-- spinner 遮罩层（done 前给漫画加半透明遮罩） -->
        <div id="spinner-overlay"></div>
        <div id="stage">
          <div class="nav-arrow left disabled" id="prev-btn" title="上一页"><span>‹</span></div>
          <div class="nav-arrow right" id="next-btn" title="下一页"><span>›</span></div>
          <img id="imgA" />
          <img id="imgB" />
          <div id="province-tag">{display_name} · 山海漫画</div>
          <div id="page-info">{total}页</div>
          <div id="skip-btn">跳过漫画 ✕</div>
          <!-- 解析完毕横幅（在 spinner 位置） -->
          <div id="done-banner"><span>🎉 解析完毕！</span></div>
        </div>
      </div>

      <script>
        const images = {images_json};
        const TOTAL_DURATION = 10000;   // 总共10秒
        const WELCOME_DURATION = 2000;  // 前2秒：欢迎面板
        const total = {total};

        const progW = document.getElementById('prog-w');
        const welcomePanel = document.getElementById('welcome-panel');
        const cartoonWrap = document.getElementById('cartoon-wrap');
        const wpTitle = document.getElementById('wp-title');
        const wpSub = document.getElementById('wp-sub');
        const wpIcon = document.getElementById('wp-icon');
        const imgA = document.getElementById('imgA');
        const imgB = document.getElementById('imgB');
        const skipBtn = document.getElementById('skip-btn');
        const stage = document.getElementById('stage');
        const prevBtn = document.getElementById('prev-btn');
        const nextBtn = document.getElementById('next-btn');
        const pageInfo = document.getElementById('page-info');
        const spinnerBar = document.getElementById('spinner-bar');
        const doneBanner = document.getElementById('done-banner');

        let idx = 0, showingA = true, animating = false, done = false;
        let cartoonShown = false;
        let phase = 'welcome';  // 'welcome' | 'spinner' | 'done'

        function notify() {{
          try {{ window.parent.postMessage({{ type: 'api_cartoon_done', value: true }}, '*'); }} catch(e) {{}}
          try {{ window.top.postMessage({{ type: 'api_cartoon_done', value: true }}, '*'); }} catch(e) {{}}
          try {{
            const u = new URL(window.parent.location.href);
            u.searchParams.set('api_cartoon_done', '1');
            window.parent.history.replaceState(null, '', u.toString());
          }} catch(e) {{}}
        }}

        function finish() {{
          if (done) return;
          done = true;
          phase = 'done';
          cartoonWrap.style.opacity = '0';
          cartoonWrap.style.transform = 'scale(0.97)';
          cartoonWrap.style.transition = 'opacity 0.45s ease, transform 0.45s ease';
          setTimeout(notify, 480);
        }}

        function updateNav() {{
          prevBtn.classList.toggle('disabled', idx <= 0);
          nextBtn.classList.toggle('disabled', idx >= total - 1);
          pageInfo.textContent = (idx + 1) + '/' + total;
        }}

        function renderPage() {{
          if (!images.length || animating) return;
          animating = true;
          const showEl = showingA ? imgA : imgB;
          const hideEl = showingA ? imgB : imgA;
          hideEl.classList.remove('show', 'exit-left');
          showEl.src = images[idx];
          showEl.classList.remove('exit-left');
          void showEl.offsetWidth;
          showEl.classList.add('show');
          hideEl.classList.add('exit-left');
          showingA = !showingA;
          updateNav();
          setTimeout(() => {{
            hideEl.classList.remove('exit-left', 'show');
            animating = false;
          }}, 450);
        }}

        function showCartoon() {{
          if (cartoonShown) return;
          cartoonShown = true;
          if (images.length > 0) renderPage();
          cartoonWrap.classList.add('show');
          // 漫画出现后立即显示 spinner
          setTimeout(() => {{
            if (!done && phase !== 'done') {{
              phase = 'spinner';
              spinnerBar.classList.add('show');
            }}
          }}, 100);
        }}

        function goNext() {{
          if (idx >= total - 1) {{ return; }}  // 最后一页不跳转，等待解析完成
          idx++;
          renderPage();
        }}
        function goPrev() {{
          if (idx <= 0) return;
          idx--;
          renderPage();
        }}

        // --- 统一 RAF 驱动时序 ---
        requestAnimationFrame(function start(ts) {{
          const wStart = ts;
          const progEnd = ts + WELCOME_DURATION;
          const totalEnd = ts + TOTAL_DURATION;

          function tick(now) {{
            // 阶段1：欢迎面板进度条
            const progPct = Math.min(100, Math.round((now - ts) / WELCOME_DURATION * 100));
            progW.style.width = progPct + '%';

            if (now >= ts + 1500 && wpTitle.style.opacity !== '0') {{
              wpTitle.style.opacity = '0';
              wpSub.style.opacity = '0';
              wpIcon.style.opacity = '0';
            }}

            if (now < progEnd) {{
              requestAnimationFrame(tick);
            }} else {{
              // 阶段2：欢迎面板消失，漫画+spinner出现
              progW.style.width = '100%';
              welcomePanel.classList.add('hidden');
              setTimeout(() => {{ welcomePanel.style.display = 'none'; }}, 650);
              setTimeout(showCartoon, 200);

              // 阶段3：spinner 继续跑到 10 秒，显示"解析完毕！"并通知跳转
              function tickSpinner(now2) {{
                if (done) return;
                if (now2 >= totalEnd) {{
                  done = true;
                  phase = 'done';
                  spinnerBar.classList.remove('show');
                  doneBanner.classList.add('show');
                  notify();   // 通知 Streamlit 跳转
                }} else {{
                  requestAnimationFrame(tickSpinner);
                }}
              }}
              requestAnimationFrame(tickSpinner);
            }}
          }}

          requestAnimationFrame(tick);
        }});

        // --- 跳过：隐藏漫画面板，spinner 继续跑，倒计时结束自动跳转 ---
        skipBtn.addEventListener('click', (e) => {{
          e.stopPropagation();
          cartoonWrap.style.opacity = '0';
          cartoonWrap.style.transform = 'scale(0.97)';
          cartoonWrap.style.transition = 'opacity 0.35s ease';
          // tickSpinner 已在运行，done=true 时会自动 notify
        }});

        stage.addEventListener('click', (e) => {{
          if (e.target === skipBtn || e.target.closest('.nav-arrow')) return;
          if (!cartoonShown) return;
          goNext();
        }});
        prevBtn.addEventListener('click', (e) => {{ e.stopPropagation(); goPrev(); }});
        nextBtn.addEventListener('click', (e) => {{ e.stopPropagation(); goNext(); }});

        if (images.length === 0) setTimeout(finish, 2000);
      </script>
    </body>
    </html>
    """
    components.html(html, height=560, scrolling=False)


# ============================================================
#  页面 1：视频解析（山海主题·四步解析展示）
# ============================================================


def render_parse_page():
    render_mountain_ridge()
    
    if st.session_state.demo_mode:
        st.markdown('<div class="demo-banner">Demo 模式 · 山海寻迹体验</div>', unsafe_allow_html=True)

    st.markdown(
        """
        <div style="text-align:center;padding:18px 8px 10px 8px;">
          <div style="display:inline-flex;align-items:center;justify-content:center;width:72px;height:72px;border-radius:32px;background:rgba(255,255,255,0.95);border:1px solid rgba(242,230,206,0.7);box-shadow:0 18px 50px -26px rgba(0,0,0,0.22);margin-bottom:12px;">
            <div style="font-size:26px;line-height:1;">🎬</div>
          </div>
          <div style="font-size:28px;font-weight:900;letter-spacing:-0.5px;line-height:1.15;color:var(--natural-text);">
            选择 Demo 视频<br/>
            <span style="color:var(--natural-muted);">一键生成山海地图</span>
          </div>
          <div style="margin-top:10px;font-size:12px;line-height:1.55;color:var(--natural-muted);padding:0 26px;">
            当前为 Demo 模式，仅支持导入示例视频进行体验。
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("导入网络视频（Demo 不支持）", use_container_width=True):
        st.error("Demo 模式不支持导入网络视频")

    # ---- Demo 模式 ----
    if st.session_state.demo_mode:
        render_tide_divider()
        params = _query_params_get()
        if st.session_state.get("demo_loading"):
            st.markdown('<div id="demo-load-done-anchor"></div>', unsafe_allow_html=True)
            st.markdown(
                """
                <style>
                  #demo-load-done-anchor { display: none !important; }
                  #demo-load-done-anchor + div,
                  #demo-load-done-anchor + div + div { display: none !important; }
                </style>
                """,
                unsafe_allow_html=True,
            )
            done_clicked = st.button("DEMO_LOAD_DONE", key="_demo_load_done_btn")

            if done_clicked or params.get("demo_load_done") == ["1"]:
                _query_params_clear()
                selected = st.session_state.demo_loading.get("selected") or {}
                try:
                    _save_demo_to_kb()
                    st.session_state.parse_result = get_demo_parse_result(selected["city"], selected["blogger"])
                    st.session_state.map_points = get_demo_map_points(selected["city"], selected["blogger"])
                    st.session_state.map_segments = get_demo_map_segments(selected["city"], selected["blogger"])
                    st.session_state.map_city = selected["transit_city"]
                    st.session_state.current_tab = "地图"
                finally:
                    st.session_state.demo_loading = None
                st.rerun()
            else:
                province = st.session_state.demo_loading.get("province") or "浙江省"
                images = _load_cartoon_uris(province)
                _render_demo_loading_cartoon(images, duration_sec=20)
                st.stop()

        catalog = get_demo_catalog()
        demo_catalog = {f"demo_{i}": item for i, item in enumerate(catalog)}
        
        if not catalog:
            st.error("未找到 Demo 数据文件")
        else:
            if st.session_state.demo_choice not in demo_catalog:
                st.session_state.demo_choice = "demo_0"

            st.markdown("**🎮 Demo 视频（任选其一）**")
            chosen_key = st.radio(
                "选择 Demo",
                options=list(demo_catalog.keys()),
                index=list(demo_catalog.keys()).index(st.session_state.demo_choice) if st.session_state.demo_choice in demo_catalog else 0,
                format_func=lambda k: demo_catalog[k]["label"],
                label_visibility="collapsed",
            )
            st.session_state.demo_choice = chosen_key

            selected = demo_catalog[chosen_key]
            render_tide_divider()
            if st.button("加载所选 Demo 路线 →", use_container_width=True, type="primary"):
                province = "浙江省" if "杭州" in selected.get("city", "") else "四川省" if "成都" in selected.get("city", "") else st.session_state.get("map_province", "浙江省")
                st.session_state.demo_loading = {
                    "selected": selected,
                    "province": province,
                    "cartoons": _load_cartoon_uris(province),
                }
                _query_params_clear()
                st.rerun()

            render_tide_divider()
            demo_kb = get_demo_knowledge_base()
            demo_data = demo_kb[selected["city"]][selected["blogger"]]
            st.markdown(f"""
            <div class="sh-card">
                <div class="sh-card-cover">🏞️<span class="card-badge">Demo</span></div>
                <div class="sh-card-body">
                    <div class="sh-card-title">{demo_data["video_title"]}</div>
                    <div class="sh-card-meta">🦋 {selected["blogger"]} · {demo_data["video_duration"]} · {selected["city"]}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            demo_result = get_demo_parse_result(selected["city"], selected["blogger"])
            spots = demo_data["spots"]
            for pt, spot in zip(demo_result.get("points", []), spots):
                content = pt.get("content", {})
                landmarks = content.get("landmarks", [])
                name = landmarks[0] if landmarks else "未知"
                speech = (content.get("speech", "") or "")[:30] + "..."
                env = content.get("environment", "")
                tag = spot.get("tag", "城市")
                mood = spot.get("mood", "")

                if tag == "山":
                    tag_html = '<span class="tag-mountain">⛰️ 山</span>'
                elif tag == "海":
                    tag_html = '<span class="tag-sea">🌊 海</span>'
                else:
                    tag_html = '<span class="tag-city">🏙️ 城市</span>'
                mood_html = f'<span class="tag-mood">{mood}</span>' if mood else ''

                st.markdown(f"""
                <div class="point-item">
                    <h4>📍 {name} {tag_html} {mood_html}</h4>
                    <p>🗣️ {speech}</p>
                    <p>🌿 {env}</p>
                </div>
                """, unsafe_allow_html=True)

    elif st.session_state.parse_result:
        render_tide_divider()
        st.markdown("#### 📋 解析结果")
        result = st.session_state.parse_result
        for pt in result.get("points", []):
            content = pt.get("content", {})
            landmarks = content.get("landmarks", [])
            name = landmarks[0] if landmarks else "未知"
            env = content.get("environment", "")
            st.markdown(f"""
            <div class="point-item">
                <h4>📍 {name}</h4>
                <p>🌿 {env}</p>
            </div>
            """, unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("🗑️ 清除", use_container_width=True):
                st.session_state.parse_result = None
                st.session_state.map_points = []
                st.session_state.map_segments = []
                st.rerun()

    render_sea_wave_footer()


def _save_demo_to_kb():
    """将 Demo 数据保存到知识库"""
    demo_kb = get_demo_knowledge_base()
    for city, bloggers in demo_kb.items():
        if city not in st.session_state.knowledge_base:
            st.session_state.knowledge_base[city] = {}
        st.session_state.knowledge_base[city].update(bloggers)


def _save_api_result_to_kb():
    """将正式 API 解析结果保存到知识库（供旅行规划使用）"""
    result = st.session_state.get("parse_result")
    if not result:
        return
    city = result.get("city", "未知城市")
    blogger = result.get("blogger", "未知博主")
    if city not in st.session_state.knowledge_base:
        st.session_state.knowledge_base[city] = {}
    st.session_state.knowledge_base[city][blogger] = {
        "spots": result.get("spots", []),
        "food": result.get("food", []),
        "transport": result.get("transport", []),
        "tips": result.get("tips", []),
        "video_title": result.get("video_title", ""),
        "platform": result.get("platform", ""),
    }


# ============================================================
#  页面 2：灵动地图（山海主题·流动路线）
# ============================================================

def render_map_page():
    map_points = st.session_state.map_points
    map_segments = st.session_state.map_segments
    map_city = st.session_state.map_city

    plan = st.session_state.trip_plan
    if plan and plan.get("stops"):
        stop_names = [s.get("name") for s in plan.get("stops", []) if s.get("name")]
        point_names = [p.get("name") for p in map_points if p.get("name")]
        if stop_names and stop_names != point_names:
            st.session_state.map_points = _stops_to_map_points(plan["stops"])
            st.session_state.map_segments = _stops_to_map_segments(plan["city"], plan["stops"])
            st.session_state.map_city = "杭州" if "杭州" in plan["city"] else plan["city"]
            map_points = st.session_state.map_points
            map_segments = st.session_state.map_segments
            map_city = st.session_state.map_city
    if not map_points:
        st.markdown("""
        <div style="text-align:center; padding:40px 0; color:#9ca3af;">
            <div style="font-size:48px;">🏔️</div>
            <div style="font-size:14px; margin-top:8px; color:#666;">山海灵感地图尚未就绪</div>
            <div style="font-size:12px; margin-top:4px;">请前往「寻迹」萃取视频</div>
        </div>
        """, unsafe_allow_html=True)
        return

    import streamlit.components.v1 as components
    
    if st.session_state.get("virtual_tour_mode", False):
        if st.button("🔙 关闭虚拟旅游", use_container_width=True, type="primary"):
            st.session_state.virtual_tour_mode = False
            st.rerun()
        base_image_path = os.path.join(os.path.dirname(__file__), "picture", "visual")
        tour_html = generate_immersive_tour_html(map_points, base_image_path)
        components.html(tour_html, height=700, scrolling=False)
    else:
        if st.button("🎬 开始虚拟旅游", use_container_width=True, type="primary"):
            st.session_state.virtual_tour_mode = True
            st.rerun()
        map_html = generate_map_html(
            map_points,
            map_segments,
            transit_city=map_city,
        )
        components.html(map_html, height=620, scrolling=False)

    with st.expander(f"📍 {len(map_points)} 个地点", expanded=False):
        for i, pt in enumerate(map_points):
            ticket_str = f" · 🎫 {pt.get('ticket', '')}" if pt.get('ticket') else ""
            tag = pt.get('tag', '城市')
            if tag == "山":
                tag_html = '<span class="tag-mountain">⛰️</span>'
            elif tag == "海":
                tag_html = '<span class="tag-sea">🌊</span>'
            else:
                tag_html = '<span class="tag-city">🏙️</span>'
            mood_html = f'<span class="tag-mood">{pt.get("mood","")}</span>' if pt.get("mood") else ''
            
            st.markdown(f"""
            <div class="point-item">
                <h4>{i+1}. {pt['name']} {tag_html} {mood_html}{ticket_str}</h4>
                <p>🌤️ {pt['weather']}</p>
                <p>✨ {pt.get('recommendation', '')[:40]}...</p>
            </div>
            """, unsafe_allow_html=True)

    # ---- 地图→旅行的自然过渡 ----
    if st.session_state.knowledge_base:
        render_tide_divider()
        if st.button("规划我的山海之旅 →", use_container_width=True, type="primary"):
            st.session_state.current_tab = "旅行"
            st.rerun()

    render_sea_wave_footer()


# ============================================================
#  页面 3：我的山海路线（旅行规划）
# ============================================================

def render_trip_page():
    render_mountain_ridge()
    st.markdown("### 旅行管家")

    if st.session_state.get("_plan_reset_pending"):
        components.html(
            """
            <script>
            (function () {
              const win = window.parent;
              try {
                win.history.pushState({ reset: true }, '', '/plan/new?reset=true');
              } catch (e) {}

              try {
                setTimeout(function () {
                  try {
                    if (win.location && win.location.pathname !== '/plan/new') {
                      console.error('[plan] pathname not switched within 3s:', win.location.pathname);
                    }
                  } catch (e2) {}
                }, 2800);
              } catch (e) {}

              try {
                if (!win.__plan_new_back_guard) {
                  win.__plan_new_back_guard = true;
                  win.addEventListener('popstate', function () {
                    try {
                      const ok = win.confirm('开始新规划？');
                      if (ok) {
                        win.history.pushState({ reset: true }, '', '/plan/new?reset=true');
                      } else {
                        win.history.forward();
                      }
                    } catch (e2) {}
                  });
                }
              } catch (e) {}
            })();
            </script>
            """,
            height=0,
        )
        st.session_state._plan_reset_pending = False

    kb = st.session_state.knowledge_base

    def _parse_minutes(duration_text: str) -> int:
        s = (duration_text or "").strip()
        if not s:
            return 0
        m = re.search(r"(\d+(?:\.\d+)?)\s*小时", s)
        if m:
            return int(float(m.group(1)) * 60)
        m = re.search(r"(\d+)\s*分钟", s)
        if m:
            return int(m.group(1))
        m = re.search(r"(\d+)\s*min", s, flags=re.IGNORECASE)
        if m:
            return int(m.group(1))
        m = re.search(r"(\d+)", s)
        return int(m.group(1)) if m else 0

    def _haversine_km(a: dict, b: dict) -> float:
        import math

        try:
            lat1 = float(a.get("lat"))
            lon1 = float(a.get("lng"))
            lat2 = float(b.get("lat"))
            lon2 = float(b.get("lng"))
        except Exception:
            return 0.0
        r = 6371.0
        p1 = math.radians(lat1)
        p2 = math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * r * math.asin(min(1.0, math.sqrt(x)))

    def _order_spots_nearest(spots: list[dict]) -> list[dict]:
        if len(spots) <= 2:
            return spots
        remaining = [s for s in spots]
        ordered = [remaining.pop(0)]
        while remaining:
            last = ordered[-1]
            remaining.sort(key=lambda s: _haversine_km(last, s))
            ordered.append(remaining.pop(0))
        return ordered

    def _estimate_route(spots: list[dict]) -> tuple[int, float]:
        minutes = sum(_parse_minutes(s.get("visit_duration", "")) for s in spots)
        dist = 0.0
        for i in range(len(spots) - 1):
            dist += _haversine_km(spots[i], spots[i + 1])
        return minutes, dist

    if not kb:
        st.markdown("""
        <div style="text-align:center; padding:40px 0; color:#9ca3af;">
            <div style="font-size:48px;">🧭</div>
            <div style="font-size:14px; margin-top:8px; color:#666;">还没有可规划的路线</div>
            <div style="font-size:12px; margin-top:4px;">先去「寻迹」沉淀你的灵感点</div>
        </div>
        """, unsafe_allow_html=True)
        return

    # ---- Step 1: 选择目的地 ----
    cities = list(kb.keys())
    if "trip_plan" not in st.session_state or st.session_state.trip_plan is None:
        st.markdown("**🎯 选择旅行目的地**")
        for city in cities:
            bloggers = kb[city]
            spot_count = sum(len(v.get("spots", [])) for v in bloggers.values())
            food_count = sum(len(v.get("food", [])) for v in bloggers.values())
            blogger_names = "、".join(bloggers.keys())

            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"""
                <div class="kb-city-card">
                    <div style="display:flex;align-items:center;gap:10px;">
                        <div class="kb-city-icon" style="background:linear-gradient(135deg,#d4e8d0,#7eb8da);">🏔️</div>
                        <div>
                            <div class="kb-city-name">{city}</div>
                            <div class="kb-city-sub">{blogger_names} · {spot_count}个景点 · {food_count}道美食</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with c2:
                if st.button("出发", key=f"go_{city}", use_container_width=True, type="primary"):
                    st.session_state.trip_plan = {"city": city, "route": None, "stops": [], "current_stop_idx": 0}
                    st.rerun()

        render_tide_divider()
        st.markdown("**🧳 我的旅行方案**")
        plans = [t for t in (st.session_state.saved_trips or []) if isinstance(t, dict) and str(t.get("status", "planned")) != "completed"]
        _render_my_trip_plans(plans, key_prefix="trip_page_plan", open_target="trip")

    # ---- Step 2: 选择路线（可打钩选项卡） ----
    elif st.session_state.trip_plan and st.session_state.trip_plan.get("route") is None:
        city = st.session_state.trip_plan["city"]
        st.markdown(f"**📍 {city} · 选择景点**")
        st.caption("勾选想去的景点，我们将为你规划山海路线")

        bloggers = kb.get(city, {})

        # 博主推荐路线（一键选择）
        for blogger_name, data in bloggers.items():
            spots = data.get("spots", [])
            route_summary = " → ".join([s["name"] for s in spots[:5]])
            if len(spots) > 5:
                route_summary += f" …共{len(spots)}站"

            # 统计山海标签
            mountain_count = sum(1 for s in spots if s.get("tag") == "山")
            sea_count = sum(1 for s in spots if s.get("tag") == "海")

            with st.expander(f"🦋 {blogger_name}的路线（{len(spots)}站 · {mountain_count}山{sea_count}海）"):
                st.caption(route_summary)
                selected = []
                for i, spot in enumerate(spots):
                    ticket_str = f" · 🎫 {spot.get('ticket', '')}" if spot.get('ticket') else ""
                    tag = spot.get('tag', '城市')
                    tag_icon = "⛰️" if tag == "山" else "🌊" if tag == "海" else "🏙️"
                    checked = st.checkbox(
                        f"{tag_icon} {spot.get('name','')} · ⏱ {spot.get('visit_duration', '')}{ticket_str}",
                        value=True,
                        key=f"route_spot_{city}_{blogger_name}_{i}",
                    )
                    if checked:
                        selected.append(spot)

                ordered_selected = _order_spots_nearest(selected)
                est_min, est_km = _estimate_route(ordered_selected)
                if ordered_selected:
                    st.caption(f"已选 {len(ordered_selected)}/{len(spots)} 站 · 预估停留 {est_min} 分钟 · 预估里程 {est_km:.1f} km")
                    st.caption("路线预览: " + " → ".join([s.get("name", "") for s in ordered_selected]))

                if st.button(f"✅ 采用该路线", key=f"route_{blogger_name}", use_container_width=True, type="primary", disabled=not ordered_selected):
                    st.session_state.trip_plan["route"] = blogger_name
                    st.session_state.trip_plan["stops"] = ordered_selected
                    st.session_state.trip_plan["current_stop_idx"] = 0
                    st.session_state.trip_plan["preview"] = True
                    st.session_state.map_points = _stops_to_map_points(ordered_selected)
                    st.session_state.map_segments = _stops_to_map_segments(city, ordered_selected)
                    st.session_state.map_city = "杭州" if "杭州" in city else city
                    st.rerun()

        # 自定义路线 — 可打钩选项卡
        render_tide_divider()
        st.markdown("**✏️ 自定义景点**")
        st.caption("勾选想去的地方，按勾选顺序安排行程")

        all_spots = []
        for data in bloggers.values():
            all_spots.extend(data.get("spots", []))

        seen_names = set()
        unique_spots = []
        for s in all_spots:
            if s["name"] not in seen_names:
                seen_names.add(s["name"])
                unique_spots.append(s)

        selected_spots = []
        for i, spot in enumerate(unique_spots):
            checked = st.checkbox(
                f"📍 {spot['name']}  ⏱{spot.get('visit_duration', '')}",
                value=True,
                key=f"spot_check_{city}_{i}",
            )
            if checked:
                selected_spots.append(spot)

        render_tide_divider()
        st.markdown("**➕ 我还想去**")
        st.caption("这些是 AI 根据目的地主题补充的推荐点（不一定出现在博主视频里）")
        extra_spots = _get_ai_extra_spots(city, seen_names)
        for j, spot in enumerate(extra_spots):
            checked = st.checkbox(
                f"✨ {spot['name']}  ⏱{spot.get('visit_duration', '')}",
                key=f"spot_extra_{city}_{j}",
            )
            if checked:
                selected_spots.append(spot)

        if selected_spots:
            ordered_custom = _order_spots_nearest(selected_spots)
            est_min, est_km = _estimate_route(ordered_custom)
            st.caption(f"已选 {len(ordered_custom)} 站 · 预估停留 {est_min} 分钟 · 预估里程 {est_km:.1f} km")
            st.caption("路线预览: " + " → ".join([s.get("name", "") for s in ordered_custom]))

            if st.button("🚀 开始自定义路线", use_container_width=True, type="primary"):
                st.session_state.trip_plan["route"] = "自定义"
                st.session_state.trip_plan["stops"] = ordered_custom
                st.session_state.trip_plan["current_stop_idx"] = 0
                st.session_state.trip_plan["preview"] = True
                st.session_state.map_points = _stops_to_map_points(ordered_custom)
                st.session_state.map_segments = _stops_to_map_segments(city, ordered_custom)
                st.session_state.map_city = "杭州" if "杭州" in city else city
                st.rerun()

    # ---- Step 3: 旅行进行中 ----
    elif st.session_state.trip_plan and st.session_state.trip_plan.get("route"):
        if st.session_state.trip_plan.get("preview", False):
            _render_trip_preview()
        else:
            _render_trip_active()

    render_sea_wave_footer()


def _stops_to_map_points(stops: list) -> list:
    """将知识库的 stops 转为地图标注点格式"""
    points = []
    for spot in stops:
        weather = get_weather(spot["name"])
        points.append({
            "name": spot["name"],
            "lng": spot["lng"],
            "lat": spot["lat"],
            "weather": f"{weather['weather']} {weather['temperature']}°C",
            "recommendation": spot.get("recommendation", ""),
            "speech": spot.get("speech", ""),
            "environment": spot.get("environment", ""),
            "signs": spot.get("signs", []),
            "visit_duration": spot.get("visit_duration", ""),
            "best_time": spot.get("best_time", ""),
            "ticket": spot.get("ticket", ""),
            "tag": spot.get("tag", "城市"),
            "mood": spot.get("mood", ""),
        })
    return points


def _get_ai_extra_spots(city: str, existing_names: set) -> list:
    if "杭州" not in city:
        return []
    candidates = [
        {
            "name": "三潭印月",
            "lng": 120.1602,
            "lat": 30.2428,
            "speech": "来三潭印月看西湖最灵的一面，水天一色特别治愈。",
            "environment": "湖心岛屿，三潭映月石塔，碧波荡漾",
            "signs": ["三潭印月"],
            "recommendation": "建议坐船上岛，留出1小时慢慢走，拍照点很多。",
            "visit_duration": "1小时",
            "best_time": "上午/傍晚",
            "ticket": "含船票/景区票",
            "tag": "海",
            "mood": "治愈",
        },
        {
            "name": "花港观鱼",
            "lng": 120.1589,
            "lat": 30.2443,
            "speech": "花港观鱼真的太适合散步了，边走边看锦鲤。",
            "environment": "园林水系，花木繁盛，锦鲤成群",
            "signs": ["花港观鱼"],
            "recommendation": "春天花开最美，推荐和雷峰塔/苏堤串起来走。",
            "visit_duration": "45分钟",
            "best_time": "3-5月",
            "ticket": "免费",
            "tag": "海",
            "mood": "惬意",
        },
        {
            "name": "三潭印月码头",
            "lng": 120.1705,
            "lat": 30.2526,
            "speech": "从码头坐船进湖心，西湖的风一下就变温柔了。",
            "environment": "湖滨码头，游船往来，湖风轻拂",
            "signs": ["码头", "游船"],
            "recommendation": "提前看船班次，节假日建议错峰。",
            "visit_duration": "20分钟",
            "best_time": "全天",
            "ticket": "按船票",
            "tag": "城市",
            "mood": "松弛",
        },
        {
            "name": "河坊街",
            "lng": 120.1726,
            "lat": 30.2469,
            "speech": "想吃想逛就来河坊街，烟火气很足。",
            "environment": "老街巷，手作小店，杭帮小吃",
            "signs": ["河坊街"],
            "recommendation": "晚上更热闹，适合做收尾一站补给。",
            "visit_duration": "1小时",
            "best_time": "傍晚/夜晚",
            "ticket": "免费",
            "tag": "城市",
            "mood": "热闹",
        },
        {
            "name": "龙井村",
            "lng": 120.1208,
            "lat": 30.2116,
            "speech": "去龙井村喝杯茶，看山风穿过茶园。",
            "environment": "茶园与山路，清香弥漫",
            "signs": ["龙井村"],
            "recommendation": "上午去人少，顺便逛九溪十八涧。",
            "visit_duration": "1.5小时",
            "best_time": "上午",
            "ticket": "免费",
            "tag": "山",
            "mood": "宁静",
        },
    ]
    return [s for s in candidates if s["name"] not in existing_names]


def _stops_to_map_segments(city: str, stops: list) -> list:
    """将知识库的 stops 转为地图路线段格式（含交通方式）"""
    kb = st.session_state.knowledge_base
    bloggers = kb.get(city, {})

    transport_map = {}
    for data in bloggers.values():
        for t in data.get("transport", []):
            transport_map[f"{t['from']}→{t['to']}"] = t

    segments = []
    for i in range(len(stops) - 1):
        from_spot = stops[i]
        to_spot = stops[i + 1]
        key = f"{from_spot['name']}→{to_spot['name']}"
        t_info = transport_map.get(key, {})
        mode = t_info.get("mode", "步行")

        if mode == "步行":
            route_type = "walking"
        elif mode == "公交":
            route_type = "transit"
        elif mode in ("游船", "船"):
            route_type = "driving"
        else:
            route_type = "driving"

        segments.append({
            "from": {"name": from_spot["name"], "lng": from_spot["lng"], "lat": from_spot["lat"]},
            "to": {"name": to_spot["name"], "lng": to_spot["lng"], "lat": to_spot["lat"]},
            "mode": mode,
            "route_type": route_type,
            "desc": t_info.get("desc", ""),
            "duration": t_info.get("duration", ""),
            "cost": t_info.get("cost", ""),
        })
    return segments


def generate_immersive_tour_html(spots: list, base_image_path: str = "") -> str:
    """生成沉浸式虚拟旅游体验的HTML代码"""
    import base64
    import hashlib
    import subprocess
    from pathlib import Path
    
    def image_to_data_uri(image_path):
        full_path = image_path if os.path.isabs(str(image_path)) else os.path.join(base_image_path, str(image_path))
        if not os.path.exists(full_path):
            return None
        try:
            with open(full_path, "rb") as f:
                data = base64.b64encode(f.read()).decode()
                ext = os.path.splitext(full_path)[1].lower()
                mime = "image/webp" if ext == ".webp" else "image/jpeg" if ext == ".jpeg" else "image/png"
                return f"data:{mime};base64,{data}"
        except:
            return None
    
    def discover_spot_images(spot_name: str, route_dir: str = ""):
        """自动发现新增图片：支持“景点名-1.* / 景点名-2.*”命名"""
        if not spot_name or not base_image_path or not os.path.exists(base_image_path):
            return []
        img_exts = {".jpg", ".jpeg", ".png", ".webp"}
        prefix = f"{spot_name}-"
        matches = []
        scan_root = base_image_path
        if route_dir:
            candidate = os.path.join(base_image_path, route_dir)
            if os.path.exists(candidate):
                scan_root = candidate
        for root, _, files in os.walk(scan_root):
            # 文档解包目录里是 image1.webp 这类通用命名，不参与景点匹配
            if os.path.basename(root).lower() == "words" or f"{os.sep}words{os.sep}" in root:
                continue
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in img_exts:
                    continue
                if not fn.startswith(prefix):
                    continue
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, base_image_path).replace("\\", "/")
                matches.append(rel)
        def _sort_key(p: str):
            stem = os.path.splitext(os.path.basename(p))[0]
            tail = stem[len(prefix):] if stem.startswith(prefix) else ""
            m = re.match(r"(\d+)$", tail)
            return (0, int(m.group(1))) if m else (1, stem)
        matches.sort(key=_sort_key)
        return matches
    
    def speech_to_data_uri(text: str):
        text = (text or "").strip()
        if not text:
            return None
        try:
            cache_dir = os.path.join(TEMP_DIR, "tts_cache")
            os.makedirs(cache_dir, exist_ok=True)
            key = hashlib.sha1(text.encode("utf-8")).hexdigest()
            wav_path = os.path.join(cache_dir, f"{key}.wav")
            if not os.path.exists(wav_path):
                safe_path = wav_path.replace("'", "''")
                ps_script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = 0
$synth.Volume = 100
$voice = $synth.GetInstalledVoices() | Where-Object {{$_.VoiceInfo.Culture.Name -like 'zh*'}} | Select-Object -First 1
if ($voice) {{$synth.SelectVoice($voice.VoiceInfo.Name)}}
$synth.SetOutputToWaveFile('{safe_path}')
$txt = @'
{text}
'@
$synth.Speak($txt)
$synth.Dispose()
"""
                encoded = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")
                subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            with open(wav_path, "rb") as f:
                wav_data = base64.b64encode(f.read()).decode("ascii")
            return f"data:audio/wav;base64,{wav_data}"
        except Exception:
            return None
    
    def voice_to_data_uri(city: str, blogger: str, spot_name: str):
        city = (city or "").strip()
        blogger = (blogger or "").strip()
        spot_name = (spot_name or "").strip()
        if not city or not blogger or not spot_name:
            return None
        base_voice = os.path.join(os.path.dirname(__file__), "voice")
        folder = os.path.join(base_voice, f"{city}-{blogger}")
        if not os.path.exists(folder):
            return None
        candidates = []
        for ext in (".mp3", ".wav", ".m4a", ".aac", ".ogg"):
            p = os.path.join(folder, f"{spot_name}{ext}")
            if os.path.exists(p):
                candidates.append(p)
        if not candidates:
            try:
                for p in Path(folder).glob(f"{spot_name}.*"):
                    if p.is_file() and p.suffix.lower() in {".mp3", ".wav", ".m4a", ".aac", ".ogg"}:
                        candidates.append(str(p))
            except Exception:
                return None
        if not candidates:
            return None
        chosen = candidates[0]
        ext = os.path.splitext(chosen)[1].lower()
        mime = "audio/mpeg" if ext == ".mp3" else "audio/wav" if ext == ".wav" else "audio/mp4" if ext == ".m4a" else "audio/aac" if ext == ".aac" else "audio/ogg"
        try:
            with open(chosen, "rb") as f:
                blob = f.read()
            b64 = base64.b64encode(blob).decode("ascii")
            return f"data:{mime};base64,{b64}"
        except Exception:
            return None
    
    spots_data = []
    for spot in spots:
        spot_info = {
            "name": spot.get("name", ""),
            "speech": spot.get("speech", ""),
            "recommendation": spot.get("recommendation", ""),
            "environment": spot.get("environment", ""),
            "tag": spot.get("tag", "城市"),
            "mood": spot.get("mood", ""),
            "visit_duration": spot.get("visit_duration", ""),
            "ticket": spot.get("ticket", ""),
            "audio": None,
            "images": []
        }
        spot_info["audio"] = voice_to_data_uri(spot.get("_city", ""), spot.get("_blogger", ""), spot.get("name", ""))
        if not spot_info["audio"]:
            spot_info["audio"] = speech_to_data_uri(spot.get("speech", "") or spot.get("recommendation", ""))
        merged_images = []
        merged_images.extend(spot.get("images", []) or [])
        merged_images.extend(discover_spot_images(spot.get("name", ""), spot.get("_route_image_dir", "") or ""))
        
        seen = set()
        seen_stems = set()
        for img_path in merged_images:
            if not img_path or img_path in seen:
                continue
            stem = os.path.splitext(os.path.basename(str(img_path)))[0]
            if stem in seen_stems:
                continue
            seen.add(img_path)
            seen_stems.add(stem)
            data_uri = image_to_data_uri(img_path)
            if data_uri:
                spot_info["images"].append(data_uri)
        
        spots_data.append(spot_info)
    
    spots_json = json.dumps(spots_data, ensure_ascii=False)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            html, body {{ 
                margin: 0; 
                padding: 0; 
                width: 100%; 
                height: 100%; 
                overflow: hidden; 
                background: #0a0a0f;
                font-family: Inter, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
            }}
            #tour-container {{
                position: relative;
                width: 100%;
                height: 100%;
                overflow: hidden;
            }}
            #background {{
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-size: cover;
                background-position: center;
                transition: opacity 0.8s ease, transform 1.15s ease;
                transform: scale(1.02);
            }}
            #background.next {{
                opacity: 0;
            }}
            #overlay {{
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: linear-gradient(to bottom, 
                    rgba(10,10,15,0.3) 0%, 
                    rgba(10,10,15,0.1) 30%, 
                    rgba(10,10,15,0.4) 70%, 
                    rgba(10,10,15,0.85) 100%);
                pointer-events: none;
            }}
            #sprite {{
                position: absolute;
                bottom: 150px;
                left: 50%;
                transform: translateX(-50%);
                width: 80px;
                height: 80px;
                z-index: 100;
                filter: drop-shadow(0 8px 24px rgba(0,0,0,0.5));
                transition: transform 0.1s ease;
            }}
            #sprite img {{
                width: 100%;
                height: 100%;
                object-fit: contain;
                animation: spriteFloat 1.5s ease-in-out infinite;
            }}
            @keyframes spriteFloat {{
                0%, 100% {{ transform: translateY(0); }}
                50% {{ transform: translateY(-8px); }}
            }}
            #info-panel {{
                position: absolute;
                bottom: 0;
                left: 0;
                right: 0;
                padding: 20px 16px 100px 16px;
                background: linear-gradient(to top, 
                    rgba(10,10,15,0.98) 0%, 
                    rgba(10,10,15,0.9) 60%, 
                    transparent 100%);
                z-index: 50;
            }}
            #spot-name {{
                font-size: 24px;
                font-weight: 900;
                color: #fff;
                margin-bottom: 8px;
                text-shadow: 0 2px 8px rgba(0,0,0,0.5);
            }}
            #spot-description {{
                font-size: 14px;
                color: rgba(255,255,255,0.8);
                line-height: 1.6;
                margin-bottom: 12px;
                text-shadow: 0 1px 4px rgba(0,0,0,0.4);
            }}
            #spot-meta {{
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
                margin-bottom: 12px;
            }}
            .meta-chip {{
                padding: 4px 10px;
                border-radius: 16px;
                font-size: 11px;
                font-weight: 700;
                background: rgba(255,255,255,0.15);
                color: #fff;
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255,255,255,0.2);
            }}
            .meta-chip.mountain {{ background: rgba(74,103,65,0.4); border-color: rgba(74,103,65,0.6); }}
            .meta-chip.sea {{ background: rgba(126,184,218,0.4); border-color: rgba(126,184,218,0.6); }}
            .meta-chip.city {{ background: rgba(255,107,107,0.4); border-color: rgba(255,107,107,0.6); }}
            #progress-bar {{
                position: absolute;
                top: 0;
                left: 0;
                height: 3px;
                background: linear-gradient(90deg, #ff6b6b, #25b4e1);
                transition: width 0.3s ease;
                z-index: 200;
            }}
            #controls {{
                position: absolute;
                bottom: 20px;
                left: 16px;
                right: 16px;
                display: flex;
                gap: 10px;
                z-index: 100;
            }}
            .control-btn {{
                flex: 1;
                padding: 14px 0;
                border: none;
                border-radius: 16px;
                font-size: 14px;
                font-weight: 900;
                cursor: pointer;
                transition: all 0.2s ease;
                backdrop-filter: blur(10px);
            }}
            .control-btn[disabled] {{
                opacity: 0.5;
                cursor: default;
                pointer-events: none;
            }}
            .control-btn:active {{ transform: scale(0.98); }}
            .control-btn.primary {{
                background: linear-gradient(135deg, #ff6b6b, #ff2442);
                color: #fff;
                box-shadow: 0 10px 30px -10px rgba(255,36,66,0.5);
            }}
            .control-btn.secondary {{
                background: rgba(255,255,255,0.15);
                color: #fff;
                border: 1px solid rgba(255,255,255,0.2);
            }}
            #top-bar {{
                position: absolute;
                top: 16px;
                left: 16px;
                right: 16px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                z-index: 100;
            }}
            #tour-status {{
                padding: 8px 14px;
                background: rgba(255,255,255,0.15);
                border-radius: 20px;
                font-size: 12px;
                font-weight: 800;
                color: #fff;
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255,255,255,0.2);
            }}
            #top-bar-right {{
                display: flex;
                gap: 8px;
                align-items: center;
            }}
            #image-counter {{
                padding: 6px 10px;
                background: rgba(0,0,0,0.4);
                border-radius: 12px;
                font-size: 11px;
                color: rgba(255,255,255,0.8);
                backdrop-filter: blur(8px);
            }}
            #mute-btn {{
                width: 36px;
                height: 36px;
                border: none;
                border-radius: 50%;
                background: rgba(0,0,0,0.5);
                color: #fff;
                font-size: 16px;
                cursor: pointer;
                backdrop-filter: blur(8px);
                border: 1px solid rgba(255,255,255,0.2);
                transition: all 0.2s ease;
            }}
            #mute-btn:active {{ transform: scale(0.95); }}
            #mute-btn.muted {{ opacity: 0.7; }}
            #volume-slider {{
                width: 96px;
                accent-color: #25b4e1;
            }}
            #loading-overlay {{
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: #0a0a0f;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                z-index: 500;
                transition: opacity 0.5s ease;
            }}
            #loading-overlay.hidden {{ opacity: 0; pointer-events: none; }}
            .loading-spinner {{
                width: 50px;
                height: 50px;
                border: 3px solid rgba(255,255,255,0.1);
                border-top-color: #25b4e1;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }}
            @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
            .loading-text {{
                margin-top: 16px;
                color: rgba(255,255,255,0.7);
                font-size: 13px;
                font-weight: 700;
            }}
            #log-panel {{
                position: absolute;
                top: 60px;
                left: 16px;
                right: 16px;
                max-height: 120px;
                overflow-y: auto;
                background: rgba(0,0,0,0.5);
                border-radius: 12px;
                padding: 10px;
                font-size: 10px;
                color: rgba(255,255,255,0.7);
                z-index: 90;
                display: none;
            }}
            .log-entry {{ margin: 2px 0; padding: 2px 0; }}
            .log-entry.success {{ color: #4ade80; }}
            .log-entry.error {{ color: #f87171; }}
            .log-entry.info {{ color: #60a5fa; }}
        </style>
    </head>
    <body>
        <div id="tour-container">
            <div id="progress-bar" style="width: 0%;"></div>
            
            <div id="loading-overlay">
                <div class="loading-spinner"></div>
                <div class="loading-text" id="loading-text">正在加载资源...</div>
            </div>
            
            <div id="background"></div>
            <div id="background" class="next"></div>
            <div id="overlay"></div>
            
            <div id="top-bar">
                <div id="tour-status">第 1 / {len(spots_data)} 站</div>
                <div id="top-bar-right">
                    <div id="image-counter">📷 0 / 0</div>
                    <button id="mute-btn">🔊</button>
                    <input id="volume-slider" type="range" min="0" max="1" step="0.05" value="1" title="音量" />
                </div>
            </div>
            
            <div id="log-panel"></div>
            
            <div id="info-panel">
                <div id="spot-name">准备开始</div>
                <div id="spot-description">点击开始按钮，开启沉浸式虚拟旅游体验！</div>
                <div id="spot-meta"></div>
            </div>
            
            <div id="controls">
                <button class="control-btn secondary" id="btn-prev">⏮ 上一站</button>
                <button class="control-btn primary" id="btn-play">▶ 开始游览</button>
                <button class="control-btn secondary" id="btn-next">下一站 ⏭</button>
            </div>
        </div>
        
        <script>
            const spots = {spots_json};
            let currentSpotIndex = 0;
            let currentImageIndex = 0;
            let isPlaying = false;
            let isPaused = false;
            let speechSynthesis = window.speechSynthesis;
            let currentUtterance = null;
            let preloadedImages = {{}};
            let preloadedAudios = {{}};
            let spotChangeTimeout = null;
            let imageRotateInterval = null;
            let autoNextTimeout = null;
            let speechKeepAliveInterval = null;
            let selectedVoice = null;
            const STAY_DURATION = 8000; // 每个景点停留8秒
            
            const bg1 = document.querySelectorAll('#background')[0];
            const bg2 = document.querySelectorAll('#background')[1];
            const spotName = document.getElementById('spot-name');
            const spotDesc = document.getElementById('spot-description');
            const spotMeta = document.getElementById('spot-meta');
            const tourStatus = document.getElementById('tour-status');
            const imageCounter = document.getElementById('image-counter');
            const progressBar = document.getElementById('progress-bar');
            const loadingOverlay = document.getElementById('loading-overlay');
            const loadingText = document.getElementById('loading-text');
            const logPanel = document.getElementById('log-panel');
            const btnPlay = document.getElementById('btn-play');
            const btnPrev = document.getElementById('btn-prev');
            const btnNext = document.getElementById('btn-next');
            const muteBtn = document.getElementById('mute-btn');
            const volumeSlider = document.getElementById('volume-slider');
            const narrationAudio = new Audio();
            narrationAudio.preload = 'auto';
            narrationAudio.playsInline = true;
            let isMuted = false;
            let currentVolume = 1;
            let narrationToken = 0;
            
            function log(msg, type = 'info') {{
                const entry = document.createElement('div');
                entry.className = 'log-entry ' + type;
                entry.textContent = `[${{new Date().toLocaleTimeString()}}] ${{msg}}`;
                logPanel.appendChild(entry);
                logPanel.scrollTop = logPanel.scrollHeight;
                console.log(msg);
            }}
            
            function getSpotImages(spot) {{
                return Array.isArray(spot && spot.images) ? spot.images : [];
            }}
            
            function preloadAudioForIndex(index) {{
                if (index < 0 || index >= spots.length) return;
                const spot = spots[index];
                const src = (spot && spot.audio) ? spot.audio : '';
                if (!src || preloadedAudios[src]) return;
                try {{
                    const a = new Audio();
                    a.preload = 'auto';
                    a.src = src;
                    a.load();
                    preloadedAudios[src] = a;
                }} catch (e) {{}}
            }}
            
            function preloadNextAudios() {{
                for (let i = 1; i <= 3; i++) {{
                    preloadAudioForIndex(currentSpotIndex + i);
                }}
            }}
            
            function pickPreferredVoice() {{
                if (!speechSynthesis || typeof speechSynthesis.getVoices !== 'function') return null;
                const voices = speechSynthesis.getVoices() || [];
                if (!voices.length) return null;
                return (
                    voices.find(v => /^zh(-|_)?CN/i.test(v.lang)) ||
                    voices.find(v => /^zh/i.test(v.lang)) ||
                    voices[0]
                );
            }}
            
            function initSpeech() {{
                if (!speechSynthesis) return;
                selectedVoice = pickPreferredVoice();
                if (typeof speechSynthesis.onvoiceschanged !== 'undefined') {{
                    speechSynthesis.onvoiceschanged = () => {{
                        selectedVoice = pickPreferredVoice();
                    }};
                }}
            }}
            
            function preloadImage(src, index) {{
                return new Promise((resolve) => {{
                    if (preloadedImages[src]) {{
                        resolve(preloadedImages[src]);
                        return;
                    }}
                    const img = new Image();
                    img.onload = () => {{
                        preloadedImages[src] = img;
                        log(`图片预加载完成: 第${{index+1}}站`, 'success');
                        resolve(img);
                    }};
                    img.onerror = () => {{
                        log(`图片加载失败: 第${{index+1}}站`, 'error');
                        resolve(null);
                    }};
                    img.src = src;
                }});
            }}
            
            async function preloadResources() {{
                log('开始预加载资源...');
                let loaded = 0;
                let total = 0;
                
                for (let i = 0; i < spots.length; i++) {{
                    const spot = spots[i];
                    total += getSpotImages(spot).length;
                }}
                
                for (let i = 0; i < spots.length; i++) {{
                    const spot = spots[i];
                    const images = getSpotImages(spot);
                    for (let j = 0; j < Math.min(3, images.length); j++) {{
                        if (images[j]) {{
                            await preloadImage(images[j], i);
                            loaded++;
                            const denominator = Math.max(1, Math.min(total, spots.length * 3));
                            const pct = Math.round((loaded / denominator) * 100);
                            loadingText.textContent = `正在加载资源... ${{pct}}%`;
                            progressBar.style.width = pct + '%';
                        }}
                    }}
                }}
                
                log('资源预加载完成', 'success');
                setTimeout(() => {{
                    loadingOverlay.classList.add('hidden');
                }}, 500);
            }}
            
            function setBackground(src, smooth = true) {{
                const currentBg = bg1.style.opacity !== '0' ? bg1 : bg2;
                const nextBg = bg1.style.opacity !== '0' ? bg2 : bg1;
                
                if (!src) {{
                    nextBg.style.background = 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)';
                }} else {{
                    nextBg.style.backgroundImage = `url(${{src}})`;
                }}
                nextBg.style.backgroundSize = 'cover';
                nextBg.style.backgroundPosition = 'center';
                
                if (smooth) {{
                    currentBg.style.transition = 'opacity 0.8s ease, transform 1.15s ease';
                    nextBg.style.transition = 'opacity 0.8s ease, transform 1.15s ease';
                    nextBg.style.opacity = '0';
                    nextBg.style.transform = 'scale(1.03)';
                    currentBg.style.transform = 'scale(1.00)';
                    requestAnimationFrame(() => {{
                        currentBg.style.opacity = '0';
                        currentBg.style.transform = 'scale(1.04)';
                        nextBg.style.opacity = '1';
                        nextBg.style.transform = 'scale(1.00)';
                    }});
                }} else {{
                    currentBg.style.opacity = '0';
                    nextBg.style.opacity = '1';
                    currentBg.style.transform = 'scale(1.02)';
                    nextBg.style.transform = 'scale(1.00)';
                }}
            }}
            
            function getTagClass(tag) {{
                if (tag === '山') return 'mountain';
                if (tag === '海') return 'sea';
                return 'city';
            }}
            
            function updateSpotInfo() {{
                const spot = spots[currentSpotIndex];
                
                spotName.textContent = spot.name;
                spotDesc.textContent = spot.recommendation || spot.speech || spot.environment || '';
                
                spotMeta.innerHTML = '';
                if (spot.tag) {{
                    const tagChip = document.createElement('div');
                    tagChip.className = 'meta-chip ' + getTagClass(spot.tag);
                    tagChip.textContent = (spot.tag === '山' ? '⛰️ ' : spot.tag === '海' ? '🌊 ' : '🏙️ ') + spot.tag;
                    spotMeta.appendChild(tagChip);
                }}
                if (spot.mood) {{
                    const moodChip = document.createElement('div');
                    moodChip.className = 'meta-chip';
                    moodChip.textContent = '✨ ' + spot.mood;
                    spotMeta.appendChild(moodChip);
                }}
                if (spot.visit_duration) {{
                    const timeChip = document.createElement('div');
                    timeChip.className = 'meta-chip';
                    timeChip.textContent = '⏱ ' + spot.visit_duration;
                    spotMeta.appendChild(timeChip);
                }}
                if (spot.ticket) {{
                    const ticketChip = document.createElement('div');
                    ticketChip.className = 'meta-chip';
                    ticketChip.textContent = '🎫 ' + spot.ticket;
                    spotMeta.appendChild(ticketChip);
                }}
                
                tourStatus.textContent = `第 ${{currentSpotIndex + 1}} / ${{spots.length}} 站`;
                
                currentImageIndex = 0;
                updateImageCounter();
                updateBackground();
                updateNavButtons();
            }}
            
            function updateNavButtons() {{
                const isFirst = currentSpotIndex <= 0;
                const isLast = currentSpotIndex >= spots.length - 1;
                btnPrev.disabled = isFirst;
                btnNext.disabled = isLast;
                btnPrev.title = isFirst ? '已是第一站' : '上一站';
                btnNext.title = isLast ? '已是最后一站' : '下一站';
            }}
            
            function updateImageCounter() {{
                const spot = spots[currentSpotIndex];
                const totalImages = getSpotImages(spot).length || 1;
                imageCounter.textContent = `📷 ${{currentImageIndex + 1}} / ${{totalImages}}`;
            }}
            
            function updateBackground() {{
                const spot = spots[currentSpotIndex];
                const images = getSpotImages(spot);
                if (images.length > 0) {{
                    setBackground(images[currentImageIndex % images.length]);
                }} else {{
                    setBackground(null);
                }}
            }}
            
            function clearAutoNext() {{
                if (autoNextTimeout) {{
                    clearTimeout(autoNextTimeout);
                    autoNextTimeout = null;
                }}
            }}

            function armAutoNextByTimeout(ms, token) {{
                clearAutoNext();
                const wait = Math.max(250, Number(ms) || 0);
                autoNextTimeout = setTimeout(() => {{
                    if (token !== narrationToken) return;
                    if (isPlaying && !isPaused) {{
                        nextSpot();
                    }}
                }}, wait);
            }}

            function estimateSpeechMs(text) {{
                const n = String(text || '').trim().length;
                const base = Math.max(8000, n * 520 + 4000);
                return Math.min(240000, base);
            }}

            function speakWithAutoNext(text, token) {{
                if (!text) {{
                    armAutoNextByTimeout(STAY_DURATION, token);
                    return;
                }}
                if (!speechSynthesis || typeof SpeechSynthesisUtterance === 'undefined') {{
                    armAutoNextByTimeout(STAY_DURATION, token);
                    return;
                }}
                cancelSpeechSafe(false);
                currentUtterance = new SpeechSynthesisUtterance(text);
                currentUtterance.lang = 'zh-CN';
                currentUtterance.rate = 1.0;
                currentUtterance.pitch = 1.0;
                currentUtterance.volume = currentVolume;
                if (selectedVoice) {{
                    currentUtterance.voice = selectedVoice;
                    currentUtterance.lang = selectedVoice.lang || 'zh-CN';
                }}
                currentUtterance.onend = () => {{
                    if (token !== narrationToken) return;
                    if (isPlaying && !isPaused) {{
                        nextSpot();
                    }}
                }};
                try {{
                    speechSynthesis.speak(currentUtterance);
                    if (typeof speechSynthesis.resume === 'function') {{
                        setTimeout(() => speechSynthesis.resume(), 80);
                    }}
                }} catch (err) {{
                    armAutoNextByTimeout(STAY_DURATION, token);
                    return;
                }}
                armAutoNextByTimeout(estimateSpeechMs(text), token);
            }}
            
            function playSpotAudio(spot) {{
                const token = ++narrationToken;
                clearAutoNext();
                narrationAudio.onended = null;
                narrationAudio.onloadedmetadata = null;
                narrationAudio.onerror = null;
                if (!spot || !isPlaying || isPaused) return;
                if (isMuted) {{
                    armAutoNextByTimeout(STAY_DURATION, token);
                    return;
                }}
                const text = spot.speech || spot.recommendation || ('欢迎来到' + spot.name);
                const audioSrc = spot.audio || '';
                if (audioSrc) {{
                    cancelSpeechSafe(false);
                    try {{
                        narrationAudio.pause();
                        narrationAudio.currentTime = 0;
                        narrationAudio.src = audioSrc;
                        narrationAudio.volume = currentVolume;

                        narrationAudio.onended = () => {{
                            if (token !== narrationToken) return;
                            if (isPlaying && !isPaused) {{
                                nextSpot();
                            }}
                        }};
                        narrationAudio.onloadedmetadata = () => {{
                            if (token !== narrationToken) return;
                            const d = Number(narrationAudio.duration);
                            if (Number.isFinite(d) && d > 0) {{
                                const remain = Math.max(0, (d - (Number(narrationAudio.currentTime) || 0)) * 1000);
                                armAutoNextByTimeout(remain + 650, token);
                            }} else {{
                                armAutoNextByTimeout(240000, token);
                            }}
                        }};
                        narrationAudio.onerror = () => {{
                            if (token !== narrationToken) return;
                            speakWithAutoNext(text, token);
                        }};

                        const p = narrationAudio.play();
                        if (p && typeof p.catch === 'function') {{
                            p.catch(() => {{
                                speakWithAutoNext(text, token);
                            }});
                        }}
                        const d = Number(narrationAudio.duration);
                        if (Number.isFinite(d) && d > 0) {{
                            const remain = Math.max(0, (d - (Number(narrationAudio.currentTime) || 0)) * 1000);
                            armAutoNextByTimeout(remain + 650, token);
                        }} else {{
                            armAutoNextByTimeout(240000, token);
                        }}
                        return;
                    }} catch (e) {{
                        log('音频播放失败，自动回退到系统语音', 'error');
                    }}
                }}
                speakWithAutoNext(text, token);
            }}
            
            function cancelSpeechSafe(stopAudio = true) {{
                if (speechSynthesis && typeof speechSynthesis.cancel === 'function') {{
                    speechSynthesis.cancel();
                }}
                if (stopAudio) {{
                    try {{
                        narrationAudio.pause();
                        narrationAudio.currentTime = 0;
                    }} catch (e) {{}}
                }}
            }}
            
            function startSpeechKeepAlive() {{
                stopSpeechKeepAlive();
                if (!speechSynthesis || typeof speechSynthesis.resume !== 'function') return;
                speechKeepAliveInterval = setInterval(() => {{
                    if (isPlaying && !isPaused && !isMuted) {{
                        try {{ speechSynthesis.resume(); }} catch (e) {{}}
                    }}
                }}, 1500);
            }}
            
            function stopSpeechKeepAlive() {{
                if (speechKeepAliveInterval) {{
                    clearInterval(speechKeepAliveInterval);
                    speechKeepAliveInterval = null;
                }}
            }}
            
            function toggleMute() {{
                isMuted = !isMuted;
                muteBtn.textContent = isMuted ? '🔇' : '🔊';
                muteBtn.classList.toggle('muted', isMuted);
                if (isMuted) {{
                    cancelSpeechSafe();
                    clearAutoNext();
                    if (isPlaying && !isPaused) {{
                        const token = ++narrationToken;
                        armAutoNextByTimeout(STAY_DURATION, token);
                    }}
                }} else if (isPlaying && !isPaused) {{
                    const spot = spots[currentSpotIndex];
                    playSpotAudio(spot);
                }}
            }}
            
            function setVolume(v) {{
                const n = Number(v);
                if (Number.isFinite(n)) {{
                    currentVolume = Math.max(0, Math.min(1, n));
                    narrationAudio.volume = currentVolume;
                }}
            }}

            function pauseNarration() {{
                clearAutoNext();
                cancelSpeechSafe(false);
                try {{
                    narrationAudio.pause();
                }} catch (e) {{}}
            }}

            function resumeNarrationOrRestart() {{
                if (isMuted) {{
                    const token = ++narrationToken;
                    armAutoNextByTimeout(STAY_DURATION, token);
                    return;
                }}
                try {{
                    const canResume = narrationAudio.src && narrationAudio.paused && (Number(narrationAudio.currentTime) || 0) > 0 && !narrationAudio.ended;
                    if (canResume) {{
                        const token = narrationToken;
                        const p = narrationAudio.play();
                        if (p && typeof p.catch === 'function') {{
                            p.catch(() => {{
                                playSpotAudio(spots[currentSpotIndex]);
                            }});
                        }}
                        const d = Number(narrationAudio.duration);
                        if (Number.isFinite(d) && d > 0) {{
                            const remain = Math.max(0, (d - (Number(narrationAudio.currentTime) || 0)) * 1000);
                            armAutoNextByTimeout(remain + 650, token);
                        }} else {{
                            armAutoNextByTimeout(240000, token);
                        }}
                        return;
                    }}
                }} catch (e) {{}}
                playSpotAudio(spots[currentSpotIndex]);
            }}
            
            function startImageRotation() {{
                stopImageRotation();
                const spot = spots[currentSpotIndex];
                const images = getSpotImages(spot);
                if (images.length > 1) {{
                    imageRotateInterval = setInterval(() => {{
                        currentImageIndex = (currentImageIndex + 1) % images.length;
                        updateImageCounter();
                        updateBackground();
                    }}, 4000);
                }}
            }}
            
            function stopImageRotation() {{
                if (imageRotateInterval) {{
                    clearInterval(imageRotateInterval);
                    imageRotateInterval = null;
                }}
            }}
            
            function goToSpot(index) {{
                clearTimeout(spotChangeTimeout);
                clearAutoNext();
                stopImageRotation();
                cancelSpeechSafe();
                
                currentSpotIndex = Math.max(0, Math.min(index, spots.length - 1));
                updateSpotInfo();
                preloadNextAudios();
                startImageRotation();
                
                if (isPlaying && !isPaused) {{
                    const spot = spots[currentSpotIndex];
                    playSpotAudio(spot);
                }}
            }}
            
            function nextSpot() {{
                if (currentSpotIndex < spots.length - 1) {{
                    goToSpot(currentSpotIndex + 1);
                }} else {{
                    isPlaying = false;
                    btnPlay.textContent = '🔄 重新开始';
                    stopSpeechKeepAlive();
                    log('游览完成', 'success');
                }}
            }}
            
            function prevSpot() {{
                goToSpot(currentSpotIndex - 1);
            }}
            
            function togglePlay() {{
                if (!isPlaying) {{
                    isPlaying = true;
                    isPaused = false;
                    btnPlay.textContent = '⏸ 暂停';
                    log('开始游览', 'info');
                    const spot = spots[currentSpotIndex];
                    playSpotAudio(spot);
                    startImageRotation();
                    startSpeechKeepAlive();
                }} else {{
                    if (isPaused) {{
                        isPaused = false;
                        btnPlay.textContent = '⏸ 暂停';
                        resumeNarrationOrRestart();
                        startSpeechKeepAlive();
                    }} else {{
                        isPaused = true;
                        btnPlay.textContent = '▶ 继续';
                        stopSpeechKeepAlive();
                        pauseNarration();
                    }}
                }}
            }}
            
            btnPlay.addEventListener('click', togglePlay);
            btnNext.addEventListener('click', () => {{ if (!btnNext.disabled) goToSpot(currentSpotIndex + 1); }});
            btnPrev.addEventListener('click', () => {{ if (!btnPrev.disabled) goToSpot(currentSpotIndex - 1); }});
            muteBtn.addEventListener('click', toggleMute);
            volumeSlider.addEventListener('input', (e) => {{ setVolume(e.target.value); }});
            
            bg1.addEventListener('click', () => {{
                const spot = spots[currentSpotIndex];
                const images = getSpotImages(spot);
                if (images.length > 1) {{
                    currentImageIndex = (currentImageIndex + 1) % images.length;
                    updateImageCounter();
                    updateBackground();
                }}
            }});
            
            window.addEventListener('load', () => {{
                initSpeech();
                setVolume(volumeSlider.value);
                updateSpotInfo();
                preloadNextAudios();
                preloadResources();
            }});
        </script>
    </body>
    </html>
    """
    return html


def _render_trip_preview():
    def _strip_html_tags(val) -> str:
        s = "" if val is None else str(val)
        s = re.sub(r"<[^>]*?>", "", s)
        return s.strip()

    plan = st.session_state.trip_plan or {}
    city = _strip_html_tags(plan.get("city", ""))
    route = _strip_html_tags(plan.get("route", ""))
    stops = plan.get("stops") or []

    st.markdown(f"### 📋 计划预览：{city} · {route}")
    if not stops:
        st.info("暂无可预览的景点")
        return

    if "options" not in plan or not isinstance(plan.get("options"), dict):
        plan["options"] = {}
    options: dict = plan["options"]

    now = datetime.now()
    default_start = itinerary.round_to_hour(now)
    options.setdefault("start_dt", default_start.isoformat(timespec="minutes"))

    def _parse_dt(s: str) -> datetime:
        try:
            return datetime.fromisoformat(str(s))
        except Exception:
            return default_start

    start_dt = _parse_dt(options.get("start_dt"))
    if start_dt < now:
        start_dt = default_start
        options["start_dt"] = start_dt.isoformat(timespec="minutes")

    end_dt = itinerary.default_end_datetime(start_dt, stops)

    top1, top2, top3 = st.columns(3)
    with top1:
        if st.button("💾 保存", use_container_width=True, type="primary"):
            plan["status"] = "planned"
            plan["preview"] = True
            _save_trip_plan()
            st.session_state.trip_plan = None
            st.session_state._plan_reset_pending = True
            st.rerun()
    with top2:
        if st.button("🚀 立即开始", use_container_width=True):
            plan["status"] = "active"
            plan["preview"] = False
            _save_trip_plan()
            st.rerun()
    with top3:
        if st.button("🔄 新规划", use_container_width=True):
            st.session_state.trip_plan = None
            st.rerun()

    prev_preview = plan.get("itinerary_preview") if isinstance(plan.get("itinerary_preview"), dict) else None
    signature = json.dumps({"start": options.get("start_dt")}, ensure_ascii=False, sort_keys=True)
    prev_sig = str(plan.get("_opt_signature") or "")
    should_replan = prev_preview is None or signature != prev_sig
    if should_replan:
        try:
            rr = itinerary.replan_itinerary(
                base_plan=plan,
                stops=stops,
                now=now,
                start_dt=start_dt,
                end_dt=end_dt,
                budget_amount=None,
                budget_currency="CNY",
                extra_options={},
                prev_preview=prev_preview,
            )
            plan["itinerary_preview"] = rr.preview
            plan["itinerary_version"] = rr.preview.get("version")
            plan["itinerary_checksum"] = rr.preview.get("checksum")
            plan["_opt_signature"] = signature
        except Exception as e:
            st.error(f"预览生成失败：{e}")
            st.stop()

    cur_preview = plan.get("itinerary_preview") if isinstance(plan.get("itinerary_preview"), dict) else {}
    days = cur_preview.get("days") if isinstance(cur_preview.get("days"), list) else []

    st.markdown("#### 🗓️ 行程预览")
    for d in days:
        date_str = str(d.get("date", ""))
        st.markdown(f"**{date_str}**")
        for it in d.get("items", []):
            spot_name = _strip_html_tags(it.get("spot_name", ""))
            st_s = str(it.get("start", ""))
            en_s = str(it.get("end", ""))
            time_range = ""
            if "T" in st_s and "T" in en_s:
                time_range = st_s.split("T", 1)[1] + " - " + en_s.split("T", 1)[1]
            st.markdown(
                f"""
                <div style="background:white;border-radius:14px;padding:10px 12px;margin:8px 0;border:1px solid rgba(212,232,245,0.9);box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                  <div style="font-weight:900;color:#111827;">{_html.escape(time_range)} · {_html.escape(spot_name)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with st.expander("⚙️ 调整出发时间", expanded=False):
        d1, d2, d3 = st.columns([3, 2, 1])
        with d1:
            sd = st.date_input("出发日期", value=start_dt.date(), key="_opt_start_date_only")
        with d2:
            hour_str = st.selectbox(
                "小时",
                options=[f"{i:02d}" for i in range(24)],
                index=int(start_dt.hour),
                key="_opt_start_hour_only",
            )
        with d3:
            if st.button("马上开始", use_container_width=True, key="_opt_start_now_btn"):
                start_dt2 = itinerary.round_to_hour(datetime.now())
                options["start_dt"] = start_dt2.isoformat(timespec="minutes")
                st.rerun()
        start_dt2 = datetime(sd.year, sd.month, sd.day, int(hour_str), 0, 0)
        if start_dt2 < datetime.now():
            st.error("出发时间不得早于当前系统时间")
        else:
            if options.get("start_dt") != start_dt2.isoformat(timespec="minutes"):
                options["start_dt"] = start_dt2.isoformat(timespec="minutes")
                st.rerun()


def _render_navigation_tip(render_data: dict) -> None:
    if not render_data:
        return
    next_name = str(render_data.get("next_name") or "").strip()
    if not next_name:
        return
    st.markdown(f"**🗺️ 顺着风景去下一站**（第{render_data.get('step','')}/{render_data.get('total','')}站）")
    st.markdown(f"📍 {next_name}")
    weather_line = str(render_data.get("next_weather") or "").strip()
    duration_line = str(render_data.get("next_duration") or "").strip()
    parts = [p for p in [weather_line, ("⏱ " + duration_line) if duration_line else ""] if p]
    if parts:
        st.caption(" · ".join(parts))
    reco = str(render_data.get("next_reco") or "").strip()
    if reco:
        st.caption(f"✨ {reco}")
    transport_mode = str(render_data.get("transport_mode") or "").strip()
    if transport_mode:
        meta = str(render_data.get("transport_meta") or "").strip()
        st.caption(f"{render_data.get('transport_icon','')} {transport_mode} {meta}".strip())
    desc = str(render_data.get("transport_desc") or "").strip()
    if desc:
        st.caption(desc)
    alerts = render_data.get("alerts") if isinstance(render_data.get("alerts"), list) else []
    if alerts:
        st.warning("\n".join([str(a) for a in alerts if a]))


def _open_saved_trip(trip: dict, start_idx: int = 0) -> None:
    if not isinstance(trip, dict):
        return
    stops = trip.get("stops", []) or []
    idx = 0
    try:
        idx = int(start_idx)
    except Exception:
        idx = 0
    if idx < 0:
        idx = 0
    if stops and idx > len(stops) - 1:
        idx = len(stops) - 1
    st.session_state.trip_plan = {
        "city": trip.get("city", ""),
        "route": trip.get("route", ""),
        "stops": stops,
        "current_stop_idx": idx,
        "preview": False,
        "options": trip.get("options", {}) if isinstance(trip.get("options"), dict) else {},
        "status": trip.get("status", "planned"),
        "active_trip_id": trip.get("id"),
    }
    try:
        st.session_state.map_points = _stops_to_map_points(stops)
        st.session_state.map_segments = _stops_to_map_segments(trip.get("city", ""), stops)
        st.session_state.map_city = "杭州" if "杭州" in str(trip.get("city", "")) else str(trip.get("city", ""))
    except Exception:
        pass
    if st.session_state.get("current_tab") != "旅行":
        st.session_state.current_tab = "旅行"
    st.rerun()


def _open_trip_history(trip: dict) -> None:
    if not isinstance(trip, dict):
        return
    st.session_state.profile_trip_detail_id = trip.get("id")
    if st.session_state.get("current_tab") != "我的":
        st.session_state.current_tab = "我的"
    st.rerun()


def _render_my_trip_plans(trips: list[dict], key_prefix: str = "plan", open_target: str = "trip") -> None:
    if not trips:
        st.markdown(
            """
            <div style="text-align:center; padding:20px 0; color:#bbb;">
                <div style="font-size:32px;">🧳</div>
                <div style="font-size:12px; margin-top:4px;">还没有保存的旅行方案</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    for trip in trips:
        name = str(trip.get("name", ""))
        created = str(trip.get("created_at", ""))
        status = str(trip.get("status", "planned"))
        status_text = "🟢 进行中" if status == "active" else "✅ 已完成" if status == "completed" else "📌 已保存"
        stops = trip.get("stops", []) or []
        preview = " → ".join([str(s.get("name", "")) for s in stops[:4] if isinstance(s, dict)])
        if len(stops) > 4:
            preview += "…"
        st.markdown(
            f"""
            <div class="trip-card">
                <h4>{_html.escape(name)}</h4>
                <p>{_html.escape(status_text)} · {_html.escape(created)} · {len(stops)}站</p>
                <p>{_html.escape(preview)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📋 查看", key=f"{key_prefix}_view_{trip.get('id')}", use_container_width=True):
                if open_target == "history":
                    _open_trip_history(trip)
                else:
                    _open_saved_trip(trip, 0)
        with c2:
            if st.button("🗑️ 删除", key=f"{key_prefix}_del_{trip.get('id')}", use_container_width=True):
                try:
                    user_id = st.session_state.get("user_id", "")
                    db_path = st.session_state.get("local_db_path", "")
                    if isinstance(user_id, str) and isinstance(db_path, str) and user_id and db_path and trip.get("id"):
                        local_db.delete_trip(db_path, user_id, str(trip.get("id")))
                except Exception:
                    pass
                st.session_state.saved_trips = [t for t in st.session_state.saved_trips if str(t.get("id")) != str(trip.get("id"))]
                st.rerun()


def _render_trip_active():
    """渲染旅行进行中页面（山海主题·潮汐进度）"""
    def _strip_html_tags(val) -> str:
        s = "" if val is None else str(val)
        s = re.sub(r"<[^>]*?>", "", s)
        return s.strip()

    def _safe_html_text(val) -> str:
        return _html.escape(_strip_html_tags(val), quote=True)

    plan = st.session_state.trip_plan
    city = plan["city"]
    route_name = plan["route"]
    stops = plan["stops"]
    current_idx = plan.get("current_stop_idx", 0)
    kb = st.session_state.knowledge_base
    bloggers = kb.get(city, {})

    # ---- 顶部状态栏 ----
    progress = min(current_idx + 1, len(stops))
    st.markdown(f"""
    <div class="demo-banner">🧳 {_safe_html_text(city)} · {_safe_html_text(route_name)} · 第{progress}/{len(stops)}站</div>
    """, unsafe_allow_html=True)

    nav1, nav2 = st.columns(2)
    with nav1:
        if st.button("← 返回预览", use_container_width=True):
            st.session_state.trip_plan["preview"] = True
            st.rerun()
    with nav2:
        with st.popover("🗑 放弃计划", use_container_width=True):
            st.caption("确认放弃后，将删除本地保存并回到路线选择。")
            if st.button("确认放弃", use_container_width=True, type="primary"):
                try:
                    trip_id = st.session_state.trip_plan.get("active_trip_id")
                    user_id = st.session_state.get("user_id", "")
                    db_path = st.session_state.get("local_db_path", "")
                    if trip_id and isinstance(user_id, str) and isinstance(db_path, str) and user_id and db_path:
                        local_db.delete_trip(db_path, user_id, str(trip_id))
                    st.session_state.saved_trips = [t for t in st.session_state.saved_trips if str(t.get("id")) != str(trip_id)]
                except Exception:
                    pass
                st.session_state.trip_plan = None
                st.rerun()

    # 潮汐/山峰进度条
    progress_pct = int(progress / len(stops) * 100)
    st.markdown(f"""
    <div class="tide-progress">
        <div class="tide-progress-bar" style="width: {progress_pct}%"></div>
    </div>
    """, unsafe_allow_html=True)

    # ---- 当前站点详情 ----
    if current_idx < len(stops):
        spot = stops[current_idx]
        spot_name_raw = spot.get("name", "")
        spot_name_safe = _safe_html_text(spot_name_raw)
        weather = get_weather(spot_name_raw)
        ticket_str = f" · 🎫 {_safe_html_text(spot.get('ticket', ''))}" if spot.get('ticket') else ""
        
        # 山海标签
        tag = spot.get('tag', '城市')
        if tag == "山":
            tag_html = '<span class="tag-mountain">⛰️ 山</span>'
        elif tag == "海":
            tag_html = '<span class="tag-sea">🌊 海</span>'
        else:
            tag_html = '<span class="tag-city">🏙️ 城市</span>'
        mood_html = f'<span class="tag-mood">{_safe_html_text(spot.get("mood",""))}</span>' if spot.get("mood") else ''

        st.markdown(f"### 📍 第{current_idx+1}站：{_strip_html_tags(spot_name_raw)}")
        st.markdown(
            f"{tag_html} {mood_html} · 🌤️ {_safe_html_text(weather.get('weather',''))} {_safe_html_text(weather.get('temperature',''))}°C · ⏱ {_safe_html_text(spot.get('visit_duration', ''))}{ticket_str}",
            unsafe_allow_html=True,
        )

        st.markdown(f"**✨ 推荐理由**")
        st.caption(_strip_html_tags(spot.get("recommendation", "")))
        st.caption(f"🗣️ _{_strip_html_tags(spot.get('speech', ''))}_")

        base_image_path = os.path.join(os.path.dirname(__file__), "picture", "visual")
        first_img = None
        try:
            imgs = spot.get("images", []) or []
            if isinstance(imgs, list) and imgs:
                cand = imgs[0]
                first_img = cand if os.path.isabs(str(cand)) else os.path.join(base_image_path, str(cand))
                if not os.path.exists(first_img):
                    first_img = None
        except Exception:
            first_img = None

        if first_img:
            st.image(first_img, use_container_width=True)

        # 打卡卡片
        user_id = st.session_state.get("user_id", "")
        db_path = st.session_state.get("local_db_path", "")
        already_checked = False
        try:
            if isinstance(db_path, str) and isinstance(user_id, str) and db_path and user_id:
                already_checked = local_db.has_checkin(db_path, user_id, str(spot_name_raw))
        except Exception:
            already_checked = str(spot_name_raw) in st.session_state.all_checkins

        if already_checked:
            st.button(
                "✅ 已完成",
                use_container_width=True,
                type="primary",
                disabled=True,
                key=f"_checkin_btn_{current_idx}",
            )
        else:
            if st.button("✅ 打卡", use_container_width=True, type="primary", key=f"_checkin_btn_{current_idx}"):
                inserted = _record_checkin(str(spot_name_raw))
                if inserted:
                    st.toast(f"✅ 已打卡 {_strip_html_tags(spot_name_raw)}！")
                st.rerun()

        # 附近美食
        nearby_food = []
        for data in bloggers.values():
            for food in data.get("food", []):
                if any(kw in food.get("location", "") for kw in [spot["name"], "附近", "周边"]):
                    nearby_food.append(food)
        if not nearby_food:
            for data in bloggers.values():
                nearby_food = data.get("food", [])[:3]
                break

        if nearby_food:
            st.markdown("**🍜 附近美食**")
            for food in nearby_food[:3]:
                food_name = _safe_html_text(food.get("name", ""))
                food_rating = _safe_html_text(food.get("rating", ""))
                food_loc = _safe_html_text(food.get("location", ""))
                food_price = _safe_html_text(food.get("price", ""))
                food_desc = _safe_html_text(food.get("desc", ""))
                st.markdown(f"""
                <div class="food-item">
                    <h4>{food_name} {food_rating}</h4>
                    <p>📍 {food_loc} · 💰 {food_price}</p>
                    <p>{food_desc}</p>
                </div>
                """, unsafe_allow_html=True)

        # ============ 顺着风景去下一站 ============
        if current_idx < len(stops) - 1:
            next_spot = stops[current_idx + 1]
            next_name_raw = next_spot.get("name", "")
            next_name_safe = _safe_html_text(next_name_raw)
            next_weather = get_weather(next_name_raw)

            transport_found = None
            for data in bloggers.values():
                for t in data.get("transport", []):
                    if t["from"] == spot["name"] and t["to"] == next_spot["name"]:
                        transport_found = t
                        break

            mode_icons = {"步行": "🚶", "游船": "🚢", "公交": "🚌", "驾车": "🚗", "出租车": "🚕", "地铁": "🚇"}
            mode_icon = mode_icons.get(transport_found["mode"], "🚶") if transport_found else "🚶"

            mode_colors = {"步行": "#4a6741", "游船": "#5b8fb9", "公交": "#5b8fb9", "驾车": "#d44060", "出租车": "#d44060", "地铁": "#7c5cbf"}
            mode_color = mode_colors.get(transport_found["mode"], "#9ca3af") if transport_found else "#9ca3af"

            alerts = []
            w_text = weather.get("weather", "")
            if any(kw in w_text for kw in ["雨", "雪"]):
                alerts.append(f"⚠️ 当前{_strip_html_tags(w_text)}，注意携带雨具")
            next_w_text = next_weather.get("weather", "")
            if any(kw in next_w_text for kw in ["雨", "雪"]):
                alerts.append(f"⚠️ 下一站{_strip_html_tags(next_w_text)}，建议提前准备")
            if transport_found and transport_found["mode"] == "游船":
                alerts.append("🚢 游船需到指定码头，建议提前10分钟到达")
            best_time = next_spot.get("best_time", "")
            if best_time:
                alerts.append(f"🕐 下一站最佳时间：{_strip_html_tags(best_time)}")

            next_ticket_str = f" · 🎫 {_safe_html_text(next_spot.get('ticket', ''))}" if next_spot.get('ticket') else ""
            
            # 下一站山海标签
            next_tag = next_spot.get('tag', '城市')
            if next_tag == "山":
                next_tag_html = '<span class="tag-mountain">⛰️ 山</span>'
            elif next_tag == "海":
                next_tag_html = '<span class="tag-sea">🌊 海</span>'
            else:
                next_tag_html = '<span class="tag-city">🏙️ 城市</span>'

            transport_mode = _safe_html_text(transport_found["mode"]) if transport_found else "步行"
            transport_duration = _safe_html_text(transport_found.get("duration", "")) if transport_found else ""
            transport_cost = _safe_html_text(transport_found.get("cost", "")) if transport_found else ""
            transport_desc = _safe_html_text(transport_found.get("desc", "")) if transport_found and transport_found.get("desc") else ""

            transport_meta_html = ""
            if transport_found and (transport_duration or transport_cost):
                transport_meta_html = f"<div style='font-size:11px;color:#666;margin-bottom:2px;'>⏱️ {transport_duration} · 💰 {transport_cost}</div>"
            transport_desc_html = f"<div style='font-size:11px;color:#888;line-height:1.4;margin-top:3px;'>{transport_desc}</div>" if transport_desc else "<div style='font-size:11px;color:#888;'>建议使用地图导航前往</div>"
            alerts_html = ""
            if alerts:
                alerts_html = "<div style='background:#fffbe6;border-radius:8px;padding:6px 10px;font-size:11px;color:#ad6800;line-height:1.5;'>" + "<br>".join([_safe_html_text(a) for a in alerts]) + "</div>"

            render_tide_divider()
            render_data = {
                "next_name": _strip_html_tags(next_name_raw),
                "next_weather": f"🌤️ {_strip_html_tags(next_weather.get('weather',''))} {_strip_html_tags(next_weather.get('temperature',''))}°C",
                "next_duration": _strip_html_tags(next_spot.get("visit_duration", "")),
                "next_reco": _strip_html_tags(next_spot.get("recommendation", "")),
                "transport_mode": _strip_html_tags(transport_found.get("mode", "")) if transport_found else "步行",
                "transport_meta": " · ".join(
                    [
                        x
                        for x in [
                            _strip_html_tags(transport_found.get("duration", "")) if transport_found else "",
                            _strip_html_tags(transport_found.get("cost", "")) if transport_found else "",
                        ]
                        if x
                    ]
                ),
                "transport_desc": _strip_html_tags(transport_found.get("desc", "")) if transport_found else "",
                "transport_icon": mode_icon,
                "alerts": alerts,
                "step": current_idx + 2,
                "total": len(stops),
            }
            _render_navigation_tip(render_data)

            if st.button(f"🚀 顺着风景去「{_strip_html_tags(next_name_raw)}」", use_container_width=True, type="primary"):
                st.session_state.trip_plan["current_stop_idx"] = current_idx + 1
                st.toast(f"🚀 前往 {_strip_html_tags(next_name_raw)}！")
                st.rerun()

    # ---- 最后一站完成 ----
    if current_idx >= len(stops) - 1:
        render_tide_divider()
        st.markdown(
            """
            <div style="text-align:center;padding:22px 12px;border-radius:18px;background:linear-gradient(135deg,rgba(255,107,107,0.14),rgba(126,184,218,0.14));border:1px solid rgba(212,232,245,0.9);">
              <div style="font-size:44px;line-height:1;">🎉</div>
              <div style="margin-top:8px;font-size:20px;font-weight:900;color:#111827;">圆满完成</div>
              <div style="margin-top:6px;font-size:12px;color:#6b7280;">这段山海旅程已收录到「路线足迹」</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("🎉 圆满完成", use_container_width=True, type="primary"):
            st.session_state.trip_plan["status"] = "completed"
            st.session_state.trip_plan["preview"] = False
            _save_trip_plan()
            trip_id = st.session_state.trip_plan.get("active_trip_id")
            st.session_state.trip_plan = None
            st.session_state.profile_trip_detail_id = trip_id
            st.session_state.current_tab = "我的"
            st.rerun()

    # ---- 操作按钮 ----
    render_tide_divider()
    c1, c2, c3 = st.columns(3)

    with c1:
        if current_idx > 0:
            if st.button("⬅️ 上一站", use_container_width=True):
                st.session_state.trip_plan["current_stop_idx"] = current_idx - 1
                st.rerun()

    with c2:
        if st.button("🗺️ 地图", use_container_width=True):
            st.session_state.current_tab = "地图"
            st.rerun()

    with c3:
        with st.popover("📋 路线", use_container_width=True):
            def _norm_name(x) -> str:
                return ("" if x is None else str(x)).strip()

            trip_id = st.session_state.get("trip_plan", {}).get("active_trip_id")
            trip_checkins = set()
            if trip_id:
                for t in st.session_state.saved_trips:
                    if str(t.get("id")) == str(trip_id):
                        trip_checkins = set(_norm_name(v) for v in (t.get("checkins", []) or []))
                        break

            global_checkins = set(_norm_name(v) for v in (st.session_state.get("all_checkins", []) or []))
            db_checkins = set()
            try:
                user_id = st.session_state.get("user_id", "")
                db_path = st.session_state.get("local_db_path", "")
                if isinstance(user_id, str) and isinstance(db_path, str) and user_id and db_path:
                    db_checkins = set(_norm_name(v) for v in local_db.list_checkins(db_path, user_id))
            except Exception:
                db_checkins = set()

            effective_checkins = set()
            effective_checkins.update(global_checkins)
            effective_checkins.update(trip_checkins)
            effective_checkins.update(db_checkins)

            for i, s in enumerate(stops):
                nm = _norm_name(s.get("name", ""))
                done = nm in effective_checkins
                prefix = "📍" if i == current_idx else "✅" if done else "⭕"
                ticket_str = f" · 🎫 {s.get('ticket', '')}" if s.get('ticket') else ""
                tag = s.get('tag', '城市')
                tag_icon = "⛰️" if tag == "山" else "🌊" if tag == "海" else "🏙️"
                if st.button(f"{prefix} {tag_icon} {nm}{ticket_str}", key=f"route_jump_{trip_id}_{i}", use_container_width=True):
                    st.session_state.trip_plan["current_stop_idx"] = i
                    st.rerun()

    # ---- 计划有变 ----
    render_tide_divider()
    with st.expander("🧩 计划有变", expanded=False):
        st.caption("取消勾选不想去的景点后点击「重新规划」，已打卡景点将保持锁定。")
        trip_id = st.session_state.get("trip_plan", {}).get("active_trip_id")
        trip_checkins = set()
        if trip_id:
            for t in st.session_state.saved_trips:
                if str(t.get("id")) == str(trip_id):
                    trip_checkins = set((str(v) or "").strip() for v in (t.get("checkins", []) or []))
                    break

        selections: list[dict] = []
        for i, s in enumerate(stops):
            nm = (str(s.get("name", "")) or "").strip()
            tag = s.get("tag", "城市")
            tag_icon = "⛰️" if tag == "山" else "🌊" if tag == "海" else "🏙️"
            locked = nm in trip_checkins
            checked = st.checkbox(
                f"{tag_icon} {nm} · ⏱ {s.get('visit_duration','')}",
                value=True,
                disabled=locked,
                key=f"plan_change_{trip_id}_{i}",
            )
            if checked or locked:
                selections.append(s)

        if st.button("🔁 重新规划", use_container_width=True, type="primary", disabled=not selections):
            old_current = str(stops[current_idx].get("name", "")) if stops and current_idx < len(stops) else ""
            st.session_state.trip_plan["stops"] = selections
            if old_current:
                new_idx = 0
                for j, s in enumerate(selections):
                    if str(s.get("name", "")) == old_current:
                        new_idx = j
                        break
                st.session_state.trip_plan["current_stop_idx"] = min(new_idx, len(selections) - 1) if selections else 0
            else:
                st.session_state.trip_plan["current_stop_idx"] = 0

            try:
                st.session_state.map_points = _stops_to_map_points(selections)
                st.session_state.map_segments = _stops_to_map_segments(city, selections)
                st.session_state.map_city = "杭州" if "杭州" in city else city
            except Exception:
                pass

            _save_trip_plan()
            st.toast("已更新旅行方案")
            st.rerun()


def _record_checkin(spot_name: str):
    """记录打卡（幂等：同一 user_id + spot_id 仅写入一次）"""
    spot_id = (spot_name or "").strip()
    if not spot_id:
        return False

    user_id = st.session_state.get("user_id", "")
    db_path = st.session_state.get("local_db_path", "")
    inserted = False

    try:
        if isinstance(db_path, str) and isinstance(user_id, str) and db_path and user_id:
            if local_db.has_checkin(db_path, user_id, spot_id):
                inserted = False
            else:
                inserted = local_db.insert_checkin(db_path, user_id, spot_id)
    except Exception:
        inserted = False

    if spot_id not in st.session_state.all_checkins:
        st.session_state.all_checkins.append(spot_id)

    trip_id = None
    try:
        trip_id = st.session_state.get("trip_plan", {}).get("active_trip_id")
    except Exception:
        trip_id = None

    if trip_id:
        for trip in st.session_state.saved_trips:
            if str(trip.get("id")) == str(trip_id):
                if "checkins" not in trip or not isinstance(trip.get("checkins"), list):
                    trip["checkins"] = []
                if spot_id not in trip["checkins"]:
                    trip["checkins"].append(spot_id)
                try:
                    if isinstance(db_path, str) and isinstance(user_id, str) and db_path and user_id:
                        local_db.update_trip(db_path, user_id, str(trip_id), trip)
                except Exception:
                    pass
                break

    return inserted


def _save_trip_plan():
    """保存当前旅行方案"""
    plan = st.session_state.trip_plan
    if not plan:
        return

    existing_id = plan.get("active_trip_id")
    existing_trip = None
    if existing_id:
        for t in st.session_state.saved_trips:
            if str(t.get("id")) == str(existing_id):
                existing_trip = t
                break

    status = str(plan.get("status") or "planned")
    is_active = status == "active"
    checkins_list = existing_trip.get("checkins", []) if isinstance(existing_trip, dict) and isinstance(existing_trip.get("checkins"), list) else []
    checkins_list = [("" if v is None else str(v)).strip() for v in checkins_list if ("" if v is None else str(v)).strip()]
    checkins_list = list(dict.fromkeys(checkins_list))

    trip_data = {
        "name": existing_trip.get("name") if isinstance(existing_trip, dict) and existing_trip.get("name") else f"{plan['city']}·{plan['route']}",
        "city": plan["city"],
        "route": plan["route"],
        "stops": plan["stops"],
        "created_at": existing_trip.get("created_at") if isinstance(existing_trip, dict) and existing_trip.get("created_at") else datetime.now().strftime("%m-%d %H:%M"),
        "checkins": checkins_list,
        "status": status,
        "active": is_active,
        "options": plan.get("options", {}) if isinstance(plan.get("options"), dict) else {},
        "itinerary_preview": plan.get("itinerary_preview", {}),
        "itinerary_version": plan.get("itinerary_version"),
        "itinerary_checksum": plan.get("itinerary_checksum"),
    }

    if is_active:
        for t in st.session_state.saved_trips:
            t["active"] = False

    trip_id = None
    try:
        user_id = st.session_state.get("user_id", "")
        db_path = st.session_state.get("local_db_path", "")
        if isinstance(user_id, str) and isinstance(db_path, str) and user_id and db_path:
            if existing_id:
                trip_data["id"] = str(existing_id)
                local_db.update_trip(db_path, user_id, str(existing_id), trip_data)
            else:
                trip_id = local_db.save_trip(db_path, user_id, trip_data)
                trip_data["id"] = trip_id
    except Exception:
        if existing_id:
            trip_data["id"] = str(existing_id)
        else:
            trip_data["id"] = f"trip_{int(time.time())}"

    if existing_trip is not None:
        existing_trip.clear()
        existing_trip.update(trip_data)
    else:
        st.session_state.saved_trips.append(trip_data)
    st.session_state.trip_plan["active_trip_id"] = trip_data["id"]


# ============================================================
#  页面 4：我的（山海成就系统）
# ============================================================

def render_profile_page():
    render_mountain_ridge()
    st.markdown("""
    <div class="profile-header">
        <div class="profile-avatar">🏔️</div>
        <div class="profile-name">Dy灵动地图</div>
        <div class="profile-bio">山有脉 · 海有流 · 路有灵</div>
    </div>
    """, unsafe_allow_html=True)

    render_tide_divider()
    st.caption("💡 Demo 模式已开启：去「寻迹」选择示例视频并生成地图")

    trip_detail_id = st.session_state.get("profile_trip_detail_id")
    if trip_detail_id:
        render_tide_divider()
        trip = None
        for t in st.session_state.saved_trips:
            if str(t.get("id")) == str(trip_detail_id):
                trip = t
                break
        if not trip:
            st.session_state.profile_trip_detail_id = None
            st.rerun()

        st.markdown("#### 👣 路线足迹详情")
        b1, b2 = st.columns([1, 3])
        with b1:
            if st.button("← 返回", use_container_width=True):
                st.session_state.profile_trip_detail_id = None
                st.rerun()
        with b2:
            st.markdown(f"**{_html.escape(str(trip.get('name','')))}**")
            st.caption(f"{_html.escape(str(trip.get('created_at','')))} · {len(trip.get('stops', []) or [])}站")

        stops = trip.get("stops", []) or []
        checkins = set(trip.get("checkins", []) or [])
        if checkins:
            tags = []
            seen_names = set()
            for s in stops:
                if not isinstance(s, dict):
                    continue
                nm = s.get("name")
                if nm in checkins and nm not in seen_names:
                    seen_names.add(nm)
                    tag = s.get("tag", "城市")
                    if tag == "山":
                        tags.append('<span class="tag-mountain">⛰️ ' + str(nm) + "</span>")
                    elif tag == "海":
                        tags.append('<span class="tag-sea">🌊 ' + str(nm) + "</span>")
                    else:
                        tags.append('<span class="tag-city">🏙️ ' + str(nm) + "</span>")
            if tags:
                st.markdown(" ".join(tags), unsafe_allow_html=True)

        st.markdown("**行程计划**")
        for i, s in enumerate(stops):
            if not isinstance(s, dict):
                continue
            nm = str(s.get("name", ""))
            done = nm in checkins
            flag = "✅" if done else "⬜"
            if st.button(f"{flag} {i+1}. {nm}", key=f"profile_trip_jump_{trip_detail_id}_{i}", use_container_width=True):
                _open_saved_trip(trip, i)
            st.caption(f"⏱ {s.get('visit_duration','')}")

        render_sea_wave_footer()
        return

    # ---- 山海人格 ----
    render_tide_divider()
    all_checkins = st.session_state.all_checkins
    all_stops = []
    for trip in st.session_state.saved_trips:
        all_stops.extend(trip.get("stops", []))
    # 也从 demo 数据获取
    if st.session_state.demo_mode:
        kb = get_demo_knowledge_base()
        for city, bloggers in kb.items():
            for data in bloggers.values():
                all_stops.extend(data.get("spots", []))

    personality = _get_user_personality(all_checkins, all_stops)
    personality_desc = {
        "⛰️ 山行者": "你偏爱登高望远，山的脊线是你的路标",
        "🌊 浪迹者": "你钟情水岸风光，海的潮汐是你的节奏",
        "🏔️‍🌊 山海客": "你穿梭于山海之间，来去自如",
        "待探索": "出发吧，山海正在等你",
        "自由行者": "你步履不停，每一步都是风景",
    }
    
    st.markdown(f"""
    <div class="personality-card">
        <div class="personality-icon">{personality.split(' ')[0] if ' ' in personality else '🏔️'}</div>
        <div class="personality-title">{personality}</div>
        <div class="personality-desc">{personality_desc.get(personality, '探索属于你的山海')}</div>
    </div>
    """, unsafe_allow_html=True)

    # ---- 山海徽章 ----
    render_tide_divider()
    st.markdown("#### 🏅 山海徽章")

    progress = _calc_achievement_progress(all_checkins, all_stops)

    for ach in ACHIEVEMENTS:
        aid = ach["id"]
        # 判断是否达成
        earned = False
        progress_text = ""
        if aid == "wave_rider":
            earned = progress["water_routes"] >= 3
            progress_text = f"{progress['water_routes']}/3"
        elif aid == "peak_climber":
            earned = progress["mountain_checkins"] >= 5
            progress_text = f"{progress['mountain_checkins']}/5"
        elif aid == "sunset_chaser":
            earned = progress["sunset_routes"] >= 2
            progress_text = f"{progress['sunset_routes']}/2"
        elif aid == "food_collector":
            earned = progress["food_spots"] >= 10
            progress_text = f"{progress['food_spots']}/10"
        elif aid == "dual_scene":
            earned = progress["dual_scene"]
            progress_text = "✓" if earned else "—"

        css_class = "earned" if earned else "locked"
        st.markdown(f"""
        <div class="badge-card">
            <div class="badge-icon {css_class}">{ach['icon']}</div>
            <div>
                <div class="badge-name">{ach['name']}</div>
                <div class="badge-desc">{ach['desc']}</div>
                <div class="badge-progress">{progress_text}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    saved_trips = st.session_state.saved_trips

    render_tide_divider()
    st.markdown("#### 🧳 我的旅行方案")
    plans = [t for t in (saved_trips or []) if isinstance(t, dict) and str(t.get("status", "planned")) != "completed"]
    _render_my_trip_plans(plans, key_prefix="profile_plan", open_target="trip")

    render_tide_divider()
    st.markdown("#### 👣 路线足迹")

    completed = [
        t
        for t in (saved_trips or [])
        if isinstance(t, dict)
        and (
            str(t.get("status", "")) == "completed"
            or (not t.get("active") and isinstance(t.get("checkins"), list) and len(t.get("checkins")) > 0)
        )
    ]

    if not completed and not all_checkins:
        st.markdown(
            """
            <div style="text-align:center; padding:20px 0; color:#bbb;">
                <div style="font-size:32px;">👣</div>
                <div style="font-size:12px; margin-top:4px;">还没有路线足迹</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        if all_checkins:
            st.markdown(f"**已打卡 {len(all_checkins)} 个地点**")
            checkin_tags = []
            seen_checkins = set()
            for c in all_checkins:
                if c in seen_checkins:
                    continue
                seen_checkins.add(c)
                for s in all_stops:
                    if s["name"] == c:
                        tag = s.get("tag", "城市")
                        if tag == "山":
                            checkin_tags.append('<span class="tag-mountain">⛰️ ' + c + "</span>")
                        elif tag == "海":
                            checkin_tags.append('<span class="tag-sea">🌊 ' + c + "</span>")
                        else:
                            checkin_tags.append('<span class="tag-city">🏙️ ' + c + "</span>")
                        break
            st.markdown(" ".join(checkin_tags[:10]), unsafe_allow_html=True)

        _render_my_trip_plans(completed, key_prefix="profile_done", open_target="history")

    render_sea_wave_footer()


def _render_knowledge_base(kb: dict):
    """渲染知识库：城市 → 博主 → 详情"""
    for city, bloggers in kb.items():
        with st.expander(f"🏔️ {city}（{len(bloggers)}位博主）", expanded=False):
            for blogger_name, data in bloggers.items():
                spots = data.get("spots", [])
                food = data.get("food", [])
                transport = data.get("transport", [])
                tips = data.get("tips", [])

                st.markdown(f"**🦋 {blogger_name}**")
                st.caption(data.get("video_title", ""))

                if spots:
                    st.markdown(f"📍 **景点**（{len(spots)}个）")
                    for spot in spots:
                        ticket_str = f' <span class="tag-ticket">🎫 {spot.get("ticket","")}</span>' if spot.get('ticket') else ""
                        tag = spot.get('tag', '城市')
                        if tag == "山":
                            tag_html = '<span class="tag-mountain">⛰️ 山</span>'
                        elif tag == "海":
                            tag_html = '<span class="tag-sea">🌊 海</span>'
                        else:
                            tag_html = '<span class="tag-city">🏙️ 城市</span>'
                        st.markdown(f"""
                        <div class="point-item">
                            <h4>📍 {spot['name']} {tag_html} <span class="tag-ticket">⏱ {spot.get('visit_duration','')}</span>{ticket_str}</h4>
                            <p>{spot.get('recommendation','')[:50]}...</p>
                            <p>🕐 最佳：{spot.get('best_time','')}</p>
                        </div>
                        """, unsafe_allow_html=True)

                if food:
                    st.markdown(f"🍜 **美食**（{len(food)}道）")
                    for f_item in food:
                        st.markdown(f"""
                        <div class="food-item">
                            <h4>{f_item['name']} {f_item.get('rating','')} · 💰 {f_item.get('price','')}</h4>
                            <p>📍 {f_item.get('location','')}</p>
                            <p>{f_item.get('desc','')}</p>
                        </div>
                        """, unsafe_allow_html=True)

                if transport:
                    st.markdown(f"🚌 **交通**（{len(transport)}条）")
                    for t in transport:
                        st.markdown(f"""
                        <div class="transport-item">
                            <h4>{t['from']} → {t['to']} · {t['mode']} · {t['duration']} · {t['cost']}</h4>
                            <p>{t.get('desc','')}</p>
                        </div>
                        """, unsafe_allow_html=True)

                if tips:
                    st.markdown(f"💡 **贴士**")
                    for tip in tips:
                        st.caption(f"• {tip}")


def _check_ytdlp() -> bool:
    try:
        import yt_dlp
        return True
    except ImportError:
        return False


# ============================================================
#  主渲染逻辑
# ============================================================

render_header()
render_bottom_nav()

current = st.session_state.current_tab
if current != "地图" and st.session_state.get("virtual_tour_mode", False):
    st.session_state.virtual_tour_mode = False

if current == "寻迹":
    render_parse_page()
elif current == "地图":
    render_map_page()
elif current == "旅行":
    render_trip_page()
elif current == "我的":
    render_profile_page()
