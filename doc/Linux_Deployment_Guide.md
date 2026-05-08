# SomnoLight Linux 服务器部署说明

本文档面向当前项目代码仓库 `F:\sleep` 的实际结构编写，适用于将项目部署到 Linux 服务器（推荐 Ubuntu 22.04 / Debian 12）。

如果你希望直接使用一键部署脚本，仓库里已经提供：

- [deploy_linux.sh](/F:/sleep/scripts/deploy_linux.sh)

最简单的使用方式：

```bash
cd /opt/somnolight/sleep
chmod +x scripts/deploy_linux.sh
DOMAIN=somnolight.example.com \
PUBLIC_BASE_URL=https://somnolight.example.com \
bash scripts/deploy_linux.sh
```

## 1. 项目部署结构

当前项目由两部分组成：

- 前端：`frontend/`
  - 技术栈：Vue 3 + Vite + ECharts
  - 通过 `npm run build` 构建静态文件，产物位于 `frontend/dist/`
- 后端：`backend/`
  - 技术栈：FastAPI + Uvicorn + SQLite
  - 数据库存储目录：`backend/storage/`
  - 模型文件目录：`backend/storage/models/`
  - 上传文件目录：`backend/storage/uploads/`
  - 产物目录：`backend/storage/artifacts/`

推荐部署方式：

- `Nginx` 提供前端静态页面
- `systemd` 托管 FastAPI 后端
- 前后端走同一域名
- `Nginx` 反向代理 `/api`、`/health`、`/storage`

## 2. 部署前准备

建议服务器环境：

- Python `3.10` 或 `3.11`
- Node.js `20.x`
- `npm`
- `nginx`
- `git`

如果服务器还没装这些组件，可先执行：

```bash
sudo apt update
sudo apt install -y git nginx python3 python3-venv python3-pip curl
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

## 3. 上传项目代码

将项目放到服务器，例如：

```bash
sudo mkdir -p /opt/somnolight
sudo chown -R $USER:$USER /opt/somnolight
cd /opt/somnolight
git clone <你的仓库地址> sleep
cd /opt/somnolight/sleep
```

如果不是通过 git，也可以直接把整个项目目录上传到：

```bash
/opt/somnolight/sleep
```

## 4. 安装后端依赖

### 4.1 创建虚拟环境

```bash
cd /opt/somnolight/sleep
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### 4.2 安装 Python 依赖

项目根目录已有 `requirements.txt`，但它主要是模型与信号处理依赖；当前后端还需要额外安装 Web 运行依赖。

执行：

```bash
pip install -r requirements.txt
pip install fastapi uvicorn python-multipart
```

如果服务器上后续要做 EDF 读取或 PDF/文件解析，按你的业务再补充安装相关包即可。

## 5. 安装前端依赖并构建

### 5.1 安装依赖

```bash
cd /opt/somnolight/sleep/frontend
npm install
```

### 5.2 生产环境 API 地址

当前前端代码里的 API 基址来自：

```js
import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'
```

也就是说，生产环境构建时必须显式指定 `VITE_API_BASE`，否则前端会继续请求本机 `127.0.0.1:8000`。

推荐在 `frontend/` 下创建：

```bash
cat > .env.production <<'EOF'
VITE_API_BASE=https://你的域名
EOF
```

例如：

```bash
cat > .env.production <<'EOF'
VITE_API_BASE=https://somnolight.example.com
EOF
```

### 5.3 构建前端

```bash
cd /opt/somnolight/sleep/frontend
npm run build
```

构建完成后，静态文件位于：

```bash
/opt/somnolight/sleep/frontend/dist
```

## 6. 后端启动验证

先手动启动一次，确认后端可用：

```bash
cd /opt/somnolight/sleep
source .venv/bin/activate
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

然后另开一个终端测试：

```bash
curl http://127.0.0.1:8000/health
```

如果返回类似：

```json
{"status":"ok"}
```

说明后端启动成功。

注意：

- 当前项目启动时会自动初始化数据库并执行一次性种子逻辑
- 后端代码本身是 `reload=False` 思路，生产环境改代码后需要手动重启服务
- `backend/storage/` 必须有写权限，否则上传模型、上传诊断文件、生成预测结果都会失败

## 7. 配置 systemd 托管后端

创建服务文件：

```bash
sudo nano /etc/systemd/system/somnolight-backend.service
```

写入以下内容：

```ini
[Unit]
Description=SomnoLight FastAPI Backend
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/somnolight/sleep
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/somnolight/sleep/.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

