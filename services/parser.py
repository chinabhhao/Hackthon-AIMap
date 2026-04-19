# ============================================================
# services/parser.py - 视频解析服务
# 流程：下载视频 → 提取关键帧 → 语音识别 → 视觉分析 → 结构化输出
# 本地模型从 MODEL_BASE_PATH 加载，API 调用预留真实接口
# ============================================================

import os
import uuid
import time
import base64
import subprocess
import tempfile
from typing import Optional

# ---- 导入配置 ----
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import QWEN_API_KEY, QWEN_VL_URL, QWEN_VL_MODEL, WHISPER_API_KEY, WHISPER_ASR_URL, MODEL_BASE_PATH, is_key_configured

# 禁用系统代理，直连 API 服务（避免 ProxyError 导致请求失败）
_NO_PROXY = {"http": None, "https": None}


# ============================================================
#  Whisper 语音识别
# ============================================================

def call_whisper_api(audio_path: str) -> dict:
    """
    调用 Whisper 进行语音识别

    优先级：
    1. 自建 Whisper ASR 服务（WHISPER_ASR_URL） → 最优先
    2. OpenAI Whisper API（WHISPER_API_KEY） → 备用
    3. 本地 Whisper 模型（MODEL_BASE_PATH/whisper/） → 离线备用
    4. 模拟数据 → 兜底

    参数:
        audio_path: 音频/视频文件路径

    返回:
        {"text": "...", "segments": [{start, end, text}, ...]}
    """
    # ---- 方式 1：自建 Whisper ASR 服务（最高优先级） ----
    if WHISPER_ASR_URL and WHISPER_ASR_URL.strip():
        return _call_whisper_asr_service(audio_path)

    # ---- 方式 2：远程 Whisper API ----
    if is_key_configured("WHISPER_API_KEY"):
        return _call_whisper_remote_api(audio_path)

    # ---- 方式 3：本地 Whisper 模型 ----
    local_model_path = os.path.join(MODEL_BASE_PATH, "whisper")
    if os.path.isdir(local_model_path):
        return _call_whisper_local(audio_path, local_model_path)

    # ---- 方式 4：模拟数据 ----
    return _mock_whisper_result()


def _call_whisper_asr_service(audio_path: str) -> dict:
    """调用自建 Whisper ASR 服务 (POST multipart/form-data)
    
    接口地址: http://219.223.251.100:5001/transcribe
    参数: file (音频文件)
    返回: {"text": "识别结果"}
    """
    import requests

    try:
        with open(audio_path, "rb") as f:
            response = requests.post(
                WHISPER_ASR_URL,
                files={"file": f},
                timeout=120,  # 语音识别可能较慢，给足超时
                proxies=_NO_PROXY,
            )

        if response.status_code != 200:
            print(f"[parser] 自建 Whisper ASR 调用失败 ({response.status_code})，尝试备用方式")
            return _fallback_whisper(audio_path)

        data = response.json()
        full_text = data.get("text", "").strip()

        if not full_text:
            print("[parser] 自建 ASR 返回空文本，尝试备用方式")
            return _fallback_whisper(audio_path)

        # 自建 ASR 返回完整文本，尝试按标点拆分为 segments
        # 如果返回中已有 segments 字段则直接使用
        if "segments" in data and isinstance(data["segments"], list):
            return {
                "text": full_text,
                "segments": [
                    {
                        "start": seg.get("start", 0),
                        "end": seg.get("end", 0),
                        "text": seg.get("text", "").strip(),
                    }
                    for seg in data["segments"]
                ],
            }

        # 无 segments 时，按句号/问号/感叹号简单拆分
        segments = _split_text_to_segments(full_text)
        return {"text": full_text, "segments": segments}

    except requests.exceptions.ConnectionError:
        print("[parser] 无法连接自建 Whisper ASR 服务，尝试备用方式")
        return _fallback_whisper(audio_path)
    except requests.exceptions.Timeout:
        print("[parser] 自建 Whisper ASR 请求超时，尝试备用方式")
        return _fallback_whisper(audio_path)
    except Exception as e:
        print(f"[parser] 自建 ASR 调用异常: {e}，尝试备用方式")
        return _fallback_whisper(audio_path)


