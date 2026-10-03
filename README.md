# ImageLibrary 公开图库系统

> 当前版本：**v1.1.1** ｜ 变更记录见 [CHANGELOG.md](CHANGELOG.md)

一个可公开访问的图片图库系统：**访客无需登录**即可浏览、搜索、查看详情、下载与批量导出图片；**管理员**通过独立端口的后台完成上传与维护；**普通用户**可自行注册登录，参与图片评论；**他人**还可凭管理员发放的「上传 Token」上传图片，经审核通过后公开。前后端分离，前台与后台各自独立端口，图片按多级分类文件夹组织，并提供多套可自定义的主题（内置 + 自定义 ZIP 主题包）。

---

## 一、项目简介

- **访客（免登录）**：浏览缩略图网格、按关键词/文件夹/标签搜索筛选、查看图片详情（含 EXIF）、下载原图、多选打包导出 ZIP。
- **普通用户**：在前台注册 / 登录（账号密码或 GitHub / 通用 OAuth2），登录后可在图片详情页发表评论；无权限进入后台。
- **管理员后台**：登录、仪表盘统计、上传（支持多文件/拖拽）、图库管理（编辑/移动/打标签/批量操作）、审核队列、文件夹管理、标签管理、上传 Token 管理、回收站（软删除/还原/彻底删除）、站点设置、主题管理、用户管理、评论管理、登录配置。
- **他人凭证上传**：在前台 `upload.html` 输入管理员发放的上传 Token，即可上传图片；上传内容默认进入待审核（`pending`）状态，不出现在公开列表，需管理员审核通过后才公开。

---

## 二、功能特性

- **多级分类文件夹**：可嵌套的树形文件夹（物化路径实现），每张图片归属一个文件夹（可空=未分类）；移动/删除文件夹时自动维护子节点与图片归属。
- **标签系统**：图片与标签多对多，前台可按标签筛选。
- **上传 Token 与凭证上传**：管理员可创建多个 Token（备注、有效期、最大上传次数、单文件大小上限、启用/禁用、重新生成），他人凭 Token 上传。
- **审核队列**：单张或批量「通过 / 拒绝」（拒绝可填原因），凭证上传默认待审核。
- **回收站（软删除）**：删除进入回收站，支持还原与彻底删除（同时清理磁盘文件）。
- **分享链接**：为图片生成唯一分享 token，得到公开的前台分享地址。
- **EXIF 展示**：上传时用 Pillow 提取拍摄时间、相机厂商/型号、镜头、ISO、光圈、快门、焦距、方向等（**不含 GPS**），详情页展示；缩略图按 EXIF 方向自动纠正。
- **批量导出 ZIP**：前台与后台均可将所选图片打包下载。
- **主题系统**：内置 6 套主题（明亮 / 暗夜 / 海洋 / 森林 / 日落 / 樱花），并支持上传 **ZIP 自定义主题包**（导入 / 下载 / 删除 / 设为默认 / 启用禁用）；前台可切换并本地记忆。
- **Notion 风格界面**：前台与后台均采用接近 Notion 的简洁排版与配色（近黑正文、浅灰底、细边框、克制阴影）。
- **站点设置**：后台可维护站点名称、SEO（标题/描述/关键词/OG）、favicon、robots、sitemap、评论开关与页脚文案，前台动态生效。
- **用户与社区**：普通用户注册/登录（本地账号 + GitHub + 通用 OAuth2）、图片评论（需登录，可在站点设置关闭）、后台用户管理与评论管理。
- **根路径跳转**：API（8080）根路径重定向到交互式文档；前台（8000）根路径进入首页；后台（8001）根路径按登录状态进入仪表盘或登录页。
- **限流**：凭证上传按客户端 IP 做进程内滑动窗口限流。
- **公开浏览 / 搜索 / 下载**：无需登录，仅展示 `approved` 且未删除的图片。

---

## 三、技术栈

- **后端**：Python 3.13、FastAPI、Uvicorn、SQLAlchemy 2.x、Pydantic / pydantic-settings、SQLite、Pillow、PyJWT、bcrypt。
- **前端**：原生 HTML / CSS / JavaScript **多页应用**，无任何构建工具。
- **存储**：本地文件系统（原图、缩略图、自定义主题、favicon）+ SQLite（元数据）。图片文件扁平存储于 `data/uploads/`，文件夹为逻辑结构（移动图片不移动文件）。

---

## 四、目录结构

