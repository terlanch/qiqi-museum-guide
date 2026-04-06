# -*- coding: utf-8 -*-
"""从卢浮宫馆藏 JSON 的 room / currentLocation 解析馆区、楼层、展厅号（法文字段）。"""
from __future__ import annotations

import re
from typing import Any, Dict

# 侧楼法语名 -> 前端筛选用 key + 中文展示
WINGS = (
    ("richelieu", "黎塞留馆"),
    ("denon", "德农馆"),
    ("sully", "叙利馆"),
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def parse_louvre_location(room: str, current_location: str) -> Dict[str, Any]:
    room_n = _norm(room)
    loc_n = _norm(current_location)
    blob = f"{room_n} {loc_n}"

    wing_key = ""
    wing_zh = ""
    for en, zh in WINGS:
        if en in blob:
            wing_key = en
            wing_zh = zh
            break

    gallery = ""
    for src in (room or "", current_location or ""):
        m = re.search(r"(?i)salle\s+(\d+)", src)
        if m:
            gallery = m.group(1)
            break

    floor = ""
    for src in (room or "", current_location or ""):
        m = re.search(r"(?i)niveau\s+(-?\d+)", src)
        if m:
            floor = m.group(1)
            break

    return {
        "wingKey": wing_key or "unknown",
        "wingZh": wing_zh or "馆区未识别",
        "floor": floor,
        "floorLabel": f"{floor} 层" if floor else "",
        "gallery": gallery,
        "galleryLabel": f"{gallery} 号展厅" if gallery else "",
        "roomFr": (room or "").strip(),
        "currentLocationFr": (current_location or "").strip(),
    }