def _fallback_whisper(audio_path: str) -> dict:
    """自建 ASR 失败后的降级逻辑：OpenAI API → 本地模型 → 模拟数据"""
    if is_key_configured("WHISPER_API_KEY"):
        return _call_whisper_remote_api(audio_path)
    local_model_path = os.path.join(MODEL_BASE_PATH, "whisper")
    if os.path.isdir(local_model_path):
        return _call_whisper_local(audio_path, local_model_path)
    return _mock_whisper_result()


def _split_text_to_segments(text: str, avg_seg_duration: float = 5.0) -> list:
    """将纯文本按标点拆分为带时间戳的 segments（粗略估算）"""
    import re
    # 按中英文句号、问号、感叹号拆分
    sentences = re.split(r'[。？！\.\?!]', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return [{"start": 0, "end": avg_seg_duration, "text": text}]

    segments = []
    current_time = 0.0
    for sent in sentences:
        # 根据字符数粗略估算时长（中文约 4 字/秒）
        duration = max(len(sent) / 4.0, 1.0)
        segments.append({
            "start": round(current_time, 2),
            "end": round(current_time + duration, 2),
            "text": sent,
        })
        current_time += duration

    return segments


def _call_whisper_remote_api(audio_path: str) -> dict:
    """调用远程 Whisper API"""
    import requests

    with open(audio_path, "rb") as f:
        response = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {WHISPER_API_KEY}"},
            files={"file": f},
            data={
                "model": "whisper-1",
                "language": "zh",
                "response_format": "verbose_json",
            },
            proxies=_NO_PROXY,
        )

    if response.status_code != 200:
        print(f"[parser] Whisper API 调用失败 ({response.status_code})，回退模拟数据")
        return _mock_whisper_result()

    data = response.json()
    return {
        "text": data.get("text", ""),
        "segments": [
            {"start": seg.get("start", 0), "end": seg.get("end", 0), "text": seg.get("text", "").strip()}
            for seg in data.get("segments", [])
        ],
    }


def _call_whisper_local(audio_path: str, model_path: str) -> dict:
    """
    使用本地 Whisper 模型进行语音识别
    模型路径: MODEL_BASE_PATH/whisper/
    """
    try:
        import whisper

        # 尝试从自定义路径加载模型
        model_files = [f for f in os.listdir(model_path) if f.endswith(".pt")]
        if model_files:
            model_file = os.path.join(model_path, model_files[0])
            print(f"[parser] 加载本地 Whisper 模型: {model_file}")
            model = whisper.load_model(model_file)
        else:
            # 回退到 whisper 默认下载路径
            print(f"[parser] 本地目录无模型文件，使用 whisper 默认加载")
            model = whisper.load_model("base")

        result = model.transcribe(audio_path, language="zh")
        return {
            "text": result.get("text", ""),
            "segments": [
                {"start": seg.get("start", 0), "end": seg.get("end", 0), "text": seg.get("text", "").strip()}
                for seg in result.get("segments", [])
            ],
        }
    except ImportError:
        print("[parser] whisper 库未安装，回退模拟数据。安装: pip install openai-whisper")
        return _mock_whisper_result()
    except Exception as e:
        print(f"[parser] 本地 Whisper 推理失败: {e}，回退模拟数据")
        return _mock_whisper_result()


def _mock_whisper_result() -> dict:
    """模拟 Whisper 返回数据"""
    return {
        "text": "我现在在西湖边，前面就是断桥，风景非常美。沿着北山街一直走，可以到岳庙。今天天气很好，适合散步。",
        "segments": [
            {"start": 0.0, "end": 4.2, "text": "我现在在西湖边，前面就是断桥，风景非常美。"},
            {"start": 4.2, "end": 8.5, "text": "沿着北山街一直走，可以到岳庙。"},
            {"start": 8.5, "end": 12.0, "text": "今天天气很好，适合散步。"},
        ],
    }


