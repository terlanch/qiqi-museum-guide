#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成访问验证码（默认 1000 条 × 16 位随机字符串）。

公开部署文件（不含明文，仅 SHA-256 十六进制）：
  docs/data/access_codes.json

明文清单（仅本地留存、发给买家；勿提交 Git）：
  config/private/access_codes_plaintext.txt

用法：
  python3 scripts/generate_access_codes.py
  python3 scripts/generate_access_codes.py --count 500 --expires 2026-04-30
"""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import string
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_OUT = ROOT / "docs" / "data" / "access_codes.json"
PRIVATE_DIR = ROOT / "config" / "private"
TXT_OUT = PRIVATE_DIR / "access_codes_plaintext.txt"

ALPHABET = string.ascii_letters + string.digits  # A–Z a–z 0–9

DEFAULT_MERCHANT = "https://xhslink.com/m/9XCmYeaBoVu"


def code_sha256_hex(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def random_code(length: int) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=1000, help="生成条数")
    ap.add_argument("--length", type=int, default=16, help="每条字符数")
    ap.add_argument(
        "--expires",
        type=str,
        default="2026-04-30",
        help="本批统一截止日期 YYYY-MM-DD（含当日仍有效）",
    )
    ap.add_argument(
        "--merchant-url",
        type=str,
        default=DEFAULT_MERCHANT,
        help="过期后引导用户咨询的链接",
    )
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

    hashes = [code_sha256_hex(c) for c in codes]

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 2,
        "algorithm": "sha256",
        "length": args.length,
        "count": len(hashes),
        "expiresAt": args.expires,
        "merchantConsultUrl": args.merchant_url,
        "hashes": hashes,
    }
    JSON_OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    header = (
        "【机密 · 勿提交 Git】卢浮宫语音讲解 · 验证码明文清单\n"
        f"本批共 {len(codes)} 条，每条 {args.length} 位（大小写字母与数字）。\n"
        f"截止日期（含当日有效）：{args.expires}\n"
        "公开站点仅部署哈希，无法从网络还原这些字符串。\n"
        "---\n"
    )
    TXT_OUT.write_text(header + "\n".join(codes) + "\n", encoding="utf-8")

    print(f"已写入公开校验文件 {JSON_OUT}（仅哈希，不含明文）。")
    print(f"已写入明文清单 {TXT_OUT}（请勿提交到 Git）。")


if __name__ == "__main__":
    main()
