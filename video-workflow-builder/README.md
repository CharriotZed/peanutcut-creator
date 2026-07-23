# video-workflow-builder

一个"生成 skill 的 skill"。它不直接帮你选题、写文稿、做封面——它把这一整套能力，按照你的**平台、垂类、人设**量身定制成一个独立、可安装、开箱即用的专属视频创作工作流 skill，覆盖从选题到文稿、标题、封面的完整链路，并把最终成片收口到**花生 AI**（素材剪辑 + MG 动画 + 本地素材，口播驱动）。

## 它是怎么工作的

问你三件必答（平台、垂类、人设）+ 一件选答（有没有想参考的对标账号），剩下的受众画像、爆款打法、变现路径、平台算法动向靠联网研究 + 内置资料补齐，先给一份账号定位诊断供你确认方向，确认后才生成产物 skill。整个过程分五个阶段：

1. **极简访谈**——问平台/垂类/人设三件必答，外加"有没有对标账号"这一件选答（给了就拆解它加速搭建 + 做差异化，没给就跳过），不追问受众画像、差异化定位这类研究阶段才该有的答案。
2. **联网研究**——WebSearch/WebFetch 查受众画像、爆款案例、竞品格局、变现路径、平台算法动向；若有对标账号，额外拆解它的选题/标题/封面/文稿套路与差异化空档；同时读取内置的 `references/platforms/*.md` 平台算法拆解作为补充和校验。
3. **诊断提案（STOP）**——产出目标受众、差异化定位、内容方向、变现路径、各平台适配建议，**必须停下来等用户确认**，不确认不生成产物。
4. **生成工作流 skill**——按「生成规范」把研究成果和确认后的定位，填进 `references/skill-template/*.tmpl` 落地成完整产物目录，并运行 `scripts/validate_skill.py` 自查。
5. **交付说明**——告知安装路径、触发词、四个模块的独立调用方式、怎么把口播稿落到花生 AI 成片、API key 设置方式。

## 最终成片走花生 AI

产出的核心是**一段能直接粘进花生 AI 的纯口播稿**：花生按口播文字的语义自动匹配画面素材、生成 MG 动画、穿插本地素材成片。因此文稿模块只输出纯口播稿（中文标点规范、不带章节/画面/分镜标注），选题阶段也会把"口播讲得动、素材找得到"作为一条硬准入门槛。详见 `references/methodology/peanut-production.md`。

## 安装

把整个 `video-workflow-builder/` 目录放到 Claude Code 的 skills 目录下：

- **Claude Code**：`~/.claude/skills/video-workflow-builder`

Claude Code 通过读取 `SKILL.md` 识别技能，联网/写文件/跑脚本的能力映射已经写在 `SKILL.md` 里，不需要额外配置。

## 依赖

生成的产物 skill 会带一个 `scripts/generate_cover.py`，调用 `gpt-image-2`（走 LLM 网关）生成封面图，需要：

```bash
pip install openai
```

本技能自身（生成器）不需要额外依赖，只用到 `python3` 标准库跑 `scripts/validate_skill.py` 做结构校验。

## 生成出来的产物长什么样

产物目录命名为 `<账号名>-workflow`，结构大致如下：

```
<账号名>-workflow/
├── SKILL.md                    # 主入口，含账号人设、工作流总览、定位速览
├── references/
│   ├── positioning.md          # 账号定位诊断（受众/差异化/变现路径/平台适配）
│   ├── topic-selection.md      # 选题模块
│   ├── script-writing.md       # 文稿模块
│   ├── title-craft.md          # 标题模块（继承 title-gen-v3 的文稿深度分析方法）
│   └── cover-design.md         # 封面模块
├── scripts/
│   └── generate_cover.py       # 封面生成脚本（调用 gpt-image-2）
├── .env.example                 # 密钥占位模板，会被提交
├── .env                          # 真实密钥，git-ignored，不会被提交
└── .gitignore
```

产物是**自包含**的——用户装上产物 skill 后不再依赖本生成器技能本身：平台算法事实（推荐机制/核心指标权重/内容形态/冷启动打法）在生成时已经复制改写进各模块正文，而不是留一个指回生成器的链接。

## 怎么用生成出来的产物

- **触发词**：产物 `SKILL.md` 的 frontmatter 里配置了该账号场景下的触发短语（如"帮我想个理财选题""起个理财标题"），说这类话就能唤起。
- **完整流程**：选题 → 人工确认选定方向 → 文稿 → 标题 → 封面，中间只有"选题确认"这一个人工决策点。
- **单模块独立调用**：四个模块（`references/topic-selection.md`、`script-writing.md`、`title-craft.md`、`cover-design.md`）都可以单独唤起，比如已经有文稿只想起标题，直接说需求即可，不必每次都从选题走完整流程。

## 安全：API key 处理

产物的封面生成脚本要用到 `LLM_GATEWAY_API_KEY`。**真实密钥只允许写进产物目录下、已被 `.gitignore` 排除的 `.env` 文件**，由用户自己填入或本技能在生成时以环境变量形式写入这个 git-ignored 文件；随产物一起提交/追踪的 `.env.example` 永远只放占位符（`your-key-here`）。任何真实密钥值都不允许出现在 `SKILL.md`、脚本源码或任何会被版本控制追踪的文件里——这条是生成规范里的安全红线，`scripts/validate_skill.py` 校验通过不代表密钥处理合规，仍需人工确认 `.env` 内容从未被 `git add`。

## 开发自查

本仓库自带的校验和测试：

```bash
cd video-workflow-builder
python3 -m pytest -q                     # 单元测试（validate_skill / generate_cover）
python3 scripts/validate_skill.py .      # 结构校验（frontmatter + 内部链接）
python3 scripts/validate_skill.py <产物目录>   # 校验任意生成产物
```
