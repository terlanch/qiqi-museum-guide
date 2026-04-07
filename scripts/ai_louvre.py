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

    wrapped = (
        "【输出要求】只输出最终讲解正文。\n"
        "禁止：内心独白、推理过程、自问自答、草稿、括号里自我纠正；"
        "禁止出现「用户」「笔记」「不对」「哦对」「首先我需要」等元话语。\n"
        "正文内不要使用 Markdown、不要用项目符号列表。\n\n"
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
    # 关闭深度思考，避免模型把推理过程写进正文（方舟 Responses API）
    # 可选：ARK_THINKING=disabled|enabled|auto，默认 disabled
    _tt = os.environ.get("ARK_THINKING", "disabled").strip().lower()
    if _tt in ("disabled", "enabled", "auto"):
        body["thinking"] = {"type": _tt}
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


def _museum_guide_spec() -> str:
    """一线博物馆语音导览级讲解词要求（与高质量人工稿对齐）。"""
    return """你正在撰写卢浮宫藏品的中文语音讲解词，质量须达到一线博物馆现场导览水准。

【篇幅】全文约 550～900 个汉字；宜分 4～7 个短自然段，段间用换行分隔。不要用项目符号、不要用 Markdown。

【风格】第三人称客观讲述；语气稳重、清晰，适合男声朗读；避免网络用语与空洞形容词堆砌。

【内容组织】按材料灵活取舍，通常应覆盖：
1）开篇点题：作品通行中文名、作者或文化背景（仅依据材料，材料无则弱化）；
2）时代、材质、题材与画中/雕塑中主要形象（人物身份等，以材料为准）；
3）细读至少一两处视觉或技法亮点（如神态、手势、构图、线条、设色、体量感、材质对比等）；若出现专业术语（如油画中的渐隐法、Sfumato 等），用一两句白话解释；
4）背景或整体氛围（若材料提及风景、建筑、空间等）；
5）艺术史或文化意义上的一笔收束（忌空泛口号）；
6）若材料明确写到当代展陈、防护玻璃、展厅位置等，应用一两句自然收尾。

【严谨】所给法文或元数据为唯一事实来源：可转写、重组、润色与合理串联，禁止编造具体年代阴谋、杜撰人物关系与无依据的历史事件。

【禁止】禁止任何思考过程、禁止元话语（如「用户问」「笔记」「不对」「哦对」）、禁止问答式自言自语。"""


def translate_title_fr_to_zh(title_fr: str) -> str:
    t = (title_fr or "").strip()
    if not t:
        return ""
    out = _chat(
        "任务：法文标题 → 中文展览通行译名。\n"
        "要求：只输出一行译名，不要书名号外的解释、不要第二行。\n\n"
        + t,
        max_tokens=128,
    )
    return out.split("\n")[0].strip()[:200]


def translate_narration_fr_to_zh(source_text: str, max_chars: int = 2400) -> str:
    """以法文素材为事实依据，重写为高质量中文讲解（非字对字机翻）。"""
    text = (source_text or "").strip()
    if not text:
        raise RuntimeError("无法翻译：法语正文为空")
    if len(text) > 6000:
        text = text[:6000] + "…"
    prompt = (
        _museum_guide_spec()
        + "\n\n【任务】以下内容为卢浮宫官网法文信息（含标题、年代、材质、描述、展厅位置等）。"
        "请综合写成一篇完整中文讲解词，不要标注「以下为译文」。\n\n---\n"
        + text
        + "\n---"
    )
    out = _chat(prompt, max_tokens=2800)
    return out[:max_chars].strip()


def generate_narration_zh(meta: Dict[str, Any], max_chars: int = 2400) -> str:
    """官网简介过短时，根据结构化字段生成同水准讲解。"""
    payload = {
        "title_fr": meta.get("titleFr") or "",
        "collection_fr": meta.get("collectionFr") or "",
        "date_fr": meta.get("displayDateCreatedFr") or "",
        "materials_fr": meta.get("materialsFr") or "",
        "description_fr": meta.get("descriptionFr") or "",
        "room_fr": meta.get("roomFr") or "",
        "location_fr": meta.get("currentLocationFr") or "",
    }
    prompt = (
        _museum_guide_spec()
        + "\n\n【任务】官网文字较少。请仅根据下列 JSON 元数据写同一水准的中文讲解词；"
        "信息不足处可概括性描述，但不得捏造具体史实与人名关系。\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
    out = _chat(prompt, max_tokens=2800)
    return out[:max_chars].strip()


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
