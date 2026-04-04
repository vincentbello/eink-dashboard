#!/usr/bin/env bash
# scripts/setup.sh — One-shot setup for the e-ink dashboard on a Raspberry Pi.
#
# Run from the project root:
#   chmod +x scripts/setup.sh
#   sudo ./scripts/setup.sh
#
# What this script does:
#   1. Installs system (apt) dependencies and Poetry
#   2. Installs Python dependencies via poetry install
#   3. Clones the Waveshare e-Paper library and installs its Python module
#   4. Downloads DejaVu fonts into assets/fonts/
#   5. Creates a systemd service that starts the dashboard on boot
#   6. Enables and starts the service

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
    python3-dev \
    libopenjp2-7 \
    libtiff6 \
    libjpeg-dev \
    libfreetype6-dev \
    zlib1g-dev \
    git \
    fonts-dejavu-core \
    wget

# ---------------------------------------------------------------------------
# 2. Poetry + Python dependencies
# ---------------------------------------------------------------------------

if ! command -v poetry &>/dev/null; then
    log "Installing Poetry…"
    sudo -u "${REAL_USER}" pip install --user poetry --quiet
fi

POETRY="$(sudo -u "${REAL_USER}" python3 -m site --user-base)/bin/poetry"

log "Installing Python dependencies via Poetry…"
cd "${PROJECT_ROOT}"
sudo -u "${REAL_USER}" "${POETRY}" install --no-interaction --quiet

VENV_DIR="$(sudo -u "${REAL_USER}" "${POETRY}" env info --path)"

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

log "Installing Waveshare Python library via Poetry…"
sudo -u "${REAL_USER}" "${POETRY}" run pip install \
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
    # Fallback: download from SourceForge release archive.
    log "System font not found — downloading from SourceForge…"
    local tmp_archive
    tmp_archive="$(mktemp /tmp/dejavu.XXXXXX.tar.bz2)"
    wget -q -O "${tmp_archive}" \
        "https://sourceforge.net/projects/dejavu/files/dejavu/2.37/dejavu-fonts-ttf-2.37.tar.bz2/download"
    tar -xjf "${tmp_archive}" -C /tmp/ dejavu-fonts-ttf-2.37/ttf/"${src_name}"
    mv "/tmp/dejavu-fonts-ttf-2.37/ttf/${src_name}" "${dst}"
    rm -f "${tmp_archive}"
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
log "  MOCK_MODE=1 poetry run python tests/mock_display.py"
log ""
log "Edit config.py to set your stop IDs and station IDs."
