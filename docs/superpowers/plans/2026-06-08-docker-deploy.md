# Docker 容器化 + 部署计划（Plan 3）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将资讯平台容器化并配置生产部署环境——含 Dockerfile、docker-compose（app + RSSHub 两个服务）、Nginx 反代配置（SSL 终止）、更新 .env.example、Docker 环境 crontab，最终通过本地结构验证。

**Architecture:** 单宿主机部署。Docker Compose 管理两个服务（`app` 监听 127.0.0.1:8000，`rsshub` 监听 127.0.0.1:1200），Nginx 在宿主机做 SSL 终止并反代到 :8000。SQLite 数据库和 config.yaml 通过 volume 挂载持久化。Cron 运行在宿主机，通过 `docker exec` 触发容器内任务。

**Tech Stack:** Docker, Docker Compose v2, Nginx, Let's Encrypt (certbot), Python 3.11-slim 基础镜像

---

## 文件清单

```
news-platform/
├── Dockerfile                    # 创建
├── .dockerignore                 # 创建
├── docker-compose.yml            # 创建
├── deploy/
│   └── nginx.conf                # 创建：news.daichao.fun Nginx 配置
├── .env.example                  # 修改：补充 SECRET_KEY
└── crontab.example               # 修改：添加 Docker exec 版 cron 命令
```

---

## Task 1: Dockerfile + .dockerignore

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

- [ ] **Step 1: 创建 Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 先复制依赖文件，利用 Docker layer 缓存
COPY pyproject.toml .
RUN pip install --no-cache-dir -e . || true

# 复制应用代码
COPY app/ app/
COPY config.yaml .

# 数据目录
RUN mkdir -p data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
```

**说明：**
- `--proxy-headers` 让 FastAPI 信任 Nginx 转发的 X-Forwarded-Proto
- `--forwarded-allow-ips=*` 允许来自 127.0.0.1（宿主机 Nginx）的代理头
- `config.yaml` 复制到镜像作为默认值；volume 挂载会在运行时覆盖（支持热更新）
- data/ 目录在镜像中预创建，volume 挂载后持久化

- [ ] **Step 2: 创建 .dockerignore**

```
.env
.git/
.pytest_cache/
__pycache__/
*.pyc
*.egg-info/
dist/
.venv/
venv/
data/
tests/
docs/
deploy/
```

- [ ] **Step 3: 验证 Dockerfile 关键指令**

```bash
cd /Users/daichao/news-platform && python3 -c "
content = open('Dockerfile').read()
checks = [
    'FROM python:3.11-slim',
    'WORKDIR /app',
    'COPY pyproject.toml',
    'pip install',
    'COPY app/',
    'EXPOSE 8000',
    'uvicorn app.main:app',
    '--proxy-headers',
]
ok = True
for c in checks:
    if c not in content:
        print('MISSING:', c); ok = False
    else:
        print('OK:', c)
print('PASS' if ok else 'FAIL')
"
```

Expected: 全部 OK + PASS

- [ ] **Step 4: Commit**

```bash
cd /Users/daichao/news-platform && git add Dockerfile .dockerignore && git commit -m "feat: Dockerfile for Python 3.11-slim"
```

---

## Task 2: docker-compose.yml

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: 创建 docker-compose.yml**

```yaml
services:
  app:
    build: .
    image: news-platform:latest
    container_name: news-app
    restart: unless-stopped
    ports:
      - "127.0.0.1:8000:8000"
    env_file: .env
    environment:
      # 覆盖 .env 中的值，使用 Docker 内部服务名访问 RSSHub
      - RSSHUB_BASE_URL=http://rsshub:1200
    volumes:
      - ./data:/app/data
      - ./config.yaml:/app/config.yaml
    depends_on:
      - rsshub
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3

  rsshub:
    image: diygod/rsshub:latest
    container_name: news-rsshub
    restart: unless-stopped
    ports:
      - "127.0.0.1:1200:1200"
    environment:
      - NODE_ENV=production
      - CACHE_TYPE=memory
      - CACHE_EXPIRE=300
