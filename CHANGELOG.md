# Changelog

本项目的所有重要变更都记录在此文件。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [2.1.0] - 2026-10-25

主题配置聚焦与视频封面版本。

### Added

- **视频封面截取**：上传视频后使用 ffmpeg 尝试从 1 秒处截取一帧（失败时回退首帧）作为缩略图；未找到系统 ffmpeg 时自动使用 `imageio-ffmpeg` 自带二进制，仍失败则保留视频占位图标。
- **主题示例封面**：为基础与导航两套主题补充 `preview.png` 示例截图，后台主题卡片直接展示。
- **内置预设下载**：后台主题卡片支持下载每套主题的内置预设 CSS；新增管理接口 `GET /api/admin/theme-settings/{theme}/presets/{preset}/download`。
- **视频封面展示**：前台与后台图片列表在视频存在封面时展示封面帧，并保留「视频」标识；前台详情播放器使用该封面作为 `poster`。

### Changed

- **主题配置仅针对当前启用主题**：管理端「主题配置」标签不再提供主题切换，只展示当前启用主题的预设与导航统计；预设/配置写接口对非启用主题返回 400。
- **主题版本与静态资源版本参数**升级为 2.1.0。
- `requirements.txt` 新增 `imageio-ffmpeg`，用于没有系统 ffmpeg 的环境。

### Upgrade Notes

- 升级后请执行 `python -m pip install -r requirements.txt` 安装 `imageio-ffmpeg`。
- 系统已安装 ffmpeg 时优先使用系统版本；容器镜像会自动使用 `imageio-ffmpeg` 内置二进制。
- 视频封面仅在成功截帧时生成，历史视频不会自动补封面。
- 主题配置现在需要先启用对应主题才能修改。

## [2.0.1] - 2026-10-25

安全加固与健壮性版本：修复代码审查发现的全部可证实问题，并补上配置/迁移的防御性处理。

### Added

- **自动生成签名密钥**：未配置 `SECRET_KEY`（或仍为示例值）时，启动会生成随机密钥并持久化到 `data/.secret_key`，避免使用公开默认密钥；启动日志会提示。
- **随机初始管理员密码**：`ADMIN_PASSWORD` 留空或为弱口令时，首次建库会生成随机密码并在控制台打印一次（不写入数据库/通知）；已有管理员仍使用弱密码时启动会告警。
- **请求体大小限制**：新增 `MAX_REQUEST_BODY_SIZE`（默认 512 MB），在解析 multipart 之前按 `Content-Length` 快速拒绝，并在流式读取时兜底返回 413。
- **公开导出限制**：新增 `PUBLIC_EXPORT_MAX_ITEMS`（默认 100）与按 IP 的导出限流（默认 60 秒 10 次）。
- **OAuth 一次性登录码**：新增 `POST /api/auth/oauth/exchange`，登录成功后先签发一次性 code，再由前端换取令牌，JWT 不再出现在跳转 URL。
- **回收站服务端过滤**：`GET /api/admin/images` 新增 `deleted_only=1`，回收站不再拉取全部图片后在浏览器筛选。

### Changed

- **OAuth state 绑定 Cookie**：授权跳转时写入 HttpOnly `il_oauth_state` Cookie，回调需与服务端 state 一致，防止登录 CSRF/账号固定。
- **媒体不再 GZip 压缩**：`/media`、`/thumbnails`、`*/download` 与带 `Range` 的请求跳过压缩，修复 `206` 响应丢失 `Content-Length`、与 `Content-Range` 冲突的问题。
- **分类数量与统计口径统一**：`/api/folders` 对加密分类返回 `image_count=null`；`/api/tags`、`/api/theme/nav-stats` 均排除加密分类，避免泄露受保护内容规模。
- **删除加密分类需强制确认**：`DELETE /api/admin/folders/{id}` 对设置了密码的分类默认返回 400，必须显式 `force=true`；后台确认框同步提示图片将公开。
- **站点自检不再清空配置**：启动自检只告警，站点地址仅能在后台手动清除；探测禁止跟随重定向。
- **媒体缓存**：公开/私有媒体 `Cache-Control` 由 300 秒调整为 60 秒，降低内容移入加密分类后的短期缓存风险。
- **后台静态资源**：后台 HTML/CSS/JS 统一 `no-cache` 协商缓存，并在引用中增加版本参数，避免升级后执行旧脚本。
- **主题页文案**：导航统计开关说明改为「最多 1 分钟内更新」，与 `config.js` 的 60 秒缓存一致。

