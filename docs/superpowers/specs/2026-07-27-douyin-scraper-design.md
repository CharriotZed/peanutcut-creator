# 抖音账号数据抓取 + 分析报告生成器

## 概述

一个 Python 脚本，使用 Playwright 浏览器自动化抓取抖音用户主页的完整数据，并自动生成结构化分析报告。

## 数据模型

### 账号级（Account）

| 字段 | 类型 | 说明 |
|------|------|------|
| `nickname` | string | 账号昵称 |
| `douyin_id` | string | 抖音号 |
| `avatar_url` | string | 头像图片链接 |
| `signature` | string | 个人简介 |
| `follower_count` | int | 粉丝数 |
| `following_count` | int | 关注数 |
| `total_likes` | int | 获赞总数 |
| `video_count` | int | 作品数量 |
| `verified_badge` | string\|null | 认证标识（如"企业认证"） |

### 视频级（Video）

| 字段 | 类型 | 说明 |
|------|------|------|
| `video_id` | string | 视频唯一 ID |
| `url` | string | 视频页面链接 |
| `title` | string | 视频标题/描述 |
| `cover_url` | string | 封面图链接 |
| `duration_sec` | int | 视频时长（秒） |
| `publish_time` | string | 发布时间 ISO 格式 |
| `views` | int | 播放量 |
| `likes` | int | 点赞数 |
| `comments_count` | int | 评论数 |
| `shares` | int | 分享数 |
| `hashtags` | string[] | 话题标签列表 |
| `top_comments` | Comment[] | Top 20 热评 |

### 评论级（Comment）

| 字段 | 类型 | 说明 |
|------|------|------|
| `user` | string | 评论者昵称 |
| `text` | string | 评论内容 |
| `likes` | int | 评论点赞数 |
| `reply_count` | int | 回复数 |
| `time` | string | 评论时间（抓取到的文本格式） |

## 架构

```
scrape_douyin.py       ← 单文件脚本，零内部依赖
  ├── Playwright → Chromium 浏览器
  ├── 手动扫码登录（session cookie 持久化）
  ├── 主页 → 账号数据提取
  ├── 作品列表 → 滚动加载 + 视频 URL 收集
  ├── 视频详情页 → 指标提取 + Top 20 评论
  └── 输出
      ├── data/<timestamp>-douyin-account.json   ← 结构化原始数据
      └── data/<timestamp>-douyin-report.md     ← 分析报告
```

## 数据流

1. 用户运行 `python3 scripts/scrape_douyin.py --url <主页URL>`
2. Playwright 启动非 headless Chromium，打开抖音首页
3. 等待用户扫码登录（超时 120s），登录成功后保存 storage state
4. 导航到主页 URL，提取账号数据
5. 在作品 Tab 下滚动加载视频列表，收集所有视频 URL
6. 逐个打开视频详情页，提取播放/点赞/评论/分享/时长/标签
7. 在详情页加载并提取 Top 20 条评论（含评论点赞数）
8. 每抓完一个视频立即追加写入 JSON（断点可恢复）
9. 全部抓完后生成 Markdown 分析报告

## 反爬策略

- 真实 Chromium 浏览器，不做 headless（避免被识别）
- 模拟真人操作速度：滚动间隔 1-2s，视频间间隔 2-3s
- 不并发请求，单线程顺序抓取
- 遇到验证码：打印提示，等待用户手动处理后继续
- 已登录 session 保存到文件，再次运行可跳过登录

## 断点续抓

- 每抓完一个视频立即 `flush` 写入 JSON 文件
- 脚本启动时检测已有 JSON 文件，跳过已抓取的 video_id
- 中断后重跑自动从断点继续

## 分析报告结构

1. **账号概览** — 昵称、ID、粉丝、获赞、关注、作品数一览
2. **基础健康度** — 赞粉比、平均互动率、更新频率估算
3. **视频表现排名** — 按播放/点赞/评论/分享分别 Top 10
4. **内容特征分析** — 热门标签、发布时间分布、视频时长分布
5. **评论洞察** — 高频词统计、情感倾向简析
6. **趋势观察** — 近期 10 条 vs 早期 10 条视频表现均值对比

## 依赖

- **新增**: `playwright` — 浏览器自动化（需 `pip install playwright && playwright install chromium`）

## 与 content_db 的关系

本脚本独立运行，产出纯 JSON/Markdown。后续可通过适配层将 JSON 数据导入 `content_db.py` frontmatter 格式与 `archive_content.py` 对接，但本脚本不做硬耦合。

## 作用域限定

- 只抓取抖音 Web 端公开可见数据
- Top 20 热评（不做全量评论翻页）
- 视频总数上限由主页展示决定（通常全部作品）
- 不做直播数据、橱窗商品数据
