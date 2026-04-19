// ============================================================
// modules/parser.js
// 视频解析模块：集成 Whisper 语音识别 + Qwen-VL 视觉分析
// 输出结构化 JSON 数据（含 point_id, coordinates, content 等）
// ============================================================

const fs = require('fs');
const path = require('path');
const CONFIG = require('../config');

// -------------------- 常量 --------------------

const WHISPER_API_URL = 'https://api.openai.com/v1/audio/transcriptions';
const QWEN_VL_API_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions';

// 关键帧提取间隔（秒），可根据视频长度调整
const KEYFRAME_INTERVAL_SEC = 5;

// -------------------- Whisper 语音识别 --------------------

/**
 * 调用 Whisper API 对视频/音频文件进行语音转文字
 * @param {string} filePath - 视频/音频文件的本地路径
 * @param {object} [options] - 可选参数
 * @param {string} [options.language='zh'] - 语言代码
 * @param {boolean} [options.timestamp_granularities=true] - 是否返回时间戳
 * @returns {Promise<{text: string, segments: Array<{start: number, end: number, text: string}>}>}
 */
async function transcribeAudio(filePath, options = {}) {
  const { language = 'zh', timestamp_granularities = true } = options;

  if (!CONFIG.WHISPER_API_KEY) {
    throw new Error('WHISPER_API_KEY 未配置，请在 config.js 中填写');
  }

  // 构建 FormData（Node 18+ 原生支持 FormData）
  const formData = new FormData();
  const fileBuffer = fs.readFileSync(filePath);
  const fileName = path.basename(filePath);

  formData.append('file', new Blob([fileBuffer]), fileName);
  formData.append('model', 'whisper-1');
  formData.append('language', language);

  if (timestamp_granularities) {
    formData.append('timestamp_granularities[]', 'segment');
    formData.append('response_format', 'verbose_json');
  }

  const response = await fetch(WHISPER_API_URL, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${CONFIG.WHISPER_API_KEY}`,
    },
    body: formData,
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Whisper API 调用失败 (${response.status}): ${errText}`);
  }

  const data = await response.json();

  return {
    text: data.text || '',
    segments: (data.segments || []).map((seg) => ({
      start: seg.start,
      end: seg.end,
      text: seg.text.trim(),
    })),
  };
}

// -------------------- 关键帧提取 --------------------

/**
 * 从视频中提取关键帧（Base64 编码）
 * 需要系统安装 ffmpeg
 * @param {string} videoPath - 视频文件路径
 * @param {number} [intervalSec=5] - 提取间隔（秒）
 * @returns {Promise<Array<{timestamp: number, frameBase64: string}>>}
 */
async function extractKeyframes(videoPath, intervalSec = KEYFRAME_INTERVAL_SEC) {
  const { execSync } = require('child_process');

  const tmpDir = path.join(__dirname, '..', '.tmp_frames');
  if (!fs.existsSync(tmpDir)) fs.mkdirSync(tmpDir, { recursive: true });

  // 使用 ffmpeg 按 interval 提取帧
  const outputPattern = path.join(tmpDir, 'frame_%04d.jpg');
  const cmd = `ffmpeg -i "${videoPath}" -vf "fps=1/${intervalSec}" -q:v 2 "${outputPattern}" -y`;

  try {
    execSync(cmd, { stdio: 'pipe' });
  } catch (err) {
    throw new Error(`ffmpeg 关键帧提取失败：${err.message}`);
  }

  // 读取所有提取的帧
  const frameFiles = fs
    .readdirSync(tmpDir)
    .filter((f) => f.startsWith('frame_') && f.endsWith('.jpg'))
    .sort();

  const keyframes = frameFiles.map((file, index) => {
    const framePath = path.join(tmpDir, file);
    const buffer = fs.readFileSync(framePath);
    // 清理临时文件
    fs.unlinkSync(framePath);
    return {
      timestamp: (index + 1) * intervalSec,
      frameBase64: buffer.toString('base64'),
    };
  });

  // 清理临时目录
  try { fs.rmdirSync(tmpDir); } catch (_) { /* ignore */ }

  return keyframes;
}