### Fixed

1. 修复管理员仍可使用默认弱密码、默认 `SECRET_KEY` 可伪造管理员令牌的问题。
2. 修复登录 `redirect` 参数可被 `https:/evil.com`、`/\evil.com`、`javascript:` 绕过的问题，改为同源 URL 校验。
3. 修复 OAuth 登录令牌出现在 URL、前端未校验即落盘导致的会话固定风险。
4. 修复媒体 `Range` 响应被 GZip 破坏的问题。
5. 修复未授权/超大上传请求可打满磁盘的问题（请求体上限）。
6. 修复旧库迁移失败后无法自愈的问题：迁移前清理 `_alembic_tmp_*`、补齐缺失表，`0002` 改为幂等可重试。
7. 修复后台关闭「本地账号登录」后 `/api/user/login`、`/api/user/register` 仍可调用的问题。
8. 修复删除加密分类会让图片静默公开的问题。
9. 修复公开统计/标签泄露加密分类数量与标签的问题。
10. 修复回收站需拉取全部图片、打开缓慢的问题。
11. 修复视频评论在后台评论管理显示破图的问题（`thumb_url` 为空时返回空串）。
12. 修复 `/api/site` 缺少 `upload_max_size` 导致上传页不显示图片大小上限的问题。
13. 修复 IPv6 直连时 `config.js`/分享链接生成非法地址的问题。
14. 修复 `PUT /api/admin/settings` 静默忽略未知字段、`PATCH` 可写入非法 `status` 的问题。
15. 修复修改密码未校验长度、可设置空密码导致管理员永久无法登录的问题。
16. 修复缩略图生成失败写入 0 字节 JPEG、前端显示破图的问题。
17. 修复后台顶栏重复渲染导致 `themechange`/侧边栏监听器累积的问题，以及后台重复请求 `/api/settings` 的问题。
18. 修复上传页点击上传区可能因 click 冒泡递归的问题（补充 `e.target === fileInput` 保护）。
19. 修复上传部分失败后所有文件被清空、无法重试的问题。
20. 修复后台分页缺少页码范围校验、空结果残留统计与全选状态的问题。

### Upgrade Notes

- 升级前请备份 `data/`。
- 若此前未设置 `SECRET_KEY`：升级后会自动生成并写入 `data/.secret_key`，原有登录令牌失效，需要重新登录。
- 若数据库中的管理员仍使用 `admin123` 等弱密码，启动日志会给出告警，请尽快在后台修改。
- 未设置 `ADMIN_PASSWORD` 的全新部署会打印随机初始密码，请从容器日志中获取。

## [2.0.0] - 2026-10-24

### Added

- **Alembic 数据库迁移**：新增 `alembic.ini`、`migrations/` 与基线 revision `0001`，启动时自动执行迁移。
  - 空库直接 `upgrade head`；已有业务表但无 `alembic_version` 的旧库先 `stamp 0001` 再升级，不丢失图片、分类、Token、评论数据。
  - `0002` 增加分类密码字段、`images.uploaded_by` 外键改为 `ON DELETE SET NULL`、新增性能索引、扁平化历史文件夹并切换主题设置键。
  - `0003` 为早于「后台通知」功能创建的旧库补齐 `notifications` 表。
  - Docker 镜像同步包含 `alembic.ini` 与 `migrations/`。
