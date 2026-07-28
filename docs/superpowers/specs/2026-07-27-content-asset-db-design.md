# 内容资产库设计 · content-asset-db

## 背景与目标

用户用 `video-workflow-builder` 生成专属工作流 skill 后，会开始持续生产内容。单支视频产出即消失、散落在对话历史里，无法沉淀。一个账号发布的内容需要有**系列性**，选题不希望**重复**，也会做**系列合集**。

目标：给**生成器**（video-workflow-builder）增加一套「内容资产库」能力模板 + 脚本，使它今后生成的**每一个产物 skill** 都自带结构化存档与按需索引能力，构建一个长期私人内容数据库。

**改动对象是生成器本身**（模板 + 生成规范 + 内置脚本），让它以后产出的 skill 都带这个能力；不是去改某一个已生成的产物。

至少需要存储：创建时间、最终选题、标题、文稿内容、发布后数据总结。

## 已确认的核心决策

1. **存储位置**：独立数据目录 `~/.claude/content-db/<账号slug>/`（Codex 下 `~/.codex/content-db/<账号slug>/`），与 skill 生命周期解耦——skill 重装/更新不影响数据。
2. **存储格式**：每条内容一个 Markdown 文件（frontmatter 存结构化字段，正文存文稿）+ 一个自动维护的 `index.json` 汇总索引供 skill 机读。人读机读兼顾。
3. **存档时机**：创作流程末尾（文稿模块完成后）**自动存档**（status=pending），无需用户记得。发布数据后续手动回填。
4. **指标字段**：固定一套**通用指标**，不按平台动态生成；某平台没有的指标留空。

## 架构

### 目录结构

```
~/.claude/content-db/<账号slug>/
├── index.json              # 自动维护的汇总索引（供 skill 机读，扁平汇总所有条目的 frontmatter）
├── content/
│   ├── 2026-07-27-maotai-diedting.md
│   ├── 2026-07-28-catl-guzhi.md
│   └── ...
└── series/                 # 系列合集元数据（轻量，只存系列定位与成员）
    └── zhangting-fupan.md
```

产物 skill 通过其已有的 `SKILL_DIR` 解析逻辑（`~/.claude/skills/<slug>-workflow` 或 `~/.codex/...`），推导出对应的 `content-db/<slug>/` 数据根路径。脚本负责在首次写入时按需创建目录，不假设目录已存在。

### 单条内容文件结构

`content/<日期>-<选题slug>.md`：

```markdown
---
id: 2026-07-27-maotai-diedting
created: 2026-07-27
platform: [抖音, B站]
topic: 茅台跌停复盘——高端白酒的逻辑变了吗
title: "茅台跌停!压垮它的不是股价,是这三个信号"
series: 涨停复盘          # 无则留空
tags: [白酒, 财报, 估值]
status: pending          # draft | pending | published
publish_date:            # 发布后回填
metrics:                 # 发布后回填,固定通用指标,记不上的留空
  views:
  likes:
  comments:
  shares:
  completion_rate:
  notes:
---

（完整口播稿正文）
```

`status` 串起两阶段：创作完自动写为 `pending`、`metrics` 留空；发布后手动回填 `metrics`、`publish_date`，status 改 `published`。

### 系列元数据文件结构

`series/<系列slug>.md`：

```markdown
---
name: 涨停复盘
slug: zhangting-fupan
created: 2026-07-27
positioning: 每期复盘一支当日涨停/跌停的个股,提炼可复用的判断信号
members:                 # 该系列下已产出内容的 id 列表
  - 2026-07-27-maotai-diedting
---

（系列备注:形态约定、开场固定话术、已覆盖角度等）
```

### index.json 结构

所有 `content/*.md` frontmatter 的扁平汇总（不含正文），供 skill 选题前快速扫描，避免逐个读 md 文件：

```json
{
  "updated": "2026-07-27T20:00:00",
  "entries": [
    {
      "id": "2026-07-27-maotai-diedting",
      "created": "2026-07-27",
      "topic": "茅台跌停复盘——高端白酒的逻辑变了吗",
      "title": "茅台跌停!压垮它的不是股价,是这三个信号",
      "series": "涨停复盘",
      "tags": ["白酒", "财报", "估值"],
      "status": "pending",
      "platform": ["抖音", "B站"],
      "metrics": { "views": null, "likes": null, "completion_rate": null }
    }
  ]
}
```

## 组件

### 脚本（放进产物 skill 的 `scripts/`，随生成器模板分发）