```text
ImageLibrary/
├── backend/
│   └── app/
│       ├── main.py              # FastAPI 应用装配（CORS、根路径重定向、静态媒体挂载、路由注册、启动初始化）
│       ├── config.py            # 全局配置（路径、端口、密钥、管理员、上传限制、限流、前台/API 对外地址）
│       ├── database.py          # SQLAlchemy 引擎与会话
│       ├── models.py            # ORM 模型（admins / folders / images / tags / image_tags / upload_tokens / settings / users / comments）
│       ├── schemas.py           # Pydantic 请求/响应模型
│       ├── security.py          # 密码哈希 + JWT + Token 生成
│       ├── deps.py              # 管理员认证依赖、普通用户认证依赖、上传 Token 校验、客户端 IP 提取
│       ├── images_service.py    # 保存/缩略图/EXIF/文件清理
│       ├── ratelimit.py         # 进程内滑动窗口限流
│       ├── export_service.py    # 打包 ZIP
│       ├── theme_service.py     # 自定义主题：枚举、ZIP 导入/导出/删除、路径解析
│       ├── oauth_service.py     # OAuth：授权 URL 构建、code 换令牌、用户资料拉取与字段映射、state 管理
│       ├── static_server.py     # 通用静态站点 ASGI 应用工厂（前台可挂载 robots/sitemap/favicon 动态路由）
│       ├── seed.py              # 初始化默认管理员与默认设置（含站点/登录配置默认值）
│       ├── themes.py            # 预设主题常量（6 套）
│       └── routers/             # API 路由
│           ├── auth.py          # 管理员登录 / 当前管理员 / 修改密码
│           ├── oauth.py         # 登录方式查询、GitHub/通用 OAuth2 授权跳转与回调
│           ├── user.py          # 普通用户注册 / 登录 / 当前用户
│           ├── images.py        # 公开图片：列表/详情/下载/分享/导出
│           ├── comments.py      # 图片评论（公开查看/发表 + 管理端评论管理）
│           ├── folders.py       # 文件夹（公开树 + 管理端增删改）
│           ├── tags.py          # 标签（公开列表 + 管理端增删）
│           ├── tokens.py        # 上传 Token 管理（管理员）
│           ├── review.py        # 审核队列（管理员）
│           ├── settings.py      # 站点设置（公开读取 + 管理端读写）
│           ├── site.py          # 站点信息/图标（公开）+ 管理端站点设置与图标上传
│           ├── themes.py        # 主题 CSS/预览（公开）+ 管理端主题导入/下载/删除/设为默认
│           ├── login_settings.py# 登录配置（管理员：本地/GitHub/通用 OAuth2）
│           ├── admin_users.py   # 用户管理（管理员：列表/启禁用/删除/重置密码）
│           ├── stats.py         # 仪表盘统计（管理员）
│           ├── admin_images.py  # 后台图片管理（上传/批量/导出/回收站/分享）
│           └── credential.py    # 凭证上传（含限流）
├── frontend/                    # 前台公开站点（端口 8000）
│   ├── index.html  image.html  search.html  folder.html  upload.html  share.html  login.html
│   ├── css/                     # base.css / components.css / layout.css
│   ├── js/
│   │   ├── api.js  config.js  layout.js  theme.js  ui.js  user.js
│   │   └── pages/               # index.js / image.js / search.js / folder.js / upload.js / share.js / login.js
│   ├── themes/                  # light.css / dark.css / ocean.css / forest.css / sunset.css / sakura.css
│   └── assets/
├── admin/                       # 管理后台站点（端口 8001）
│   ├── index.html  login.html  dashboard.html  upload.html  images.html  review.html
│   ├── folders.html  tags.html  tokens.html  recycle.html  settings.html
│   ├── site-settings.html  themes.html  users.html  comments.html  login-settings.html
│   ├── css/                     # base.css / components.css / layout.css
│   ├── js/
│   │   ├── api.js  auth.js  config.js  layout.js  theme.js  ui.js
│   │   └── pages/               # dashboard.js / upload.js / images.js / review.js / folders.js / tags.js / tokens.js / recycle.js / settings.js
│   │                            # + site-settings.js / themes.js / users.js / comments.js / login-settings.js
│   ├── themes/                  # 与前台同名的 6 套主题
│   └── assets/
├── data/                        # 运行时生成（已被 .gitignore 忽略）
│   ├── app.db                   # SQLite 数据库
│   ├── uploads/                 # 原图
│   ├── thumbnails/              # 缩略图（JPEG）
│   ├── themes/                  # 自定义主题：themes/<id>/{theme.json,theme.css[,preview.png]}
│   └── favicon.*                # 上传的站点图标（如 favicon.png）
├── run.py                       # 一键启动三服务
├── requirements.txt             # Python 依赖
└── README.md
```

---

## 五、环境要求

- **Python 3.13**（本项目在 3.13 下开发）。
- Windows / macOS / Linux 均可运行。
- 本机（Windows）可直接使用解释器路径：`E:\environment\python\python313\python.exe`。

---

## 六、安装步骤

1. 安装依赖（在项目根目录执行）：

   ```powershell
   python -m pip install -r requirements.txt
   ```

   若 `python` 未加入环境变量，可用指定解释器路径：

   ```powershell
   E:\environment\python\python313\python.exe -m pip install -r requirements.txt
   ```

2. （可选）如需覆盖默认配置，在项目根目录新建 `.env` 文件（见下方「配置说明」）。无需手动建库，首次启动会自动创建数据表、默认管理员与默认设置。

---

## 七、配置说明

配置定义于 `backend/app/config.py`，使用 `pydantic-settings`，可通过**同名环境变量**或项目根目录的 **`.env` 文件**覆盖默认值（环境变量名与字段名一致，大小写不敏感）。

| 配置项 | 环境变量 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `BASE_DIR` | `BASE_DIR` | 项目根目录 | 项目根路径（自动推导） |
| `DATA_DIR` | `DATA_DIR` | `<根>/data` | 数据目录 |
| `UPLOAD_DIR` | `UPLOAD_DIR` | `<根>/data/uploads` | 原图存储目录 |
| `THUMBNAIL_DIR` | `THUMBNAIL_DIR` | `<根>/data/thumbnails` | 缩略图存储目录 |
| `DB_PATH` | `DB_PATH` | `<根>/data/app.db` | SQLite 数据库文件 |
| `HOST` | `HOST` | `127.0.0.1` | 三服务监听地址 |
| `API_PORT` | `API_PORT` | `8080` | API 端口 |
| `FRONTEND_PORT` | `FRONTEND_PORT` | `8000` | 前台站点端口 |
| `ADMIN_PORT` | `ADMIN_PORT` | `8001` | 管理后台端口 |
| `SECRET_KEY` | `SECRET_KEY` | `change-me-please-in-production` | JWT 签名密钥，**生产环境必须修改** |
| `JWT_ALGORITHM` | `JWT_ALGORITHM` | `HS256` | JWT 算法 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | 登录令牌有效期（分钟，默认 1 天） |
| `ADMIN_USERNAME` | `ADMIN_USERNAME` | `admin` | 默认管理员用户名（默认仅首次建库时写入，见 `ADMIN_FORCE_SYNC`） |
| `ADMIN_PASSWORD` | `ADMIN_PASSWORD` | `admin123` | 默认管理员密码（默认仅首次建库时写入，见 `ADMIN_FORCE_SYNC`） |
| `ADMIN_FORCE_SYNC` | `ADMIN_FORCE_SYNC` | `false` | 为 `true` 时每次启动都用上面的账号密码覆盖已有管理员 |
| `MAX_UPLOAD_SIZE` | `MAX_UPLOAD_SIZE` | `20971520`（20 MB） | 单文件最大字节数 |
| `ALLOWED_EXTENSIONS` | `ALLOWED_EXTENSIONS` | `{.jpg, .jpeg, .png, .gif, .webp, .bmp}` | 允许的上传扩展名 |
| `ALLOWED_MIME_TYPES` | `ALLOWED_MIME_TYPES` | `image/jpeg, image/png, image/gif, image/webp, image/bmp` | 允许的真实 MIME 类型 |
| `THUMBNAIL_SIZE` | `THUMBNAIL_SIZE` | `420` | 缩略图最长边像素 |
| `RATE_LIMIT_MAX_REQUESTS` | `RATE_LIMIT_MAX_REQUESTS` | `20` | 凭证上传限流：窗口内最大请求数 |
| `RATE_LIMIT_WINDOW_SECONDS` | `RATE_LIMIT_WINDOW_SECONDS` | `60` | 凭证上传限流：窗口秒数 |
| `FRONTEND_BASE_URL` | `FRONTEND_BASE_URL` | `http://127.0.0.1:8000` | 生成分享链接、sitemap、OAuth 回跳使用的前台地址 |
| `API_BASE_URL` | `API_BASE_URL` | `http://127.0.0.1:8080` | API 对外地址，用于生成 OAuth 回调地址 |
| `PUBLIC_HOST` | `PUBLIC_HOST` | 空 | **远程部署时填写服务器 IP 或域名**；设置后分享链接、OAuth 回调、前端 API 地址与 CORS 均以它为准 |
| `PUBLIC_SCHEME` | `PUBLIC_SCHEME` | `http` | 对外协议（使用 HTTPS 反向代理时设为 `https`） |
| `CORS_ORIGINS` | `CORS_ORIGINS` | 空 | 额外允许的跨域来源，逗号分隔（如 `https://gallery.example.com`） |
| `CORS_ALLOW_ALL_ORIGINS` | `CORS_ALLOW_ALL_ORIGINS` | `true` | 是否放行任意来源跨域；设为 `false` 时仅放行 `CORS_ORIGINS` 中列出的来源 |

