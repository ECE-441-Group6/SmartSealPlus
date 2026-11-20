#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run with sudo: sudo bash install_smartseal_service.sh" >&2
    exit 1
fi

service_user="${SUDO_USER:-}"
if [[ -z "${service_user}" || "${service_user}" == "root" ]]; then
    echo "Run this script with sudo from the normal Pi user account." >&2
    exit 1
fi

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python_bin="${project_dir}/.venv/bin/python"
if [[ ! -x "${python_bin}" ]]; then
    python_bin="/usr/bin/python3"
fi

unit_file="/etc/systemd/system/smartseal.service"
cat > "${unit_file}" <<EOF
[Unit]
Description=SmartSeal dashboard and BLE gateway
After=network-online.target bluetooth.target
Wants=network-online.target bluetooth.target

[Service]
Type=simple
User=${service_user}
WorkingDirectory=${project_dir}
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
Environment=SMARTSEAL_DASHBOARD_HOST=0.0.0.0
Environment=SMARTSEAL_DASHBOARD_PORT=5000
Environment=SMARTSEAL_SIMULATION=0
ExecStart=${python_bin} ${project_dir}/run_smartseal.py
Restart=on-failure
RestartSec=5
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

chmod 0644 "${unit_file}"
systemctl daemon-reload
systemctl enable --now smartseal.service
echo "SmartSeal is enabled at boot and started now."
echo "Open http://<pi-ip-address>:5000 from a device on the same network."