# ============================================================
#  Qwen-VL 视觉分析
# ============================================================

def call_qwen_vl_api(image_frames: list) -> list:
    """
    调用 Qwen-VL 分析关键帧画面，识别地标、路牌、环境

    优先级：
    1. 如果 QWEN_VL_URL 已配置 → 调用自建 Qwen-VL 服务（最高优先级）
    2. 如果 QWEN_API_KEY 已配置 → 调用远程 Qwen-VL API
    3. 否则 → 返回模拟数据

    参数:
        image_frames: 关键帧列表，每项为 base64 编码图片字符串
    """
    # 方式 1：自建 Qwen-VL 服务（最高优先级）
    if QWEN_VL_URL and QWEN_VL_URL.strip():
        return _call_qwen_vl_self_hosted(image_frames)

    # 方式 2：阿里云 DashScope API
    if is_key_configured("QWEN_API_KEY"):
        return _call_qwen_vl_remote_api(image_frames)

    return _mock_qwen_vl_result()


def _call_qwen_vl_self_hosted(image_frames: list) -> list:
    """调用自建 Qwen-VL 服务（OpenAI 兼容格式）"""
    import requests

    results = []
    prompt_text = (
        "请分析这张图片，识别以下内容并以 JSON 格式返回：\n"
        "1. landmarks: 画面中可辨识的地标建筑或自然景观（数组）\n"
        "2. signs: 画面中路牌、标识牌上的文字（数组）\n"
        "3. environment: 对整体环境的简要描述\n\n"
        '请严格返回: {"landmarks": [...], "signs": [...], "environment": "..."}'
    )

    for i, frame_b64 in enumerate(image_frames):
        timestamp = (i + 1) * 5
        try:
            response = requests.post(
                QWEN_VL_URL,
                json={
                    "model": QWEN_VL_MODEL,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_text},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{frame_b64}"}},
                        ],
                    }],
                },
                timeout=60,  # 视觉分析可能较慢
                proxies=_NO_PROXY,
            )

            if response.status_code != 200:
                print(f"[parser] 自建 Qwen-VL 失败 ({response.status_code})，帧 {i+1} 使用模拟数据")
                results.append(_mock_single_vl(timestamp))
                continue

            content = response.json()["choices"][0]["message"]["content"]
            analysis = _parse_vl_response(content)
            results.append({"timestamp": timestamp, "analysis": analysis})

        except requests.exceptions.ConnectionError:
            print(f"[parser] 无法连接自建 Qwen-VL 服务，帧 {i+1} 使用模拟数据")
            results.append(_mock_single_vl(timestamp))
        except requests.exceptions.Timeout:
            print(f"[parser] 自建 Qwen-VL 请求超时，帧 {i+1} 使用模拟数据")
            results.append(_mock_single_vl(timestamp))
        except Exception as e:
            print(f"[parser] 自建 Qwen-VL 帧分析异常: {e}，帧 {i+1} 使用模拟数据")
            results.append(_mock_single_vl(timestamp))

        # 简易限流
        time.sleep(0.3)

    return results if results else _mock_qwen_vl_result()