> 说明：
> - `ADMIN_USERNAME` / `ADMIN_PASSWORD` 默认只在 **数据库首次初始化**（admins 表为空）时生效；若希望每次启动都用环境变量覆盖已有管理员，设置 `ADMIN_FORCE_SYNC=true`。
> - CORS 默认**放行任意来源**（`CORS_ALLOW_ALL_ORIGINS=true`），以兼容反向代理到 80/443、`Origin` 不带端口的场景；鉴权使用 Authorization 头（Bearer）而非 Cookie，放宽来源不会造成越权。如需严格限制，设置 `CORS_ALLOW_ALL_ORIGINS=false` 并用 `CORS_ORIGINS` 列出允许来源。
> - 前端 `js/config.js` 由后端**动态生成**：未设置 `PUBLIC_HOST` 时按访问者所用主机名自动推断 API 地址，因此以服务器 IP/域名访问无需改动任何前端文件。
> - **站点级配置**（站点名称、SEO、favicon、robots、sitemap、页脚、评论开关）与**登录配置**（本地 / GitHub / 通用 OAuth2）存储于数据库 `settings` 表，可在后台页面维护，**无需改 `.env`**；`seed.py` 在首次建库时写入其默认值。
> - 修改了 API 端口时，请同步更新 `API_BASE_URL`（OAuth 回调地址由它生成），回调地址必须与第三方平台中登记的地址完全一致。

---

## 八、启动与访问

一键启动三个服务（前台/后台静态站运行于守护线程，API 运行于主线程，`Ctrl+C` 可整体退出）：

```powershell
python run.py
# 或
E:\environment\python\python313\python.exe run.py
```

| 服务 | 地址 | 根路径行为 |
| --- | --- | --- |
| 前台公开站点 | http://127.0.0.1:8000 | `/` 直接返回首页 `index.html` |
| 管理后台 | http://127.0.0.1:8001 | `/` 为跳转页：已登录 → `dashboard.html`，未登录 → `login.html` |
| API | http://127.0.0.1:8080 | `/` 302 重定向到 `/docs` |
| API 文档（Swagger UI） | http://127.0.0.1:8080/docs | — |
| 健康检查 | http://127.0.0.1:8080/api/health | — |

启动后终端会打印三服务的访问地址横幅。静态媒体通过 API 暴露：`/media/*`（原图）、`/thumbnails/*`（缩略图）。

**前台动态站点文件**（仅前台 8000 端口注册，由 `static_server.py` 提供）：

- `GET /robots.txt`：根据站点设置的 `allow_index` 与 `robots_extra` 动态生成；关闭 `allow_index` 时输出 `Disallow: /`。
- `GET /sitemap.xml`：首页 + 文件夹 + 已公开未删除图片（`sitemap_enabled` 关闭时返回 404）。
- `GET /favicon.ico`：返回已上传的站点图标；未设置或文件缺失返回 404，外链则 302 重定向。

> 后台（8001）不注册上述路由，站点图标与站点信息仍通过 API `/api/favicon`、`/api/site` 提供。

---

## 九、默认管理员账号

- 用户名：`admin`
- 密码：`admin123`

> ⚠️ **首次使用后请务必修改密码**。两种方式：
> 1. 登录后台 → **设置**页 → 修改密码（校验原密码后更新）；
> 2. 或在首次启动前通过环境变量 `.env` 设置 `ADMIN_USERNAME` / `ADMIN_PASSWORD`（仅在数据库首次初始化时写入）。
>
> 同时建议在生产环境中修改 `SECRET_KEY`。

---

## 十、使用说明

### 管理员（后台 http://127.0.0.1:8001）

1. **登录**：访问后台登录页，使用管理员账号登录（令牌保存在浏览器 localStorage，键名 `il_admin_token`）。
2. **仪表盘**：查看图片总数、待审核数、文件夹数、标签数、回收站数量、Token 数、总浏览量、总下载量。
3. **上传**：选择或多文件拖拽上传，填写标题/描述/文件夹/标签；上传后状态直接为 `approved`，并自动生成缩略图与提取 EXIF。
4. **图库管理**（`images.html`）：按关键词/文件夹/标签/状态筛选与排序，编辑信息、批量删除/移动/打标签/审核、批量导出 ZIP、生成分享链接。
5. **审核**（`review.html`）：处理凭证上传的待审图片，单张或批量「通过 / 拒绝」。
6. **文件夹 / 标签**：创建多级文件夹、调整层级；创建/删除标签。
7. **上传 Token**（`tokens.html`）：创建、启用/禁用、编辑、重新生成、删除 Token，并查看已用次数与剩余额度。
8. **回收站**（`recycle.html`）：还原或彻底删除图片。
9. **站点设置 / 主题 / 用户 / 评论 / 登录配置**：见下方「站点设置」「主题管理」「用户与社区」「登录配置（OAuth）」章节。
10. **设置**（`settings.html`）：站点名称、默认主题、启用主题列表，以及修改管理员密码。

### 访客（前台 http://127.0.0.1:8000）

