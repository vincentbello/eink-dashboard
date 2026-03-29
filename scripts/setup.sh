#!/usr/bin/env bash
# scripts/setup.sh — One-shot setup for the e-ink dashboard on a Raspberry Pi.
#
# Run from the project root:
#   chmod +x scripts/setup.sh
#   sudo ./scripts/setup.sh
#
# What this script does:
#   1. Installs system (apt) and Python (pip) dependencies
#   2. Clones the Waveshare e-Paper library and installs its Python module
#   3. Downloads DejaVu fonts into assets/fonts/
#   4. Creates a systemd service that starts the dashboard on boot
#   5. Enables and starts the service

set -euo pipefail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log()  { echo "[setup] $*"; }
die()  { echo "[setup] ERROR: $*" >&2; exit 1; }

require_root() {
    [[ $EUID -eq 0 ]] || die "This script must be run as root (sudo ./scripts/setup.sh)"
}

# Resolve the project root (one level up from this script).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# The user who owns the project (not root even when running with sudo).
REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME=$(eval echo "~${REAL_USER}")

log "Project root : ${PROJECT_ROOT}"
log "Running as   : ${REAL_USER}"

# ---------------------------------------------------------------------------
# 1. System dependencies
# ---------------------------------------------------------------------------

require_root

log "Updating apt package lists…"
apt-get update -qq

log "Installing system packages…"
apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    python3-setuptools \
    python3-wheel \
    libopenjp2-7 \
    libtiff5 \
    libjpeg-dev \
    libfreetype6-dev \
    zlib1g-dev \
    git \
    fonts-dejavu-core \
    wget

# ---------------------------------------------------------------------------
# 2. Python virtual environment + pip packages
# ---------------------------------------------------------------------------

VENV_DIR="${PROJECT_ROOT}/.venv"

if [[ ! -d "${VENV_DIR}" ]]; then
    log "Creating Python virtual environment at ${VENV_DIR}…"
    python3 -m venv "${VENV_DIR}"
fi

log "Installing Python dependencies from requirements.txt…"
"${VENV_DIR}/bin/pip" install --upgrade pip --quiet
"${VENV_DIR}/bin/pip" install -r "${PROJECT_ROOT}/requirements.txt" --quiet

# ---------------------------------------------------------------------------
# 3. Waveshare e-Paper library
# ---------------------------------------------------------------------------

WAVESHARE_DIR="${PROJECT_ROOT}/waveshare_epaper"

if [[ -d "${WAVESHARE_DIR}" ]]; then
    log "Waveshare repo already cloned — pulling latest…"
    git -C "${WAVESHARE_DIR}" pull --quiet
else
    log "Cloning Waveshare e-Paper library…"
    git clone --depth=1 \
        https://github.com/waveshare/e-Paper.git \
        "${WAVESHARE_DIR}" --quiet
fi

log "Installing Waveshare Python library into venv…"
"${VENV_DIR}/bin/pip" install \
    "${WAVESHARE_DIR}/RaspberryPi_JetsonNano/python/" --quiet

# ---------------------------------------------------------------------------
# 4. DejaVu fonts
# ---------------------------------------------------------------------------

FONT_DIR="${PROJECT_ROOT}/assets/fonts"
mkdir -p "${FONT_DIR}"

FONT_REGULAR="${FONT_DIR}/DejaVuSans.ttf"
FONT_BOLD="${FONT_DIR}/DejaVuSans-Bold.ttf"

# DejaVu fonts are packaged in fonts-dejavu-core (installed above).
# Copy from the system font directory if not already present.
SYSTEM_FONT_DIRS=(
    "/usr/share/fonts/truetype/dejavu"
    "/usr/share/fonts/dejavu"
)

copy_font() {
    local src_name="$1"
    local dst="$2"
    if [[ -f "${dst}" ]]; then
        log "Font already exists: ${dst}"
        return
    fi
    for dir in "${SYSTEM_FONT_DIRS[@]}"; do
        if [[ -f "${dir}/${src_name}" ]]; then
            cp "${dir}/${src_name}" "${dst}"
            log "Copied ${src_name} → ${dst}"
            return
        fi
    done
    # Fallback: download directly.
    log "System font not found — downloading ${src_name} from GitHub…"
    wget -q -O "${dst}" \
        "https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/${src_name}"
}

copy_font "DejaVuSans.ttf"      "${FONT_REGULAR}"
copy_font "DejaVuSans-Bold.ttf" "${FONT_BOLD}"

chown "${REAL_USER}:${REAL_USER}" "${FONT_DIR}"/*.ttf 2>/dev/null || true

# ---------------------------------------------------------------------------
# 5. Systemd service
# ---------------------------------------------------------------------------

SERVICE_FILE="/etc/systemd/system/dashboard.service"

log "Writing systemd service to ${SERVICE_FILE}…"
cat > "${SERVICE_FILE}" << EOF
[Unit]
Description=e-ink Fridge Dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${REAL_USER}
WorkingDirectory=${PROJECT_ROOT}
ExecStart=${VENV_DIR}/bin/python ${PROJECT_ROOT}/main.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=dashboard

# Allow the service to read hardware interfaces (SPI for e-ink).
SupplementaryGroups=spi gpio

[Install]
WantedBy=multi-user.target
EOF

log "Reloading systemd daemon…"
systemctl daemon-reload

log "Enabling dashboard service…"
systemctl enable dashboard.service

log "Starting dashboard service…"
systemctl start dashboard.service || log "Service start failed — check: sudo journalctl -u dashboard -n 50"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

log ""
log "Setup complete!"
log ""
log "Useful commands:"
log "  sudo systemctl status dashboard"
log "  sudo journalctl -u dashboard -f"
log "  sudo systemctl restart dashboard"
log ""
log "To test without hardware:"
log "  cd ${PROJECT_ROOT}"
log "  MOCK_MODE=1 ${VENV_DIR}/bin/python tests/mock_display.py"
log ""
log "Edit config.py to set your API keys, stop IDs, and station IDs."
