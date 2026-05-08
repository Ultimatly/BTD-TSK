#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

APP_NAME="${APP_NAME:-somnolight}"
APP_USER="${APP_USER:-www-data}"
APP_GROUP="${APP_GROUP:-www-data}"
DOMAIN="${DOMAIN:-somnolight.example.com}"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-http://${DOMAIN}}"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
NGINX_SITE_NAME="${NGINX_SITE_NAME:-${APP_NAME}}"
ENABLE_SSL="${ENABLE_SSL:-0}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-}"

FRONTEND_DIR="${PROJECT_ROOT}/frontend"
BACKEND_STORAGE_DIR="${PROJECT_ROOT}/backend/storage"
VENV_DIR="${PROJECT_ROOT}/.venv"
SERVICE_NAME="${APP_NAME}-backend"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
NGINX_AVAILABLE_FILE="/etc/nginx/sites-available/${NGINX_SITE_NAME}"
NGINX_ENABLED_FILE="/etc/nginx/sites-enabled/${NGINX_SITE_NAME}"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This deployment script only supports Linux."
  exit 1
fi

if ! command -v sudo >/dev/null 2>&1 && [[ "$(id -u)" -ne 0 ]]; then
  echo "sudo is required when not running as root."
  exit 1
fi

if [[ "$(id -u)" -eq 0 ]]; then
  SUDO=""
else
  SUDO="sudo"
fi

run_sudo() {
  if [[ -n "${SUDO}" ]]; then
    ${SUDO} "$@"
  else
    "$@"
  fi
}

print_step() {
  echo
  echo "==> $1"
}

ensure_file_exists() {
  local file_path="$1"
  if [[ ! -f "${file_path}" ]]; then
    echo "Missing required file: ${file_path}"
    exit 1
  fi
}

ensure_directory_exists() {
  local dir_path="$1"
  if [[ ! -d "${dir_path}" ]]; then
    echo "Missing required directory: ${dir_path}"
    exit 1
  fi
}

require_project_layout() {
  ensure_file_exists "${PROJECT_ROOT}/requirements.txt"
  ensure_file_exists "${PROJECT_ROOT}/backend/app/main.py"
  ensure_file_exists "${FRONTEND_DIR}/package.json"
  ensure_directory_exists "${BACKEND_STORAGE_DIR}"
}

install_system_packages() {
  print_step "Installing system packages"
  run_sudo apt update
  run_sudo apt install -y git nginx python3 python3-venv python3-pip curl ca-certificates

  if command -v node >/dev/null 2>&1; then
    local node_major
    node_major="$(node -p "process.versions.node.split('.')[0]")"
    if [[ "${node_major}" -lt 18 ]]; then
      print_step "Upgrading Node.js to 20.x"
      curl -fsSL https://deb.nodesource.com/setup_20.x | run_sudo bash -
      run_sudo apt install -y nodejs
    fi
  else
    print_step "Installing Node.js 20.x"
    curl -fsSL https://deb.nodesource.com/setup_20.x | run_sudo bash -
    run_sudo apt install -y nodejs
  fi
}

prepare_storage() {
  print_step "Preparing writable storage directories"
  mkdir -p \
    "${BACKEND_STORAGE_DIR}/artifacts" \
    "${BACKEND_STORAGE_DIR}/models" \
    "${BACKEND_STORAGE_DIR}/temp" \
    "${BACKEND_STORAGE_DIR}/uploads"

  run_sudo chown -R "${APP_USER}:${APP_GROUP}" "${BACKEND_STORAGE_DIR}"
}

setup_python_env() {
  print_step "Setting up Python virtual environment"
  if [[ ! -d "${VENV_DIR}" ]]; then
    python3 -m venv "${VENV_DIR}"
  fi

  "${VENV_DIR}/bin/python" -m pip install --upgrade pip
  "${VENV_DIR}/bin/pip" install -r "${PROJECT_ROOT}/requirements.txt"
  "${VENV_DIR}/bin/pip" install fastapi uvicorn python-multipart
}

