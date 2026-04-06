# -*- coding: utf-8 -*-
"""中文标题、讲解翻译与生成：优先火山方舟 Responses API（ARK_API_KEY），否则回退 MaaS v2（AK/SK）。"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

try:
    from volcengine.maas.v2 import MaasService
    from volcengine.maas import MaasException, ChatRole
except ImportError:
    MaasService = None  # type: ignore
    MaasException = Exception  # type: ignore
    ChatRole = None  # type: ignore


def ark_api_configured() -> bool:
    return bool(os.environ.get("ARK_API_KEY", "").strip())


def maas_configured() -> bool:
    if MaasService is None or ChatRole is None:
        return False
    ak = os.environ.get("VOLC_ACCESSKEY", "").strip()
    sk = os.environ.get("VOLC_SECRETKEY", "").strip()
    ep = os.environ.get("VOLC_MAAS_ENDPOINT_ID", "").strip()
    return bool(ak and sk and ep)


def llm_configured() -> bool:
    """构建脚本：只要配置了 Ark API Key 或 MaaS 即视为可生成中文。"""
    return ark_api_configured() or maas_configured()


def _extract_output_text_recursive(obj: Any) -> Optional[str]:
    if isinstance(obj, dict):
        if obj.get("type") == "output_text" and isinstance(obj.get("text"), str) and obj["text"].strip():
            return obj["text"].strip()
        if isinstance(obj.get("text"), str) and obj["text"].strip() and obj.get("type") != "input_text":
            # 部分返回仅含 text
            return obj["text"].strip()
        for v in obj.values():
            t = _extract_output_text_recursive(v)
            if t:
                return t
    elif isinstance(obj, list):
        for item in obj:
            t = _extract_output_text_recursive(item)
            if t:
                return t
    return None


def _ark_responses_chat(user_text: str, max_tokens: int) -> str:
    """POST https://ark.cn-beijing.volces.com/api/v3/responses（与官方 curl 示例一致，纯文本）。"""
    url = os.environ.get(
        "ARK_RESPONSES_URL", "https://ark.cn-beijing.volces.com/api/v3/responses"
    ).strip()
    key = os.environ["ARK_API_KEY"].strip()
    model = os.environ.get("ARK_MODEL_ID", "doubao-seed-2-0-lite-260215").strip()

    # 避免部分模型把推理过程一并输出到正文
    wrapped = (
        "【输出要求】只输出最终要展示给读者的正文，不要内心独白、推理步骤、草稿或「用户问」等元话语。\n\n"
        + user_text
    )

    body: Dict[str, Any] = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": wrapped}],
            }
        ],
    }
    if max_tokens > 0:
        body["max_output_tokens"] = max_tokens

    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        raise RuntimeError(f"Ark API HTTP {e.code}: {err_body[:800]}") from e

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Ark API 返回非 JSON: {raw[:500]}") from e

    text = _extract_output_text_recursive(data)
    if text:
        return text
    raise RuntimeError(f"Ark API 响应中未找到文本: {raw[:1200]}")


def _service() -> MaasService:
    maas = MaasService(
        host="maas-api.ml-platform-cn-beijing.volces.com",
        region="cn-beijing",
        connection_timeout=60,
        socket_timeout=120,
    )
    maas.set_ak(os.environ["VOLC_ACCESSKEY"].strip())
    maas.set_sk(os.environ["VOLC_SECRETKEY"].strip())
    return maas


def _maas_chat(user_content: str, max_tokens: int) -> str:
    if not maas_configured():
        raise RuntimeError(
            "未配置火山方舟 MaaS：请设置 VOLC_ACCESSKEY、VOLC_SECRETKEY、VOLC_MAAS_ENDPOINT_ID"
        )
    ep = os.environ["VOLC_MAAS_ENDPOINT_ID"].strip()
    maas = _service()
    req = {
        "parameters": {"max_new_tokens": max_tokens, "temperature": 0.45},
        "messages": [{"role": ChatRole.USER, "content": user_content}],
    }
    try:
        resp = maas.chat(ep, req)
    except MaasException as e:
        raise RuntimeError(f"MaaS 调用失败: {e}") from e
    if not resp or not getattr(resp, "choices", None):
        raise RuntimeError("MaaS 返回为空")
    ch0 = resp.choices[0]
    if not ch0.message or not ch0.message.content:
        raise RuntimeError("MaaS 无文本内容")
    return ch0.message.content.strip()


def _chat(user_content: str, max_tokens: int = 1200) -> str:
    if ark_api_configured():
        return _ark_responses_chat(user_content, max_tokens)
    return _maas_chat(user_content, max_tokens)


def translate_title_fr_to_zh(title_fr: str) -> str:
    t = (title_fr or "").strip()
    if not t:
        return ""
    out = _chat(
        "将下列卢浮宫藏品法文标题译为中文展览常用译名。只输出一行译文，不要引号或解释。\n\n" + t,
        max_tokens=128,
    )
    return out.split("\n")[0].strip()[:200]


def translate_narration_fr_to_zh(source_text: str, max_chars: int = 900) -> str:
    text = (source_text or "").strip()
    if not text:
        raise RuntimeError("无法翻译：法语正文为空")
    if len(text) > 3500:
        text = text[:3500] + "…"
    out = _chat(
        "你是博物馆中文讲解员。将下列卢浮宫官网法语文本译为自然、口语化的中文讲解稿，"
        "适合男声朗读；作品名用常见中文译名；不要列表或 Markdown；控制在约 450 字以内。\n\n"
        + text,
        max_tokens=1024,
    )
    return out[:max_chars]


def generate_narration_zh(meta: Dict[str, Any], max_chars: int = 600) -> str:
    """官网简介过短时，根据结构化字段生成中文讲解。"""
    payload = {
        "title_fr": meta.get("titleFr") or "",
        "collection_fr": meta.get("collectionFr") or "",
        "date_fr": meta.get("displayDateCreatedFr") or "",
        "materials_fr": meta.get("materialsFr") or "",
        "description_fr": meta.get("descriptionFr") or "",
        "room_fr": meta.get("roomFr") or "",
        "location_fr": meta.get("currentLocationFr") or "",
    }
    out = _chat(
        "你是卢浮宫中文讲解员。官网对该件藏品文字介绍很短或为空。请根据下列法文元数据写一段中文讲解，"
        "约 200～350 字，口语化、适合男声朗读；信息不足处可合理概括，勿编造具体历史事件细节；"
        "不要列表或 Markdown。元数据（JSON）：\n"
        + json.dumps(payload, ensure_ascii=False, indent=2),
        max_tokens=900,
    )
    return out[:max_chars]


def narration_zh_from_louvre(
    *,
    fr_brief: str,
    meta_for_generate: Dict[str, Any],
    min_desc_len: int = 80,
) -> str:
    """优先翻译简介；正文太短则走生成。"""
    plain = (meta_for_generate.get("descriptionFr") or "").replace("\r\n", " ").strip()
    if len(plain) >= min_desc_len and (fr_brief or "").strip():
        return translate_narration_fr_to_zh(fr_brief)
    return generate_narration_zh(meta_for_generate)
