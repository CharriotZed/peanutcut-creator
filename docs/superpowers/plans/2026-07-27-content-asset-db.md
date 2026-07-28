# 内容资产库 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 video-workflow-builder 生成器增加「内容资产库」能力，使其今后生成的每个产物 skill 都自带结构化存档 + 按需索引，构建长期私人内容数据库。

**Architecture:** 三个纯 Python 标准库脚本（archive/query/update）放进生成器 `scripts/`，随产物一起分发；脚本从自身 `__file__` 路径推导账号 slug 与数据根 `~/.claude|.codex/content-db/<slug>/`，无需模板替换、可原样复制。数据以「每条一个 md 文件（frontmatter+正文）+ 一个 index.json 汇总」存储。三处产物模板（SKILL.md/选题/文稿）接入这套能力，生成器主 SKILL.md 的生成规范与质量标准各加一条。

**Tech Stack:** Python 3 标准库（`json`、`os`、`argparse`、`datetime`、`re`），无第三方依赖；Markdown 模板（`.tmpl`）。

## Global Constraints

- 仅用 Python 标准库，禁止引入第三方依赖（含 PyYAML）——产物 skill 不能增加安装负担。
- md frontmatter 的结构化值（列表 `platform`/`tags`、字典 `metrics`）用 JSON flow 风格书写（如 `tags: ["白酒", "财报"]`、`metrics: {"views": null}`），标量值裸写或用双引号；这样脚本用 `json.loads` 即可解析，不需要 YAML。
- 数据根解析：脚本从 `os.path.realpath(__file__)` 推导——`scripts/` 的父目录是 `<slug>-workflow`，去掉 `-workflow` 后缀得 slug；再上溯到 `~/.claude`（或 `~/.codex`）拼 `content-db/<slug>/`。允许环境变量 `CONTENT_DB_ROOT` 覆盖数据根（供测试与用户自定义）。
- 绝不硬编码真实 API key（本次脚本不涉及密钥，但保持红线）。
- 数据目录首次写入时按需创建；读取时目录不存在返回空结果，不崩溃。
- 三个脚本随生成器分发：生成产物时无条件复制进产物 `scripts/`（与 `generate_cover.py` 同级处理）。

---

## 文件结构

- 新建 `scripts/content_db.py` —— 共享模块：数据根解析、frontmatter 读写、index.json 读写/重建。三个 CLI 脚本都 import 它。
- 新建 `scripts/archive_content.py` —— CLI：写一条新内容（status=pending）+ 更新 index.json + 可选追加系列。
- 新建 `scripts/query_db.py` —— CLI：--search / --series / --top / 无参列全部。
- 新建 `scripts/update_metrics.py` —— CLI：回填 metrics + publish_date + status=published。
- 新建 `scripts/test_content_db.py` —— pytest 测试，覆盖上述四个脚本。
- 改 `scripts/validate_skill.py` —— 增加产物脚本清单校验。
- 改 `scripts/test_validate_skill.py`（若不存在则新建）—— 校验器新逻辑的测试。
- 改 `references/skill-template/topic-selection.md.tmpl` —— 选题模块开头接入查库去重/系列。
- 改 `references/skill-template/script-writing.md.tmpl` —— 文稿模块末尾接入自动存档。
- 改 `references/skill-template/SKILL.md.tmpl` —— 新增「内容资产库」章节。
- 改 `SKILL.md`（生成器主体）—— 生成规范 + 质量标准各加一条。

> 说明：脚本路径为生成器技能目录相对路径。校验/测试命令假设已 `cd` 到技能目录（`~/.claude/skills/video-workflow-builder`，即仓库内 `video-workflow-builder/`）。

---

## Task 1: 共享模块 content_db.py（数据根解析 + frontmatter 编解码）

**Files:**
- Create: `video-workflow-builder/scripts/content_db.py`
- Test: `video-workflow-builder/scripts/test_content_db.py`

**Interfaces:**
- Produces:
  - `resolve_data_root() -> str` — 返回数据根绝对路径（优先 `CONTENT_DB_ROOT` 环境变量，否则从 `__file__` 推导）。
  - `dump_frontmatter(meta: dict) -> str` — 把字段 dict 序列化为 frontmatter 文本块（不含正文，含首尾 `---`）。结构化值用 JSON flow 风格。
  - `parse_frontmatter(text: str) -> tuple[dict, str]` — 解析 md 文本，返回 (字段 dict, 正文字符串)。无 frontmatter 返回 (`{}`, 原文)。
  - `slugify(text: str) -> str` — 中文/任意文本转短 slug（保留中文，去标点空格，截断）。

- [ ] **Step 1: 写失败测试**