// -------------------- Qwen-VL 视觉分析 --------------------

/**
 * 调用 Qwen-VL API 分析单帧画面中的地标、路牌文字和环境
 * @param {string} frameBase64 - Base64 编码的图片数据
 * @returns {Promise<{landmarks: string[], signs: string[], environment: string}>}
 */
async function analyzeFrame(frameBase64) {
  if (!CONFIG.QWEN_API_KEY) {
    throw new Error('QWEN_API_KEY 未配置，请在 config.js 中填写');
  }

  const prompt = [
    '请分析这张图片，识别以下内容并以 JSON 格式返回：',
    '1. landmarks: 画面中可辨识的地标建筑或自然景观（数组）',
    '2. signs: 画面中路牌、标识牌上的文字（数组）',
    '3. environment: 对整体环境的简要描述，包括地形、植被、天气等',
    '',
    '请严格按以下 JSON 格式返回，不要添加任何其他内容：',
    '{"landmarks": [...], "signs": [...], "environment": "..."}',
  ].join('\n');

  const response = await fetch(QWEN_VL_API_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${CONFIG.QWEN_API_KEY}`,
    },
    body: JSON.stringify({
      model: 'qwen-vl-max',
      messages: [
        {
          role: 'user',
          content: [
            { type: 'text', text: prompt },
            {
              type: 'image_url',
              image_url: { url: `data:image/jpeg;base64,${frameBase64}` },
            },
          ],
        },
      ],
    }),
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Qwen-VL API 调用失败 (${response.status}): ${errText}`);
  }

  const data = await response.json();
  const content = data.choices?.[0]?.message?.content || '';

  // 尝试从返回文本中提取 JSON
  try {
    const jsonMatch = content.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      return JSON.parse(jsonMatch[0]);
    }
  } catch (_) { /* fall through */ }

  // 如果解析失败，返回原始内容
  return {
    landmarks: [],
    signs: [],
    environment: content,
  };
}

/**
 * 批量分析关键帧
 * @param {Array<{timestamp: number, frameBase64: string}>} keyframes
 * @returns {Promise<Array<{timestamp: number, analysis: object}>>}
 */
async function analyzeKeyframes(keyframes) {
  const results = [];

  for (const frame of keyframes) {
    try {
      const analysis = await analyzeFrame(frame.frameBase64);
      results.push({
        timestamp: frame.timestamp,
        analysis,
      });
    } catch (err) {
      console.warn(`[parser] 关键帧 @${frame.timestamp}s 分析失败: ${err.message}`);
      results.push({
        timestamp: frame.timestamp,
        analysis: { landmarks: [], signs: [], environment: '', error: err.message },
      });
    }

    // 简易限流：避免 API 请求过快
    await new Promise((r) => setTimeout(r, 500));
  }

  return results;
}

// -------------------- 数据合并与结构化 --------------------

/**
 * 将 Whisper 语音片段与 Qwen-VL 视觉分析结果合并为结构化 JSON
 *
 * 输出格式：
 * {
 *   "video_id": "xxx",
 *   "points": [
 *     {
 *       "point_id": "pt_001",
 *       "timestamp_start": 0,
 *       "timestamp_end": 5,
 *       "coordinates": { "lng": null, "lat": null },
 *       "content": {
 *         "speech": "...",
 *         "landmarks": ["..."],
 *         "signs": ["..."],
 *         "environment": "..."
 *       }
 *     }
 *   ]
 * }
 *
 * @param {object} whisperResult - Whisper 转写结果 { text, segments }
 * @param {Array} visionResults - Qwen-VL 分析结果数组
 * @param {object} [metadata] - 视频元数据
 * @returns {object} 结构化解析结果
 */