def _call_qwen_vl_remote_api(image_frames: list) -> list:
    """调用远程 Qwen-VL API"""
    import requests

    results = []
    prompt_text = (
        "请分析这张图片，识别以下内容并以 JSON 格式返回：\n"
        "1. landmarks: 画面中可辨识的地标建筑或自然景观（数组）\n"
        "2. signs: 画面中路牌、标识牌上的文字（数组）\n"
        "3. environment: 对整体环境的简要描述\n\n"
        '请严格返回: {"landmarks": [...], "signs": [...], "environment": "..."}'
    )

    for i, frame_b64 in enumerate(image_frames):
        timestamp = (i + 1) * 5
        try:
            response = requests.post(
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {QWEN_API_KEY}",
                },
                json={
                    "model": "qwen-vl-max",
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_text},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{frame_b64}"}},
                        ],
                    }],
                },
                timeout=30,
                proxies=_NO_PROXY,
            )

            if response.status_code != 200:
                print(f"[parser] Qwen-VL API 失败 ({response.status_code})，帧 {i+1} 使用模拟数据")
                results.append(_mock_single_vl(timestamp))
                continue

            content = response.json()["choices"][0]["message"]["content"]

            # 尝试从返回中提取 JSON
            analysis = _parse_vl_response(content)
            results.append({"timestamp": timestamp, "analysis": analysis})

        except Exception as e:
            print(f"[parser] Qwen-VL 帧分析异常: {e}，帧 {i+1} 使用模拟数据")
            results.append(_mock_single_vl(timestamp))

        # 简易限流
        time.sleep(0.5)

    return results if results else _mock_qwen_vl_result()


def _parse_vl_response(content: str) -> dict:
    """解析 Qwen-VL 返回的文本，提取 JSON"""
    import json as _json
    try:
        json_match = content.replace("```json", "").replace("```", "").strip()
        json_match = _json.loads(json_match)
        return {
            "landmarks": json_match.get("landmarks", []),
            "signs": json_match.get("signs", []),
            "environment": json_match.get("environment", ""),
        }
    except Exception:
        # 尝试正则提取
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                parsed = _json.loads(json_match.group())
                return {
                    "landmarks": parsed.get("landmarks", []),
                    "signs": parsed.get("signs", []),
                    "environment": parsed.get("environment", ""),
                }
            except Exception:
                pass
        return {"landmarks": [], "signs": [], "environment": content}


