# Lingdong-Map

灵动地图 —— 视频解析 × 智能推荐的交互式地图应用

## 项目结构

```
Lingdong-Map/
├── app.py                  # Streamlit 主程序（含高德地图嵌入）
├── config.py               # API 密钥配置（⚠️ 请先填写后再运行）
├── services/
│   ├── __init__.py
│   ├── parser.py           # 视频解析服务（Whisper + Qwen-VL）
│   └── map_service.py      # 地理编码 & 天气查询
├── modules/
│   └── parser.js           # （旧）Node.js 视频解析模块
├── .gitignore
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install streamlit
```

> 视频关键帧提取还需要系统安装 [ffmpeg](https://ffmpeg.org/)

### 2. 配置 API Key

在 `config.py` 中填写：

| Key | 用途 | 获取地址 |
|-----|------|----------|
| `AMAP_KEY` | 高德地图 JS API | [申请](https://console.amap.com/dev/key/app) |
| `AMAP_SECURITY_CODE` | 高德安全密钥 | 同上 |
| `QWEN_API_KEY` | 通义千问 AI | [申请](https://dashscope.console.aliyun.com/apiKey) |
| `WHISPER_API_KEY` | Whisper 语音识别 | [申请](https://platform.openai.com/api-keys) |

> ⚠️ 未填 Key 时程序仍可运行（使用模拟数据），但地图底图需要 `AMAP_KEY` 才能加载。

### 3. 运行

```bash
streamlit run app.py
```

## 功能模块

### 📹 视频解析 (`services/parser.py`)
- 上传视频 → 提取关键帧 → Whisper 语音识别 → Qwen-VL 视觉分析 → 结构化输出
- 输出格式：`video_id → points[] → {point_id, coordinates, content}`

### 🗺️ 地图与天气 (`services/map_service.py`)
- 地理编码：地名 → 经纬度（高德 Geocoding API）
- 天气查询：城市 → 实时天气（高德 Weather API）

### 🖥️ 主界面 (`app.py`)
- 侧边栏：上传视频、查看解析结果、配置状态
- 主区域：全屏高德地图，标注轨迹点并显示弹窗（地点名、天气、AI 推荐语）

### ✅ 路线勾选（旅行管家）
- 入口：底部导航「旅行」
- 支持博主路线与自定义路线两种方式选择景点
- 博主路线：可在博主路线展开页内逐个取消/勾选景点，实时展示剩余站点数与路线预览
- 自定义路线：景点默认全选，可按需取消

### 📋 计划预览（旅行管家）
- 选择路线后进入“计划预览”页，单屏展示完整行程表
- 顶部提供三按钮：保存并稍后查看 / 重新选择 / 立即开始
- 旅行进行中页支持“← 返回预览”与“🗑 放弃计划”

## 注意事项

- `config.py` 已加入 `.gitignore`，请勿将密钥提交至公开仓库
- 高德地图 JS API 2.0 需要同时配置 Key 和安全密钥
- 当前所有外部 API 均使用模拟数据，填入 Key 后自动切换为真实调用
