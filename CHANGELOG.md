# Changelog

本项目的所有重要变更都记录在此文件。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

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

[Unreleased]: https://github.com/BUXIN-A/ImageLibrary/compare/v1.2.1...HEAD
[1.2.1]: https://github.com/BUXIN-A/ImageLibrary/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/BUXIN-A/ImageLibrary/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/BUXIN-A/ImageLibrary/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/BUXIN-A/ImageLibrary/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/BUXIN-A/ImageLibrary/releases/tag/v1.0.0
