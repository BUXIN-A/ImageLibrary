<div align="center">

<h1>ImageLibrary</h1>

[![Docker Publish](https://github.com/BUXIN-A/ImageLibrary/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/BUXIN-A/ImageLibrary/actions/workflows/docker-publish.yml)
[![Version](https://img.shields.io/badge/version-2.1.0-blue)](https://github.com/BUXIN-A/ImageLibrary/blob/main/CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**面向公开访问的图片与视频图库：访客免登录浏览，管理员使用独立后台管理；支持一级分类、分类密码、受控媒体、两套前台主题、上传 Token 审核与 Docker 部署。**

<!-- TODO: 添加预览图/GIF，例如 docs/preview.png（前台首页与后台仪表盘），当前仓库暂无截图资源。 -->

</div>

[功能特性](#功能特性) · [快速开始](#快速开始) · [配置](#配置) · [技术栈](#技术栈) · [升级与迁移](#升级与迁移) · [参与贡献](#参与贡献) · [License](#license)

> 前台是免登录的公开图库，后台是独立端口的管理端；两者通过 FastAPI API、SQLite 与本地文件存储协作。访客可浏览、搜索、下载与导出，普通用户可登录评论，管理员负责上传、审核、分类与站点维护。

## 功能特性

| 功能 | 说明 |
| --- | --- |
| 图片 + 视频 | 支持 JPG/PNG/GIF/WebP/BMP 与 MP4/M4V/MOV/WebM/OGV；视频使用原生播放器并支持 HTTP Range 拖动播放，上传时自动截取内容帧作为封面，列表与详情播放器优先展示该封面。 |
| 一级分类 | 分类最多一级，不存在的层级操作已移除；图片可属于一个分类或为「未分类」，删除分类后图片自动归为未分类。 |
| 分类密码 | 可为分类设置、修改、清除访问密码；未解锁时该分类的列表、详情、下载、评论、分享与媒体文件均被服务端拒绝。 |
| 受控媒体 | `/media` 与 `/thumbnails` 由后端按图片状态、分类密码与后台短时签名令牌授权，不再直连静态目录。 |
| 上传 Token | 管理员可创建带备注、有效期、次数与单文件大小限制的 Token；凭证上传默认进入待审核队列。 |
| 审核与回收站 | 单张/批量通过或拒绝；软删除进入回收站，支持还原与彻底删除（同时清理磁盘文件）。 |
| 标签与搜索 | 图片与标签多对多；前台支持关键词、分类、标签筛选与排序。 |
| EXIF | 图片上传时提取拍摄时间、相机、镜头、ISO、光圈、快门、焦距、方向等，不读取 GPS；视频不提取 EXIF。 |
| 分享链接 | 为图片生成唯一分享 token；加密分类的分享链接需先解锁。 |
| 批量导出 | 前台与后台均可将所选内容打包为 ZIP，条目名经过路径穿越安全处理。 |
| 两套前台主题 | `base`（经典图库首页）与 `nav`（导航首页 + 分类入口 + 统计面板）；主题目录自包含 HTML/CSS/JS，切换无需重启，后台提供示例封面。 |
| 主题预设 | 基础主题「明亮/暗夜」、导航主题「亮色/暗色」；仅当前启用主题可配置，支持上传、移除、设为默认与下载内置预设，每个主题至少保留一个预设。 |
| 导航统计 | 导航主题首页可开关展示分类图片数、总图片数、总浏览数、总评论数、总下载数。 |
| 用户与评论 | 普通用户注册/登录（本地账号、GitHub、通用 OAuth2），登录后评论；后台可管理用户与评论。 |
| 站点设置 | 站点名称、SEO、favicon、robots、sitemap、评论开关、页脚与通知开关；站点地址使用独立二次校验流程。 |
| 后台通知 | 记录服务启动、站点地址检测、服务端错误、管理员登录与用户访问，支持筛选、已读、删除。 |
| 性能 | GZip、关联预加载、数据库索引、HTML 不缓存 + 主题资源版本化缓存、媒体 ETag/304、页面悬停/聚焦预取。 |
| 部署 | 一键启动三服务；提供 Dockerfile、Compose 与 GitHub Actions 多架构镜像发布。 |

### 安全与访问控制

- **媒体文件**：公开、审核中、已拒绝、回收站、加密分类与后台预览分别授权；未授权统一返回 404，不泄露文件是否存在。
- **分类令牌**：解锁后签发限时、限分类的 `folder_token`；修改或清除密码会递增 `auth_version`，旧令牌立即失效。
- **密钥保护**：后台设置接口过滤键名包含 `secret` 的配置；OAuth 密钥仅通过登录设置接口的 `*_set` / `*_masked` 字段展示。
- **站点地址**：只允许通过 `POST /api/admin/site/address` 写入，需要管理员账号密码二次校验，并由前端先探测新地址。
- **代理头**：仅当直连来源属于 `TRUSTED_PROXIES` 时才采信 `X-Forwarded-For` / `X-Forwarded-Proto`；默认不信任任何代理。
- **密钥与口令**：未配置 `SECRET_KEY` 时自动生成随机密钥并保存到 `data/.secret_key`；`ADMIN_PASSWORD` 留空或为弱口令时，首次建库会生成随机密码并只在启动日志打印一次。
- **OAuth 安全**：`state` 同时保存在服务端与 HttpOnly Cookie 中，登录成功后用一次性 code 换取令牌（JWT 不出现在 URL）。
- **上传与导出**：单个请求体上限由 `MAX_REQUEST_BODY_SIZE` 控制；公开导出限制单次数量并按 IP 限流。
- **加密分类**：公开分类列表/标签/导航统计默认排除加密分类内容；删除加密分类必须显式 `force=true`（图片会转为未分类并公开）。

## 快速开始

### 环境要求

- Python **3.13**
- 可选：Docker 24+（容器部署）
- 可选：Node.js（仅用于本地 JS 语法检查，不是运行依赖）

### 本地运行

```powershell
git clone https://github.com/BUXIN-A/ImageLibrary.git
cd ImageLibrary
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

macOS / Linux 将激活命令替换为：

```bash
source .venv/bin/activate
```

启动后终端会输出三个服务地址：

```text
API      : http://127.0.0.1:8080
前台站点 : http://127.0.0.1:8000
管理后台 : http://127.0.0.1:8001
```

首次启动会自动执行 Alembic 迁移、创建 SQLite 数据库、管理员与主题预设。

管理员密码规则：

- 在 `.env` 中设置了强密码（`ADMIN_PASSWORD`）时，首次建库直接使用该密码；
- 未设置或使用弱口令（如 `admin123`）时，系统会生成随机密码，并且**只在启动日志打印一次**：

```text
========================================================
 已生成随机管理员密码（仅本次显示，请立即妥善保存）
 用户名：admin
 密码：<随机密码>
========================================================
```

> 首次登录后请立即在后台「账号与安全」中修改密码。未配置 `SECRET_KEY` 时系统会自动生成并保存到 `data/.secret_key`，可在 `.env` 中显式设置固定密钥。

可选：在项目根目录创建 `.env` 覆盖默认配置（见 [配置](#配置)）。无需手动建库，启动时自动迁移。

### Docker 运行

```bash
# 本地构建
docker compose up -d --build

# 或直接拉取 GHCR 镜像（服务器零构建）
docker compose -f docker-compose.deploy.yml pull
docker compose -f docker-compose.deploy.yml up -d
```

默认访问地址仍为前台 `8000`、后台 `8001`、API `8080`。数据持久化在 `./data`，升级或重建容器前请备份。

## 配置

配置定义于 `backend/app/config.py`，可通过同名环境变量或项目根目录 `.env` 覆盖。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `HOST` | `127.0.0.1` | 三个服务的监听地址；Docker 中应设为 `0.0.0.0`。 |
| `API_PORT` | `8080` | API 端口。 |
| `FRONTEND_PORT` | `8000` | 前台公开站点端口。 |
| `ADMIN_PORT` | `8001` | 管理后台端口。 |
| `SECRET_KEY` | 空 | JWT 签名密钥；留空会自动生成随机密钥并保存到 `data/.secret_key`，生产环境建议显式设置 >= 32 字节随机串。 |
| `ADMIN_USERNAME` | `admin` | 默认管理员用户名，仅首次建库时写入。 |
| `ADMIN_PASSWORD` | 空 | 初始管理员密码；留空或弱口令时首次建库自动生成随机密码并打印一次。 |
| `ADMIN_FORCE_SYNC` | `false` | 为 `true` 时每次启动都用环境变量覆盖已有管理员账号密码。 |
| `PUBLIC_HOST` | 空 | 对外访问的服务器 IP 或域名；影响分享链接、OAuth 回调、CORS 与前端 API 地址推断。 |
| `PUBLIC_SCHEME` | `http` | 对外协议；HTTPS 反向代理时设为 `https`。 |

<details>
<summary>高级配置</summary>

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `MAX_UPLOAD_SIZE` | `20971520`（20 MB） | 图片单文件上限（字节）。 |
| `MAX_VIDEO_UPLOAD_SIZE` | `209715200`（200 MB） | 视频单文件上限（字节）。 |
| `MAX_REQUEST_BODY_SIZE` | `536870912`（512 MB） | 单个 HTTP 请求体上限；在解析上传前即拒绝超大请求。 |
| `PUBLIC_EXPORT_MAX_ITEMS` | `100` | 公开批量导出单次最多张数。 |
| `PUBLIC_EXPORT_RATE_MAX` | `10` | 公开导出限流：窗口内最大次数。 |
| `PUBLIC_EXPORT_RATE_WINDOW` | `60` | 公开导出限流窗口秒数。 |
| `MEDIA_TOKEN_EXPIRE_MINUTES` | `30` | 后台媒体预览签名 `media_token` 有效期。 |
| `FOLDER_TOKEN_EXPIRE_MINUTES` | `120` | 分类解锁 `folder_token` 有效期。 |
| `TRUSTED_PROXIES` | 空 | 可信反向代理 IP/CIDR，逗号分隔；例如 `127.0.0.1,10.0.0.0/8`。 |
| `RATE_LIMIT_MAX_REQUESTS` | `20` | 凭证上传限流窗口内最大请求数。 |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | 凭证上传限流窗口秒数。 |
| `CORS_ORIGINS` | 空 | 额外允许的跨域来源，逗号分隔。 |
| `CORS_ALLOW_ALL_ORIGINS` | `true` | 是否放行任意 http/https 来源；鉴权使用 Bearer 头，不依赖 Cookie。 |
| `API_BASE_URL` | `http://127.0.0.1:8080` | API 对外默认地址；未配置 `PUBLIC_HOST` 时用于回调与推断。 |
| `FRONTEND_BASE_URL` | `http://127.0.0.1:8000` | 前台对外默认地址；未配置 `PUBLIC_HOST` 时用于分享链接与 sitemap。 |
| `DATA_DIR` | `<项目>/data` | 数据目录。 |
| `DB_PATH` | `<项目>/data/app.db` | SQLite 数据库文件。 |
| `UPLOAD_DIR` | `<项目>/data/uploads` | 原图/视频存储目录。 |
| `THUMBNAIL_DIR` | `<项目>/data/thumbnails` | 图片缩略图目录。 |

</details>

站点级配置（站点名称、SEO、favicon、robots、sitemap、评论开关、页脚、站点地址）与主题配置存储在数据库 `settings` 表中，通过后台页面维护，无需改 `.env`。

> 反向代理部署时请正确配置 `TRUSTED_PROXIES`，否则所有请求都会按直连地址处理，访问日志 IP 与站点地址推断可能不准确。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.13、FastAPI、Uvicorn、SQLAlchemy 2.x、Pydantic / pydantic-settings、Alembic |
| 数据 | SQLite、本地文件系统（原图/视频、缩略图、主题预设、favicon） |
| 媒体 | Pillow、ffmpeg（imageio-ffmpeg）、HTTP Range、ETag/304 |
| 认证 | PyJWT、bcrypt、GitHub OAuth、通用 OAuth2 |
| 前端 | 原生 HTML / CSS / JavaScript 多页应用，无构建工具；两套自包含主题 |
| 部署 | Docker、Docker Compose、GitHub Actions（amd64/arm64 GHCR 镜像） |

<details>
<summary>目录结构</summary>

```text
ImageLibrary/
├── backend/app/
│   ├── main.py                  # FastAPI 装配、CORS、GZip、路由与启动初始化
│   ├── config.py                # 全局配置
│   ├── database.py              # SQLAlchemy + Alembic 自动迁移入口
│   ├── models.py / schemas.py   # ORM 与请求/响应模型
│   ├── security.py / deps.py    # 密码、JWT、认证依赖、客户端 IP
│   ├── images_service.py        # 图片/视频落盘、校验、缩略图、EXIF
│   ├── media_service.py         # 媒体授权、后台 media_token、分类 folder_token
│   ├── theme_settings_service.py# 主题/预设状态与导航统计
│   ├── static_server.py         # 前台主题调度、动态 config.js/robots/sitemap
│   └── routers/                 # auth/oauth/user/images/media/comments/folders/
│                                # tags/tokens/review/settings/site/theme_settings/...
├── frontend/themes/
│   ├── base/                    # 基础主题（完整 HTML/CSS/JS）
│   └── nav/                     # 导航主题（完整 HTML/CSS/JS）
├── admin/                       # 独立管理后台（HTML/CSS/JS）
├── migrations/                  # Alembic 迁移
├── alembic.ini
├── docker/healthcheck.py
├── Dockerfile
├── docker-compose.yml
├── docker-compose.deploy.yml
├── run.py                       # 一键启动三服务
├── requirements.txt
└── README.md / CHANGELOG.md
```

</details>

<details>
<summary>API 摘要</summary>

| 类型 | 主要接口 |
| --- | --- |
| 公开 | `GET /api/images`、`GET /api/images/{id}`、`GET /api/images/{id}/download`、`GET /api/images/{id}/comments`、`POST /api/images/export` |
| 公开 | `GET /api/folders`、`GET /api/folders/summary`、`POST /api/folders/{id}/unlock`、`GET /api/share/{token}` |
| 公开 | `GET /api/site`、`GET /api/settings`、`GET /api/theme`、`GET /api/theme/nav-stats`、`GET /robots.txt`、`GET /sitemap.xml` |
| 媒体 | `GET /media/{filename}`、`GET /thumbnails/{filename}`（支持 Range、ETag、签名/分类令牌） |
| 用户 | `POST /api/user/register`、`POST /api/user/login`、`GET /api/user/me` |
| 管理 | `GET/POST /api/admin/images`、`POST /api/admin/images/batch`、`POST /api/admin/images/export`、`PATCH/DELETE /api/admin/images/{id}` |
| 管理 | `POST/PATCH/DELETE /api/admin/folders`、`GET /api/admin/review`、`GET/POST /api/admin/tokens` |
| 主题 | `GET /api/admin/theme-settings`、`PUT /api/admin/theme-settings/active`、`POST/DELETE /api/admin/theme-settings/{theme}/presets`、`GET .../presets/{preset}/download` |
| 站点 | `GET/PUT /api/admin/site`、`POST /api/admin/site/address`、`GET/PUT /api/admin/login-settings` |
| 其他 | `GET /api/admin/comments`、`GET /api/admin/users`、`GET /api/admin/stats`、`GET /api/admin/notifications` |

</details>

## 升级与迁移

> **升级（含 2.1.0）前请先备份 `data/` 目录。**

```bash
# 停止服务后备份
cp -r data data.bak
```

启动时会自动执行迁移：

- 空库：直接创建全部表、索引与默认设置。
- 已存在业务表但无 `alembic_version` 的旧库：清理迁移残留并补齐缺失表 → `stamp 0001` → 升级到最新 revision。
- 已有 `alembic_version` 的库：清理 `_alembic_tmp_*` 残留并补齐意外缺失表后升级（迁移可安全重试）。
- `0002`：增加分类密码字段、`images.uploaded_by` 改为 `ON DELETE SET NULL`、新增性能索引、扁平化历史文件夹、切换主题设置键。
- `0003`：为早于「后台通知」功能的旧库补齐 `notifications` 表。

也可手动执行：

```bash
python -m alembic upgrade head
```

2.0.0 的破坏性变化：

- 历史多级文件夹会被扁平化，所有分类提升为顶级，重名自动加后缀。
- 旧 6 套前台 CSS 主题与 ZIP 自定义主题不再加载；`data/themes/` 文件保留但忽略。
- `/media`、`/thumbnails` 改为受控路由；非公开内容需要签名令牌。
- 站点地址不能再通过通用站点设置接口写入，只能走专用地址弹窗流程。

2.1.0 的升级注意：

- 执行 `python -m pip install -r requirements.txt` 安装新增的 `imageio-ffmpeg`；系统已安装 ffmpeg 时优先使用系统版本。
- 视频封面在升级后上传的视频上生效，历史视频不会自动补封面，仍显示视频占位图标。
- 管理端主题配置仅能修改当前启用主题；如需配置另一套主题，请先在「主题」标签中启用它。

2.0.1 的升级注意：

- 未设置 `SECRET_KEY` 的部署会生成 `data/.secret_key`，原有登录令牌失效，需要重新登录。
- 全新部署若未设置 `ADMIN_PASSWORD`，随机初始密码只会在启动日志打印一次，请及时保存。
- 若数据库中的管理员仍使用 `admin123` 等弱密码，启动日志会告警，请尽快在后台修改。

若站点地址填错导致后台无法访问，可在服务器执行：

```bash
python run.py clear-site-address
```

> 若升级后后台页面提示 `Cannot read properties of null (reading 'addEventListener')` 或出现空白，通常是浏览器仍在使用旧版 `admin/js`。当前版本已为后台 HTML/CSS/JS 使用协商缓存并为静态资源增加版本参数；部署后请强制刷新一次（Windows：`Ctrl+F5`），后续升级会自动获取新脚本。

## 参与贡献

1. Fork 本仓库并创建功能分支：

   ```bash
   git checkout -b feature/your-feature
   ```

2. 修改后至少执行：

   ```bash
   python -m compileall backend run.py
   node --check frontend/themes/base/js/pages/index.js   # 可选，需 Node.js
   ```

3. 使用临时数据库验证，避免污染真实数据：

   ```powershell
   $env:DB_PATH="$env:TEMP\il-test.db"
   $env:DATA_DIR="$env:TEMP\il-test-data"
   python run.py
   ```

4. 提交 PR，说明变更目的、影响范围与验证步骤。

请勿提交 `data/`、`.env`、真实密钥或用户上传内容。

## License

本项目采用 [MIT License](LICENSE)。

Copyright (c) 2026 BUXIN