- **浏览**：首页缩略图网格，支持排序（最新 / 最热 / 名称）。
- **搜索 / 筛选**：按关键词（标题、描述、文件名）、文件夹（可含子文件夹）、标签筛选。
- **详情**：点击图片查看大图、标题、描述、尺寸、标签、所属文件夹与 EXIF，并可下载原图、查看/发表评论。
- **批量导出**：多选图片后一键打包为 ZIP 下载。

### 他人上传（凭 Token）

1. 打开前台上传页 `upload.html`。
2. 输入管理员发放的 Token 并点击「校验」，确认有效性与剩余额度。
3. 选择图片（支持多文件）后上传；上传成功即进入待审核队列，提示「已提交，等待管理员审核」。

---

## 十一、用户与社区

### 前台注册 / 登录（`frontend/login.html`）

- 页面同时提供「登录」「注册」两个标签页，注册字段：用户名（3–32 位）、密码（≥6 位）、邮箱（可选，需唯一）。
- 登录支持三种方式，实际可选项由后台「登录配置」与 `/api/auth/providers` 决定：
  - **账号密码**（本地）：`POST /api/user/login`；
  - **GitHub**：跳转 `GET /api/auth/github/authorize`，第三方授权后回调；
  - **自定义 OAuth2**：跳转 `GET /api/auth/oauth2/authorize`，第三方授权后回调。
- 登录成功后用户令牌保存在 localStorage（键名 `il_user_token`，见 `frontend/js/user.js`），页头用户区显示头像/昵称与「退出」。
- 页头用户区未登录时显示「登录 / 注册」入口。

### 图片评论

- 图片详情页可查看评论列表（`GET /api/images/{id}/comments`，公开、仅显示可见评论）。
- **发表评论需登录**（普通用户令牌）：`POST /api/images/{id}/comments`，内容去空格后非空且不超过 1000 字，评论默认 `visible`。
- 站点设置中的 `comments_enabled` 为 `false` 时，发表评论返回 403「评论功能已关闭」（前台相应隐藏评论输入）。

### 后台管理

- **用户管理**（`users.html` → `/api/admin/users`）：按关键词/来源（`local` / `github` / `oauth2`）/启用状态筛选；启用/禁用用户、删除用户、重置密码。
- **评论管理**（`comments.html` → `/api/admin/comments`）：按关键词/图片/状态筛选；单条隐藏/恢复/删除，或批量 `delete` / `hide` / `show`。

---

## 十二、站点设置

后台「站点设置」页（`site-settings.html`）对应接口 `GET`/`PUT /api/admin/site`，favicon 上传 `POST /api/admin/site/favicon`。字段与前台生效位置如下：

| 字段 | 含义 | 前台生效位置 |
| --- | --- | --- |
| `site_name` | 站点名称 | 页头品牌名、页脚默认文案、`og:site_name` |
| `site_title` | 站点标题 | `<title>`（页面原题追加 `｜站点标题`）与 `og:title` |
| `site_description` | 站点描述 | `<meta name="description">`、`og:description` |
| `site_keywords` | 关键词 | `<meta name="keywords">`（逗号分隔） |
| `favicon` | 站点图标 | `<link rel="icon">`（指向 `/api/favicon`），并影响 `/favicon.ico` |
| `allow_index` | 是否允许搜索引擎抓取 | `GET /robots.txt`（关闭时 `Disallow: /`） |
| `robots_extra` | robots 附加内容（管理端字段） | 追加到 `/robots.txt` 正文 |
| `sitemap_enabled` | 是否启用站点地图 | `GET /sitemap.xml`（关闭时 404） |
| `comments_enabled` | 评论开关 | 前台评论输入显隐；关闭后发表评论返回 403 |
| `footer_text` | 页脚文案 | 页脚文本（留空则用 `© 年份 站点名称`） |
| `api_base_url` | API 站点地址（**后台可配置**，留空自动） | 前端 `js/config.js` 的 `API_BASE`、OAuth 回调地址、登录回调基址 |
| `frontend_base_url` | 前台站点地址（**后台可配置**，留空自动） | 分享链接、`/sitemap.xml`、OAuth 登录回跳 |

- 前台页面加载时通过 `GET /api/site` 拉取上述信息并注入（见 `frontend/js/layout.js`），失败静默降级，不阻断页面渲染。
- **站点地址解析优先级**：后台配置值 → `PUBLIC_HOST` 环境变量 → 访问者使用的主机名 → 配置文件默认值（`API_BASE_URL` / `FRONTEND_BASE_URL`）。
  因此以服务器 IP 或域名直连时通常**无需任何配置**；如需固定为特定域名（例如经反向代理后），在后台填写即可。修改后请刷新页面。
- favicon 上传限制：单文件 ≤ 2 MB，且必须是可识别的图片（`.ico/.png/.jpg/.jpeg/.gif/.webp/.bmp`，其它扩展名统一按 `.png` 保存），文件写入 `data/favicon.*`。

---

## 十三、主题管理

### 内置主题（6 套）

`light`（明亮）、`dark`（暗夜）、`ocean`（海洋）、`forest`（森林）、`sunset`（日落）、`sakura`（樱花）。CSS 文件位于 `frontend/themes/*.css` 与 `admin/themes/*.css`（前台、后台各一套，同名对应），常量定义于 `backend/app/themes.py` 的 `PRESET_THEMES`。

- 每套主题以选择器 `:root[data-theme="<id>"]` 声明一组 CSS 变量。
- 切换机制：页面通过改写 `<html data-theme="…">` 即时应用对应主题；用户选择写入 `localStorage`（前台键名 `il_theme`，后台键名 `il_admin_theme`），刷新后保持。
- **内置主题的 CSS 变量清单（共 17 个）**：

  ```css
  :root[data-theme="mytheme"] {
    --color-bg: #fbfbfa;
    --color-surface: #ffffff;
    --color-surface-2: #f1f1ef;
    --color-text: #37352f;
    --color-text-muted: #787774;
    --color-primary: #2383e2;
    --color-primary-contrast: #ffffff;
    --color-border: rgba(55, 53, 47, 0.09);
    --color-danger: #eb5757;
    --color-success: #0f7b6c;
    --color-warning: #cb912f;
    --shadow-sm: 0 1px 2px rgba(15, 15, 15, 0.04);
    --shadow-md: 0 4px 14px rgba(15, 15, 15, 0.1);
    --radius-sm: 4px;
    --radius-md: 6px;
    --radius-lg: 10px;
    --font-sans: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;
  }
  ```