- **一级分类与分类密码**：
  - 分类最多一级，新增 `folders.password_hash` / `folders.auth_version`。
  - 管理端创建/更新分类支持设置、修改、清除密码（bcrypt），接口仅返回 `has_password`。
  - 新增 `POST /api/folders/{id}/unlock`，校验密码并签发限时 `folder_token`；按「IP + 分类」限流（5 分钟 10 次）。
  - 未解锁时分类列表、详情、下载、评论、分享与媒体访问均被拒绝；聚合列表默认排除加密分类内容。
  - 密码变更/清除递增 `auth_version`，旧令牌立即失效。
  - 新增 `GET /api/folders/summary` 返回全部/未分类/分类/加密分类数量。
- **视频支持**：
  - 支持 `mp4`、`m4v`、`mov`、`webm`、`ogv`，按扩展名 + 文件头（`ftyp` / EBML / `OggS`）校验，拒绝伪装文件。
  - 新增 `MAX_VIDEO_UPLOAD_SIZE`（默认 200 MB）；Token 的 `max_file_size` 对图片与视频均生效。
  - 上传改为 1 MB 分块落盘，避免大文件整体读入内存。
  - 视频不生成缩略图、不提取 EXIF；列表使用占位封面与播放标识，详情使用原生播放器。
  - 媒体路由支持单段 `Range`、`206`、`Accept-Ranges`；下载与 ZIP 导出包含视频原文件。
  - 响应新增 `is_video` / `media_type`，站点信息返回视频上限与允许格式。
- **受控媒体路由**：新增 `backend/app/media_service.py` 与 `routers/media.py`。
  - 公开、审核中、已拒绝、回收站、加密分类与后台预览分别按状态、分类令牌与后台签名令牌授权。
  - 后台列表为每项附带短时 `media_token`（URL 参数 `access`，默认 30 分钟）。
  - 新增 `MEDIA_TOKEN_EXPIRE_MINUTES`、`FOLDER_TOKEN_EXPIRE_MINUTES` 配置。
  - 媒体响应带 ETag、`Last-Modified`、`Cache-Control` 与 `Accept-Ranges`，未授权统一 404。
- **主题重构（基础 / 导航）**：
  - 前台改为 `frontend/themes/base/` 与 `frontend/themes/nav/` 两套完全自包含主题（HTML/CSS/JS/assets）。
  - 新增 `theme_settings_service.py` 与 `routers/theme_settings.py`，设置键改为 `active_theme`、`theme_config`、`theme_presets`。
  - 主题预设存放于 `data/theme-presets/<theme_id>/<preset_id>.css`，支持上传、移除、设为默认；每个主题至少保留一个。
  - 新增公开接口 `GET /api/theme`、`GET /api/theme/nav-stats`、`GET /api/theme/preview/{theme_id}`。
  - 新增管理接口 `GET /api/admin/theme-settings`、`PUT /api/admin/theme-settings/active`、预设上传/删除/设为默认与主题配置更新。
  - 后台「主题设置」改为「主题 / 主题配置」双标签；导航主题支持首页统计开关。
  - 前台预设通过 `/presets/{id}.css` 加载，`localStorage` 键为 `il_preset_base` / `il_preset_nav`。
- **导航主题首页**：展示统计面板、全部/未分类/分类入口（含数量与锁定标识）以及全部公开图片网格。
- **可信代理配置**：新增 `TRUSTED_PROXIES`（IP/CIDR，逗号分隔），仅当直连来源可信时才采信 `X-Forwarded-For` / `X-Forwarded-Proto`。
- **性能优化**：
  - 启用 GZip（大于 500 字节的 JSON/HTML/CSS/JS）。
  - 新增 `images.folder_id`、`images.thumb_name`、`images(status,is_deleted,created_at)`、`comments(image_id,status)` 索引。
  - 图片/评论列表使用关联预加载，减少 N+1 查询。
  - 前台 `config.js` 注入主题配置并使用短缓存；HTML 为 `no-cache`，主题资源长缓存；页面脚本使用 `defer`，导航链接支持悬停/聚焦预取。
  - 媒体支持 ETag/304 与 Range，避免重复传输。

### Changed