**`archive_content.py`** — 写入一条新内容
- 输入：选题、标题、文稿正文、平台、tags、（可选）系列
- 行为：生成 id（`<日期>-<选题slug>`）→ 写 `content/<id>.md`（status=pending）→ 更新 `index.json`→ 若指定了系列，把 id 追加进 `series/<系列slug>.md` 的 members
- 边界：目录不存在则创建；同 id 已存在则追加数字后缀（`-2`/`-3`）区分，不静默覆盖

**`query_db.py`** — 读 `index.json` 支持三种查询
- `--search <关键词>`：选题/标题/tags 去重检索——"我以前做过类似的吗"（服务**去重**）
- `--series <系列名>`：列出该系列已产出的各期——"涨停复盘系列做过哪几期"（服务**系列性/合集**）
- `--top <N> [--by views]`：按指标排序列出——"播放最高的几条选题,复制打法"
- 无参数：列出全部（时间倒序）

**`update_metrics.py`** — 回填发布数据（独立脚本，与 archive 分开）
- 输入：id、各项 metrics、publish_date
- 行为：更新对应 md 的 frontmatter + index.json，status 改 published

脚本用 Python 标准库解析/写 frontmatter（不引第三方 YAML 依赖，避免产物 skill 增加安装负担；用简单的手写 frontmatter 读写或最小实现）。

### 工作流衔接（改产物模板）

三个接入点，全部落在生成器的模板里：

1. **选题模块开头**（`topic-selection.md.tmpl`）：先调 `query_db.py --search`/`--series` 拉出历史选题与系列，把"这些已做过、别重复""这个系列可以接上一期第 N 期"作为选题约束注入。直接服务**去重**与**系列性**。
2. **文稿模块结尾**（`script-writing.md.tmpl`）：文稿定稿后自动调 `archive_content.py` 存档（status=pending）。
3. **SKILL.md 新增一节**（`SKILL.md.tmpl`）「内容资产库」：说明数据存在哪、怎么手动查库（`query_db.py`）、怎么回填发布数据（`update_metrics.py`）、系列合集怎么用。

### 生成器主体改动

- **`SKILL.md`「生成规范」**：新增一条——产物必须包含内容资产库能力，`archive_content.py` / `query_db.py` / `update_metrics.py` 三个脚本无条件复制进产物（与 `generate_cover.py` 同级处理）。
- **`SKILL.md`「质量标准」**：新增一条非负项——产物必须具备可运行的内容存档与查询能力，脚本能正确读写 `content-db/<slug>/`。
- **`validate_skill.py`**：校验产物包含这三个脚本（若校验器当前检查脚本清单）。

## 数据流

**创作时**：选题模块启动 → `query_db.py` 读历史 → 注入去重/系列约束 → 走完选题/标题/封面/文稿 → 文稿定稿 → `archive_content.py` 自动写入（pending）→ index.json 更新。

**发布后**：用户说"回填 XX 的数据" → `update_metrics.py` 更新 metrics + status=published。

**复盘/选题参考时**：`query_db.py --top` 或 `--series` 供用户或 skill 主动检索。

## 错误处理

- 数据目录不存在：脚本首次写入时自动创建，读取时返回空结果（不报错崩溃，视为"还没有历史内容"）。
- index.json 损坏/缺失：`query_db.py` 降级为扫描 `content/*.md` 重建，并告警。
- 无联网/无 Python：存档是纯本地文件操作，不依赖联网；Python3 两个运行环境都有。
- 选题 slug 冲突（同日同选题）：id 追加短后缀区分，不覆盖已有文件。

## 测试

- `archive_content.py`：空库首次写入建目录、写入后 index.json 正确、指定系列时 members 更新、同 id 冲突报错。
- `query_db.py`：`--search` 命中/未命中、`--series` 列出成员、`--top --by` 排序正确、空库返回空、index.json 缺失时重建。
- `update_metrics.py`：回填后 md frontmatter 与 index.json 同步、status 变 published。
- 集成：生成一个样例产物 skill，跑一遍"存档→查询→回填"闭环，确认三脚本协同 + `validate_skill.py` 通过。

## 范围外（YAGNI）

- 不做 Web UI / 可视化面板——纯文件 + 命令行查询。
- 不做跨账号的全局检索——每个账号 slug 一个独立库。
- 不做自动抓取发布数据——发布数据手动回填（平台 API 各异，不在本次范围）。
- 不引入数据库引擎（SQLite）或第三方依赖。
```