# syntax=docker/dockerfile:1
# 图库系统镜像：单容器内同时运行 API(8080)、前台站点(8000)、管理后台(8001)
FROM python:3.13-slim

# 运行环境：HOST 必须为 0.0.0.0 才能被容器外访问；端口可用环境变量覆盖
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai \
    HOST=0.0.0.0 \
    API_PORT=8080 \
    FRONTEND_PORT=8000 \
    ADMIN_PORT=8001

# 时区数据（让容器内时间显示正确；不需要时可删除本段）
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖，利用构建缓存
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝项目代码（被 .dockerignore 过滤的不会进入镜像）
COPY backend ./backend
COPY frontend ./frontend
COPY admin ./admin
COPY docker ./docker
COPY run.py ./

# 数据目录：运行时建议挂载卷持久化（数据库、原图、缩略图、自定义主题）
RUN mkdir -p /app/data/uploads /app/data/thumbnails /app/data/themes

# 对外端口（默认值；如用环境变量改动端口，请同步调整端口映射）
EXPOSE 8080 8000 8001

CMD ["python", "run.py"]