- **分类体系改为一级分类**：管理端不再接受 `parent_id`，公开分类接口返回扁平列表；删除分类后图片归为未分类。
- **分类页与筛选**：前后台移除嵌套树与「包含子文件夹」开关，改为「全部 / 未分类 / 各分类」。
- **公开序列化**：不再返回 `original_name`；新增 `folder_locked`；后台序列化附带 `media_token`。
- **前台详情页**：不显示原始文件名，无标题时显示「未命名图片」；视频使用播放器；加密分类未解锁时提示并引导解锁。
- **上传页**：管理员上传页与凭证上传页均支持图片/视频选择、格式与大小上限提示。
- **站点设置**：
  - `GET/PUT /api/admin/settings` 统一过滤敏感键，避免 OAuth 密钥明文回传。
  - `PUT /api/admin/settings` 仅保留 `site_name`；主题配置迁移至主题设置接口。
  - `SiteUpdate` 移除 `api_base_url`、`frontend_base_url`、`admin_api_base_url`；站点地址只能通过 `POST /api/admin/site/address`（管理员账号密码二次校验 + 前端探测）写入。
  - 后台站点设置页移除地址输入框与 robots/sitemap 的硬编码初始链接。
- **评论管理**：管理端评论列表返回按站点配置解析的 `frontend_url`，图片链接不再硬编码 `127.0.0.1:8000`。
- **写入校验**：图片编辑、批量移动等写入路径校验目标分类存在，不存在时返回 400/404，不再触发外键 500；上传时若分类不存在则归为未分类。
- **静态服务**：前台按 `active_theme` 动态调度主题目录（3 秒缓存，切换后立即失效）；新增预设 CSS、动态 `config.js` 与缓存头；媒体不再由 StaticFiles 直出。
- **Docker**：镜像包含 Alembic 文件，数据目录新增 `theme-presets/`；`data/themes/` 不再加载。
- **文档**：README 与 CHANGELOG 同步 2.0.0 的迁移、媒体访问、视频、主题、分类密码与可信代理说明。

### Fixed

1. 修复管理端设置接口明文返回 `github_client_secret`、`oauth2_client_secret` 等敏感键的问题（统一敏感键过滤，登录配置仅返回 `*_set` / `*_masked`）。
2. 修复删除已被图片引用的上传 Token 返回 500 的问题（先置空 `images.uploaded_by`，外键改为 `ON DELETE SET NULL`）。
3. 修复导出 ZIP 的路径穿越风险（条目名安全化、去重、长度限制与空名回退）。
4. 修复审核中/已拒绝/回收站图片可通过 `/media`、`/thumbnails` 直连的问题（改为受控媒体路由与签名令牌）。
5. 修复站点地址可绕过「二次密码验证 + 探测」通过通用站点设置写入的问题（仅保留 `/api/admin/site/address`）。
6. 修复无条件信任 `X-Forwarded-For` 的问题（仅在可信代理下解析，并从右向左取首个非可信地址；协议头同样受限）。
7. 修复后台评论管理图片链接硬编码 `127.0.0.1:8000` 的问题（后端返回 `frontend_url`）。
8. 修复设置不存在的 `folder_id` 触发 500 的问题（图片编辑、批量移动返回 400/404；上传时将不存在的分类归为未分类）。
9. 修复升级后后台「主题设置」页因浏览器缓存旧版 `themes.js` 而报 `Cannot read properties of null (reading 'addEventListener')` 的问题：后台 HTML/CSS/JS 统一使用协商缓存，静态资源引用增加版本参数。

### Removed

- 移除前台旧 6 套 CSS 主题（明亮 / 暗夜 / 海洋 / 森林 / 日落 / 樱花）与自定义 ZIP 主题包的上传/下载/删除/设为默认能力。
- 移除 `backend/app/themes.py`、`backend/app/theme_service.py`、`backend/app/routers/themes.py`。
- 移除 `/api/themes/{id}/css`、`/api/themes/{id}/preview`、`/api/admin/themes*` 等旧主题接口。
- 移除设置键 `default_theme`、`enabled_themes` 与 `/api/settings` 中的主题字段。
- 移除多级文件夹与 `include_subfolders` 参数，以及前端/后台的层级分类 UI。
- 移除 `/media`、`/thumbnails` 的 StaticFiles 挂载。
- 移除 `SiteUpdate` 中的三个站点地址字段。