然后授权存储目录：

```bash
sudo chown -R www-data:www-data /opt/somnolight/sleep/backend/storage
sudo chown -R www-data:www-data /opt/somnolight/sleep/frontend/dist
```

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable somnolight-backend
sudo systemctl start somnolight-backend
sudo systemctl status somnolight-backend
```

查看日志：

```bash
journalctl -u somnolight-backend -f
```

## 8. 配置 Nginx

创建站点配置：

```bash
sudo nano /etc/nginx/sites-available/somnolight
```

写入示例配置：

```nginx
server {
    listen 80;
    server_name 你的域名;

    root /opt/somnolight/sleep/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    location /storage/ {
        proxy_pass http://127.0.0.1:8000/storage/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用站点：

```bash
sudo ln -s /etc/nginx/sites-available/somnolight /etc/nginx/sites-enabled/somnolight
sudo nginx -t
sudo systemctl reload nginx
```

## 9. HTTPS 配置

如果域名已解析到服务器，推荐直接使用 Certbot：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d 你的域名
```

如果你使用 HTTPS，请确认 `.env.production` 中的 `VITE_API_BASE` 也使用 `https://`。

## 10. 首次上线后的检查项

上线后建议依次检查：

### 10.1 页面是否可打开

浏览器访问：

```text
https://你的域名
```

### 10.2 健康检查

访问：

```text
https://你的域名/health
```

### 10.3 后端 API 是否正常

访问：

```text
https://你的域名/api/models
```

### 10.4 存储目录是否正常写入

需要实际测试：

- 上传一个模型
- 新建一次诊断
- 下载一次预测 CSV

这些操作都成功，说明以下目录权限是正常的：

- `backend/storage/models`
- `backend/storage/uploads`
- `backend/storage/artifacts`
- `backend/storage/temp`
- `backend/storage/somnolight_live.db`

## 11. 更新发布流程

后续更新建议按下面流程执行：

```bash
cd /opt/somnolight/sleep
git pull

source .venv/bin/activate
pip install -r requirements.txt
pip install fastapi uvicorn python-multipart

cd /opt/somnolight/sleep/frontend
npm install
npm run build

sudo systemctl restart somnolight-backend
sudo systemctl reload nginx
```

## 12. 当前项目的几个部署注意事项

### 12.1 前端必须设置生产 API 地址

这是当前项目最容易遗漏的一点。

如果你不创建 `frontend/.env.production`，前端会默认请求：

```text
http://127.0.0.1:8000
```

这样浏览器访问你的公网页面时，接口一定会错。

### 12.2 存储目录不能只读

这个项目不是纯静态展示，它会持续写入：

- SQLite 数据库
- 模型文件
- 上传的诊断文件
- 导出的预测结果

所以 `backend/storage/` 及其子目录必须可写。

### 12.3 不建议前后端跨域分开部署

当前后端默认 CORS 只允许本地开发地址：

- `http://127.0.0.1:5173`
- `http://localhost:5173`

因此生产环境最推荐的做法是：

- 前端和后端走同一域名
- 由 Nginx 统一代理

这样最省事，也最稳定。

### 12.4 代码更新后要重启后端

当前后端生产运行不是热重载模式。只要你更新了 Python 代码，就要执行：

```bash
sudo systemctl restart somnolight-backend
```

## 13. 推荐的生产目录布局

推荐最终结构如下：

```text
/opt/somnolight/sleep
├── backend
│   ├── app
│   └── storage
│       ├── artifacts
│       ├── models
│       ├── temp
│       ├── uploads
│       └── somnolight_live.db
├── frontend
│   ├── dist
│   ├── src
│   ├── package.json
│   └── .env.production
├── data
├── models
├── requirements.txt
└── .venv
```

## 14. 一句话部署建议

如果你想最快、最稳地上线当前项目，建议就按这一套：

1. Linux 服务器安装 Python、Node、Nginx
2. 项目放到 `/opt/somnolight/sleep`
3. 后端放进 `.venv` 跑 `uvicorn`
4. 前端执行 `npm run build`
5. `Nginx` 提供 `frontend/dist`
6. `Nginx` 反代 `/api`、`/health`、`/storage`
7. `systemd` 托管后端

---

如果你愿意，我下一步可以继续帮你补两样东西：

- 一份可直接放服务器的 `somnolight-backend.service` 成品文件
- 一份可直接使用的 `nginx` 配置成品文件