```python
# video-workflow-builder/scripts/test_content_db.py
import os
import content_db as cdb


def test_resolve_data_root_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTENT_DB_ROOT", str(tmp_path))
    assert cdb.resolve_data_root() == str(tmp_path)


def test_dump_and_parse_frontmatter_roundtrip():
    meta = {
        "id": "2026-07-27-maotai",
        "created": "2026-07-27",
        "platform": ["抖音", "B站"],
        "tags": ["白酒", "财报"],
        "title": "茅台跌停:压垮它的不是股价",
        "series": "",
        "status": "pending",
        "metrics": {"views": None, "likes": None},
    }
    text = cdb.dump_frontmatter(meta) + "\n正文台词第一句\n"
    parsed, body = cdb.parse_frontmatter(text)
    assert parsed["platform"] == ["抖音", "B站"]
    assert parsed["tags"] == ["白酒", "财报"]
    assert parsed["metrics"] == {"views": None, "likes": None}
    assert parsed["title"] == "茅台跌停:压垮它的不是股价"
    assert parsed["series"] == ""
    assert "正文台词第一句" in body


def test_slugify_handles_chinese_and_punct():
    # 所有非词字符(标点、空格)各自压成单个 dash,首尾 dash 去掉
    assert cdb.slugify("茅台跌停!复盘 2026") == "茅台跌停-复盘-2026"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd video-workflow-builder && python3 -m pytest scripts/test_content_db.py -v`
Expected: FAIL —`ModuleNotFoundError: No module named 'content_db'`

- [ ] **Step 3: 实现 content_db.py**