### Breaking Changes

- **必须执行数据库迁移**：升级前请备份 `data/`；迁移会扁平化历史多级分类（重名自动追加后缀）、重建 `images` 表并删除旧主题设置键，旧层级不可恢复。
- **旧主题失效**：旧 6 套前台主题、ZIP 自定义主题与相关设置不再生效；`data/themes/` 文件保留但不会被加载，需改用 `base` / `nav` 与预设。
- **媒体直链行为变化**：审核中、已拒绝、回收站与加密分类内容不再能通过原始 `/media`、`/thumbnails` URL 直接访问，需要 `access` 或 `folder_token`；未授权返回 404。
- **API 变更**：移除旧主题接口与 `enabled_themes` / `default_theme` / `include_subfolders`；站点地址写入统一为 `/api/admin/site/address`；公开图片响应不再包含 `original_name`。
- **分类访问**：加密分类的列表、详情、下载、评论、分享与媒体均需有效 `folder_token`；密码变更后旧令牌立即失效。

## [1.3.0] - 2026-10-03

### Added

- **后台通知界面**（后台「系统 → 后台通知」）：集中记录服务日志，支持按级别（信息/警告/错误）、分类、关键词与「仅看未读」筛选，可标记已读、批量删除、清空已读或全部（含统计卡片与未读高亮）。记录范围：
  - 服务启动（含版本号与时间）；
  - 站点地址检测与变更（后台设置变更、启动自检结果）；
  - 服务端错误（HTTP 500 未捕获异常，含请求方法与路径、来源 IP）；
  - 管理员登录成功/失败（失败含来源 IP）；
  - 用户关键访问：图片详情浏览、普通用户登录成功/失败。
- **启动时自动检测站点地址可用性**（默认开启，可在「站点设置 → 通知与日志」关闭）：采用「折中」策略——仅**明确失败**时清空并回退自动推断（连上了但响应异常、连接被拒绝/端口不通），**不确定**情况（域名解析失败、超时、网络不可达）只写告警、不清空；结果记录到后台通知。检测在后台线程执行，不阻塞服务启动。
- **清空站点地址命令**：`python run.py clear-site-address`（Docker：`docker compose exec <服务名> python run.py clear-site-address`），可在后台无法访问时于服务器终端直接清空 API / 后台专属 / 前台三项站点地址，并写入一条通知。
- 新增设置项 `site_check_on_startup`、`visit_log_enabled`（均默认 `true`），可在后台「站点设置 → 通知与日志」中调整。
- 新增管理端接口：`GET /api/admin/notifications`、`/meta`、`/summary`，`POST /read`、`/delete`、`/clear`。
- 新增接口 `POST /api/admin/site/address` 的变更日志（站点地址变更写入后台通知）。

## [1.2.1] - 2026-10-03

### Added

- **站点地址专用设置流程**：后台「站点设置 → 站点地址」的三项地址改为只读，统一通过「设置站点地址」按钮弹窗修改。
  - 弹窗内可选择设置目标（API 站点地址 / 后台专属 API 地址 / 前台站点地址，可多选）。
  - 需输入管理员账户与密码，后端二次校验，避免误操作。
  - 保存前先用当前浏览器探测新地址：API 类地址请求 `/api/health`（同时验证连通性与跨域），前台地址仅探测可达性；**探测失败即取消保存、不改动原配置**。
  - 新增「清除站点地址」按钮：一键清除三项并恢复自动推断（同样需要账号密码）。
- 新增接口 `POST /api/admin/site/address`（设置/清除站点地址，需管理员账号密码二次校验）。

### Changed

- 站点地址不再随「保存设置」主表单提交，避免误改导致后台失联；主表单仅保留普通站点设置字段。

## [1.2.0] - 2026-10-03

### Added

