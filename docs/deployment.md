# 部署 CodefyUI-OJ

針對校內、跨班級競賽（100–500 人）的部署指南。

## 前置需求

- Linux 主機（建議 Ubuntu 22.04 / 24.04）
- Docker ≥ 24 + docker compose plugin
- 4 vCPU / 8 GB RAM 起跳（每份 submission 沙箱 1 CPU + 2 GB）
- 50 GB SSD 給 submission 檔案與 hidden test data
- 反向代理（nginx / Caddy）給 HTTPS

## 一次性準備

### 1. 取得 cdui 原始碼

OJ 沙箱 image 需要打包 cdui 的後端：

```bash
cd /opt
git clone https://github.com/treeleaves30760/CodefyUI.git
git clone https://github.com/treeleaves30760/CodefyUI-OJ.git
cd CodefyUI-OJ
```

### 2. 設定環境變數

```bash
cp .env.prod.example .env.prod
# 編輯 .env.prod，至少改：
#   POSTGRES_PASSWORD
#   JWT_SECRET   （python -c "import secrets; print(secrets.token_urlsafe(48))"）
#   CORS_ORIGINS （改成你的前端網址）
```

### 3. 建沙箱 image

```bash
# Linux
CDUI_PATH=/opt/CodefyUI ./backend/docker/build_sandbox.sh

# Windows PowerShell
.\backend\docker\build_sandbox.ps1 -CduiPath C:\path\to\CodefyUI
```

### 4. 啟動全部服務

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

服務：
- `api` 監聽 `127.0.0.1:8100`（含 health check, 自動跑 alembic upgrade head）
- `worker` RQ worker，掛 docker.sock 用以啟動沙箱 container
- `frontend` 監聽 `127.0.0.1:8080`，proxy `/api` 到 `api`
- `db` / `redis` 內部 network only

### 5. 反向代理 + HTTPS

範例 nginx 設定：

```nginx
server {
    listen 443 ssl http2;
    server_name oj.example.com;

    ssl_certificate     /etc/letsencrypt/live/oj.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/oj.example.com/privkey.pem;

    client_max_body_size 50M;   # 給隱藏測資上傳

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 常用維運

```bash
# 看 worker 日誌
docker compose -f docker-compose.prod.yml logs -f worker

# 重新跑某個 submission 的判題
docker compose -f docker-compose.prod.yml exec api python -c "
from app.judge.queue import enqueue_judge
enqueue_judge(123)
"

# 開帳號為 teacher
docker compose -f docker-compose.prod.yml exec db psql -U oj -d codefyui_oj \
  -c "UPDATE users SET role='teacher' WHERE email='teacher@school.edu';"

# 備份
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U oj codefyui_oj > backups/db-$(date +%Y%m%d).sql

# 重啟 API（migrations 會在啟動時跑）
docker compose -f docker-compose.prod.yml up -d --no-deps --build api
```

## 升級 cdui

當 cdui 新增了節點或修改了 schema：

```bash
cd /opt/CodefyUI && git pull
cd /opt/CodefyUI-OJ
CDUI_PATH=/opt/CodefyUI ./backend/docker/build_sandbox.sh
# Worker 在下次拉 job 時會用到新 image — 不需重啟服務
```

## 安全注意事項

1. **JWT_SECRET 必須是 32+ 字元的隨機字串**。洩漏的話登入 token 會被偽造。
2. **不要把 .env.prod 簽進 git**。`.gitignore` 已排除 `.env*`。
3. **sandbox container 限制**：`docker-compose.prod.yml` 已設 `--network=none --cpus=1 --memory=2g --read-only`；非必要不要鬆綁。
4. **資料庫不對外暴露**：docker-compose 中 `db` 與 `redis` 沒有 host port mapping。要直連請從 host 用 `docker compose exec`。
5. **反向代理上的 HTTPS**：JWT 在 Authorization header 傳遞，必須走 TLS。
6. **rate limit**：MVP 還沒上 rate limiter；正式上線前建議在 nginx 層加 `limit_req_zone`。
