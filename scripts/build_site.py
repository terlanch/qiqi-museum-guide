#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1) 抓取卢浮宫官方馆藏 JSON（collections.louvre.fr）
2) 解析馆区/楼层/展厅（room、currentLocation）
3) 火山方舟 MaaS：法文标题 -> 中文名；简介翻译或 AI 生成中文讲解（必须中文）
4) 每藏品写入 artifacts/{arkId}.json；TTS 写入 docs/audio/{arkId}.mp3
5) 汇总 docs/data/catalog.json 供静态页筛选与搜索
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Set

# 与 volc_tts.py、ai_louvre.py 等同在 scripts/ 目录下
_SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = _SCRIPT_DIR.parent

DOCS = ROOT / "docs"
ARTIFACTS_DIR = ROOT / "artifacts"
LOCAL_RAW_JSON = ROOT / "data" / "louvre_json"
DATA_DIR = DOCS / "data"
AUDIO_DIR = DOCS / "audio"
DEFAULT_SEEDS = ROOT / "config" / "seeds.json"

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

if not (_SCRIPT_DIR / "volc_tts.py").is_file():
    print(
        f"缺少 scripts/volc_tts.py，请从仓库根目录运行：python3 scripts/build_site.py\n"
        f"期望：{_SCRIPT_DIR / 'volc_tts.py'}",
        file=sys.stderr,
    )
    sys.exit(1)

sys.path.insert(0, str(_SCRIPT_DIR))
from volc_tts import tts_http_stream_save  # noqa: E402
from location_parse import parse_louvre_location  # noqa: E402
from ai_louvre import (  # noqa: E402
    llm_configured,
    narration_zh_from_louvre,
    translate_title_fr_to_zh,
)


