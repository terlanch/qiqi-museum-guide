#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从卢浮宫馆藏站官方 sitemap 收集全部 arkId，并逐条下载 .json 到本地（可断点续传、限速）。

规模说明：全库约 48 万+ 条，完整下载需较长时间与数 GB 磁盘；请合理设置 --delay，
勿开过高并发，以免对官方站点造成压力。

用法：
  python3 scripts/download_louvre_dump.py collect-ids
  python3 scripts/download_louvre_dump.py download-curated --delay 0.35   # 默认 config/important10.json
  python3 scripts/download_louvre_dump.py download-curated --config config/classics100.json --delay 0.35
  python3 scripts/download_louvre_dump.py download --delay 0.35
  python3 scripts/download_louvre_dump.py download --max 500 --delay 0.2   # 试跑（需先 collect-ids）
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
IDS_FILE = DATA_DIR / "louvre_ark_ids.txt"
JSON_DIR = DATA_DIR / "louvre_json"
DEFAULT_CURATED_JSON = ROOT / "config" / "important10.json"
SITEMAP_INDEX = "https://collections.louvre.fr/sitemap.xml"
SITEMAP_COUNT = 26  # sitemap0 .. sitemap25

USER_AGENT = "LouvreGuideBulkFetch/1.0 (+https://github.com; educational local mirror)"

ARK_RE = __import__("re").compile(r"ark:/53355/(cl\d+)")


def http_get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def discover_sitemap_piece_urls() -> list[str]:
    """解析主 sitemap 索引，返回各分片 URL。"""
    xml = http_get(SITEMAP_INDEX, timeout=60).decode("utf-8", errors="replace")
    urls: list[str] = []
    for i in range(SITEMAP_COUNT):
        u = f"https://collections.louvre.fr/media/sitemap/sitemap{i}.xml"
        if u not in urls:
            urls.append(u)
    # 若索引里出现额外分片，也扫出来
    import re

    for m in re.finditer(
        r"https://collections\.louvre\.fr/media/sitemap/sitemap\d+\.xml", xml
    ):
        u = m.group(0)
        if u not in urls:
            urls.append(u)
    urls.sort()
    return urls


def extract_ark_ids_from_sitemap_xml(url: str) -> set[str]:
    """流式读取分片 sitemap，用正则提取 cl 编号（去重）。"""
    out: set[str] = set()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    buf = ""
    with urllib.request.urlopen(req, timeout=300) as r:
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            buf += chunk.decode("utf-8", errors="replace")
            for m in ARK_RE.finditer(buf):
                out.add(m.group(1))
            if len(buf) > 80000:
                buf = buf[-8000:]
    return out


def cmd_collect_ids(_: argparse.Namespace) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    piece_urls = discover_sitemap_piece_urls()
    print(f"共 {len(piece_urls)} 个 sitemap 分片，开始拉取…")
    all_ids: set[str] = set()
    for i, url in enumerate(piece_urls, 1):
        t0 = time.time()
        try:
            part = extract_ark_ids_from_sitemap_xml(url)
        except Exception as e:
            print(f"[{i}/{len(piece_urls)}] 失败 {url}: {e}", file=sys.stderr)
            continue
        all_ids |= part
        print(
            f"[{i}/{len(piece_urls)}] +{len(part)} 唯一累计 {len(all_ids)} "
            f"({time.time() - t0:.1f}s)"
        )

    sorted_ids = sorted(all_ids)
    IDS_FILE.write_text("\n".join(sorted_ids) + "\n", encoding="utf-8")
    print(f"已写入 {IDS_FILE} ，共 {len(sorted_ids)} 个 arkId。")


def json_path(ark_id: str) -> Path:
    return JSON_DIR / f"{ark_id}.json"


def fetch_json(ark_id: str, retries: int = 3) -> bool:
    url = f"https://collections.louvre.fr/ark:/53355/{ark_id}.json"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                raw = r.read()
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict) or not data.get("arkId"):
                return False
            p = json_path(ark_id)
            p.write_bytes(raw)
            return True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False
            time.sleep(2 ** attempt + random.random())
        except Exception:
            time.sleep(2 ** attempt + random.random())
    return False


def run_download_ids(ids: list[str], delay: float, progress_every: int = 500) -> None:
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    delay = max(0.05, float(delay))
    ok = skip = fail = 0
    t_start = time.time()
    n = len(ids)

    for i, ark_id in enumerate(ids, 1):
        dest = json_path(ark_id)
        if dest.is_file() and dest.stat().st_size > 10:
            try:
                json.loads(dest.read_text(encoding="utf-8"))
                skip += 1
                if n >= 2000 and i % 2000 == 0:
                    print(f"… {i}/{n} 跳过已存在 {skip} 条")
                continue
            except Exception:
                pass

        if fetch_json(ark_id):
            ok += 1
            print(f"  OK {ark_id}")
        else:
            fail += 1
            print(f"  失败 {ark_id}")

        if progress_every and (i % progress_every == 0 or i == n):
            elapsed = time.time() - t_start
            print(
                f"进度 {i}/{n} 新下载 {ok} 跳过 {skip} 失败 {fail} "
                f"用时 {elapsed / 60:.1f} min"
            )

        time.sleep(delay)

    print(f"完成。新下载 {ok}，跳过 {skip}，失败 {fail}。目录: {JSON_DIR}")


def cmd_download_curated(args: argparse.Namespace) -> None:
    curated_path = Path(args.config).resolve()
    if not curated_path.is_file():
        print(f"缺少 {curated_path}")
        sys.exit(1)
    data = json.loads(curated_path.read_text(encoding="utf-8"))
    rows = data.get("arks") or []
    ids = [str(x.get("arkId", "")).strip() for x in rows if x.get("arkId")]
    ids = [x for x in ids if x]
    if not ids:
        print(f"{curated_path.name} 中没有 arkId")
        sys.exit(1)
    print(f"精选 {len(ids)} 条，开始下载到 {JSON_DIR} …")
    run_download_ids(ids, args.delay, progress_every=0)


def cmd_download(args: argparse.Namespace) -> None:
    if not IDS_FILE.is_file():
        print(f"缺少 {IDS_FILE}，请先运行: python3 scripts/download_louvre_dump.py collect-ids")
        sys.exit(1)

    ids = [ln.strip() for ln in IDS_FILE.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if args.max:
        ids = ids[: args.max]

    run_download_ids(ids, args.delay, progress_every=500)


def main() -> None:
    ap = argparse.ArgumentParser(description="卢浮宫馆藏 JSON 批量镜像")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("collect-ids", help="从 sitemap 收集全部 arkId 写入 data/louvre_ark_ids.txt")

    p_cur = sub.add_parser(
        "download-curated",
        help="下载精选列表中的馆藏 JSON（默认 important10.json，无需 collect-ids）",
    )
    p_cur.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CURATED_JSON,
        help="含 arks 数组的 JSON（如 config/classics100.json）",
    )
    p_cur.add_argument("--delay", type=float, default=0.35, help="每条请求间隔（秒）")

    p_dl = sub.add_parser("download", help="按 data/louvre_ark_ids.txt 全量下载 JSON 到 data/louvre_json/")
    p_dl.add_argument("--delay", type=float, default=0.35, help="每条请求间隔（秒）")
    p_dl.add_argument("--max", type=int, default=0, help="仅下载前 N 条（试跑）")

    args = ap.parse_args()
    if args.cmd == "collect-ids":
        cmd_collect_ids(args)
    elif args.cmd == "download-curated":
        cmd_download_curated(args)
    else:
        cmd_download(args)


if __name__ == "__main__":
    main()