```python
#!/usr/bin/env python3
"""Shared helpers for the content asset DB scripts (stdlib only)."""
import json
import os
import re


def resolve_data_root():
    """Return the content-db root for this account.

    Priority: CONTENT_DB_ROOT env override, else derive from this file's
    location. scripts/ lives under <slug>-workflow, which lives under
    ~/.claude/skills (or ~/.codex/skills). Data root is a sibling of skills/:
    ~/.claude/content-db/<slug>/.
    """
    override = os.environ.get("CONTENT_DB_ROOT")
    if override:
        return override
    script_dir = os.path.dirname(os.path.realpath(__file__))
    skill_dir = os.path.dirname(script_dir)          # <slug>-workflow
    skill_name = os.path.basename(skill_dir)
    slug = skill_name[:-len("-workflow")] if skill_name.endswith("-workflow") else skill_name
    skills_root = os.path.dirname(skill_dir)          # .../skills
    base = os.path.dirname(skills_root)               # ~/.claude or ~/.codex
    return os.path.join(base, "content-db", slug)


def slugify(text):
    """Keep CJK + alnum, collapse everything else to single dashes."""
    text = text.strip()
    text = re.sub(r"[^\w一-鿿]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:40]


def _dump_value(value):
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    s = str(value)
    if s == "" or ":" in s or s.strip() != s:
        return json.dumps(s, ensure_ascii=False)
    return s


def dump_frontmatter(meta):
    lines = ["---"]
    for key, value in meta.items():
        lines.append("%s: %s" % (key, _dump_value(value)))
    lines.append("---")
    return "\n".join(lines) + "\n"


def _parse_value(raw):
    raw = raw.strip()
    if raw == "":
        return ""
    if raw[0] in "[{\"":
        try:
            return json.loads(raw)
        except ValueError:
            pass
    return raw


def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block = text[3:end].strip("\n")
    body = text[end + len("\n---"):].lstrip("\n")
    meta = {}
    for line in block.splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, _, raw = line.partition(":")
        meta[key.strip()] = _parse_value(raw)
    return meta, body
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd video-workflow-builder && python3 -m pytest scripts/test_content_db.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 提交**

```bash
git add video-workflow-builder/scripts/content_db.py video-workflow-builder/scripts/test_content_db.py
git commit -m "feat: add content_db shared module (data root + frontmatter codec)"
```

---

## Task 2: archive_content.py（写入 + 更新 index.json + 系列追加）

**Files:**
- Create: `video-workflow-builder/scripts/archive_content.py`
- Test: 追加到 `video-workflow-builder/scripts/test_content_db.py`

**Interfaces:**
- Consumes: `content_db.resolve_data_root`, `dump_frontmatter`, `parse_frontmatter`, `slugify`。
- Produces:
  - `archive(topic, title, script_body, platform, tags, series="", created=None, data_root=None) -> str` — 返回写入的 md 文件绝对路径。生成 `id = <created>-<slug(topic)>`，写 `content/<id>.md`（status=pending，metrics 全 None），更新 `index.json`，series 非空时追加进 `series/<slug(series)>.md` 的 members。
  - `rebuild_index(data_root) -> dict` — 扫描 `content/*.md` 重建 index 结构并写回 `index.json`。
  - CLI：`--topic --title --script(文件路径或 -) --platform(逗号分隔) --tags(逗号分隔) --series`。

- [ ] **Step 1: 写失败测试（追加）**

```python
def test_archive_creates_file_and_index(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTENT_DB_ROOT", str(tmp_path))
    import archive_content as ac
    path = ac.archive(
        topic="茅台跌停复盘", title="茅台跌停!三个信号",
        script_body="开头钩子...", platform=["抖音"], tags=["白酒"],
        created="2026-07-27",
    )
    assert os.path.isfile(path)
    index = json.load(open(os.path.join(str(tmp_path), "index.json"), encoding="utf-8"))
    ids = [e["id"] for e in index["entries"]]
    assert "2026-07-27-茅台跌停复盘" in ids
    entry = index["entries"][0]
    assert entry["status"] == "pending"
    assert entry["title"] == "茅台跌停!三个信号"


def test_archive_appends_series_member(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTENT_DB_ROOT", str(tmp_path))
    import archive_content as ac
    ac.archive(topic="第一期", title="T1", script_body="a",
               platform=["抖音"], tags=[], series="涨停复盘", created="2026-07-27")
    ac.archive(topic="第二期", title="T2", script_body="b",
               platform=["抖音"], tags=[], series="涨停复盘", created="2026-07-28")
    series_file = os.path.join(str(tmp_path), "series", cdb.slugify("涨停复盘") + ".md")
    meta, _ = cdb.parse_frontmatter(open(series_file, encoding="utf-8").read())
    assert len(meta["members"]) == 2


def test_archive_duplicate_id_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTENT_DB_ROOT", str(tmp_path))
    import archive_content as ac
    ac.archive(topic="同题", title="T", script_body="a",
               platform=["抖音"], tags=[], created="2026-07-27")
    import pytest
    with pytest.raises(FileExistsError):
        ac.archive(topic="同题", title="T", script_body="a",
                   platform=["抖音"], tags=[], created="2026-07-27")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd video-workflow-builder && python3 -m pytest scripts/test_content_db.py -k archive -v`
Expected: FAIL —`ModuleNotFoundError: No module named 'archive_content'`

- [ ] **Step 3: 实现 archive_content.py**

```python
#!/usr/bin/env python3
"""Archive one produced piece of content into the asset DB."""
import argparse
import datetime
import json
import os
import sys

import content_db as cdb

_METRIC_KEYS = ["views", "likes", "comments", "shares", "completion_rate", "notes"]


def _empty_metrics():
    return {k: None for k in _METRIC_KEYS}


def _load_index(data_root):
    path = os.path.join(data_root, "index.json")
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except ValueError:
            pass
    return {"updated": "", "entries": []}


def _write_index(data_root, index):
    index["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
    with open(os.path.join(data_root, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def _index_entry(meta):
    return {
        "id": meta["id"], "created": meta["created"], "topic": meta["topic"],
        "title": meta["title"], "series": meta.get("series", ""),
        "tags": meta.get("tags", []), "status": meta["status"],
        "platform": meta.get("platform", []), "metrics": meta.get("metrics", {}),
    }


def rebuild_index(data_root):
    content_dir = os.path.join(data_root, "content")
    index = {"updated": "", "entries": []}
    if os.path.isdir(content_dir):
        for name in sorted(os.listdir(content_dir)):
            if not name.endswith(".md"):
                continue
            with open(os.path.join(content_dir, name), encoding="utf-8") as f:
                meta, _ = cdb.parse_frontmatter(f.read())
            if meta:
                index["entries"].append(_index_entry(meta))
    _write_index(data_root, index)
    return index


def _append_series_member(data_root, series, member_id, created):
    series_dir = os.path.join(data_root, "series")
    os.makedirs(series_dir, exist_ok=True)
    path = os.path.join(series_dir, cdb.slugify(series) + ".md")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            meta, body = cdb.parse_frontmatter(f.read())
    else:
        meta = {"name": series, "slug": cdb.slugify(series),
                "created": created, "positioning": "", "members": []}
        body = "（系列备注:形态约定、开场固定话术、已覆盖角度等）\n"
    members = meta.get("members", [])
    if member_id not in members:
        members.append(member_id)
    meta["members"] = members
    with open(path, "w", encoding="utf-8") as f:
        f.write(cdb.dump_frontmatter(meta) + "\n" + body)


def archive(topic, title, script_body, platform, tags,
            series="", created=None, data_root=None):
    data_root = data_root or cdb.resolve_data_root()
    created = created or datetime.date.today().isoformat()
    content_dir = os.path.join(data_root, "content")
    os.makedirs(content_dir, exist_ok=True)
    content_id = "%s-%s" % (created, cdb.slugify(topic))
    md_path = os.path.join(content_dir, content_id + ".md")
    if os.path.exists(md_path):
        raise FileExistsError("content already exists: %s" % md_path)
    meta = {
        "id": content_id, "created": created, "platform": platform,
        "topic": topic, "title": title, "series": series or "",
        "tags": tags, "status": "pending", "publish_date": "",
        "metrics": _empty_metrics(),
    }
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(cdb.dump_frontmatter(meta) + "\n" + script_body.rstrip() + "\n")
    index = _load_index(data_root)
    index["entries"] = [e for e in index["entries"] if e["id"] != content_id]
    index["entries"].append(_index_entry(meta))
    _write_index(data_root, index)
    if series:
        _append_series_member(data_root, series, content_id, created)
    return md_path


def main(argv):
    p = argparse.ArgumentParser(description="Archive content into the asset DB")
    p.add_argument("--topic", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--script", required=True, help="script body file path, or - for stdin")
    p.add_argument("--platform", default="", help="comma-separated")
    p.add_argument("--tags", default="", help="comma-separated")
    p.add_argument("--series", default="")
    args = p.parse_args(argv)
    body = sys.stdin.read() if args.script == "-" else open(args.script, encoding="utf-8").read()
    platform = [x.strip() for x in args.platform.split(",") if x.strip()]
    tags = [x.strip() for x in args.tags.split(",") if x.strip()]
    path = archive(args.topic, args.title, body, platform, tags, series=args.series)
    print("archived:", path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd video-workflow-builder && python3 -m pytest scripts/test_content_db.py -k archive -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 提交**

```bash
git add video-workflow-builder/scripts/archive_content.py video-workflow-builder/scripts/test_content_db.py
git commit -m "feat: add archive_content.py (write content + index + series)"
```

---

## Task 3: query_db.py（去重检索 / 系列 / 排序）

**Files:**
- Create: `video-workflow-builder/scripts/query_db.py`
- Test: 追加到 `video-workflow-builder/scripts/test_content_db.py`

**Interfaces:**
- Consumes: `content_db.resolve_data_root`；`archive_content.rebuild_index`（index 缺失时降级重建）。
- Produces:
  - `load_entries(data_root=None) -> list[dict]` — 读 index.json 的 entries；缺失/损坏时调 `rebuild_index` 重建后返回。
  - `search(keyword, data_root=None) -> list[dict]` — topic/title/tags 命中关键词的条目。
  - `list_series(name, data_root=None) -> list[dict]` — series 字段等于 name 的条目（按 created 升序）。
  - `top(n, by="views", data_root=None) -> list[dict]` — 按 metrics[by] 降序取前 n（None 视为最小）。
  - CLI：`--search KW` / `--series NAME` / `--top N [--by views]` / 无参列全部。

- [ ] **Step 1: 写失败测试（追加）**

```python
def _seed(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTENT_DB_ROOT", str(tmp_path))
    import archive_content as ac
    ac.archive(topic="茅台跌停复盘", title="茅台三个信号", script_body="a",
               platform=["抖音"], tags=["白酒"], series="复盘", created="2026-07-27")
    ac.archive(topic="宁德时代估值", title="宁王还能买吗", script_body="b",
               platform=["B站"], tags=["新能源"], series="复盘", created="2026-07-28")


def test_search_matches_topic_and_tags(monkeypatch, tmp_path):
    _seed(tmp_path, monkeypatch)
    import query_db as q
    hits = q.search("白酒")
    assert len(hits) == 1 and hits[0]["topic"] == "茅台跌停复盘"


def test_list_series_sorted(monkeypatch, tmp_path):
    _seed(tmp_path, monkeypatch)
    import query_db as q
    members = q.list_series("复盘")
    assert [m["created"] for m in members] == ["2026-07-27", "2026-07-28"]


def test_top_by_views(monkeypatch, tmp_path):
    _seed(tmp_path, monkeypatch)
    import update_metrics as um
    um.update("2026-07-28-宁德时代估值", {"views": 9000}, publish_date="2026-07-29")
    um.update("2026-07-27-茅台跌停复盘", {"views": 100}, publish_date="2026-07-28")
    import query_db as q
    ranked = q.top(2, by="views")
    assert ranked[0]["id"] == "2026-07-28-宁德时代估值"


def test_load_entries_rebuilds_when_index_missing(monkeypatch, tmp_path):
    _seed(tmp_path, monkeypatch)
    os.remove(os.path.join(str(tmp_path), "index.json"))
    import query_db as q
    assert len(q.load_entries()) == 2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd video-workflow-builder && python3 -m pytest scripts/test_content_db.py -k "search or series or top or rebuild" -v`
Expected: FAIL —`ModuleNotFoundError: No module named 'query_db'`（`update_metrics` 亦未建，Task 4 会补；本任务先建 query_db，top 测试依赖 update_metrics，故本步骤 top 测试预期 error，其余 fail）

- [ ] **Step 3: 实现 query_db.py**

```python
#!/usr/bin/env python3
"""Query the content asset DB: dedup search, series listing, top ranking."""
import argparse
import json
import os
import sys

import content_db as cdb
import archive_content as ac


def load_entries(data_root=None):
    data_root = data_root or cdb.resolve_data_root()
    path = os.path.join(data_root, "index.json")
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f).get("entries", [])
        except ValueError:
            pass
    return ac.rebuild_index(data_root).get("entries", [])


def search(keyword, data_root=None):
    kw = keyword.lower()
    out = []
    for e in load_entries(data_root):
        hay = " ".join([e.get("topic", ""), e.get("title", ""),
                        " ".join(e.get("tags", []))]).lower()
        if kw in hay:
            out.append(e)
    return out


def list_series(name, data_root=None):
    members = [e for e in load_entries(data_root) if e.get("series") == name]
    return sorted(members, key=lambda e: e.get("created", ""))


def top(n, by="views", data_root=None):
    def key(e):
        v = (e.get("metrics") or {}).get(by)
        return v if isinstance(v, (int, float)) else float("-inf")
    return sorted(load_entries(data_root), key=key, reverse=True)[:n]


def _print(entries):
    for e in entries:
        print("%s | %s | %s | series=%s | status=%s" % (
            e.get("created", ""), e.get("id", ""), e.get("title", ""),
            e.get("series", "") or "-", e.get("status", "")))


def main(argv):
    p = argparse.ArgumentParser(description="Query the content asset DB")
    p.add_argument("--search")
    p.add_argument("--series")
    p.add_argument("--top", type=int)
    p.add_argument("--by", default="views")
    args = p.parse_args(argv)
    if args.search is not None:
        _print(search(args.search))
    elif args.series is not None:
        _print(list_series(args.series))
    elif args.top is not None:
        _print(top(args.top, by=args.by))
    else:
        _print(sorted(load_entries(), key=lambda e: e.get("created", ""), reverse=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: 跑测试确认通过（先跑不依赖 update_metrics 的三个）**

Run: `cd video-workflow-builder && python3 -m pytest scripts/test_content_db.py -k "search or series or rebuild" -v`
Expected: PASS (3 passed)。`top` 测试待 Task 4 后转绿。

- [ ] **Step 5: 提交**

```bash
git add video-workflow-builder/scripts/query_db.py video-workflow-builder/scripts/test_content_db.py
git commit -m "feat: add query_db.py (dedup search, series, top ranking)"
```

---

## Task 4: update_metrics.py（回填发布数据）

**Files:**
- Create: `video-workflow-builder/scripts/update_metrics.py`
- Test: 已在 Task 3 追加 `test_top_by_views` 依赖它；本任务让其转绿。

**Interfaces:**
- Consumes: `content_db.parse_frontmatter`, `dump_frontmatter`, `resolve_data_root`；`archive_content.rebuild_index`。
- Produces:
  - `update(content_id, metrics: dict, publish_date="", data_root=None) -> str` — 更新 `content/<id>.md` frontmatter 的 metrics（部分更新，合并）、publish_date、status=published，然后重建 index.json。返回 md 路径。content 不存在时抛 `FileNotFoundError`。
  - CLI：`--id`、`--publish-date`，及各指标 `--views/--likes/--comments/--shares/--completion-rate/--notes`。

- [ ] **Step 1: 测试已在 Task 3 存在（test_top_by_views）**

无需新增；本任务实现使其通过。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd video-workflow-builder && python3 -m pytest scripts/test_content_db.py -k top_by_views -v`
Expected: FAIL/ERROR —`ModuleNotFoundError: No module named 'update_metrics'`

- [ ] **Step 3: 实现 update_metrics.py**

```python
#!/usr/bin/env python3
"""Backfill post-publish metrics for an archived content item."""
import argparse
import os
import sys

import content_db as cdb
import archive_content as ac


def update(content_id, metrics, publish_date="", data_root=None):
    data_root = data_root or cdb.resolve_data_root()
    md_path = os.path.join(data_root, "content", content_id + ".md")
    if not os.path.isfile(md_path):
        raise FileNotFoundError("no such content: %s" % md_path)
    with open(md_path, encoding="utf-8") as f:
        meta, body = cdb.parse_frontmatter(f.read())
    current = meta.get("metrics") or {}
    for k, v in metrics.items():
        if v is not None:
            current[k] = v
    meta["metrics"] = current
    if publish_date:
        meta["publish_date"] = publish_date
    meta["status"] = "published"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(cdb.dump_frontmatter(meta) + "\n" + body.rstrip() + "\n")
    ac.rebuild_index(data_root)
    return md_path


def main(argv):
    p = argparse.ArgumentParser(description="Backfill metrics for content")
    p.add_argument("--id", required=True)
    p.add_argument("--publish-date", default="")
    p.add_argument("--views", type=int)
    p.add_argument("--likes", type=int)
    p.add_argument("--comments", type=int)
    p.add_argument("--shares", type=int)
    p.add_argument("--completion-rate", type=float)
    p.add_argument("--notes")
    args = p.parse_args(argv)
    metrics = {
        "views": args.views, "likes": args.likes, "comments": args.comments,
        "shares": args.shares, "completion_rate": args.completion_rate,
        "notes": args.notes,
    }
    path = update(args.id, metrics, publish_date=args.publish_date)
    print("updated:", path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: 跑全部 content_db 测试确认通过**

Run: `cd video-workflow-builder && python3 -m pytest scripts/test_content_db.py -v`
Expected: PASS（全部通过，含 top_by_views）

- [ ] **Step 5: 提交**

```bash
git add video-workflow-builder/scripts/update_metrics.py
git commit -m "feat: add update_metrics.py (backfill post-publish metrics)"
```

---

## Task 5: validate_skill.py 增加产物脚本清单校验

**Files:**
- Modify: `video-workflow-builder/scripts/validate_skill.py`
- Test: Create `video-workflow-builder/scripts/test_validate_skill.py`

**Interfaces:**
- Consumes: 现有 `validate_skill_dir(path) -> list[str]`。
- Produces: `validate_skill_dir` 新增校验——产物目录 `scripts/` 下必须存在 `content_db.py`、`archive_content.py`、`query_db.py`、`update_metrics.py`、`generate_cover.py`，缺失则每个报一行 problem。

- [ ] **Step 1: 写失败测试**

```python
# video-workflow-builder/scripts/test_validate_skill.py
import os
import validate_skill as v

_REQUIRED = ["content_db.py", "archive_content.py", "query_db.py",
             "update_metrics.py", "generate_cover.py"]


def _make_skill(tmp_path, with_scripts):
    (tmp_path / "SKILL.md").write_text(
        "---\nname: x-workflow\ndescription: d\n---\n# x\n", encoding="utf-8")
    if with_scripts:
        sd = tmp_path / "scripts"
        sd.mkdir()
        for name in _REQUIRED:
            (sd / name).write_text("# stub\n", encoding="utf-8")


def test_missing_scripts_reported(tmp_path):
    _make_skill(tmp_path, with_scripts=False)
    problems = v.validate_skill_dir(str(tmp_path))
    assert any("archive_content.py" in p for p in problems)
    assert any("query_db.py" in p for p in problems)


def test_all_scripts_present_ok(tmp_path):
    _make_skill(tmp_path, with_scripts=True)
    problems = v.validate_skill_dir(str(tmp_path))
    assert problems == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd video-workflow-builder && python3 -m pytest scripts/test_validate_skill.py -v`
Expected: FAIL —`test_missing_scripts_reported` 失败（当前校验器不查脚本）

- [ ] **Step 3: 修改 validate_skill.py**

在 `video-workflow-builder/scripts/validate_skill.py` 的 `validate_skill_dir` 函数里，`return problems` 之前插入脚本清单校验：

```python
    required_scripts = [
        "content_db.py", "archive_content.py", "query_db.py",
        "update_metrics.py", "generate_cover.py",
    ]
    scripts_dir = os.path.join(path, "scripts")
    for name in required_scripts:
        if not os.path.isfile(os.path.join(scripts_dir, name)):
            problems.append("missing required script: scripts/%s" % name)

    return problems
```

（即把原来的 `return problems` 替换为上面这段——先追加脚本校验，再 return。）

- [ ] **Step 4: 跑测试确认通过**

Run: `cd video-workflow-builder && python3 -m pytest scripts/test_validate_skill.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 提交**

```bash
git add video-workflow-builder/scripts/validate_skill.py video-workflow-builder/scripts/test_validate_skill.py
git commit -m "feat: validate_skill checks required product scripts"
```

---

## Task 6: 选题模块模板接入查库（去重 + 系列）

**Files:**
- Modify: `video-workflow-builder/references/skill-template/topic-selection.md.tmpl`

**Interfaces:**
- Consumes: 产物运行时的 `query_db.py`（`--search`/`--series`）。
- Produces: 选题模块正文新增「查库」前置小节，纯文本指令，无代码依赖。

- [ ] **Step 1: 在「起点」小节之前插入查库前置步骤**

在 [topic-selection.md.tmpl:6](video-workflow-builder/references/skill-template/topic-selection.md.tmpl#L6)（"## 起点" 之前）插入以下小节：

````markdown
## 前置：查历史内容库（避免重复 + 找系列线索）

产出候选选题前，先查一遍本账号的历史内容库，让新选题不撞车、能接上系列：

```bash
SKILL_DIR="$HOME/.claude/skills/{{ACCOUNT_SLUG}}-workflow"
[ -d "$SKILL_DIR" ] || SKILL_DIR="$HOME/.codex/skills/{{ACCOUNT_SLUG}}-workflow"
# 按本次方向的关键词查是否做过类似选题
python3 "$SKILL_DIR/scripts/query_db.py" --search "关键词"
# 若在做某个系列,列出该系列已产出的各期
python3 "$SKILL_DIR/scripts/query_db.py" --series "系列名"
```

- **去重**：命中的历史选题里,已经讲透的角度不要再重复;可以做"上次没展开的那一面"或"有新增量后的更新版"。
- **系列性**：若本次属于某个系列,先看已做过哪几期,新一期要和既有各期形成递进或互补,并在存档时带上同一个系列名。
- 库为空(新账号第一次用)或无法运行脚本时,跳过本步骤,照常产出选题。
````

- [ ] **Step 2: 校验模板未破坏（生成器自检）**

Run: `cd video-workflow-builder && python3 -c "print(open('references/skill-template/topic-selection.md.tmpl', encoding='utf-8').read()[:80])"`
Expected: 正常打印文件开头，无异常。

- [ ] **Step 3: 提交**

```bash
git add video-workflow-builder/references/skill-template/topic-selection.md.tmpl
git commit -m "feat: topic-selection template queries content DB for dedup + series"
```

---

## Task 7: 文稿模块模板接入自动存档

**Files:**
- Modify: `video-workflow-builder/references/skill-template/script-writing.md.tmpl`

**Interfaces:**
- Consumes: 产物运行时的 `archive_content.py`。
- Produces: 文稿模块末尾新增「自动存档」小节。

- [ ] **Step 1: 在文稿模块末尾追加存档小节**

在 [script-writing.md.tmpl:95](video-workflow-builder/references/skill-template/script-writing.md.tmpl#L95)（文件最后一行"文稿产出即完成本次工作流"之后）追加：

````markdown

## 存档到内容库（文稿定稿后自动执行）

文稿定稿后,自动把本次内容写入长期内容库(状态标记为待发布),供以后去重、追系列、复盘数据:

```bash
SKILL_DIR="$HOME/.claude/skills/{{ACCOUNT_SLUG}}-workflow"
[ -d "$SKILL_DIR" ] || SKILL_DIR="$HOME/.codex/skills/{{ACCOUNT_SLUG}}-workflow"
python3 "$SKILL_DIR/scripts/archive_content.py" \
  --topic "本次最终选题" \
  --title "本次选定标题" \
  --platform "{{PLATFORMS}}" \
  --tags "标签1,标签2" \
  --series "系列名(无则省略此项)" \
  --script - <<'SCRIPT_EOF'
（把完整口播稿正文粘到这里）
SCRIPT_EOF
```

存档成功后告诉用户:内容已存入库、当前状态为「待发布」;发布后可随时说"回填 XX 的数据"来补播放/点赞等指标(见 SKILL.md「内容资产库」一节)。若脚本执行失败,如实告知用户本次未存档,不要谎报成功。
````

- [ ] **Step 2: 校验模板未破坏**

Run: `cd video-workflow-builder && python3 -c "t=open('references/skill-template/script-writing.md.tmpl', encoding='utf-8').read(); print('存档到内容库' in t)"`
Expected: `True`

- [ ] **Step 3: 提交**

```bash
git add video-workflow-builder/references/skill-template/script-writing.md.tmpl
git commit -m "feat: script-writing template auto-archives content after finalize"
```

---

## Task 8: SKILL.md 模板新增「内容资产库」章节

**Files:**
- Modify: `video-workflow-builder/references/skill-template/SKILL.md.tmpl`

**Interfaces:**
- Produces: 产物 SKILL.md 新增一节，说明数据位置、查库、回填、系列用法。

- [ ] **Step 1: 在模板末尾追加章节**

在 [SKILL.md.tmpl:82](video-workflow-builder/references/skill-template/SKILL.md.tmpl#L82)（文件最后"完整的定位依据…见账号定位诊断"之后）追加：

````markdown

## 内容资产库

本工作流会把你每次产出的内容结构化沉淀到一个长期数据库,独立于本 skill 存放,重装/更新 skill 不会丢数据:

- **数据位置**：`~/.claude/content-db/{{ACCOUNT_SLUG}}/`（Codex 下 `~/.codex/content-db/{{ACCOUNT_SLUG}}/`）。每条内容一个 md 文件（`content/`）,一个 `index.json` 汇总索引,系列元数据在 `series/`。
- **自动存档**：走完文稿模块后自动写入,状态为「待发布」(pending),含创建时间、选题、标题、平台、文稿正文。
- **回填发布数据**：内容发出去后,说"回填 <内容id> 的数据",或直接跑:

  ```bash
  SKILL_DIR="$HOME/.claude/skills/{{ACCOUNT_SLUG}}-workflow"
  [ -d "$SKILL_DIR" ] || SKILL_DIR="$HOME/.codex/skills/{{ACCOUNT_SLUG}}-workflow"
  python3 "$SKILL_DIR/scripts/update_metrics.py" --id 2026-07-27-选题slug \
    --views 125000 --likes 8300 --comments 420 --completion-rate 0.42 \
    --publish-date 2026-07-28 --notes "前3秒钩子有效"
  ```

- **查库**：`query_db.py --search "关键词"`（查是否做过）、`--series "系列名"`（列出某系列各期）、`--top 5 --by views`（按播放排序找可复制的打法）。选题模块会自动查库去重、找系列线索。
- **系列合集**：存档时带 `--series "系列名"` 即把该条归入系列,系列成员与定位记录在 `series/<系列slug>.md`。
````

- [ ] **Step 2: 校验模板未破坏**

Run: `cd video-workflow-builder && python3 -c "t=open('references/skill-template/SKILL.md.tmpl', encoding='utf-8').read(); print('内容资产库' in t)"`
Expected: `True`

- [ ] **Step 3: 提交**

```bash
git add video-workflow-builder/references/skill-template/SKILL.md.tmpl
git commit -m "feat: product SKILL template documents content asset DB"
```

---

## Task 9: 生成器主 SKILL.md 更新生成规范 + 质量标准

**Files:**
- Modify: `video-workflow-builder/SKILL.md`

**Interfaces:**
- Produces: 生成器要求产物必带内容库能力，脚本无条件复制进产物。

- [ ] **Step 1: 「配置脚本」小节增加脚本复制要求**

在 [SKILL.md:237](video-workflow-builder/SKILL.md#L237)（"无条件复制进产物：`generate_cover.py`…"那一行）把该行改为同时包含内容库三脚本 + 共享模块：

```markdown
- 无条件复制进产物：`generate_cover.py`（封面生成脚本）、`content_db.py` / `archive_content.py` / `query_db.py` / `update_metrics.py`（内容资产库脚本，产物借此结构化存档与索引每次产出的内容）、`.env.example`（密钥占位模板）、`.gitignore`（确保真实 `.env` 不被提交）
```

- [ ] **Step 2: 「生成规范」末尾新增内容库落地说明**

在 [SKILL.md:240](video-workflow-builder/SKILL.md#L240)（「密钥处理（安全红线）」小节之前）插入一个新小节：

```markdown
**内容资产库（每个产物必带）**：产物要能把每次产出的内容结构化沉淀到独立于 skill 的长期数据库 `~/.claude|.codex/content-db/<账号slug>/`。落地方式：把 `content_db.py`/`archive_content.py`/`query_db.py`/`update_metrics.py` 复制进产物 `scripts/`（脚本从自身路径推导账号 slug 与数据根,无需改写）；产物的选题模块开头查库去重与找系列、文稿模块末尾自动存档、SKILL.md 说明回填与查库方式——这三处已在模板中就位,填模板时不要删。数据独立存放,重装产物 skill 不影响历史内容。

```

- [ ] **Step 3: 「质量标准」新增一条非负项**

在 [SKILL.md:256](video-workflow-builder/SKILL.md#L256)（封面密钥那条之后、validate 那条之前）插入：

```markdown
- 产物必须具备可运行的内容资产库能力：`content_db.py`/`archive_content.py`/`query_db.py`/`update_metrics.py` 四个脚本齐全并能正确读写 `content-db/<slug>/`,选题模块查库去重、文稿模块自动存档两处衔接不能缺失。
```

- [ ] **Step 4: 生成器自校验通过**

Run: `cd video-workflow-builder && python3 scripts/validate_skill.py .`
Expected: 无输出（生成器自身 SKILL.md frontmatter/链接合法）。注意：生成器自身不含产物脚本清单里的 `content_db.py` 等运行时脚本约束不适用——校验器的脚本清单校验针对**产物目录**；生成器目录跑校验若因新脚本清单报缺失，说明校验器不应对生成器自身套用产物规则。

> 复核点：Task 5 的脚本清单校验会对任意传入目录生效，包括生成器自身。生成器 `scripts/` 里确实已有 `content_db.py`/`archive_content.py`/`query_db.py`/`update_metrics.py`/`generate_cover.py`（Task 1-4 已创建 + 原有 generate_cover.py），故对生成器目录跑校验也应通过。执行本步骤确认无 "missing required script" 输出即可。

- [ ] **Step 5: 提交**

```bash
git add video-workflow-builder/SKILL.md
git commit -m "feat: generator requires content asset DB in every product skill"
```

---

## Task 10: 端到端集成验证 + 全量测试

**Files:**
- Test: 追加 `video-workflow-builder/scripts/test_content_db.py::test_end_to_end`

**Interfaces:**
- Consumes: archive/query/update 全链路。

- [ ] **Step 1: 写端到端测试**

```python
def test_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTENT_DB_ROOT", str(tmp_path))
    import archive_content as ac
    import query_db as q
    import update_metrics as um
    # 1. 存档两条同系列内容
    ac.archive(topic="第一期茅台", title="T1", script_body="稿1",
               platform=["抖音"], tags=["白酒"], series="复盘", created="2026-07-27")
    ac.archive(topic="第二期宁王", title="T2", script_body="稿2",
               platform=["B站"], tags=["新能源"], series="复盘", created="2026-07-28")
    # 2. 查重命中
    assert len(q.search("茅台")) == 1
    # 3. 系列列出两期
    assert len(q.list_series("复盘")) == 2
    # 4. 回填数据后 status=published 且排序生效
    um.update("2026-07-27-第一期茅台", {"views": 500}, publish_date="2026-07-28")
    ranked = q.top(1, by="views")
    assert ranked[0]["id"] == "2026-07-27-第一期茅台"
    assert ranked[0]["status"] == "published"
```

- [ ] **Step 2: 跑全量测试**

Run: `cd video-workflow-builder && python3 -m pytest scripts/ -v`
Expected: PASS（含 test_content_db.py 全部 + test_validate_skill.py 全部 + test_end_to_end）

- [ ] **Step 3: 跑校验器确认生成器目录合法**

Run: `cd video-workflow-builder && python3 scripts/validate_skill.py .`
Expected: 无输出（退出码 0）

- [ ] **Step 4: 清理 __pycache__ 等临时产物（若测试生成）**

Run: `cd video-workflow-builder && find scripts -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; git status --short`
Expected: 仅列出预期的新增/修改文件，无游离临时文件。

- [ ] **Step 5: 提交**

```bash
git add video-workflow-builder/scripts/test_content_db.py
git commit -m "test: end-to-end content DB archive→query→update flow"
```

---

## Self-Review

**1. Spec coverage:**
- 存储位置（独立 content-db/<slug>/）→ Task 1 `resolve_data_root` ✅
- md+frontmatter+index.json 格式 → Task 1/2 ✅
- 创作完自动存档（pending）→ Task 2 + Task 7 模板 ✅
- 固定通用 metrics → Task 2 `_METRIC_KEYS` ✅
- 三脚本 archive/query/update → Task 2/3/4 ✅
- 去重/系列/排序三种查询 → Task 3 ✅
- 发布数据回填 → Task 4 ✅
- series 元数据 → Task 2 `_append_series_member` ✅
- 工作流三接入点（选题查库/文稿存档/SKILL.md 说明）→ Task 6/7/8 ✅
- 生成规范 + 质量标准 → Task 9 ✅
- validate_skill 脚本校验 → Task 5 ✅
- 错误处理（目录不存在、index 缺失重建、id 冲突）→ Task 2/3 及测试 ✅
- 无第三方依赖 → Global Constraints + JSON flow frontmatter ✅

**2. Placeholder scan:** 无 TBD/TODO；每个代码步骤含完整代码。

**3. Type consistency:** `archive()`/`update()`/`search()`/`list_series()`/`top()`/`load_entries()`/`rebuild_index()`/`resolve_data_root()`/`dump_frontmatter()`/`parse_frontmatter()`/`slugify()` 全链路签名一致；`_METRIC_KEYS` 与 update CLI 参数、SKILL.md 文档一致（views/likes/comments/shares/completion_rate/notes）。
```