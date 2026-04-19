# ============================================================
# config.py - Lingdong-Map 项目配置文件
# ============================================================

# -------------------- 高德地图 API --------------------
# Web 端（前端 JS API 使用）
AMAP_WEB_KEY = "2fd149a3126bc6e7c9337d52b1b72cd8"           # 高德 Web 端 Key
AMAP_WEB_SECURITY = "df9345c07afc8971be213dea161c87e4"       # 高德 Web 端安全密钥

# 后端服务端（REST API 调用使用，如天气、地理编码）
AMAP_SERVER_KEY = "a9a366f3917844bcc7a6cd49386f78e0"         # 高德后端服务 Key

# -------------------- 通义千问 --------------------
# 方式1：自建 Qwen-VL 服务（优先使用）
QWEN_VL_URL = "http://219.223.251.100:5002/v1/chat/completions"  # 自建 Qwen-VL 视觉分析接口
QWEN_VL_MODEL = "Qwen/Qwen2.5-VL-7B-Instruct"  # 自建服务使用的模型名称

# 方式2：阿里云 DashScope API（备用）
# 申请地址: https://dashscope.console.aliyun.com/apiKey
QWEN_API_KEY = ""  # 通义千问 API Key（对话 & VL 视觉分析共用）

# -------------------- Whisper 语音识别 --------------------
# 方式1：自建 Whisper ASR 服务（优先使用）
WHISPER_ASR_URL = "http://219.223.251.100:5001/transcribe"  # 自建 Whisper ASR 接口
# 同机器内部调用也可用: http://127.0.0.1:5001/transcribe

# 方式2：OpenAI Whisper API（备用）
WHISPER_API_KEY = ""  # Whisper API Key

# -------------------- 本地模型路径 --------------------
# 自定义本地模型存放目录（用于 Whisper 等本地模型加载）
MODEL_BASE_PATH = "/new_raid/nanhangproj/api/models"

# -------------------- 临时文件目录 --------------------
TEMP_DIR = "./temp"  # 视频下载临时目录


# -------------------- 辅助函数 --------------------

def is_key_configured(key_name: str) -> bool:
    """检查某个 Key 是否已填写（非空且非占位符）"""
    value = globals().get(key_name, "")
    return bool(value and value.strip())
