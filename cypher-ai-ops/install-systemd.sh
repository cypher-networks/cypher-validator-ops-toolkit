#!/usr/bin/env bash
set -euo pipefail

APP_NAME="cypher-ai-ops"
APP_USER="${APP_USER:-${SUDO_USER:-$USER}}"
APP_GROUP="${APP_GROUP:-$APP_USER}"
INSTALL_DIR="${INSTALL_DIR:-/opt/cypher-ai-ops}"
LIBRARY_DIR="${LIBRARY_DIR:-/opt/ai-lookup-library}"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
SOURCE_LIBRARY_DIR="${SOURCE_ROOT}/ai-lookup-library"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo: sudo bash install-systemd.sh" >&2
  exit 1
fi

if ! id "${APP_USER}" >/dev/null 2>&1; then
  echo "User ${APP_USER} does not exist. Create it first or run with APP_USER=<linux_user>." >&2
  exit 1
fi

if [[ ! -f "${SCRIPT_DIR}/.env" ]]; then
  echo "Missing ${SCRIPT_DIR}/.env. Create it before installing the service." >&2
  exit 1
fi

install -d -o "${APP_USER}" -g "${APP_GROUP}" "${INSTALL_DIR}"
install -d -o "${APP_USER}" -g "${APP_GROUP}" "${LIBRARY_DIR}"

rsync -a \
  --exclude ".venv" \
  --exclude "__pycache__" \
  --exclude ".pytest_cache" \
  --exclude "data" \
  "${SCRIPT_DIR}/" "${INSTALL_DIR}/"

if [[ -d "${SOURCE_LIBRARY_DIR}" ]]; then
  rsync -a "${SOURCE_LIBRARY_DIR}/" "${LIBRARY_DIR}/"
fi

chown -R "${APP_USER}:${APP_GROUP}" "${INSTALL_DIR}" "${LIBRARY_DIR}"
chmod 600 "${INSTALL_DIR}/.env"

sudo -u "${APP_USER}" python3 -m venv "${INSTALL_DIR}/.venv"
sudo -u "${APP_USER}" "${INSTALL_DIR}/.venv/bin/pip" install --upgrade pip
sudo -u "${APP_USER}" "${INSTALL_DIR}/.venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt"

sed -i "s|^KNOWLEDGE_LIBRARY_DIR=.*|KNOWLEDGE_LIBRARY_DIR=${LIBRARY_DIR}|" "${INSTALL_DIR}/.env"

cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=Cypher AI Ops Discord Bot
After=network-online.target ollama.service
Wants=network-online.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${INSTALL_DIR}/.venv/bin/python ${INSTALL_DIR}/bot.py
Restart=always
RestartSec=10
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "${APP_NAME}"
systemctl status "${APP_NAME}" --no-pager

echo
echo "Installed ${APP_NAME}."
echo "Logs: journalctl -u ${APP_NAME} -f"
echo "Library: ${LIBRARY_DIR}"
