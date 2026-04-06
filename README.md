# 卢浮宫馆藏语音导览（静态站）

## 数据从哪来

唯一权威来源是卢浮宫馆藏站 **官方 JSON**（与网页同源）：

- 入口：`https://collections.louvre.fr/ark:/53355/{arkId}.json`（在条目 URL 后加 `.json` 即可）
- 常用字段：
  - **藏品名称**：`title`、`titleComplement`
  - **馆区 / 楼层 / 展厅**：`room`（如 `Salle 345, Aile Sully, Niveau 0`）、`currentLocation`（展线说明）
  - **部类**：`collection`
  - **简介与细节**：`description`、`materialsAndTechniques`、`displayDateCreated`
  - **馆藏编号**：`objectNumber` 数组
- 使用须遵守馆藏站 [条款](https://collections.louvre.fr/en/page/cgu)。

本站用脚本解析 `room` / `currentLocation` 中的 **Salle / Aile / Niveau** 得到展厅号、侧楼（叙利 / 德农 / 黎塞留）、楼层；中文名与讲解正文由 **火山方舟 MaaS** 翻译或生成；音频由 **火山引擎 TTS** 合成。

## 目录结构

| 路径 | 说明 |
|------|------|
| `artifacts/{arkId}.json` | 每藏品一份：法文元数据、解析后的位置、中文标题与讲解等 |
| `docs/audio/{arkId}.mp3` | 对应讲解音频 |
| `docs/data/catalog.json` | 前端用的汇总索引（同时写入 `works.json` 兼容旧逻辑） |
| `config/seeds.json` | 要抓取的 `arkId` 列表（可与 `important10.json` 同步） |
| `config/important10.json` | 10 件名作清单，用于试跑 |
| `data/louvre_json/` | 官方原始 `.json` 镜像（`download-curated` / `download`） |

仅下载 **10 条名作** 官方原始 JSON（无需先跑 `collect-ids`）：

```bash
python3 scripts/download_louvre_dump.py download-curated --delay 0.35
```

## 快速开始

```bash
cd opc
python3 -m venv .venv && source .venv/bin/activate   # 可选
pip install -r requirements.txt
cp .env.example .env   # 填写 VOLC_TTS_*；中文讲解推荐 ARK_API_KEY（或 MaaS AK/SK + 接入点）
```

正常构建（**必须**已配置 MaaS，以生成中文讲解；简介过短时会由 AI 扩写）。若已执行 `download-curated`，构建会**优先读** `data/louvre_json/`，减少重复请求官网。

```bash
python3 scripts/build_site.py
```

在未配置 `VOLC_ACCESSKEY` 等时，可仅同步法文元数据与目录（无中文讲解、无音频）：

```bash
python3 scripts/build_site.py --allow-without-maas --skip-tts
```

只生成 `artifacts/`、`catalog.json`，不调用语音：

```bash
python3 scripts/build_site.py --skip-tts
```

仅调试抓取、未配 MaaS（法文落盘、无中文）：

```bash
python3 scripts/build_site.py --allow-without-maas --skip-tts
```

单条中文讲解也可在 `config/seeds.json` 里为该 `arkId` 增加 `narration_zh`（仍会尝试翻译标题，除非未配 MaaS）。

## 网页功能

- 按 **馆区**（侧楼）、**楼层** 筛选
- 按 **中文名、法文名、馆藏编号** 搜索
- 播放对应 MP3

## GitHub Pages

1. **Settings → Pages** 发布目录选 **`/docs`**。
2. 提交 `docs/` 下静态资源、`data/catalog.json`（或 `works.json`）、`audio/*.mp3`，以及可选提交 `artifacts/` 便于版本管理。
3. 若站点为 `https://user.github.io/repo/`，将 `docs/app.js` 顶部 `BASE` 设为 `"/repo"`。

## 安全说明

勿将 `VOLC_TTS_ACCESS_KEY`、AK/SK 提交到 Git；泄露后请在控制台轮换。

## 声明

本项目与卢浮宫无关联；数据版权归权利方所有。