### 自定义主题（ZIP 主题包）

后台「主题管理」页（`themes.html`）用于上传/下载/删除/设为默认/启用禁用主题。

**ZIP 主题包格式**（扁平结构，包内不允许出现目录，仅允许以下文件）：

| 文件 | 必需 | 说明 |
| --- | --- | --- |
| `theme.json` | ✅ | 主题元信息（UTF-8 JSON 对象） |
| `theme.css` | ✅ | 主题样式，**必须包含** `:root[data-theme="<id>"]` 变量块（即含子串 `[data-theme="<id>"]`） |
| `preview.png` | ❌ | 可选预览图 |

`theme.json` 字段：

| 字段 | 必需 | 说明 |
| --- | --- | --- |
| `id` | ✅ | 主题 id，必须匹配 `^[a-z0-9_-]{2,32}$`（2–32 位小写字母/数字/下划线/连字符），且不得与内置主题冲突、不得与已存在自定义主题重复 |
| `name` | ✅ | 主题显示名称 |
| `author` | ❌ | 作者 |
| `version` | ❌ | 版本 |
| `description` | ❌ | 描述 |

`theme.json` 示例：

```json
{
  "id": "mytheme",
  "name": "我的主题",
  "author": "me",
  "version": "1.0.0",
  "description": "示例自定义主题"
}
```

> 上传校验：ZIP 解压后总大小 ≤ 5 MB；解析失败的 ZIP、缺少 `theme.json`/`theme.css`、`id`/`name` 缺失或 `id` 非法、`theme.css` 未包含对应 `[data-theme="<id>"]` 选择器等均返回 400 与中文原因。

**操作路径**：

| 操作 | 接口 |
| --- | --- |
| 列出全部主题（内置+自定义） | `GET /api/admin/themes` |
| 上传（导入）主题 ZIP | `POST /api/admin/themes`（表单字段 `file`） |
| 下载主题 ZIP | `GET /api/admin/themes/{id}/download` |
| 删除自定义主题（内置不可删） | `DELETE /api/admin/themes/{id}` |
| 设为默认（并自动加入启用列表） | `POST /api/admin/themes/{id}/set-default` |
| 启用 / 禁用主题 | `PUT /api/admin/settings`（提交 `enabled_themes` 列表） |

**存储与加载**：自定义主题解压后存放在 `data/themes/<id>/`（含 `theme.json`、`theme.css`，可选 `preview.png`）。前台通过 `GET /api/themes/{id}/css` 动态加载自定义主题样式（`frontend/js/theme.js` 会为 custom 来源主题注入指向该接口的 `<link>`），预览图通过 `GET /api/themes/{id}/preview` 获取。

**新增内置主题步骤**（如需扩展内置集）：

1. 在 `frontend/themes/` 与 `admin/themes/` 各新增一份 CSS 文件（如 `neon.css`），复用上表 17 个变量，选择器使用 `:root[data-theme="neon"]`。
2. 在前台/后台各 HTML 页面中引入该主题的 `<link rel="stylesheet">`。
3. 在 `backend/app/themes.py` 的 `PRESET_THEMES` 中登记主题 `{ "id": "neon", "name": "霓虹" }`。
4. 在前端 `theme.js` 的 `ALL_THEMES` 中同步登记（作为接口不可用时的回退列表）。
5. 登录后台「主题管理」将新主题加入启用列表，并可设为默认。

---

## 十四、登录配置（OAuth）

后台「登录配置」页（`login-settings.html`）对应接口 `GET` / `PUT /api/admin/login-settings`。**密钥字段（`github_client_secret`、`oauth2_client_secret`）不会回传明文**：读取时仅返回 `*_set`（是否已设置）与 `*_masked`（`****`）；更新时字段缺失或为 `null` 表示不修改，空字符串表示清空，非空表示更新。未启用的方式不会出现在前台登录页（`GET /api/auth/providers` 返回其 `enabled=false`）。

### 本地登录

- `login_local_enabled`（默认 `true`）：控制前台是否显示账号密码登录/注册表单。

### GitHub 登录

1. 在 GitHub 创建 OAuth App，将 **Authorization callback URL** 设为：
   `http://127.0.0.1:8080/api/auth/github/callback`
   （由 `API_BASE_URL` + `/api/auth/github/callback` 生成，改了 API 地址请同步调整）
2. 在后台「登录配置」填写 `github_client_id`、`github_client_secret`，并开启 `login_github_enabled`。
3. 授权范围固定为 `read:user user:email`；启用后前台登录页出现「GitHub」入口。

### 通用 OAuth2 登录

1. 在后台「登录配置」填写以下字段并开启 `login_oauth2_enabled`：

   | 字段 | 说明 |
   | --- | --- |
   | `oauth2_client_id` / `oauth2_client_secret` | 客户端凭据 |
   | `oauth2_authorize_url` | 授权地址 |
   | `oauth2_token_url` | 换取令牌地址 |
   | `oauth2_userinfo_url` | 用户信息地址 |
   | `oauth2_scope` | 授权范围（默认 `openid profile email`） |
   | `oauth2_user_id_field` | 用户唯一标识字段（默认 `sub`） |
   | `oauth2_username_field` | 用户名字段（默认 `preferred_username`） |
   | `oauth2_nickname_field` | 昵称字段（默认 `name`） |
   | `oauth2_email_field` | 邮箱字段（默认 `email`） |
   | `oauth2_avatar_field` | 头像字段（默认 `picture`） |

2. 在第三方平台登记回调地址为：
   `http://127.0.0.1:8080/api/auth/oauth2/callback`
   （由 `API_BASE_URL` + `/api/auth/oauth2/callback` 生成）

> 第三方用户首次登录会自动创建本地 `users` 记录（`provider` 为 `github` / `oauth2`；用户名冲突时自动加后缀，邮箱冲突时置空）；已禁用用户登录会被拒绝。

---

## 十五、数据与备份

- `data/app.db`：SQLite 数据库，保存管理员、普通用户、图片元数据、文件夹、标签、评论、上传 Token、站点设置与登录配置等。
- `data/uploads/`：原图文件（文件名为 uuid，安全化处理）。
- `data/thumbnails/`：缩略图文件（JPEG，命名形如 `<原图名>_thumb.jpg`）。
- `data/themes/`：自定义主题目录（`themes/<id>/`）。
- `data/favicon.*`：上传的站点图标。

