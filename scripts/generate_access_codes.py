#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成访问验证码列表（默认 1000 条 × 16 位随机字符串），写入：
  - docs/data/access_codes.json  （站点校验用，随 Pages 部署）
  - docs/access_codes_1000.txt    （可分发的明文清单）

用法：
  python3 scripts/generate_access_codes.py
  python3 scripts/generate_access_codes.py --count 500 --length 16
"""
from __future__ import annotations

import argparse
import json
import secrets
import string
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_OUT = ROOT / "docs" / "data" / "access_codes.json"
TXT_OUT = ROOT / "docs" / "access_codes_1000.txt"

ALPHABET = string.ascii_letters + string.digits  # A–Z a–z 0–9


def random_code(length: int) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=1000, help="生成条数")
    ap.add_argument("--length", type=int, default=16, help="每条字符数")
    args = ap.parse_args()

    if args.count < 1 or args.length < 8:
        raise SystemExit("count>=1, length>=8")

    used: set[str] = set()
    codes: list[str] = []
    while len(codes) < args.count:
        c = random_code(args.length)
        if c not in used:
            used.add(c)
            codes.append(c)

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "length": args.length,
        "count": len(codes),
        "codes": codes,
    }
    JSON_OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    header = (
        f"卢浮宫语音讲解站点 · 访问验证码清单\n"
        f"共 {len(codes)} 条，每条 {args.length} 位（大小写字母与数字）。\n"
        f"校验数据：docs/data/access_codes.json\n"
        f"请勿将本文件公开托管；站点使用 sessionStorage 记住本次浏览器内的通过状态。\n"
        f"---\n"
    )
    TXT_OUT.write_text(header + "\n".join(codes) + "\n", encoding="utf-8")

    print(f"已写入 {JSON_OUT} 与 {TXT_OUT} ，共 {len(codes)} 条。")


if __name__ == "__main__":
    main()