def fetch_louvre_json(ark_id: str) -> Dict[str, Any]:
    """优先使用 download-curated 已下载的本地 JSON，否则请求官网。"""
    local = LOCAL_RAW_JSON / f"{ark_id}.json"
    if local.is_file() and local.stat().st_size > 10:
        return json.loads(local.read_text(encoding="utf-8"))
    url = f"https://collections.louvre.fr/ark:/53355/{ark_id}.json"
    req = urllib.request.Request(url, headers={"User-Agent": "LouvreGuideBuilder/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def get_modified(d: Dict[str, Any]) -> str:
    return (d.get("modified ") or d.get("modified") or "").strip()


def inventory_entries(d: Dict[str, Any]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for item in d.get("objectNumber") or []:
        if isinstance(item, dict) and item.get("value"):
            out.append(
                {"value": str(item["value"]).strip(), "type": str(item.get("type") or "")}
            )
    return out


def normalize_token(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[\s./\-_]+", "", s)
    return s


def name_search_blob(title_zh: str, title_fr: str) -> str:
    return normalize_token(title_zh + title_fr)


def build_french_brief(d: Dict[str, Any], max_len: int = 2200) -> str:
    parts: List[str] = []
    title = (d.get("title") or "").strip()
    if title:
        parts.append(title)
    comp = (d.get("titleComplement") or "").strip()
    if comp:
        parts.append(comp)
    dc = (d.get("displayDateCreated") or "").strip()
    if dc:
        parts.append(dc.replace("\r\n", " ").strip())
    mat = (d.get("materialsAndTechniques") or "").strip()
    if mat:
        parts.append(mat.replace("\r\n", " ").strip())
    desc = (d.get("description") or "").strip()
    if desc:
        parts.append(desc.replace("\r\n", " ").strip())
    loc = (d.get("currentLocation") or "").strip()
    if loc:
        parts.append(f"Localisation : {loc}")
    text = "\n\n".join(parts)
    if len(text) > max_len:
        text = text[: max_len - 1] + "…"
    return text


def load_seeds(path: Path) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("arks") or [])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seeds",
        type=Path,
        default=None,
        help=f"种子 JSON（含 arks 数组），默认 {DEFAULT_SEEDS.name}",
    )
    parser.add_argument(
        "--skip-tts",
        action="store_true",
        help="只生成 artifacts 与 catalog，不调用语音合成",
    )
    parser.add_argument(
        "--allow-without-maas",
        action="store_true",
        help="仅调试：未配置 MaaS 时仍抓取并写法文 artifacts（无中文、无 TTS）",
    )
    args = parser.parse_args()

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    if not args.allow_without_maas and not llm_configured():
        print(
            "错误：必须配置中文翻译/生成能力。任选其一：\n"
            "  · 火山方舟 Responses：ARK_API_KEY（可选 ARK_MODEL_ID、ARK_RESPONSES_URL）\n"
            "  · 火山方舟 MaaS：VOLC_ACCESSKEY、VOLC_SECRETKEY、VOLC_MAAS_ENDPOINT_ID\n"
            "或传入 --allow-without-maas 仅做法文调试。",
            file=sys.stderr,
        )
        sys.exit(1)

    seeds_path = (args.seeds or DEFAULT_SEEDS).resolve()
    if not seeds_path.is_file():
        print(f"错误：找不到种子文件 {seeds_path}", file=sys.stderr)
        sys.exit(1)
    seeds = load_seeds(seeds_path)
    catalog: List[Dict[str, Any]] = []

    for i, seed in enumerate(seeds):
        ark_id = str(seed.get("arkId") or "").strip()
        if not ark_id:
            continue
        override_zh = (seed.get("narration_zh") or "").strip() or None
        print(f"[{i + 1}/{len(seeds)}] 抓取 {ark_id} …")

        try:
            d = fetch_louvre_json(ark_id)
        except Exception as e:
            print(f"  跳过：抓取失败 {e}")
            continue

        title_fr = (d.get("title") or "").strip()
        room_fr = (d.get("room") or "").strip()
        loc_fr = (d.get("currentLocation") or "").strip()
        desc_fr = (d.get("description") or "").strip()
        mat_fr = (d.get("materialsAndTechniques") or "").strip()
        dc_fr = (d.get("displayDateCreated") or "").strip()
        coll_fr = (d.get("collection") or "").strip()

        loc = parse_louvre_location(room_fr, loc_fr)
        inv = inventory_entries(d)
        fr_brief = build_french_brief(d)

        meta_for_gen = {
            "titleFr": title_fr,
            "collectionFr": coll_fr,
            "displayDateCreatedFr": dc_fr,
            "materialsFr": mat_fr,
            "descriptionFr": desc_fr,
            "roomFr": room_fr,
            "currentLocationFr": loc_fr,
        }

        narration_source = "override"
        title_zh = ""
        narration_zh = ""

        plain_desc = desc_fr.replace("\r\n", " ").strip()
        if override_zh:
            narration_zh = override_zh
            if llm_configured():
                title_zh = translate_title_fr_to_zh(title_fr)
            else:
                title_zh = title_fr
        elif llm_configured():
            title_zh = translate_title_fr_to_zh(title_fr)
            narration_zh = narration_zh_from_louvre(
                fr_brief=fr_brief,
                meta_for_generate=meta_for_gen,
                min_desc_len=80,
            )
            narration_source = (
                "translated" if len(plain_desc) >= 80 and fr_brief.strip() else "generated"
            )
        else:
            title_zh = title_fr
            narration_zh = ""
            narration_source = "none"

        artifact: Dict[str, Any] = {
            "id": ark_id,
            "source": {
                "url": d.get("url") or f"https://collections.louvre.fr/ark:/53355/{ark_id}",
                "modified": get_modified(d),
            },
            "titleFr": title_fr,
            "titleZh": title_zh,
            "location": loc,
            "collectionFr": coll_fr,
            "inventory": inv,
            "narrationZh": narration_zh,
            "narrationSource": narration_source,
            "frenchBrief": fr_brief,
        }

        art_path = ARTIFACTS_DIR / f"{ark_id}.json"
        with open(art_path, "w", encoding="utf-8") as f:
            json.dump(artifact, f, ensure_ascii=False, indent=2)
        print(f"  已写 {art_path.relative_to(ROOT)}")

        audio_rel = f"audio/{ark_id}.mp3"
        audio_path = DOCS / audio_rel

        if args.skip_tts:
            audio_rel = ""
        elif narration_zh:
            try:
                tts_http_stream_save(str(narration_zh), str(audio_path), explicit_language="zh")
                print(f"  已生成 {audio_rel}")
            except Exception as e:
                print(f"  TTS 失败：{e}")
                audio_rel = ""
        else:
            audio_rel = ""

        inv_tokens: Set[str] = set()
        for e in inv:
            inv_tokens.add(normalize_token(e["value"]))
            for part in re.split(r"[^\w]+", e["value"]):
                p = part.strip().lower()
                if len(p) >= 2:
                    inv_tokens.add(p)

        catalog.append(
            {
                "id": ark_id,
                "titleZh": title_zh,
                "titleFr": title_fr,
                "wingKey": loc["wingKey"],
                "wingZh": loc["wingZh"],
                "floor": loc["floor"],
                "floorLabel": loc["floorLabel"],
                "gallery": loc["gallery"],
                "galleryLabel": loc["galleryLabel"],
                "collectionFr": coll_fr,
                "inventory": inv,
                "nameSearch": name_search_blob(title_zh, title_fr),
                "inventorySearch": " ".join(sorted(inv_tokens)),
                "narrationPreview": (narration_zh[:480] + "…") if len(narration_zh) > 480 else narration_zh,
                "audio": audio_rel if narration_zh and audio_path.is_file() else "",
                "url": artifact["source"]["url"],
            }
        )
        time.sleep(0.35)

    payload = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "works": catalog,
    }
    out_catalog = DATA_DIR / "catalog.json"
    with open(out_catalog, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # 保留 works.json 别名，避免旧链接失效；内容与 catalog 相同结构
    with open(DATA_DIR / "works.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"已写入 {out_catalog.relative_to(ROOT)}，共 {len(catalog)} 条；单件 JSON 在 artifacts/。")


if __name__ == "__main__":
    main()
