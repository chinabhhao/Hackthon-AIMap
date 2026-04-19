# ============================================================
# services/download_service.py - 视频下载服务
# 支持：直链 / B站 / 抖音（短链接解析 + 去水印） / yt-dlp 通用
# ============================================================

import os
import re
import sys
import time
import json
import subprocess
import requests

# 禁用系统代理，直连下载源（避免 ProxyError 导致请求失败）
_NO_PROXY = {"http": None, "https": None}
from urllib.parse import urlparse, unquote

# ---- 导入配置 ----
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TEMP_DIR


# ============================================================
#  常量
# ============================================================

# 移动端 User-Agent
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/16.6 Mobile/15E148 Safari/604.1"
)

# 桌面端 User-Agent
DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# 抖音通用 Cookie（模拟移动端已登录状态）
# tt_webid 和 s_v_web_id 为随机生成的设备标识，非真实用户凭据
DOUYIN_COOKIE = (
    "tt_webid=7123456789012345678; "
    "s_v_web_id=verify_m123abc456def; "
    "tt_webid_v2=7123456789012345678; "
    "msToken=abcdef1234567890; "
    "__ac_nonce=0658a1e8900123ab"
)


# ============================================================
#  辅助函数：从分享文本中提取 URL
# ============================================================

def _extract_url_from_text(text: str) -> str | None:
    """
    从抖音/社交平台的分享文本中提取真正的 URL

    分享文本示例：
    "5.87 Gip:/ I@V.lC 07/14 贵州很美... https://v.douyin.com/bwkP9blOo6c/ 复制此链接，打开Dou音搜索，直接观看视频！"
    "8.86 KDJ:/ ... https://www.douyin.com/video/7621141205632949425 ..."

    优先提取 http/https 开头的 URL，若没有则提取 v.douyin.com/xxx 格式
    """
    if not text:
        return None

    # 模式1: 标准的 http/https URL
    url_match = re.search(r'(https?://[^\s<>"\'」》]+)', text)
    if url_match:
        extracted = url_match.group(1).rstrip('.,;:!）》」')
        # 验证提取到的是否看起来像个 URL（至少有域名）
        if '.' in extracted:
            return extracted

    # 模式2: 抖音特有的 v.douyin.com/xxx 格式（没有 https:// 前缀）
    douyin_match = re.search(r'(v\.douyin\.com/[a-zA-Z0-9]+/?\d*)', text)
    if douyin_match:
        return 'https://' + douyin_match.group(1)

    # 模式3: www.douyin.com/video/xxx 格式（没有 https:// 前缀）
    dy_match = re.search(r'(www\.douyin\.com/video/\d+)', text)
    if dy_match:
        return 'https://' + dy_match.group(1)

    # 模式4: bilibili.com 短链接
    bili_match = re.search(r'(b23\.tv/[a-zA-Z0-9]+)', text)
    if bili_match:
        return 'https://' + bili_match.group(1)

    return None


# ============================================================
#  主入口
# ============================================================