def _mock_single_vl(timestamp: int) -> dict:
    """生成单个模拟视觉分析结果"""
    mock_data = _mock_qwen_vl_result()
    idx = min((timestamp // 5) - 1, len(mock_data) - 1)
    idx = max(idx, 0)
    return mock_data[idx]


def _mock_qwen_vl_result() -> list:
    """模拟 Qwen-VL 返回数据"""
    return [
        {
            "timestamp": 5,
            "analysis": {
                "landmarks": ["断桥", "白堤"],
                "signs": ["北山街 →", "断桥残雪"],
                "environment": "西湖湖畔，晴天，碧水青山，游人如织",
            },
        },
        {
            "timestamp": 10,
            "analysis": {
                "landmarks": ["岳庙"],
                "signs": ["北山街 58号"],
                "environment": "城市街道，两侧法国梧桐，天气晴朗",
            },
        },
        {
            "timestamp": 15,
            "analysis": {
                "landmarks": ["曲院风荷"],
                "signs": ["曲院风荷 →"],
                "environment": "公园入口，绿树成荫，湖面波光粼粼",
            },
        },
    ]


# ============================================================
#  关键帧提取（依赖 ffmpeg）
# ============================================================

def extract_keyframes(video_path: str, interval_sec: int = 5) -> list:
    """
    使用 ffmpeg 从视频中按时间间隔提取关键帧

    参数:
        video_path: 视频文件路径
        interval_sec: 提取间隔（秒），默认 5 秒

    返回:
        [{"timestamp": 5, "frame_path": "/tmp/frame_001.jpg"}, ...]
    """
    tmp_dir = tempfile.mkdtemp(prefix="ldmap_frames_")
    output_pattern = os.path.join(tmp_dir, "frame_%04d.jpg")

    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"fps=1/{interval_sec}",
        "-q:v", "2",
        output_pattern,
        "-y",
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg 未安装或不在 PATH 中，请先安装 ffmpeg")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg 提取关键帧失败: {e.stderr.decode()}")

    frames = []
    for fname in sorted(os.listdir(tmp_dir)):
        if fname.startswith("frame_") and fname.endswith(".jpg"):
            idx = int(fname.replace("frame_", "").replace(".jpg", ""))
            frames.append({
                "timestamp": idx * interval_sec,
                "frame_path": os.path.join(tmp_dir, fname),
            })

    return frames


# ============================================================
#  数据合并与结构化
# ============================================================

def merge_results(
    whisper_result: dict,
    vision_results: list,
    video_id: Optional[str] = None,
) -> dict:
    """
    将 Whisper 语音片段与 Qwen-VL 视觉分析结果合并为结构化 JSON

    输出格式:
    {
        "video_id": "vid_xxx",
        "points": [
            {
                "point_id": "pt_001",
                "timestamp_start": 0,
                "timestamp_end": 5,
                "coordinates": {"lng": null, "lat": null},
                "content": {
                    "speech": "...",
                    "landmarks": [...],
                    "signs": [...],
                    "environment": "..."
                }
            }
        ]
    }
    """
    segments = whisper_result.get("segments", [])
    points = []

    for i, vr in enumerate(vision_results):
        ts = vr["timestamp"]
        prev_ts = vision_results[i - 1]["timestamp"] if i > 0 else 0
        analysis = vr.get("analysis", {})

        matched_speech = " ".join(
            seg["text"] for seg in segments
            if prev_ts <= seg["start"] < ts
        )

        points.append({
            "point_id": f"pt_{i + 1:03d}",
            "timestamp_start": prev_ts,
            "timestamp_end": ts,
            "coordinates": {"lng": None, "lat": None},
            "content": {
                "speech": matched_speech,
                "landmarks": analysis.get("landmarks", []),
                "signs": analysis.get("signs", []),
                "environment": analysis.get("environment", ""),
            },
        })

    # 处理最后一个关键帧之后的残余语音
    if vision_results and segments:
        last_ts = vision_results[-1]["timestamp"]
        trailing = [seg for seg in segments if seg["start"] >= last_ts]
        if trailing and points:
            points[-1]["content"]["speech"] += " " + " ".join(s["text"] for s in trailing)
            points[-1]["timestamp_end"] = trailing[-1]["end"]

    return {
        "video_id": video_id or f"vid_{int(time.time())}_{uuid.uuid4().hex[:6]}",
        "points": points,
    }


# ============================================================
#  主入口：完整解析流水线
# ============================================================

def parse_video(video_path: str, interval_sec: int = 5) -> dict:
    """
    解析视频文件，返回结构化数据
    流程：提取关键帧 → 语音转写 → 视觉分析 → 合并输出

    参数:
        video_path: 视频文件路径（本地路径，由 app.py 下载后传入）
        interval_sec: 关键帧提取间隔（秒）

    返回:
        结构化解析结果 dict
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"视频文件不存在: {video_path}")

    print(f"[parser] 开始解析视频: {video_path}")
    print(f"[parser] 本地模型路径: {MODEL_BASE_PATH}")

    # Step 1: 提取关键帧
    print("[parser] Step 1/3: 提取关键帧...")
    keyframes = extract_keyframes(video_path, interval_sec)
    print(f"[parser] 提取到 {len(keyframes)} 帧")

    # Step 2: 语音转写
    print("[parser] Step 2/3: 语音转写...")
    whisper_result = call_whisper_api(video_path)
    print(f"[parser] 转写完成，共 {len(whisper_result.get('segments', []))} 个片段")

    # Step 3: 视觉分析
    print("[parser] Step 3/3: 视觉分析...")
    frame_b64_list = []
    for kf in keyframes:
        if os.path.exists(kf["frame_path"]):
            with open(kf["frame_path"], "rb") as f:
                frame_b64_list.append(base64.b64encode(f.read()).decode())

    vision_results = call_qwen_vl_api(frame_b64_list) if frame_b64_list else call_qwen_vl_api([])
    print(f"[parser] 分析完成，共 {len(vision_results)} 个结果")

    # Step 4: 合并
    result = merge_results(whisper_result, vision_results)
    print(f"[parser] 解析完成，共生成 {len(result['points'])} 个数据点")

    return result
