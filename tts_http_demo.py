# -*- coding: utf-8 -*-
"""
本地快速验证 TTS：与字节大模型语音合成 HTTP 单向流式示例一致，实现已抽离到 scripts/volc_tts.py。

使用前在环境变量中配置（勿把密钥写入仓库）：
  VOLC_TTS_APP_ID、VOLC_TTS_ACCESS_KEY、VOLC_TTS_RESOURCE_ID
可选：VOLC_TTS_SPEAKER、VOLC_TTS_URL
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from volc_tts import tts_http_stream_save  # noqa: E402

if __name__ == "__main__":
    tts_http_stream_save(
        "这是一段测试文本，用于测试语音合成 HTTP 单向流式接口。",
        str(ROOT / "tts_test.mp3"),
        explicit_language="zh",
    )
    print("已写入", ROOT / "tts_test.mp3")