- **上传进度展示**：后台上传与前台凭证上传均使用 `XMLHttpRequest` 上报进度，界面显示实时进度条（百分比 + 已上传/总字节），传输完成后提示「服务器处理中…」，失败时保留进度并显示原因。
- **后台专属 API 站点地址**（`admin_api_base_url`）：后台「站点设置 → 站点地址」可单独配置，留空则与普通 API 站点地址相同；用于后台本地/内网直连上传，绕过域名与反向代理。

### Changed

- 后台静态站点的 `js/config.js` 改为使用「后台专属 API 地址」（未配置时回退普通地址），前台不受影响。
- `create_static_app()` 新增 `admin_config` 参数以区分前台与后台的 API 地址解析来源。

## [1.1.1] - 2026-10-03

### Fixed

- **修复跨域（CORS）导致前台请求 API 全部失败**：反向代理到标准 80/443 时 `Origin` 头不带端口（如 `https://gallery.example.com`），原有的「主机:端口」正则无法匹配，浏览器拦截所有 API 请求；现默认放行任意 `http/https` 来源（含带端口与不带端口）。
- 修复登录页在 `/api/auth/providers` 请求失败时误显示「暂无可用登录方式」的问题：改为展示可诊断的失败原因，并保留账号密码表单。

### Added

- 新增配置项 `CORS_ALLOW_ALL_ORIGINS`（默认 `true`）：设为 `false` 时仅放行 `CORS_ORIGINS` 中显式列出的来源。

## [1.1.0] - 2026-10-03

### Added

- 后台「站点设置」新增**站点地址**配置：可分别设置 API 站点地址与前台站点地址（留空则自动推断）。
- 新增应用版本号（`backend/app/version.py`），并通过接口暴露：`GET /api/health`、`GET /api/settings`、`GET /api/site` 均返回 `version`；后台侧边栏底部显示版本号。
- 新增本 `CHANGELOG.md`。

### Changed

- 前端 `js/config.js`、OAuth 回调地址、分享链接、`sitemap.xml` 与 OAuth 登录回跳地址，统一按「后台配置 → `PUBLIC_HOST` → 访问者主机名 → 配置文件默认值」解析。

## [1.0.0] - 2026-10-03

### Added

- FastAPI 后端：图片上传与缩略图、多级分类文件夹、标签、审核队列、回收站（软删除/还原/彻底删除）、分享链接、批量导出 ZIP、EXIF 提取。
- 上传 Token 与凭证上传（默认进入待审核），凭证上传按 IP 限流。
- 原生 HTML/CSS/JS 前台公开站点与管理后台（独立端口），Notion 风格界面，6 套可切换主题。
- 主题管理：ZIP 主题包上传 / 下载 / 删除 / 设为默认 / 启用禁用，自定义主题可在前台动态加载。
- 站点设置：站点名称、SEO 元信息、favicon、robots.txt、sitemap.xml、评论开关、页脚文案。
- 普通用户账号体系（开放注册 / 登录），图片评论（需登录）与后台评论管理、用户管理。
- 登录配置：本地账号 / GitHub OAuth / 通用 OAuth2，可在后台开关与配置。
- 一键启动三服务（`run.py`）与 Docker 部署（`Dockerfile`、`docker-compose.yml`）。
- GitHub Actions 自动构建 amd64/arm64 镜像并推送到 GHCR；`docker-compose.deploy.yml` 支持服务器零构建部署。

[Unreleased]: https://github.com/BUXIN-A/ImageLibrary/compare/v2.1.0...HEAD
[2.1.0]: https://github.com/BUXIN-A/ImageLibrary/compare/v2.0.1...v2.1.0
[2.0.1]: https://github.com/BUXIN-A/ImageLibrary/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/BUXIN-A/ImageLibrary/compare/v1.3.0...v2.0.0
[1.3.0]: https://github.com/BUXIN-A/ImageLibrary/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/BUXIN-A/ImageLibrary/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/BUXIN-A/ImageLibrary/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/BUXIN-A/ImageLibrary/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/BUXIN-A/ImageLibrary/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/BUXIN-A/ImageLibrary/releases/tag/v1.0.0