build_frontend() {
  print_step "Building frontend"
  cat > "${FRONTEND_DIR}/.env.production" <<EOF
VITE_API_BASE=${PUBLIC_BASE_URL}
EOF

  (
    cd "${FRONTEND_DIR}"
    npm install
    npm run build
  )

  run_sudo chown -R "${APP_USER}:${APP_GROUP}" "${FRONTEND_DIR}/dist"
}

write_systemd_service() {
  print_step "Writing systemd service"
  run_sudo tee "${SERVICE_FILE}" >/dev/null <<EOF
[Unit]
Description=SomnoLight FastAPI Backend
After=network.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${PROJECT_ROOT}
Environment=PYTHONUNBUFFERED=1
ExecStart=${VENV_DIR}/bin/python -m uvicorn backend.app.main:app --host ${BACKEND_HOST} --port ${BACKEND_PORT}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

  run_sudo systemctl daemon-reload
  run_sudo systemctl enable "${SERVICE_NAME}"
  run_sudo systemctl restart "${SERVICE_NAME}"
}

write_nginx_config() {
  print_step "Writing Nginx config"
  run_sudo tee "${NGINX_AVAILABLE_FILE}" >/dev/null <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    root ${FRONTEND_DIR}/dist;
    index index.html;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://${BACKEND_HOST}:${BACKEND_PORT}/api/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /health {
        proxy_pass http://${BACKEND_HOST}:${BACKEND_PORT}/health;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
    }

    location /storage/ {
        proxy_pass http://${BACKEND_HOST}:${BACKEND_PORT}/storage/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

  if [[ ! -L "${NGINX_ENABLED_FILE}" ]]; then
    run_sudo ln -s "${NGINX_AVAILABLE_FILE}" "${NGINX_ENABLED_FILE}"
  fi

  if [[ -f /etc/nginx/sites-enabled/default ]]; then
    run_sudo rm -f /etc/nginx/sites-enabled/default
  fi

  run_sudo nginx -t
  run_sudo systemctl enable nginx
  run_sudo systemctl restart nginx
}

setup_ssl_if_requested() {
  if [[ "${ENABLE_SSL}" != "1" ]]; then
    return
  fi

  if [[ -z "${LETSENCRYPT_EMAIL}" ]]; then
    echo "ENABLE_SSL=1 requires LETSENCRYPT_EMAIL to be set."
    exit 1
  fi

  print_step "Enabling HTTPS via Certbot"
  run_sudo apt install -y certbot python3-certbot-nginx
  run_sudo certbot --nginx --non-interactive --agree-tos -m "${LETSENCRYPT_EMAIL}" -d "${DOMAIN}" --redirect
}

verify_deployment() {
  print_step "Verifying backend health"
  for _ in {1..20}; do
    if curl -fsS "http://${BACKEND_HOST}:${BACKEND_PORT}/health" >/dev/null 2>&1; then
      echo "Backend health check passed."
      return
    fi
    sleep 1
  done

  echo "Backend health check failed. Check logs with:"
  echo "  journalctl -u ${SERVICE_NAME} -f"
  exit 1
}

show_summary() {
  print_step "Deployment finished"
  echo "Project root: ${PROJECT_ROOT}"
  echo "Public URL:    ${PUBLIC_BASE_URL}"
  echo "Backend:       http://${BACKEND_HOST}:${BACKEND_PORT}"
  echo "Systemd unit:  ${SERVICE_NAME}"
  echo "Nginx site:    ${NGINX_AVAILABLE_FILE}"
  echo
  echo "Useful commands:"
  echo "  sudo systemctl status ${SERVICE_NAME}"
  echo "  journalctl -u ${SERVICE_NAME} -f"
  echo "  sudo nginx -t"
}

main() {
  require_project_layout
  install_system_packages
  prepare_storage
  setup_python_env
  build_frontend
  write_systemd_service
  write_nginx_config
  setup_ssl_if_requested
  verify_deployment
  show_summary
}

main "$@"