def download_video(url: str) -> str:
    """
    智能下载视频：根据 URL 自动选择下载方式

    优先级：
    1. 直链 (.mp4/.mov 等) → requests 流式下载
    2. 抖音短链接 (v.douyin.com) → 解析 → 去水印下载
    3. 抖音长链接 (www.douyin.com/video/) → 直接去水印下载
    4. 其他平台 (B站等) → yt-dlp 下载

    支持直接粘贴抖音分享文本（如 "5.87 Gip:/ ... https://v.douyin.com/xxx/ 复制此链接..."）

    参数:
        url: 视频链接或抖音分享文本

    返回:
        本地文件路径
    """
    if not url or not url.strip():
        raise ValueError("视频链接不能为空")

    url = url.strip()
    os.makedirs(TEMP_DIR, exist_ok=True)

    # ---- 从抖音分享文本中提取真正的 URL ----
    extracted_url = _extract_url_from_text(url)
    if extracted_url and extracted_url != url:
        print(f"[download] 从分享文本中提取到链接: {extracted_url}")
        url = extracted_url

    # ---- 判断链接类型 ----
    parsed = urlparse(url)
    host = parsed.hostname or ""
    path_lower = unquote(parsed.path).lower()

    # 1. 直链
    direct_exts = (".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".ts")
    if any(path_lower.endswith(ext) for ext in direct_exts):
        print(f"[download] 检测到直链: {url[:80]}")
        return _download_direct(url)

    # 2. 抖音短链接
    if "v.douyin.com" in host:
        print(f"[download] 检测到抖音短链接: {url[:80]}")
        return _download_douyin(url)

    # 3. 抖音长链接
    if "douyin.com" in host and "/video/" in path_lower:
        print(f"[download] 检测到抖音长链接: {url[:80]}")
        return _download_douyin(url)

    # 4. 其他平台 → yt-dlp
    print(f"[download] 检测到平台链接: {url[:80]}")
    return _download_with_ytdlp(url)


# ============================================================
#  直链下载
# ============================================================

def _download_direct(url: str) -> str:
    """直接流式下载"""
    parsed = urlparse(url)
    filename = os.path.basename(unquote(parsed.path))
    if not filename:
        filename = f"video_{int(time.time())}.mp4"

    local_path = os.path.join(TEMP_DIR, filename)

    try:
        with requests.get(url, stream=True, timeout=60, proxies=_NO_PROXY) as resp:
            resp.raise_for_status()
            downloaded = 0
            with open(local_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
            print(f"[download] 直链下载完成: {local_path} ({downloaded / 1024 / 1024:.1f} MB)")
    except requests.RequestException as e:
        if os.path.exists(local_path):
            os.remove(local_path)
        raise RuntimeError(f"直链下载失败: {e}")

    return local_path


# ============================================================
#  抖音下载（核心逻辑）
# ============================================================

def _resolve_douyin_short_url(short_url: str) -> str:
    """
    解析抖音短链接，获取重定向后的长链接

    参数:
        short_url: https://v.douyin.com/xxxxxx/

    返回:
        重定向后的长链接
    """
    headers = {
        "User-Agent": MOBILE_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    try:
        # allow_redirects=False 手动跟随，以获取中间跳转 URL
        resp = requests.get(short_url, headers=headers, allow_redirects=True, timeout=15, proxies=_NO_PROXY)
        final_url = resp.url
        print(f"[douyin] 短链接解析: {short_url[:50]} → {final_url[:80]}")
        return final_url
    except requests.RequestException as e:
        print(f"[douyin] 短链接解析失败: {e}")
        # 回退：尝试不跟随重定向
        try:
            resp = requests.head(short_url, headers=headers, allow_redirects=False, timeout=10, proxies=_NO_PROXY)
            if "Location" in resp.headers:
                return resp.headers["Location"]
        except:
            pass
        raise RuntimeError(f"抖音短链接解析失败: {e}")


def _extract_douyin_video_id(url: str) -> str:
    """
    从抖音链接中提取视频 ID

    支持格式:
    - https://www.douyin.com/video/7621141205632949425
    - https://www.iesdouyin.com/share/video/7621141205632949425/
    - https://www.douyin.com/user/xxx?modal_id=7621141205632949425
    - ?video_id=xxx 格式

    返回:
        视频唯一 ID 字符串
    """
    # 模式 1: /video/数字
    match = re.search(r"/video/(\d+)", url)
    if match:
        return match.group(1)

    # 模式 2: modal_id=数字
    match = re.search(r"modal_id=(\d+)", url)
    if match:
        return match.group(1)

    # 模式 3: ?video_id=数字 或 video_id=数字
    match = re.search(r"video_id[=:](\d+)", url)
    if match:
        return match.group(1)

    # 模式 4: URL 路径末尾的纯数字
    match = re.search(r"/(\d{15,25})(?:/|\?|$)", url)
    if match:
        return match.group(1)

    raise RuntimeError(f"无法从链接中提取抖音视频 ID: {url[:100]}")


def _download_douyin(url: str) -> str:
    """
    抖音视频下载主流程

    Step 1: 如果是短链接 → 解析为长链接
    Step 2: 提取视频 ID
    Step 3: 尝试方式 A: 抖音网页 API 获取无水印直链
    Step 4: 如果 A 失败 → 尝试方式 B: 第三方解析接口
    Step 5: 如果 B 也失败 → 尝试方式 C: yt-dlp 兜底
    """
    # Step 1: 解析短链接
    if "v.douyin.com" in url:
        long_url = _resolve_douyin_short_url(url)
    else:
        long_url = url

    # Step 2: 提取视频 ID
    video_id = _extract_douyin_video_id(long_url)
    print(f"[douyin] 视频 ID: {video_id}")

    # 构造标准长链接
    standard_url = f"https://www.iesdouyin.com/share/video/{video_id}/"

    # Step 3: 方式 A - 抖音网页 API
    try:
        result = _douyin_api_download(video_id, standard_url)
        if result:
            return result
    except Exception as e:
        print(f"[douyin] 方式A(网页API)失败: {e}")

    # Step 4: 方式 B - 第三方解析接口
    try:
        result = _douyin_third_party_download(video_id)
        if result:
            return result
    except Exception as e:
        print(f"[douyin] 方式B(第三方接口)失败: {e}")

    # Step 5: 方式 C - yt-dlp 兜底
    try:
        print("[douyin] 尝试 yt-dlp 兜底下载...")
        return _download_with_ytdlp(standard_url, platform="douyin")
    except Exception as e:
        print(f"[douyin] 方式C(yt-dlp)失败: {e}")

    raise RuntimeError(
        f"抖音视频下载全部失败 (ID: {video_id})。\n"
        "可能原因：\n"
        "1. 视频已被删除或设为私密\n"
        "2. 抖音反爬策略更新，需要更新 Cookie\n"
        "3. 第三方解析接口暂时不可用\n"
        "建议：尝试其他视频链接"
    )


def _douyin_api_download(video_id: str, standard_url: str) -> str | None:
    """
    方式 A: 通过抖音网页 API 获取无水印视频直链

    请求 iesdouyin.com 网页 → 从 HTML 中提取视频播放地址
    """
    headers = {
        "User-Agent": MOBILE_UA,
        "Referer": "https://www.douyin.com/",
        "Cookie": DOUYIN_COOKIE,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    # 请求视频页面
    resp = requests.get(standard_url, headers=headers, timeout=15, proxies=_NO_PROXY)
    if resp.status_code != 200:
        print(f"[douyin] API 返回状态码: {resp.status_code}")
        return None

    html_text = resp.text

    # 尝试从 HTML 中提取播放地址
    # 方式1: 搜索 playAddr 或 play_addr 中的视频 URL
    play_url_patterns = [
        r'"playAddr"\s*:\s*\[?\{"src"\s*:\s*"([^"]+)"',
        r'"play_addr"\s*:\s*\{[^}]*"url_list"\s*:\s*\["([^"]+)"',
        r'"playApi"\s*:\s*"([^"]+)"',
        r'playAddr.*?src["\s:]+["\s]*([^"&\s]+\.mp4[^"&\s]*)',
    ]

    video_url = None
    for pattern in play_url_patterns:
        match = re.search(pattern, html_text)
        if match:
            video_url = match.group(1)
            # 解码 Unicode 转义
            video_url = video_url.encode().decode("unicode_escape", errors="ignore")
            break

    if not video_url:
        print("[douyin] 方式A: 未能从 HTML 中提取到视频地址")
        return None

    # 替换为无水印域名
    # 抖音有水印域名: playwm → 无水印域名: play
    video_url = video_url.replace("playwm", "play")

    print(f"[douyin] 方式A: 获取到视频地址: {video_url[:80]}...")

    # 下载视频
    local_path = os.path.join(TEMP_DIR, f"douyin_{video_id}.mp4")
    return _stream_download_with_headers(video_url, local_path, headers={
        "User-Agent": MOBILE_UA,
        "Referer": "https://www.douyin.com/",
    })


def _douyin_third_party_download(video_id: str) -> str | None:
    """
    方式 B: 使用第三方解析接口获取无水印视频

    接口1: https://api.douyin.wtf/api?url=...
    接口2: https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids=...
    """
    # ---- 接口1: douyin.wtf ----
    try:
        api_url = "https://api.douyin.wtf/api"
        resp = requests.get(api_url, params={
            "url": f"https://www.douyin.com/video/{video_id}",
            "minimal": "false",
        }, headers={
            "User-Agent": DESKTOP_UA,
        }, timeout=15, proxies=_NO_PROXY)

        if resp.status_code == 200:
            data = resp.json()
            # 尝试多种字段路径提取视频 URL
            video_url = None

            # 路径1: data.video_data.nwm_video_url
            video_url = (
                data.get("video_data", {})
                .get("nwm_video_url")
                or data.get("video_data", {})
                .get("wm_video_url")
            )

            # 路径2: data.video.play_addr.url_list[0]
            if not video_url:
                play_addr = data.get("video", {}).get("play_addr", {})
                url_list = play_addr.get("url_list", [])
                if url_list:
                    video_url = url_list[0]

            # 路径3: 直接在 data 中找
            if not video_url:
                video_url = data.get("nwm_video_url") or data.get("video_url")

            if video_url:
                print(f"[douyin] 方式B(第三方): 获取到视频地址: {video_url[:80]}...")
                local_path = os.path.join(TEMP_DIR, f"douyin_{video_id}.mp4")
                result = _stream_download_with_headers(video_url, local_path, headers={
                    "User-Agent": MOBILE_UA,
                    "Referer": "https://www.douyin.com/",
                })
                if result:
                    return result
    except Exception as e:
        print(f"[douyin] 第三方接口1异常: {e}")

    # ---- 接口2: iesdouyin.com iteminfo ----
    try:
        api_url = "https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/"
        resp = requests.get(api_url, params={
            "item_ids": video_id,
        }, headers={
            "User-Agent": MOBILE_UA,
            "Referer": "https://www.douyin.com/",
            "Cookie": DOUYIN_COOKIE,
        }, timeout=15, proxies=_NO_PROXY)

        if resp.status_code == 200:
            data = resp.json()
            items = data.get("item_list", [])
            if items:
                # 提取无水印视频地址
                video_info = items[0].get("video", {})
                play_addr = video_info.get("play_addr", {})
                url_list = play_addr.get("url_list", [])

                if url_list:
                    # 优先使用无水印链接
                    video_url = url_list[0]
                    # 替换有水印域名为无水印
                    video_url = video_url.replace("playwm", "play")

                    print(f"[douyin] 方式B(iteminfo): 获取到视频地址: {video_url[:80]}...")
                    local_path = os.path.join(TEMP_DIR, f"douyin_{video_id}.mp4")
                    result = _stream_download_with_headers(video_url, local_path, headers={
                        "User-Agent": MOBILE_UA,
                        "Referer": "https://www.douyin.com/",
                    })
                    if result:
                        return result
    except Exception as e:
        print(f"[douyin] 第三方接口2异常: {e}")

    print("[douyin] 方式B: 第三方接口均未成功")
    return None


# ============================================================
#  yt-dlp 通用下载
# ============================================================

def _download_with_ytdlp(url: str, platform: str = "general") -> str:
    """
    使用 yt-dlp 下载平台视频

    参数:
        url: 视频 URL
        platform: 平台标识 ("bilibili" / "douyin" / "general")
    """
    try:
        import yt_dlp
    except ImportError:
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "yt-dlp", "-q"],
                check=True,
            )
            import yt_dlp
        except Exception:
            raise RuntimeError("yt-dlp 未安装且自动安装失败。请手动运行: pip install yt-dlp")

    output_template = os.path.join(TEMP_DIR, "video_%(id)s.%(ext)s")

    # 根据平台配置不同的 headers
    if platform == "bilibili":
        http_headers = {
            "User-Agent": DESKTOP_UA,
            "Referer": "https://www.bilibili.com",
        }
    elif platform == "douyin":
        http_headers = {
            "User-Agent": MOBILE_UA,
            "Referer": "https://www.douyin.com/",
            "Cookie": DOUYIN_COOKIE,
        }
    else:
        http_headers = {
            "User-Agent": DESKTOP_UA,
        }

    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "http_headers": http_headers,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if not os.path.exists(filename):
                base, _ = os.path.splitext(filename)
                filename = base + ".mp4"
            if not os.path.exists(filename):
                raise FileNotFoundError(f"下载后找不到文件: {filename}")
            print(f"[download] yt-dlp 下载完成: {filename}")
            return filename
    except Exception as e:
        raise RuntimeError(f"yt-dlp 下载失败: {e}")


# ============================================================
#  通用下载工具
# ============================================================

def _stream_download_with_headers(url: str, local_path: str, headers: dict = None) -> str | None:
    """
    带自定义 headers 的流式下载

    参数:
        url: 视频直链
        local_path: 保存路径
        headers: 请求头

    返回:
        成功返回文件路径，失败返回 None
    """
    if headers is None:
        headers = {"User-Agent": MOBILE_UA}

    try:
        with requests.get(url, stream=True, headers=headers, timeout=60, proxies=_NO_PROXY) as resp:
            if resp.status_code != 200:
                print(f"[download] 请求失败，状态码: {resp.status_code}")
                return None

            # 检查是否真的是视频内容
            content_type = resp.headers.get("Content-Type", "")
            if "text" in content_type and "video" not in content_type:
                print(f"[download] 返回非视频内容: {content_type}")
                return None

            downloaded = 0
            with open(local_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

            # 检查文件大小，过小可能是错误页面
            file_size = os.path.getsize(local_path)
            if file_size < 10240:  # 小于 10KB
                os.remove(local_path)
                print(f"[download] 文件过小 ({file_size} bytes)，可能不是有效视频")
                return None

            print(f"[download] 下载完成: {local_path} ({downloaded / 1024 / 1024:.1f} MB)")
            return local_path

    except requests.RequestException as e:
        if os.path.exists(local_path):
            os.remove(local_path)
        print(f"[download] 流式下载失败: {e}")
        return None


def cleanup_temp_file(filepath: str):
    """清理临时下载的视频文件"""
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            print(f"[cleanup] 已删除临时文件: {filepath}")
    except Exception as e:
        print(f"[cleanup] 删除临时文件失败: {e}")
