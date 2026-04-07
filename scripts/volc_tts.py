# -*- coding: utf-8 -*-
"""火山引擎 / 豆包 大模型语音合成 HTTP 单向流式（与 tts_http_demo 一致）。"""
from __future__ import annotations

import base64
import json
import os
from typing import Any, Dict, Optional

import requests

DEFAULT_TTS_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
DEFAULT_SPEAKER = "zh_male_ruyayichen_uranus_bigtts"


def _tts_http_error_hint(status: int, body_snip: str) -> str:
    if status != 403:
        return ""
    try:
        j = json.loads(body_snip)
        hdr = j.get("header") or {}
        code = hdr.get("code")
        msg = str(hdr.get("message") or "")
    except (json.JSONDecodeError, TypeError):
        return ""
    if code != 45000030 and "not granted" not in msg.lower():
        return ""
    return (
        "\n\n【处理说明】错误码 45000030：VOLC_TTS_RESOURCE_ID 与当前 AppId/AccessKey 未绑定或资源未开通/已过期。"
        "\n请打开 https://console.volcengine.com/ → 豆包语音（或大模型语音合成）→ 选中你的应用，"
        "复制该应用下的 AppId、Access Key、以及控制台展示的 Resource ID（勿使用他人示例里的 ResourceId）。"
        "\n三者必须同属一个应用；更新 .env 后重试。"
    )


def build_tts_headers() -> Dict[str, str]:
    app_id = os.environ.get("VOLC_TTS_APP_ID", "").strip()
    access_key = os.environ.get("VOLC_TTS_ACCESS_KEY", "").strip()
    resource_id = os.environ.get("VOLC_TTS_RESOURCE_ID", "").strip()
    if not app_id or not access_key or not resource_id:
        raise RuntimeError(
            "请设置环境变量 VOLC_TTS_APP_ID、VOLC_TTS_ACCESS_KEY、VOLC_TTS_RESOURCE_ID"
        )
    return {
        "X-Api-App-Id": app_id,
        "X-Api-Access-Key": access_key,
        "X-Api-Resource-Id": resource_id,
        "Content-Type": "application/json",
        "Connection": "keep-alive",
    }


def build_tts_payload(
    text: str,
    *,
    speaker: Optional[str] = None,
    explicit_language: str = "zh",
    uid: str = "louvre-guide",
) -> Dict[str, Any]:
    sp = (speaker or os.environ.get("VOLC_TTS_SPEAKER") or DEFAULT_SPEAKER).strip()
    additions = {
        "explicit_language": explicit_language,
        "disable_markdown_filter": True,
        "enable_timestamp": True,
    }
    return {
        "user": {"uid": uid},
        "req_params": {
            "text": text,
            "speaker": sp,
            "audio_params": {
                "format": "mp3",
                "sample_rate": 24000,
                "enable_timestamp": True,
            },
            "additions": json.dumps(additions, ensure_ascii=False),
        },
    }


def tts_http_stream_save(
    text: str,
    audio_save_path: str,
    *,
    url: Optional[str] = None,
    speaker: Optional[str] = None,
    explicit_language: str = "zh",
) -> None:
    headers = build_tts_headers()
    payload = build_tts_payload(
        text, speaker=speaker, explicit_language=explicit_language
    )
    endpoint = (url or os.environ.get("VOLC_TTS_URL") or DEFAULT_TTS_URL).strip()

    session = requests.Session()
    response = None
    try:
        response = session.post(endpoint, headers=headers, json=payload, stream=True)
        logid = response.headers.get("X-Tt-Logid")
        if response.status_code != 200:
            body_snip = response.text[:800]
            extra = _tts_http_error_hint(response.status_code, body_snip)
            raise RuntimeError(
                f"TTS HTTP {response.status_code}, logid={logid}, body={body_snip}{extra}"
            )

        audio_data = bytearray()
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            data = json.loads(line)
            code = data.get("code", 0)

            if code == 0 and data.get("data"):
                audio_data.extend(base64.b64decode(data["data"]))
                continue
            if code == 0 and data.get("sentence"):
                continue
            if code == 20000000:
                break
            if code > 0:
                raise RuntimeError(f"TTS 错误: {data}")

        if not audio_data:
            raise RuntimeError("未收到音频数据")

        os.makedirs(os.path.dirname(os.path.abspath(audio_save_path)) or ".", exist_ok=True)
        with open(audio_save_path, "wb") as f:
            f.write(audio_data)
        os.chmod(audio_save_path, 0o644)
    finally:
        if response is not None:
            response.close()
        session.close()
