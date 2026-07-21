# Video Workflow Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a meta-skill (`video-workflow-builder`) that interviews a user minimally, researches their niche/platform online, then generates a bespoke, installable video-creation workflow skill covering 选题→文稿→标题→封面, tuned to each platform's algorithm.

**Architecture:** The generator is itself a skill: a `SKILL.md` driving a five-phase flow (interview → research → diagnosis → generate → deliver), backed by three internal reference banks — `platforms/` (five platform algorithm knowledge bases), `methodology/` (four cross-niche method cores), `exemplars/` (existing assets as gold-standard samples) — plus a `skill-template/` skeleton the generator fills in. The generated product is a separate skill directory with a main orchestrator SKILL.md, four episode modules, a positioning diagnosis doc, and a cover-generation script wired to gpt-image-2.

**Tech Stack:** Markdown (skill + knowledge bases), Python 3 (cover generation via OpenAI SDK against B站 LLM gateway), pytest (script tests), git/GitHub.

## Global Constraints

- Repo remote: `https://github.com/firyrice/peanutcut-creator.git` (origin already set; repo currently empty — first push creates `main`).
- Skill root folder name: `video-workflow-builder`.
- Supported platforms (exactly these five): 抖音 douyin, B站 bilibili, 小红书 xiaohongshu, 视频号 shipinhao, 百家号 baijiahao.
- Interview asks ONLY 3 things: 平台 / 垂类 / 人设. Everything else (受众/差异化/变现) is researched, never asked.
- Every platform knowledge base MUST cover four layers: 推荐机制 / 核心指标与权重 / 内容形态适配 / 冷启动与破圈.
- Cover image model: `gpt-image-2` via `base_url="http://llmapi.bilibili.co/v1"` (OpenAI SDK compatible).
- API key `LLM_GATEWAY_API_KEY` value `bsk-fbd879a32261e2cebf0c9bb77ebaf13a` lives ONLY in `.env`; `.env` is git-ignored; ship `.env.example` with a placeholder. NEVER hardcode the key in any tracked file.
- Skill folders must work under both Claude Code (`~/.claude/skills/...`) and Codex (`~/.codex/skills/...`); scripts resolve their own dir, never assume cwd.
- Language: all skill-facing content in Chinese, matching the existing `bilibili-finance-video` voice.

---

## File Structure