```

**设计说明：**
- `app` 和 `rsshub` 均只绑定 `127.0.0.1`，不暴露到公网
- `env_file: .env` 加载 secret（ANTHROPIC_API_KEY、SECRET_KEY 等）
- `environment.RSSHUB_BASE_URL` 在 `env_file` 之后生效，覆盖为 Docker DNS 名
- `volumes` 挂载 `data/`（SQLite DB）和 `config.yaml`（来源配置）持久化

- [ ] **Step 2: 验证 docker-compose.yml 结构**

```bash
cd /Users/daichao/news-platform && python3 -c "
import yaml
data = yaml.safe_load(open('docker-compose.yml').read())
svc = data['services']
assert 'app' in svc and 'rsshub' in svc, 'Missing services'
app = svc['app']
assert '127.0.0.1:8000:8000' in app['ports'], 'app port binding wrong'
assert 'rsshub' in str(app.get('depends_on', '')), 'Missing depends_on'
assert any('data' in str(v) for v in app['volumes']), 'Missing data volume'
assert any('config.yaml' in str(v) for v in app['volumes']), 'Missing config.yaml volume'
rsshub = svc['rsshub']
assert '127.0.0.1:1200:1200' in rsshub['ports'], 'rsshub port binding wrong'
print('PASS: docker-compose.yml valid')
"
```

Expected: `PASS: docker-compose.yml valid`

- [ ] **Step 3: Commit**

```bash
cd /Users/daichao/news-platform && git add docker-compose.yml && git commit -m "feat: docker-compose with app + rsshub services"
```

---

## Task 3: Nginx 配置

**Files:**
- Create: `deploy/nginx.conf`

- [ ] **Step 1: 创建 deploy/ 目录**

```bash
mkdir -p /Users/daichao/news-platform/deploy
```

- [ ] **Step 2: 创建 deploy/nginx.conf**

```nginx
# news.daichao.fun — 个人资讯平台 Nginx 配置
#
# 服务器端部署步骤：
#   sudo cp deploy/nginx.conf /etc/nginx/sites-available/news.daichao.fun
#   sudo ln -s /etc/nginx/sites-available/news.daichao.fun /etc/nginx/sites-enabled/
#   sudo nginx -t
#   sudo certbot --nginx -d news.daichao.fun
#   sudo systemctl reload nginx

server {
    listen 80;
    server_name news.daichao.fun;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    http2 on;
    server_name news.daichao.fun;

    # Let's Encrypt 证书（certbot --nginx 自动填充）
    ssl_certificate /etc/letsencrypt/live/news.daichao.fun/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/news.daichao.fun/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers off;

    add_header X-Frame-Options SAMEORIGIN;
    add_header X-Content-Type-Options nosniff;
    add_header Referrer-Policy strict-origin-when-cross-origin;

    client_max_body_size 1m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_connect_timeout 10s;
    }

    access_log /var/log/nginx/news-platform.access.log;
    error_log  /var/log/nginx/news-platform.error.log;
}
```

- [ ] **Step 3: 验证 Nginx 配置关键指令**

```bash
cd /Users/daichao/news-platform && python3 -c "
content = open('deploy/nginx.conf').read()
checks = [
    ('HTTP→HTTPS redirect', 'return 301 https'),
    ('SSL listen', 'listen 443 ssl'),
    ('域名', 'news.daichao.fun'),
    ('SSL 证书', 'ssl_certificate'),
    ('反代目标', 'proxy_pass http://127.0.0.1:8000'),
    ('X-Forwarded-Proto', 'X-Forwarded-Proto'),
    ('TLS 版本', 'TLSv1.2'),
    ('http2', 'http2 on'),
]
ok = True
for name, token in checks:
    if token not in content:
        print('MISSING:', name); ok = False
    else:
        print('OK:', name)
print('PASS' if ok else 'FAIL')
"
```

Expected: 全部 OK + PASS

- [ ] **Step 4: Commit**

```bash
cd /Users/daichao/news-platform && git add deploy/nginx.conf && git commit -m "feat: nginx config for news.daichao.fun with SSL termination"
```

---

## Task 4: 更新 .env.example + crontab.example

**Files:**
- Modify: `.env.example`
- Modify: `crontab.example`

- [ ] **Step 1: 读取两个文件确认当前内容**

```bash
cat /Users/daichao/news-platform/.env.example && echo "---" && cat /Users/daichao/news-platform/crontab.example
```

- [ ] **Step 2: 覆写 .env.example**

完整内容如下（先读取确认，再用 Write 工具覆写）：

```
# Anthropic API
ANTHROPIC_API_KEY=your-key-here

# 飞书机器人 webhook（可选，不填则跳过推送）
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/your-token

# Web 认证
SITE_PASSWORD=changeme
SECRET_KEY=your-random-secret-key-min-32-chars

# 数据库（Docker 部署保持默认；本地开发可改为绝对路径）
DATABASE_URL=sqlite:///data/news.db

# RSSHub（本地开发用 localhost；Docker 内由 compose 自动覆盖为 http://rsshub:1200）
RSSHUB_BASE_URL=http://localhost:1200
```

- [ ] **Step 3: 覆写 crontab.example**

完整内容如下（先读取确认，再用 Write 工具覆写）：

```
# 个人资讯平台定时任务
# 二选一：直接运行（方式A）或 Docker exec（方式B）

# ── 方式 A：宿主机 virtualenv 直接运行 ───────────────────────────────────────
# 早间 9:00 — 全部类别（银行/技术/创业）
# 0 9 * * * cd /opt/news-platform && /opt/news-platform/.venv/bin/python -m app.run --slot morning --category all >> /var/log/news-platform/morning.log 2>&1