> **备份建议**：备份时请**同时**复制 `data/app.db` 与 `data/uploads/`、`data/thumbnails/`、`data/themes/`、`data/favicon.*`（数据库记录与磁盘文件需保持一致）。建议在停止服务后备份以保证一致性。整个 `data/` 目录已被 `.gitignore` 忽略，不会被提交到版本库。

---

## 十六、API 概览

API 基础地址：`http://127.0.0.1:8080`。除特别标注外均为公开接口，无需认证。

- `/api/admin/*` 管理接口需要请求头 `Authorization: Bearer <JWT>`，且令牌必须为**管理员**令牌（`role=admin`；普通用户令牌会被拒绝）。
- 少数前台接口需要**普通用户**令牌（`role=user`），单独标注。

### 公开接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查 |
| GET | `/api/site` | 公开站点信息（站名/SEO/favicon/开关/页脚等） |
| GET | `/api/favicon` | 站点图标（外链 302 / 本地文件返回 / 未设置 404） |
| POST | `/api/auth/login` | 管理员登录，返回 JWT |
| GET | `/api/auth/providers` | 可用登录方式及启用状态（local / github / oauth2） |
| GET | `/api/auth/github/authorize` | 跳转 GitHub 授权 |
| GET | `/api/auth/github/callback` | GitHub 授权回调（登录成功回跳前台登录页） |
| GET | `/api/auth/oauth2/authorize` | 跳转自定义 OAuth2 授权 |
| GET | `/api/auth/oauth2/callback` | 自定义 OAuth2 授权回调 |
| POST | `/api/user/register` | 普通用户注册（用户名 3–32 位，密码 ≥6 位，邮箱可选），返回用户令牌 |
| POST | `/api/user/login` | 普通用户登录，返回用户令牌 |
| GET | `/api/user/me` | 当前用户信息（**需用户令牌**） |
| GET | `/api/images` | 图片列表（`page` / `page_size` / `q` / `folder_id` / `tag` / `sort` / `include_subfolders`） |
| GET | `/api/images/{id}` | 图片详情（浏览量 +1） |
| GET | `/api/images/{id}/download` | 下载原图（下载量 +1） |
| GET | `/api/images/{id}/comments` | 公开评论列表（分页，仅 `visible`） |
| POST | `/api/images/{id}/comments` | 发表评论（**需用户令牌**；`comments_enabled` 关闭时 403） |
| POST | `/api/images/export` | 按 id 列表批量导出 ZIP |
| GET | `/api/share/{token}` | 通过分享 token 获取图片详情 |
| GET | `/api/folders` | 文件夹树（含图片数） |
| GET | `/api/tags` | 标签列表（含图片数） |
| GET | `/api/settings` | 公开站点设置（站名、默认/启用主题、主题列表、上传大小上限、前台地址、SEO/开关/页脚） |
| GET | `/api/themes/{id}/css` | 主题 CSS（内置或自定义，`text/css`） |
| GET | `/api/themes/{id}/preview` | 主题预览图（存在时） |
| GET | `/api/credential/validate` | 校验上传 Token 并返回剩余额度 |
| POST | `/api/credential/upload` | 凭证上传（表单字段 `token` + `files`，状态 `pending`，含 IP 限流） |
| GET | `/media/*`、`/thumbnails/*` | 原图 / 缩略图静态文件 |

### 管理接口（需 Bearer admin JWT）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/auth/me` | 当前管理员信息 |
| POST | `/api/auth/change-password` | 修改密码 |
| GET | `/api/admin/stats` | 仪表盘统计 |
| GET | `/api/admin/images` | 后台图片列表（支持状态、回收站等筛选） |
| POST | `/api/admin/images` | 管理员上传（状态 `approved`） |
| POST | `/api/admin/images/batch` | 批量操作：`delete` / `restore` / `purge` / `move` / `tag` / `approve` / `reject` |
| POST | `/api/admin/images/export` | 导出 ZIP（按 id 或按筛选条件） |
| PATCH | `/api/admin/images/{id}` | 编辑图片（标题/描述/文件夹/状态/标签） |
| DELETE | `/api/admin/images/{id}` | 软删除（移入回收站） |
| DELETE | `/api/admin/images/{id}/purge` | 彻底删除（含磁盘文件） |
| POST | `/api/admin/images/{id}/restore` | 从回收站还原 |
| POST | `/api/admin/images/{id}/share` | 生成分享 token 与链接 |
| GET | `/api/admin/review` | 待审核列表 |
| POST | `/api/admin/review/batch` | 批量审核（`approve` / `reject`） |
| POST | `/api/admin/review/{id}/approve` | 通过审核 |
| POST | `/api/admin/review/{id}/reject` | 拒绝审核（可附原因） |
| POST | `/api/admin/folders` | 新建文件夹 |
| PATCH | `/api/admin/folders/{id}` | 更新文件夹（重命名/移动/排序） |
| DELETE | `/api/admin/folders/{id}` | 删除文件夹 |
| POST | `/api/admin/tags` | 新建标签 |
| DELETE | `/api/admin/tags/{id}` | 删除标签 |
| GET | `/api/admin/tokens` | 上传 Token 列表 |
| POST | `/api/admin/tokens` | 创建 Token |
| PATCH | `/api/admin/tokens/{id}` | 更新 Token |
| DELETE | `/api/admin/tokens/{id}` | 删除 Token |
| POST | `/api/admin/tokens/{id}/regenerate` | 重新生成 Token 值 |
| GET | `/api/admin/settings` | 读取全部设置 |
| PUT | `/api/admin/settings` | 更新站点设置（`site_name` / `default_theme` / `enabled_themes`） |
| GET | `/api/admin/site` | 读取完整站点设置（含 `robots_extra`） |
| PUT | `/api/admin/site` | 更新站点设置（SEO/favicon/开关/页脚等） |
| POST | `/api/admin/site/favicon` | 上传站点图标（表单字段 `file`） |
| GET | `/api/admin/themes` | 主题列表（内置 + 自定义） |
| POST | `/api/admin/themes` | 上传自定义主题 ZIP（表单字段 `file`） |
| GET | `/api/admin/themes/{id}/download` | 下载主题 ZIP |
| DELETE | `/api/admin/themes/{id}` | 删除自定义主题 |
| POST | `/api/admin/themes/{id}/set-default` | 设为默认主题 |
| GET | `/api/admin/users` | 用户列表（`q` / `provider` / `enabled` 筛选） |
| PATCH | `/api/admin/users/{id}` | 启用/禁用用户 |
| DELETE | `/api/admin/users/{id}` | 删除用户（其评论级联删除） |
| POST | `/api/admin/users/{id}/reset-password` | 重置用户密码 |
| GET | `/api/admin/comments` | 评论列表（`q` / `image_id` / `status` 筛选） |
| PATCH | `/api/admin/comments/{id}` | 更新评论状态（`visible` / `hidden`） |
| DELETE | `/api/admin/comments/{id}` | 删除评论 |
| POST | `/api/admin/comments/batch` | 批量评论操作（`delete` / `hide` / `show`） |
| GET | `/api/admin/login-settings` | 读取登录配置（密钥脱敏） |
| PUT | `/api/admin/login-settings` | 更新登录配置 |