function mergeResults(whisperResult, visionResults, metadata = {}) {
  // 以关键帧时间点为锚点，合并语音和视觉数据
  const points = visionResults.map((vr, index) => {
    const timestamp = vr.timestamp;
    const prevTimestamp = index > 0 ? visionResults[index - 1].timestamp : 0;

    // 找出落在当前时间区间内的语音片段
    const matchedSegments = whisperResult.segments.filter(
      (seg) => seg.start >= prevTimestamp && seg.start < timestamp
    );

    const pointId = `pt_${String(index + 1).padStart(3, '0')}`;

    return {
      point_id: pointId,
      timestamp_start: prevTimestamp,
      timestamp_end: timestamp,
      coordinates: {
        lng: null, // 待后续通过地图交互或 GPS 数据填充
        lat: null,
      },
      content: {
        speech: matchedSegments.map((s) => s.text).join(' '),
        landmarks: vr.analysis.landmarks || [],
        signs: vr.analysis.signs || [],
        environment: vr.analysis.environment || '',
      },
    };
  });

  // 处理最后一个关键帧之后的残余语音段
  if (visionResults.length > 0 && whisperResult.segments.length > 0) {
    const lastTimestamp = visionResults[visionResults.length - 1].timestamp;
    const trailingSegments = whisperResult.segments.filter(
      (seg) => seg.start >= lastTimestamp
    );
    if (trailingSegments.length > 0) {
      const lastPoint = points[points.length - 1];
      lastPoint.content.speech += (lastPoint.content.speech ? ' ' : '') +
        trailingSegments.map((s) => s.text).join(' ');
      lastPoint.timestamp_end = trailingSegments[trailingSegments.length - 1].end;
    }
  }

  return {
    video_id: metadata.videoId || generateVideoId(),
    video_metadata: {
      duration: metadata.duration || null,
      created_at: new Date().toISOString(),
    },
    points,
  };
}

// -------------------- 工具函数 --------------------

/**
 * 生成唯一的 video_id
 * @returns {string}
 */
function generateVideoId() {
  return `vid_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

// -------------------- 主入口 --------------------

/**
 * 解析视频文件，返回结构化数据
 * 完整流程：提取关键帧 → 语音转写 → 视觉分析 → 合并输出
 *
 * @param {string} videoPath - 视频文件路径
 * @param {object} [options] - 可选参数
 * @param {number} [options.keyframeInterval=5] - 关键帧提取间隔（秒）
 * @param {string} [options.language='zh'] - Whisper 识别语言
 * @param {object} [options.metadata] - 视频元数据（videoId, duration 等）
 * @returns {Promise<object>} 结构化解析结果
 */
async function parseVideo(videoPath, options = {}) {
  const {
    keyframeInterval = KEYFRAME_INTERVAL_SEC,
    language = 'zh',
    metadata = {},
  } = options;

  // 校验文件
  if (!fs.existsSync(videoPath)) {
    throw new Error(`视频文件不存在: ${videoPath}`);
  }

  console.log(`[parser] 开始解析视频: ${videoPath}`);

  // Step 1: 并行执行语音转写和关键帧提取
  console.log('[parser] Step 1/3: 语音转写 & 关键帧提取（并行）...');
  const [whisperResult, keyframes] = await Promise.all([
    transcribeAudio(videoPath, { language }),
    extractKeyframes(videoPath, keyframeInterval),
  ]);

  console.log(`[parser] 语音转写完成，共 ${whisperResult.segments.length} 个片段`);
  console.log(`[parser] 关键帧提取完成，共 ${keyframes.length} 帧`);

  // Step 2: 视觉分析关键帧
  console.log('[parser] Step 2/3: 视觉分析关键帧...');
  const visionResults = await analyzeKeyframes(keyframes);

  // Step 3: 合并结果
  console.log('[parser] Step 3/3: 合并结构化数据...');
  const result = mergeResults(whisperResult, visionResults, metadata);

  console.log(`[parser] 解析完成，共生成 ${result.points.length} 个数据点`);
  return result;
}

// -------------------- 导出 --------------------

module.exports = {
  parseVideo,
  transcribeAudio,
  extractKeyframes,
  analyzeFrame,
  analyzeKeyframes,
  mergeResults,
};