# 晚间 19:00 — 仅银行类别
# 0 19 * * * cd /opt/news-platform && /opt/news-platform/.venv/bin/python -m app.run --slot evening --category banking >> /var/log/news-platform/evening.log 2>&1

# ── 方式 B：通过 docker exec 运行（推荐，docker-compose 部署）───────────────
# 早间 9:00 — 全部类别
0 9 * * * docker exec news-app python -m app.run --slot morning --category all >> /var/log/news-platform/morning.log 2>&1

# 晚间 19:00 — 仅银行类别
0 19 * * * docker exec news-app python -m app.run --slot evening --category banking >> /var/log/news-platform/evening.log 2>&1

# 创建日志目录（首次部署前执行一次）：
# mkdir -p /var/log/news-platform
```

- [ ] **Step 4: 验证两文件内容**

```bash
cd /Users/daichao/news-platform && python3 -c "
env = open('.env.example').read()
cron = open('crontab.example').read()
env_checks = ['SECRET_KEY', 'ANTHROPIC_API_KEY', 'SITE_PASSWORD', 'DATABASE_URL', 'RSSHUB_BASE_URL']
cron_checks = ['docker exec news-app', '--slot morning', '--slot evening']
ok = True
for c in env_checks:
    status = 'OK' if c in env else 'MISSING'
    if status == 'MISSING': ok = False
    print(status, c)
for c in cron_checks:
    status = 'OK' if c in cron else 'MISSING'
    if status == 'MISSING': ok = False
    print(status, c)
print('PASS' if ok else 'FAIL')
"
```

Expected: 全部 OK + PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/daichao/news-platform && git add .env.example crontab.example && git commit -m "feat: add SECRET_KEY to env.example, docker exec cron commands"
```

---

## Task 5: 全量验收

- [ ] **Step 1: 验证所有文件存在**

```bash
cd /Users/daichao/news-platform && python3 -c "
from pathlib import Path
files = ['Dockerfile', '.dockerignore', 'docker-compose.yml', 'deploy/nginx.conf', '.env.example', 'crontab.example']
ok = True
for f in files:
    status = 'OK' if Path(f).exists() else 'MISSING'
    if status == 'MISSING': ok = False
    print(status, f)
print('PASS' if ok else 'FAIL')
"
```

Expected: 全部 OK + PASS

- [ ] **Step 2: docker-compose.yml 结构验证**

```bash
cd /Users/daichao/news-platform && python3 -c "
import yaml
data = yaml.safe_load(open('docker-compose.yml').read())
svc = data['services']
assert 'app' in svc and 'rsshub' in svc
app = svc['app']
assert '127.0.0.1:8000:8000' in app['ports']
assert any('data' in str(v) for v in app['volumes'])
assert any('config.yaml' in str(v) for v in app['volumes'])
assert '127.0.0.1:1200:1200' in svc['rsshub']['ports']
print('PASS: compose structure OK')
"
```

- [ ] **Step 3: 运行全部测试确认无回归**

```bash
cd /Users/daichao/news-platform && pytest tests/ -q 2>&1 | tail -3
```

Expected: `65 passed`（或更多）

- [ ] **Step 4: git log 查看 Plan 3 提交记录**

```bash
cd /Users/daichao/news-platform && git log --oneline -6
```

Expected: 看到 Task 1-4 的 4 条 commit

- [ ] **Step 5: 输出最终验收报告**

```
STATUS: PASS
FILES: OK（6 个文件全部存在）
COMPOSE: OK（services: app + rsshub，端口绑定 127.0.0.1）
TESTS: 65 passed（无回归）
NOTES: <任何需要关注的问题>
```

---

## 服务器部署操作手册（人工执行，非自动化）

```bash
# 1. 克隆仓库到服务器
git clone <repo> /opt/news-platform && cd /opt/news-platform

# 2. 创建 .env（填写真实值）
cp .env.example .env
# 编辑：ANTHROPIC_API_KEY、SECRET_KEY（随机 32+ 字符）、SITE_PASSWORD、FEISHU_WEBHOOK_URL

# 3. 创建数据目录
mkdir -p data

# 4. 构建并启动
docker compose up -d --build

# 5. 验证健康
curl http://127.0.0.1:8000/health   # → {"status":"ok"}

# 6. 配置 Nginx
sudo cp deploy/nginx.conf /etc/nginx/sites-available/news.daichao.fun
sudo ln -sf /etc/nginx/sites-available/news.daichao.fun /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 7. SSL（certbot）
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d news.daichao.fun

# 8. 配置 Cron（方式 B）
mkdir -p /var/log/news-platform
crontab -e   # 粘贴 crontab.example 中方式 B 的两行

# 9. 验证 HTTPS
curl https://news.daichao.fun/health  # → {"status":"ok"}
```