> 列表接口统一支持 `page` 与 `page_size`（后台默认 `page_size=20` 或 `24`，上限 100 / 200）。

---

## 十七、常见问题

**Q1：端口被占用（8000 / 8001 / 8080）怎么办？**
在项目根目录 `.env` 中修改 `FRONTEND_PORT`、`ADMIN_PORT`、`API_PORT`（以及 `FRONTEND_BASE_URL`、`API_BASE_URL` 保持一致），然后重启。若端口冲突，启动时会在对应服务处报错。

**Q2：前台/后台请求 API 报 CORS 错误？**
CORS 默认**放行任意 http/https 来源**（含不带端口的标准 80/443 域名，如 `https://gallery.buxin.us.kg`），反向代理场景无需额外配置。若需收紧，设置 `CORS_ALLOW_ALL_ORIGINS=false` 并用 `CORS_ORIGINS` 显式列出允许来源（逗号分隔，需带协议，非标准端口需带端口）。

**Q3：上传时返回 429 / 「上传过于频繁，请稍后再试」？**
触发了凭证上传的 IP 限流（默认 60 秒内最多 20 次）。等待窗口结束后重试，或调整 `RATE_LIMIT_MAX_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS`。

**Q4：图片不显示（缩略图/原图为空白或 404）？**
`js/config.js` 由后端**动态生成**（可直接访问 `/js/config.js` 查看实际 `API_BASE`）：未设置 `PUBLIC_HOST` 时会按访问主机名自动推断 API 端口，通常无需手工配置。若经反向代理导致无法推断，请设置 `PUBLIC_HOST`（或 `API_BASE_URL`）。

**Q5：上传提示「不支持的图片格式」或「文件过大」？**
仅接受 jpg/jpeg/png/gif/webp/bmp，且单文件默认不超过 20 MB。可通过 `MAX_UPLOAD_SIZE`（及 Token 的 `max_file_size`）与 `ALLOWED_EXTENSIONS` 调整。

**Q6：修改了 `.env` 里的管理员账号密码但没生效？**
`ADMIN_USERNAME` / `ADMIN_PASSWORD` 默认仅在数据库首次初始化时写入。若要每次启动都强制同步为环境变量的值，设置 `ADMIN_FORCE_SYNC=true`；也可登录后台「账号与安全」页修改密码，或删除 `data/app.db` 后重启（注意会丢失数据）。

**Q7：改端口后分享链接打不开？**
分享链接基于 `FRONTEND_BASE_URL` 生成，修改前台端口时请同步更新该配置。

**Q8：OAuth（GitHub / 自定义 OAuth2）登录跳转报错「redirect_uri mismatch」或回跳失败？**
回调地址由 API 对外地址生成（优先 `PUBLIC_HOST`，否则 `API_BASE_URL`），必须与第三方平台登记的回调地址**完全一致**（GitHub 为 `http://<对外地址>:<API端口>/api/auth/github/callback`，通用 OAuth2 为 `.../api/auth/oauth2/callback`）。远程部署时设置 `PUBLIC_HOST=服务器IP或域名` 即可自动使用该地址。

**Q9：上传了自定义主题但前台看不到 / 不生效？**
确认该主题已加入**启用列表** `enabled_themes`（后台「主题管理」页可启用/禁用），否则前台主题选择器中不会出现；如需默认应用还需设为默认主题。若已启用仍无样式，检查 `data/themes/<id>/theme.css` 是否包含 `:root[data-theme="<id>"]` 变量块。

**Q10：评论框不显示或提示「评论功能已关闭」？**
发表评论需要登录普通用户账号；且站点设置 `comments_enabled` 为 `false` 时会关闭评论（返回 403）。请在后台「站点设置」中开启评论开关，并确认已登录。

**Q11：上传/更换 favicon 后浏览器仍显示旧图标？**
favicon 会被浏览器强缓存，请**强制刷新**（Ctrl+F5）或清除缓存后再查看。图标文件写入 `data/favicon.*`，可通过 `GET /api/favicon` 验证是否已生效。

---

## 十八、Docker 部署（Linux 服务器）

镜像内**单容器**同时运行 API、前台与管理后台三个服务。仓库已配置 GitHub Actions：推送到 `main` 后会自动构建**多架构**镜像并推送到 **GHCR**（`ghcr.io/buxin-a/imagelibrary:latest`），因此服务器**无需源码、无需构建**即可部署。

相关文件：`Dockerfile`、`docker-compose.yml`（本地构建）、`docker-compose.deploy.yml`（服务器拉取镜像）、`.env.example`、`.github/workflows/docker-publish.yml`。

假设服务器 IP 为 `192.168.1.10`，默认访问地址：

| 服务 | 地址 |
| --- | --- |
| 前台公开站点 | http://192.168.1.10:8000 |
| 管理后台 | http://192.168.1.10:8001 |
| API 文档 | http://192.168.1.10:8080/docs |
| 健康检查 | http://192.168.1.10:8080/api/health |

### 1. 方式 A：拉取 GHCR 镜像部署（推荐，服务器零构建）

**首次准备（只需一次）**：Actions 首次成功推送后，镜像包默认是**私有**的，需改为公开，否则服务器拉取会报 401：

> GitHub → 你的头像 → **Packages** → `imagelibrary` → 右侧 **Package settings** → 底部 **Danger Zone** → **Change visibility** → **Public**

**服务器上执行**：