Generator skill (this repo's deliverable):

```
video-workflow-builder/
├── SKILL.md                          # Task 3 — generator orchestration
├── README.md                         # Task 12 — install/usage
├── .gitignore                        # Task 1
├── references/
│   ├── platforms/
│   │   ├── douyin.md                 # Task 4
│   │   ├── bilibili.md               # Task 4
│   │   ├── xiaohongshu.md            # Task 5
│   │   ├── shipinhao.md              # Task 5
│   │   └── baijiahao.md              # Task 5
│   ├── methodology/
│   │   ├── title-craft.md            # Task 6
│   │   ├── topic-selection.md        # Task 7
│   │   ├── script-writing.md         # Task 7
│   │   └── cover-design.md           # Task 8
│   ├── exemplars/
│   │   ├── title-gen-v3.md           # Task 2 (copied asset)
│   │   └── bilibili-finance-video-skill.md  # Task 2 (copied asset)
│   └── skill-template/
│       ├── SKILL.md.tmpl             # Task 9
│       ├── positioning.md.tmpl       # Task 9
│       ├── topic-selection.md.tmpl   # Task 10
│       ├── script-writing.md.tmpl    # Task 10
│       ├── title-craft.md.tmpl       # Task 10
│       ├── cover-design.md.tmpl      # Task 10
│       ├── env.example.tmpl          # Task 11
│       └── gitignore.tmpl            # Task 11
├── scripts/
│   ├── generate_cover.py             # Task 11 — reusable cover generator
│   └── validate_skill.py             # Task 1 — structural validator (used as test harness)
└── tests/
    ├── test_generate_cover.py        # Task 11
    └── test_validate_skill.py        # Task 1
```

Each file has one responsibility: platform files hold only algorithm facts; methodology files hold only cross-niche method; template files hold only the fill-in skeleton with explicit `{{PLACEHOLDER}}` markers; scripts hold only executable logic.

---

### Task 1: Repo scaffold + structural validator

**Files:**
- Create: `video-workflow-builder/.gitignore`
- Create: `video-workflow-builder/scripts/validate_skill.py`
- Test: `video-workflow-builder/tests/test_validate_skill.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `validate_skill.py` exposing `validate_skill_dir(path: str) -> list[str]` returning a list of human-readable problem strings (empty list = valid). Rules it checks: (1) `SKILL.md` exists at `path`; (2) `SKILL.md` starts with a YAML frontmatter block containing `name:` and `description:`; (3) every `references/**/*.md` referenced by a relative link in `SKILL.md` actually exists on disk. Later tasks call this to gate their deliverables.

- [ ] **Step 1: Write the failing test**

`video-workflow-builder/tests/test_validate_skill.py`:
```python
import os
import tempfile
import textwrap

from scripts.validate_skill import validate_skill_dir


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def test_missing_skill_md_is_reported():
    with tempfile.TemporaryDirectory() as d:
        problems = validate_skill_dir(d)
        assert any("SKILL.md" in p for p in problems)


def test_missing_frontmatter_fields_reported():
    with tempfile.TemporaryDirectory() as d:
        _write(os.path.join(d, "SKILL.md"), "# no frontmatter here\n")
        problems = validate_skill_dir(d)
        assert any("name" in p for p in problems)
        assert any("description" in p for p in problems)


def test_broken_reference_link_reported():
    with tempfile.TemporaryDirectory() as d:
        _write(
            os.path.join(d, "SKILL.md"),
            textwrap.dedent(
                """\
                ---
                name: sample
                description: sample skill
                ---
                See [topic](references/topic-selection.md).
                """
            ),
        )
        problems = validate_skill_dir(d)
        assert any("references/topic-selection.md" in p for p in problems)


def test_valid_skill_returns_no_problems():
    with tempfile.TemporaryDirectory() as d:
        _write(
            os.path.join(d, "SKILL.md"),
            textwrap.dedent(
                """\
                ---
                name: sample
                description: sample skill
                ---
                See [topic](references/topic-selection.md).
                """
            ),
        )
        _write(os.path.join(d, "references", "topic-selection.md"), "# topic\n")
        problems = validate_skill_dir(d)
        assert problems == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd video-workflow-builder && python3 -m pytest tests/test_validate_skill.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.validate_skill'` (or collection error).

- [ ] **Step 3: Write minimal implementation**

`video-workflow-builder/scripts/validate_skill.py`:
```python
#!/usr/bin/env python3
"""Structural validator for generated (and generator) skill directories.

Usage:
    python3 scripts/validate_skill.py <skill_dir>
Exit code 0 = valid, 1 = problems found (printed one per line).
"""
import os
import re
import sys

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_LINK_RE = re.compile(r"\]\((references/[^)\s]+\.md)\)")


def validate_skill_dir(path):
    problems = []
    skill_md = os.path.join(path, "SKILL.md")
    if not os.path.isfile(skill_md):
        problems.append("SKILL.md is missing at %s" % path)
        return problems

    with open(skill_md, "r", encoding="utf-8") as f:
        text = f.read()

    m = _FRONTMATTER_RE.match(text)
    if not m:
        problems.append("SKILL.md missing YAML frontmatter (name/description)")
    else:
        block = m.group(1)
        if not re.search(r"^name:\s*\S+", block, re.MULTILINE):
            problems.append("SKILL.md frontmatter missing 'name'")
        if not re.search(r"^description:\s*\S+", block, re.MULTILINE):
            problems.append("SKILL.md frontmatter missing 'description'")

    for rel in _LINK_RE.findall(text):
        if not os.path.isfile(os.path.join(path, rel)):
            problems.append("SKILL.md links missing file: %s" % rel)

    return problems


def main(argv):
    if len(argv) != 2:
        print("usage: validate_skill.py <skill_dir>", file=sys.stderr)
        return 2
    problems = validate_skill_dir(argv[1])
    for p in problems:
        print(p)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

Also create `video-workflow-builder/.gitignore`:
```
.env
__pycache__/
*.pyc
.DS_Store
.pytest_cache/
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd video-workflow-builder && python3 -m pytest tests/test_validate_skill.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
cd video-workflow-builder
git add .gitignore scripts/validate_skill.py tests/test_validate_skill.py
git commit -m "feat: repo scaffold + structural skill validator"
```

---

### Task 2: Copy existing assets into exemplars

**Files:**
- Create: `video-workflow-builder/references/exemplars/title-gen-v3.md` (copy of `~/Desktop/video-title-gen-v3.md`)
- Create: `video-workflow-builder/references/exemplars/bilibili-finance-video-skill.md` (copy of `~/.claude/skills/bilibili-finance-video/SKILL.md` + its three references concatenated, with source headers)

**Interfaces:**
- Consumes: nothing.
- Produces: two exemplar files the generator cites as gold-standard quality/structure references. No code depends on their internals, only their existence (checked by later validation).

- [ ] **Step 1: Copy title-gen-v3 verbatim**

```bash
cd video-workflow-builder
cp ~/Desktop/video-title-gen-v3.md references/exemplars/title-gen-v3.md
```

- [ ] **Step 2: Assemble the bilibili exemplar**

Create `references/exemplars/bilibili-finance-video-skill.md` by concatenating, in order, with a `# === SOURCE: <path> ===` header line before each section:
1. `~/.claude/skills/bilibili-finance-video/SKILL.md`
2. `~/.claude/skills/bilibili-finance-video/references/title-formulas.md`
3. `~/.claude/skills/bilibili-finance-video/references/script-structure.md`
4. `~/.claude/skills/bilibili-finance-video/references/cover-prompts.md`

Use the Read tool to read each, then Write the combined file. Do not paraphrase — this is a verbatim reference sample. Prepend a 2-line note at top: `> 本文件是「金标准范例」，供生成器参照其质量与结构，不要原样照抄到用户产物里。`

- [ ] **Step 3: Verify files exist and are non-empty**

Run: `wc -l references/exemplars/*.md`
Expected: both files > 100 lines.

- [ ] **Step 4: Commit**

```bash
git add references/exemplars/
git commit -m "docs: add gold-standard exemplars (title-gen-v3, bilibili skill)"
```

---

### Task 3: Generator SKILL.md (orchestration)

**Files:**
- Create: `video-workflow-builder/SKILL.md`
- Test: reuse `scripts/validate_skill.py` (structural gate)

**Interfaces:**
- Consumes: references produced by Tasks 2/4-8 (links must resolve). To keep Task 3 committable before those files exist, only link to files that exist at commit time — link exemplars (Task 2) now; add platform/methodology links in their own tasks' final step OR create the target files first. Implementation note: Tasks 4-8 each append their link to SKILL.md's reference index as their last step.
- Produces: the generator entry point. Defines trigger words, the five-phase flow, and the rule set below.

- [ ] **Step 1: Write SKILL.md**

Frontmatter:
```markdown
---
name: video-workflow-builder
description: 视频创作工作流生成器。当用户想为自己的账号定制一套完整的视频创作流程（选题、文稿、标题、封面），或说"帮我做个账号工作流""定制视频流程""我想在抖音/B站/小红书/视频号/百家号做XX内容"时使用。它只问三件事（平台、垂类、人设），其余靠联网研究补齐，先给出账号定位诊断供确认，再生成一套可安装使用的专属工作流 skill。
---
```

Body MUST contain these sections (write them in full Chinese prose, following the bilibili skill's voice — this is the largest authored artifact; target 200-400 lines):

1. **`# 视频创作工作流生成器`** — one-paragraph identity: a meta-skill that builds bespoke workflow skills.
2. **`## 跨工具适配`** — copy the Claude Code / Codex mapping paragraph pattern from the bilibili exemplar (WebSearch/WebFetch, Write, python3; resolve skill dir absolutely: `~/.claude/skills/video-workflow-builder` or `~/.codex/skills/video-workflow-builder`).
3. **`## 内置资源索引`** — a link list to `references/platforms/*.md`, `references/methodology/*.md`, `references/exemplars/*.md`, `references/skill-template/`. (Links to platform/methodology files are filled in by Tasks 4-8; at Task 3 commit, include only exemplar links so validator passes.)
4. **`## 五阶段流程`** — the core. Document each phase as a numbered subsection with explicit STOP points:
   - **阶段0 · 极简访谈**: ask ONLY 平台(可多选，五选N) / 垂类 / 人设. Explicitly instruct: do NOT ask about 受众/差异化/变现.
   - **阶段1 · 联网研究**: for the chosen (平台×垂类), use WebSearch/WebFetch to gather 受众画像、当下爆款案例与共性、竞品格局、变现路径、平台最新算法动向; AND read the matching `references/platforms/<p>.md` for mechanism/metric weights. If no network, say so honestly, fall back to internal knowledge, do not fabricate live data.
   - **阶段2 · 诊断提案 (STOP 1)**: output 「账号定位诊断 + 策略提案」covering 目标受众(含受众心声)、差异化定位、内容方向、变现路径、各平台适配建议. Then STOP and ask user to confirm/adjust. Do not generate until confirmed.
   - **阶段3 · 生成工作流 skill**: after confirmation, produce the product skill (see 生成规范 below).
   - **阶段4 · 交付说明**: tell user install path, trigger words, how to call each module standalone, how to set the API key.
5. **`## 生成规范`** — how to fill the template:
   - Product folder name: `<账号名>-workflow` (ask user for a short account slug if not obvious; default to a niche-based slug).
   - Fill every `{{PLACEHOLDER}}` in `references/skill-template/*.tmpl` (list them: `{{ACCOUNT_NAME}}`, `{{PLATFORMS}}`, `{{NICHE}}`, `{{PERSONA}}`, `{{AUDIENCE}}`, `{{POSITIONING}}`, `{{TITLE_RULES}}`, `{{COVER_SIZES}}`, `{{TOPIC_FRAMEWORK}}`, etc. — cross-reference Tasks 9-11 for the full list).
   - Inject platform-specific rules by copying the relevant facts from `references/platforms/<p>.md` into each module (do not just link — the product must be self-contained).
   - Configure scripts: always copy `generate_cover.py`, `.env.example`, `.gitignore`; add niche data-scraping scripts only if the niche needs live data (state the heuristic: needs live data = 财经/热点/榜单类).
   - Run `python3 scripts/validate_skill.py <product_dir>` after generation; fix any reported problems before delivering.
6. **`## 质量标准`** — bullet the non-negotiables: every generated title module inherits title-gen-v3 logic; every platform's four algorithm layers must be reflected; cover script must never hardcode the key; product must pass the validator.

- [ ] **Step 2: Run structural validator against the generator itself**

Run: `cd video-workflow-builder && python3 scripts/validate_skill.py .`
Expected: exit 0, no output (frontmatter present, all links to existing exemplar files resolve).

- [ ] **Step 3: Commit**

```bash
git add SKILL.md
git commit -m "feat: generator orchestration SKILL.md (five-phase flow)"
```

---

### Task 4: Platform knowledge bases — 抖音 + B站

**Files:**
- Create: `video-workflow-builder/references/platforms/douyin.md`
- Create: `video-workflow-builder/references/platforms/bilibili.md`
- Modify: `video-workflow-builder/SKILL.md` (add both to 内置资源索引)

**Interfaces:**
- Consumes: nothing at runtime; content authored from research.
- Produces: two platform files, each with the mandatory four-layer structure (`## 推荐机制`, `## 核心指标与权重`, `## 内容形态适配`, `## 冷启动与破圈`) plus a `## 一句话打法` summary line.

- [ ] **Step 1: Research each platform**

Use WebSearch/WebFetch (current date 2026) to confirm/refresh: douyin 完播率与初始流量池赛马机制、竖屏时长、标签冷启动; bilibili 播放时长权重、长视频铺垫、三连与粉丝分发、搜索占比. Capture concrete, current facts — not vibes.

- [ ] **Step 2: Write douyin.md**

Must fill all four `##` layers with specifics:
- 推荐机制: 初始流量池(约200-500播放)赛马、完播率/互动率决定是否进入下一层流量池、层层放大、去中心化分发、粉丝分发占比低。
- 核心指标与权重: 完播率(最高权重) > 互动率(点赞/评论/转发/关注) > 播放时长 > CTR(封面标题). Each metric → content lever.
- 内容形态适配: 竖屏9:16、黄金3秒钩子、时长(15-60s强钩子，1-3min可承载信息)、字幕必备、BGM卡点、封面在信息流中弱、标题/开头字幕强。
- 冷启动与破圈: 新号垂直标签养成、前5条定人设、DOU+的作用与边界、避免搬运/违规限流红线。
- 一句话打法: e.g. "抖音是完播率战场：3秒钩子 + 高信息密度 + 强节奏，让人划不走。"

- [ ] **Step 3: Write bilibili.md**

Same four-layer structure, B站-specific:
- 推荐机制: 首个流量池 + 后续赛马、播放时长(总时长而非仅完播率)、三连(点赞/投币/收藏)权重高、粉丝关系链分发强、搜索与分区推荐、UP主粘性。
- 核心指标与权重: 播放时长/平均播放进度 > 三连互动 > 完播 > CTR. Each → lever.
- 内容形态适配: 横屏16:9、可长视频(5-15min)铺垫叙事、封面(4:3感)+标题双驱动、开头可稍缓但需价值预告、分P与合集。
- 冷启动与破圈: 新号选分区、前期靠标题封面破CTR、粉丝基本盘养成、恰饭红线。
- 一句话打法.

- [ ] **Step 4: Add both to SKILL.md 内置资源索引**

Append under the platforms subsection:
```markdown
- [抖音算法](references/platforms/douyin.md)
- [B站算法](references/platforms/bilibili.md)
```

- [ ] **Step 5: Validate + commit**

Run: `cd video-workflow-builder && python3 scripts/validate_skill.py .` → exit 0.
```bash
git add references/platforms/douyin.md references/platforms/bilibili.md SKILL.md
git commit -m "docs: platform knowledge bases for douyin and bilibili"
```

---

### Task 5: Platform knowledge bases — 小红书 + 视频号 + 百家号

**Files:**
- Create: `video-workflow-builder/references/platforms/xiaohongshu.md`
- Create: `video-workflow-builder/references/platforms/shipinhao.md`
- Create: `video-workflow-builder/references/platforms/baijiahao.md`
- Modify: `video-workflow-builder/SKILL.md` (add three to 内置资源索引)

**Interfaces:**
- Consumes: nothing.
- Produces: three platform files, same mandatory four-layer structure + 一句话打法 as Task 4.

- [ ] **Step 1: Research all three** via WebSearch/WebFetch (2026-current facts).

- [ ] **Step 2: Write xiaohongshu.md** — four layers:
- 推荐机制: 去中心化 + 搜索流量占比极高、CES评分(点赞/收藏/评论/关注加权)、笔记进入流量池赛马、长尾搜索复访、封面即第一入口。
- 核心指标与权重: CTR(封面+标题) 与 搜索关键词覆盖 权重极高 > 收藏(高于点赞) > 互动 > 完播. Each → lever.
- 内容形态适配: 竖屏3:4封面(1242x1660感)、封面标题党+大字、正文含关键词与话题标签、图文与短视频并行、"干货体"结构。
- 冷启动与破圈: 关键词卡位、蹲搜索、避免营销词限流、素人铺量、爆文结构复用。
- 一句话打法.

- [ ] **Step 3: Write shipinhao.md** — four layers:
- 推荐机制: 强社交推荐(朋友点赞→关系链扩散) + 机器推荐叠加、公众号/微信生态导流、看一看/搜一搜入口。
- 核心指标与权重: 社交传播(点赞=向好友扩散) 与 完播/互动 > CTR. Each → lever.
- 内容形态适配: 竖屏、时长偏短、强情绪易转发、标题弱封面弱但首帧重要、结合公众号图文。
- 冷启动与破圈: 靠社交裂变冷启动、引导好友点赞、私域导流、避免诱导分享红线。
- 一句话打法.

- [ ] **Step 4: Write baijiahao.md** — four layers:
- 推荐机制: 信息流分发(手百/百度APP) + 搜索(百度搜索加权)、内容分发以标题与领域垂直度为主、去中心化推荐。
- 核心指标与权重: CTR(标题在信息流) 与 搜索关键词/领域垂直度 > 阅读完成度/播放时长 > 互动. Each → lever.
- 内容形态适配: 图文权重高、视频亦可、标题信息流党、封面三图或单图、领域标签一致性。
- 冷启动与破圈: 领域垂直养号、原创分与信用分、蹭百度搜索热词、避免标题党违规扣分。
- 一句话打法.

- [ ] **Step 5: Add three to SKILL.md 内置资源索引:**
```markdown
- [小红书算法](references/platforms/xiaohongshu.md)
- [视频号算法](references/platforms/shipinhao.md)
- [百家号算法](references/platforms/baijiahao.md)
```

- [ ] **Step 6: Validate + commit**

Run: `python3 scripts/validate_skill.py .` → exit 0.
```bash
git add references/platforms/ SKILL.md
git commit -m "docs: platform knowledge bases for xiaohongshu, shipinhao, baijiahao"
```

---

### Task 6: Methodology core — 标题 (title-craft.md)

**Files:**
- Create: `video-workflow-builder/references/methodology/title-craft.md`
- Modify: `video-workflow-builder/SKILL.md` (add to 内置资源索引)

**Interfaces:**
- Consumes: `references/exemplars/title-gen-v3.md` (source of truth to distill).
- Produces: a cross-niche title methodology the title module template (Task 10) draws from.

- [ ] **Step 1: Distill title-gen-v3 into a platform/niche-agnostic core.** Write `title-craft.md` covering, in Chinese prose:
- 两型标题: 好问题 / 清晰的结论 (定义 + 判断标准).
- 把矛盾拉满: [强属性]+[反预期属性]，参照物要有公认印象.
- 靶子要有公共认知度(不要自造抽象标签) — include the 甘地 vs Charriot contrast as example.
- 话题可辨识 + 关键词锚定(受众口语 > 搜索关键词，但至少保留1个搜索词).
- 动机匹配(恐惧/愤怒/希望最强).
- 开头结构呼应(Hook型15秒兑现 / 非Hook型前1/3兑现).
- 通用格式约束: 说明"字数与标点规则随平台变化，具体值由平台知识库注入"(不要写死B站的25字上限，因为这是通用内核).
- 明确标注: 这是通用内核，平台专属规则(字数/标点/关键词位置)在生成时从 `platforms/*.md` 注入。

- [ ] **Step 2: Add to SKILL.md 内置资源索引:**
```markdown
- [标题方法论](references/methodology/title-craft.md)
```

- [ ] **Step 3: Validate + commit**

Run: `python3 scripts/validate_skill.py .` → exit 0.
```bash
git add references/methodology/title-craft.md SKILL.md
git commit -m "docs: cross-niche title methodology core"
```

---

### Task 7: Methodology cores — 选题 + 文稿

**Files:**
- Create: `video-workflow-builder/references/methodology/topic-selection.md`
- Create: `video-workflow-builder/references/methodology/script-writing.md`
- Modify: `video-workflow-builder/SKILL.md` (add both to 内置资源索引)

**Interfaces:**
- Consumes: `references/exemplars/*` for structural reference.
- Produces: two methodology cores feeding the 选题/文稿 module templates (Task 10).

- [ ] **Step 1: Write topic-selection.md** — cross-niche 选题方法论:
- 受众动机模型(信息服务 + 情绪价值；恐惧/愤怒/希望排序).
- 比较优势定位(更专业/更易懂/更有戏剧性/更有代入感/更有感染力，找最突出1-2个).
- 热点结合(结合平台热榜/搜索词，附"用当前环境联网工具抓热点"的指引，不写死数据源).
- 可持续选题库(建立选题矩阵，避免一次性).
- 反直觉点提炼.
- 明确标注: 垂类专属选题框架(如财经七维度)在生成时按垂类现产，本文件是通用骨架。

- [ ] **Step 2: Write script-writing.md** — cross-niche 文稿方法论:
- Hook结构(前15秒定生死；Hook型 vs 非Hook型判断).
- 节奏控制与信息密度(按平台时长调整；每段一个信息点).
- 完播设计(悬念递进、进度锚点、"然后呢"感).
- 互动引导(自然植入提问/争议点，匹配平台互动权重).
- 兑现标题承诺.
- 明确标注: 时长与形态(竖屏短/横屏长)由平台知识库注入。

- [ ] **Step 3: Add both to SKILL.md 内置资源索引:**
```markdown
- [选题方法论](references/methodology/topic-selection.md)
- [文稿方法论](references/methodology/script-writing.md)
```

- [ ] **Step 4: Validate + commit**

Run: `python3 scripts/validate_skill.py .` → exit 0.
```bash
git add references/methodology/topic-selection.md references/methodology/script-writing.md SKILL.md
git commit -m "docs: cross-niche topic-selection and script-writing methodology cores"
```

---

### Task 8: Methodology core — 封面 (cover-design.md)

**Files:**
- Create: `video-workflow-builder/references/methodology/cover-design.md`
- Modify: `video-workflow-builder/SKILL.md` (add to 内置资源索引)

**Interfaces:**
- Consumes: `references/exemplars/bilibili-finance-video-skill.md` (contains the cover-prompts patterns).
- Produces: cross-niche cover methodology feeding the cover module template (Task 10) and prompt-writing guidance for `generate_cover.py`.

- [ ] **Step 1: Write cover-design.md** — cross-niche 封面方法论:
- 封面在1秒内传达: 话题是什么 + 什么情绪 + 一句勾人大字.
- 视觉焦点与留白、大字文案(4-8字最佳)、文案与标题互补(不重复同一句话).
- 系列感(固定排布/位置，账号识别度).
- 情绪配色原则(按内容调性，不写死财经的红涨绿跌，说明"配色随垂类情绪映射").
- gpt-image-2 提示词写法: 英文描述画面 + 中文明确写"图上出现的大字"，风格词、排版要求、生成后检查中文是否正确.
- 平台尺寸: 明确各平台画幅(B站4:3≈1024x768、抖音/视频号竖屏9:16或3:4、小红书3:4≈768x1024、百家号信息流三图/单图)，说明生成时按目标平台选尺寸。
- 明确标注: 尺寸与情绪映射在生成时按平台+垂类注入。

- [ ] **Step 2: Add to SKILL.md 内置资源索引:**
```markdown
- [封面方法论](references/methodology/cover-design.md)
```

- [ ] **Step 3: Validate + commit**

Run: `python3 scripts/validate_skill.py .` → exit 0.
```bash
git add references/methodology/cover-design.md SKILL.md
git commit -m "docs: cross-niche cover-design methodology core"
```

---

### Task 9: Product template — main SKILL.md + positioning

**Files:**
- Create: `video-workflow-builder/references/skill-template/SKILL.md.tmpl`
- Create: `video-workflow-builder/references/skill-template/positioning.md.tmpl`

**Interfaces:**
- Consumes: nothing at runtime; the generator (Task 3) fills these.
- Produces: the two top-level product files. Placeholder contract (used verbatim by generator + Tasks 10-11): `{{ACCOUNT_NAME}}`, `{{ACCOUNT_SLUG}}`, `{{PLATFORMS}}`, `{{NICHE}}`, `{{PERSONA}}`, `{{TRIGGER_WORDS}}`, `{{AUDIENCE}}`, `{{AUDIENCE_VOICE}}`, `{{POSITIONING}}`, `{{DIFFERENTIATION}}`, `{{MONETIZATION}}`, `{{PLATFORM_ADAPTATION}}`.

- [ ] **Step 1: Write SKILL.md.tmpl** — the product orchestrator skeleton (Chinese), containing:
- Frontmatter with `name: {{ACCOUNT_SLUG}}-workflow` and a `description:` template embedding `{{NICHE}}`, `{{PLATFORMS}}`, `{{TRIGGER_WORDS}}`.
- `## 账号人设` → `{{PERSONA}}`.
- `## 跨工具适配` — same Claude Code/Codex mapping block (self-contained in product).
- `## 工作流程总览` — the four episode modules (选题→文稿→标题→封面) with a human decision point after 选题, and a note that each module can be triggered standalone. Links: `[选题](references/topic-selection.md)`, `[文稿](references/script-writing.md)`, `[标题](references/title-craft.md)`, `[封面](references/cover-design.md)`, `[账号定位诊断](references/positioning.md)`.
- `## 定位速览` → pulls key lines from `{{POSITIONING}}`.

- [ ] **Step 2: Write positioning.md.tmpl** — the diagnosis doc skeleton:
```markdown
# {{ACCOUNT_NAME}} 账号定位诊断

> 本文件解释「为什么这套工作流这样定制」。生成依据：平台算法知识库 + 联网研究 + 你提供的平台/垂类/人设。

## 基本信息
- 平台: {{PLATFORMS}}
- 垂类: {{NICHE}}
- 人设: {{PERSONA}}

## 目标受众
{{AUDIENCE}}

### 受众心声（他们脑子里的话）
{{AUDIENCE_VOICE}}

## 差异化定位
{{DIFFERENTIATION}}

## 内容方向
{{POSITIONING}}

## 变现路径
{{MONETIZATION}}

## 各平台适配建议
{{PLATFORM_ADAPTATION}}
```

- [ ] **Step 3: Verify placeholders are consistent**

Run: `grep -oE "\{\{[A-Z_]+\}\}" references/skill-template/SKILL.md.tmpl references/skill-template/positioning.md.tmpl | sort -u`
Expected: only placeholders from the contract above appear.

- [ ] **Step 4: Commit**

```bash
git add references/skill-template/SKILL.md.tmpl references/skill-template/positioning.md.tmpl
git commit -m "feat: product templates for main SKILL and positioning doc"
```

---

### Task 10: Product templates — four episode modules

**Files:**
- Create: `video-workflow-builder/references/skill-template/topic-selection.md.tmpl`
- Create: `video-workflow-builder/references/skill-template/script-writing.md.tmpl`
- Create: `video-workflow-builder/references/skill-template/title-craft.md.tmpl`
- Create: `video-workflow-builder/references/skill-template/cover-design.md.tmpl`

**Interfaces:**
- Consumes: methodology cores (Tasks 6-8) + platform files (Tasks 4-5), copied/injected by the generator.
- Produces: four module skeletons. Additional placeholders (extend the contract): `{{TOPIC_FRAMEWORK}}`, `{{HOT_SOURCE_GUIDE}}`, `{{SCRIPT_LENGTH}}`, `{{SCRIPT_STRUCTURE}}`, `{{TITLE_RULES}}`, `{{TITLE_KEYWORD_RULE}}`, `{{COVER_SIZES}}`, `{{COVER_EMOTION_MAP}}`, `{{COVER_SERIES_LAYOUT}}`.

- [ ] **Step 1: Write topic-selection.md.tmpl** — standalone-triggerable 选题 module:
- Trigger note (how to invoke standalone).
- Distilled 选题方法论 body (from methodology core), with `{{TOPIC_FRAMEWORK}}` = the niche-specific framework the generator writes, and `{{HOT_SOURCE_GUIDE}}` = how to fetch hot topics for this platform/niche.
- Output format: N 个选题方案，每个带钩子+预估热度，STOP 让用户选。

- [ ] **Step 2: Write script-writing.md.tmpl** — standalone 文稿 module:
- Body from script methodology, with `{{SCRIPT_LENGTH}}` and `{{SCRIPT_STRUCTURE}}` (platform-tuned) injected.
- Output format: 完整口播稿/图文稿 with hook + 完播设计 + 互动引导.

- [ ] **Step 3: Write title-craft.md.tmpl** — standalone 标题 module:
- Body from title methodology, with `{{TITLE_RULES}}` (platform 字数/标点) and `{{TITLE_KEYWORD_RULE}}` injected.
- Output: 内部生成候选 → 淘汰 → 输出 finalists + 推荐 + 开头结构建议 (mirror title-gen-v3 output format).

- [ ] **Step 4: Write cover-design.md.tmpl** — standalone 封面 module:
- Body from cover methodology, with `{{COVER_SIZES}}`, `{{COVER_EMOTION_MAP}}`, `{{COVER_SERIES_LAYOUT}}` injected.
- Include the exact `generate_cover.py` invocation examples (per-platform `--platform`/`--size`).
- Reminder: check generated Chinese text; never commit `.env`.

- [ ] **Step 5: Verify placeholder consistency**

Run: `grep -ohE "\{\{[A-Z_]+\}\}" references/skill-template/*.tmpl | sort -u`
Expected: every placeholder appears in the combined contract from Tasks 9+10. No stray/misspelled placeholders.

- [ ] **Step 6: Commit**

```bash
git add references/skill-template/topic-selection.md.tmpl references/skill-template/script-writing.md.tmpl references/skill-template/title-craft.md.tmpl references/skill-template/cover-design.md.tmpl
git commit -m "feat: product templates for four episode modules"
```

---

### Task 11: Cover generation script + product script templates

**Files:**
- Create: `video-workflow-builder/scripts/generate_cover.py`
- Create: `video-workflow-builder/references/skill-template/env.example.tmpl`
- Create: `video-workflow-builder/references/skill-template/gitignore.tmpl`
- Test: `video-workflow-builder/tests/test_generate_cover.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `generate_cover.py` with `_load_api_key() -> str | None` (env `LLM_GATEWAY_API_KEY` first, then sibling-of-parent `.env`), `resolve_size(platform: str, override: str | None) -> str`, and a `PLATFORM_SIZES` dict keyed by all five platforms. The generator copies this script verbatim into products.

- [ ] **Step 1: Write the failing test**

`video-workflow-builder/tests/test_generate_cover.py`:
```python
import importlib.util
import os

_SPEC = importlib.util.spec_from_file_location(
    "generate_cover",
    os.path.join(os.path.dirname(__file__), "..", "scripts", "generate_cover.py"),
)
gc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gc)


def test_platform_sizes_cover_all_five_platforms():
    for p in ["douyin", "bilibili", "xiaohongshu", "shipinhao", "baijiahao"]:
        assert p in gc.PLATFORM_SIZES
        assert "x" in gc.PLATFORM_SIZES[p]


def test_resolve_size_uses_platform_default():
    assert gc.resolve_size("bilibili", None) == gc.PLATFORM_SIZES["bilibili"]


def test_resolve_size_override_wins():
    assert gc.resolve_size("douyin", "512x512") == "512x512"


def test_load_api_key_prefers_env(monkeypatch):
    monkeypatch.setenv("LLM_GATEWAY_API_KEY", "env-key-123")
    assert gc._load_api_key() == "env-key-123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd video-workflow-builder && python3 -m pytest tests/test_generate_cover.py -v`
Expected: FAIL (module file not found / attributes missing).

- [ ] **Step 3: Write generate_cover.py**

Base it on the proven `~/.claude/skills/bilibili-finance-video/scripts/generate_cover.py` (env→.env key loading, base64/url handling). Changes required:
- Extend `PLATFORM_SIZES` to all five:
```python
PLATFORM_SIZES = {
    "douyin": "768x1024",
    "bilibili": "1024x768",
    "xiaohongshu": "768x1024",
    "shipinhao": "768x1024",
    "baijiahao": "1024x768",
}
```
- Extract size logic into a testable function:
```python
def resolve_size(platform, override):
    if override:
        return override
    return PLATFORM_SIZES[platform]
```
- Keep `_load_api_key()` identical in behavior (env var first, then `.env` in the script's parent-of-parent dir). Keep `BASE_URL = "http://llmapi.bilibili.co/v1"` and `MODEL = "gpt-image-2"`.
- `--platform` choices = all five keys. In `main()`, call `resolve_size(args.platform, args.size)`.
- Header docstring documents key loading and `pip install openai`.

- [ ] **Step 4: Write env.example.tmpl and gitignore.tmpl**

`env.example.tmpl`:
```
# 复制为 .env 并填入你的 key（.env 不会被提交）
LLM_GATEWAY_API_KEY=your-key-here
```
`gitignore.tmpl`:
```
.env
__pycache__/
*.pyc
.DS_Store
```
Note in the generator (Task 3 生成规范, already referenced): when generating a product, write the real key value `bsk-fbd879a32261e2cebf0c9bb77ebaf13a` into the product's `.env` (git-ignored), and copy `env.example.tmpl`→`.env.example` with the placeholder only.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd video-workflow-builder && python3 -m pytest tests/test_generate_cover.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_cover.py tests/test_generate_cover.py references/skill-template/env.example.tmpl references/skill-template/gitignore.tmpl
git commit -m "feat: five-platform cover generator + product env/gitignore templates"
```

---

### Task 12: End-to-end generation dry-run + README + push

**Files:**
- Create: `video-workflow-builder/README.md`
- Create (throwaway, in /tmp): a sample generated product to validate the pipeline.

**Interfaces:**
- Consumes: everything above.
- Produces: verified pipeline + docs + first push to origin.

- [ ] **Step 1: Manual dry-run of the generator logic**

Pick a sample: 平台=小红书, 垂类=家庭理财, 人设=二胎宝妈. By hand (simulating阶段3), fill the templates into `/tmp/baomom-workflow/` — copy each `.tmpl`, replace every `{{PLACEHOLDER}}`, copy `generate_cover.py`, write `.env` (real key) + `.env.example` + `.gitignore`.

- [ ] **Step 2: Validate the generated product**

Run: `cd video-workflow-builder && python3 scripts/validate_skill.py /tmp/baomom-workflow`
Expected: exit 0, no problems. If any `{{...}}` remain or links break, fix the template/flow, re-run.

- [ ] **Step 3: Confirm no placeholder leaked**

Run: `grep -rE "\{\{[A-Z_]+\}\}" /tmp/baomom-workflow || echo "clean"`
Expected: `clean`.

- [ ] **Step 4: Confirm key is not in any tracked-style file**

Run: `grep -rl "bsk-fbd879" /tmp/baomom-workflow`
Expected: only `/tmp/baomom-workflow/.env` (never in SKILL.md, scripts, or .example). Clean up: `rm -rf /tmp/baomom-workflow`.

- [ ] **Step 5: Write README.md** — install (Claude Code `~/.claude/skills/` and Codex `~/.codex/skills/`), what it does, the five-phase flow, `pip install openai`, how the generated product is used, security note about `.env`.

- [ ] **Step 6: Final full validation + commit + push**

```bash
cd video-workflow-builder
python3 -m pytest -q
python3 scripts/validate_skill.py .
git add README.md
git commit -m "docs: README + verified end-to-end generation dry-run"
git branch -M main
git push -u origin main
```
Expected: tests pass, validator exit 0, push creates `main` on origin.

---

## Self-Review

**Spec coverage:**
- Meta-skill/generator form → Tasks 3, 9-12. ✓
- Internal knowledge (platforms) + runtime online research → Tasks 4-5 (banks) + Task 3 阶段1 (research). ✓
- Five platforms → Tasks 4-5. ✓
- Main orchestrator + four standalone modules → Task 9 (main) + Task 10 (modules). ✓
- Interview only 3 things → Task 3 阶段0. ✓
- Diagnosis doc + confirmation gate → Task 3 阶段2 + Task 9 positioning.md.tmpl. ✓
- Full skill dir + niche scripts → Tasks 9-11 + Task 3 生成规范 (script heuristic). ✓
- Distill core (A) + exemplars (C) → Tasks 2, 6-8. ✓
- Four algorithm layers per platform → Tasks 4-5 (enforced structure). ✓
- gpt-image-2 via gateway, key in .env → Task 11 + Global Constraints. ✓
- Cross-tool (Claude Code/Codex) → Task 3 + Task 9 templates. ✓
- GitHub repo → Task 1 scaffold + Task 12 push. ✓
- YAGNI boundaries (no runtime executor, no other platforms, no data-loop) → not built; plan stays within scope. ✓

**Placeholder scan:** No "TBD/TODO"; all code steps show full code; platform/module content specified with concrete required facts rather than "add appropriate content." Authored-prose tasks (4-8) list mandatory sections and specific facts to include.

**Type consistency:** `validate_skill_dir(path)->list[str]`, `_load_api_key()`, `resolve_size(platform, override)`, `PLATFORM_SIZES` (five keys) used consistently across Tasks 1, 11, 12. Placeholder contract defined in Task 9 and extended in Task 10; Task 10 Step 5 grep enforces consistency; Task 12 Step 3 enforces no leak.