```bash
mkdir -p /opt/imagelibrary && cd /opt/imagelibrary

# 仅需两个文件（也可 git clone 整个仓库）
curl -fsSLO https://raw.githubusercontent.com/BUXIN-A/ImageLibrary/main/docker-compose.deploy.yml
curl -fsSL  https://raw.githubusercontent.com/BUXIN-A/ImageLibrary/main/.env.example -o .env

# 编辑 .env：至少修改 SECRET_KEY、ADMIN_PASSWORD、PUBLIC_HOST（填服务器 IP 或域名）
vi .env

# 拉取镜像并启动
docker compose -f docker-compose.deploy.yml pull
docker compose -f docker-compose.deploy.yml up -d
```

> 若不想把镜像设为公开，可先在服务器登录 GHCR（PAT 需 `read:packages` 权限）：
> ```bash
> echo <你的PAT> | docker login ghcr.io -u BUXIN-A --password-stdin
> ```

**更新到最新版本**：

```bash
cd /opt/imagelibrary
docker compose -f docker-compose.deploy.yml pull
docker compose -f docker-compose.deploy.yml up -d
```

> 每次 `git push` 到 `main` 后，Actions 会重新构建并覆盖 `latest`；服务器执行上面两条命令即可升级，`./data` 中的数据不受影响。

> 也可以完全不改环境变量：启动后在后台 **站点设置 → 站点地址** 中填写「API 站点地址」与「前台站点地址」，效果等同设置 `PUBLIC_HOST`（优先级更高，便于随时调整）。

### 2. 方式 B：在服务器上本地构建

适合无法访问 `ghcr.io` 或需要自行改代码的情况：

```bash
git clone https://github.com/BUXIN-A/ImageLibrary.git
cd ImageLibrary
cp .env.example .env    # 按需修改
docker compose up -d --build
```

更新：`git pull && docker compose up -d --build`。

### 3. 通过环境变量配置

把 `.env.example` 复制为 `.env`（与 compose 文件同目录，Compose 会自动读取）后按需修改：

```dotenv
# 端口：同时决定容器内监听端口与宿主机映射端口
API_PORT=8080
FRONTEND_PORT=8000
ADMIN_PORT=8001

# 管理员账号（默认仅首次初始化数据库时写入）
ADMIN_USERNAME=admin
ADMIN_PASSWORD=请改成强密码
# 改为 true 则每次启动都用上面的账号密码强制覆盖已有管理员
ADMIN_FORCE_SYNC=false

# JWT 签名密钥（务必修改为随机长字符串）
SECRET_KEY=请改成随机长字符串

# 对外访问主机：填服务器 IP 或域名（影响分享链接、OAuth 回调与 CORS）
PUBLIC_HOST=192.168.1.10
PUBLIC_SCHEME=http
# 额外允许的跨域来源（逗号分隔，一般无需设置）
CORS_ORIGINS=

# 可选
MAX_UPLOAD_SIZE=20971520
RATE_LIMIT_MAX_REQUESTS=20
RATE_LIMIT_WINDOW_SECONDS=60
TZ=Asia/Shanghai
```

保存后重新执行部署命令即可生效（方式 A：`docker compose -f docker-compose.deploy.yml up -d`；方式 B：`docker compose up -d`）。

也可不改文件，直接命令行传参（以方式 A 为例）：

```bash
API_PORT=9080 FRONTEND_PORT=9000 ADMIN_PORT=9001 \
PUBLIC_HOST=192.168.1.10 SECRET_KEY=your-secret \
ADMIN_USERNAME=admin ADMIN_PASSWORD=strong-password \
docker compose -f docker-compose.deploy.yml up -d
```

### 4. 不用 Compose（直接 docker run）

直接使用 GHCR 镜像（无需克隆源码）：

```bash
docker run -d --name imagelibrary --restart unless-stopped \
  -p 8080:8080 -p 8000:8000 -p 8001:8001 \
  -e HOST=0.0.0.0 \
  -e API_PORT=8080 -e FRONTEND_PORT=8000 -e ADMIN_PORT=8001 \
  -e PUBLIC_HOST=192.168.1.10 \
  -e SECRET_KEY=your-secret \
  -e ADMIN_USERNAME=admin -e ADMIN_PASSWORD=strong-password \
  -v /opt/imagelibrary/data:/app/data \
  ghcr.io/buxin-a/imagelibrary:latest
```

> 更新：`docker pull ghcr.io/buxin-a/imagelibrary:latest`，再 `docker rm -f imagelibrary` 重新 `run`（推荐直接用 Compose 管理）。
> 端口必须一一对应：容器内监听端口由 `API_PORT/FRONTEND_PORT/ADMIN_PORT` 决定，`-p` 映射须保持一致（如 `-p 9080:9080`）。

### 5. 数据持久化与备份

容器内全部数据位于 `/app/data`：数据库 `app.db`、原图 `uploads/`、缩略图 `thumbnails/`、自定义主题 `themes/`、`favicon.*`。**务必挂载该目录**，否则容器重建将丢失数据：

```bash
-v /opt/imagelibrary/data:/app/data
```

Compose 默认挂载项目下的 `./data`。备份时直接打包该目录即可。

### 6. 常用运维命令

方式 A（拉取镜像）把下面的 `docker compose` 换成 `docker compose -f docker-compose.deploy.yml`：

```bash
docker compose -f docker-compose.deploy.yml ps       # 查看状态（含 health）
docker compose -f docker-compose.deploy.yml logs -f  # 查看日志
docker compose -f docker-compose.deploy.yml restart  # 重启
docker compose -f docker-compose.deploy.yml down     # 停止并移除容器（./data 保留）
docker compose -f docker-compose.deploy.yml pull     # 拉取最新镜像
docker compose -f docker-compose.deploy.yml up -d    # 应用更新

# 方式 B（本地构建）
docker compose up -d --build
```

容器内置健康检查（请求 `/api/health`），`docker compose ps` 会显示 `healthy`。

### 7. HTTPS / 反向代理

推荐在前端加 Nginx / Caddy / Traefik 提供 HTTPS。此时：

- 设置 `PUBLIC_HOST=你的域名`、`PUBLIC_SCHEME=https`；
- 把站点来源加入 `CORS_ORIGINS`（例如 `https://gallery.example.com`）；
- 反向代理需将 `/api`、`/media`、`/thumbnails` 转发到 API 端口，前台与后台分别转发到各自端口（建议用子域区分，如 `gallery.example.com` 与 `admin.example.com`）。

> 开启 HTTPS 后 OAuth 回调地址会变为 `https://你的域名/api/auth/<provider>/callback`，请同步更新第三方平台登记的回调地址。
