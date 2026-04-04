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
#   4. Verifies bundled Space Grotesk fonts in assets/fonts/
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
    python3-venv \
    python3-dev \
    curl \
    libopenjp2-7 \
    libtiff6 \
    libjpeg-dev \
    libfreetype6-dev \
    zlib1g-dev \
    git

# ---------------------------------------------------------------------------
# 2. Poetry + Python dependencies
# ---------------------------------------------------------------------------
# Raspberry Pi OS / Debian mark system Python as "externally managed" (PEP 668),
# so `pip install --user poetry` fails. The official installer puts Poetry in
# ~/.local (no system-site pip). We avoid apt python3-poetry here: it is often
# Poetry 1.x while this project needs poetry-core 2.x (see pyproject.toml).

POETRY="${REAL_HOME}/.local/bin/poetry"
if ! sudo -u "${REAL_USER}" test -x "${POETRY}"; then
    log "Installing Poetry (official installer)…"
    sudo -u "${REAL_USER}" env HOME="${REAL_HOME}" \
        bash -c 'curl -sSL https://install.python-poetry.org | python3 - --yes'
fi
sudo -u "${REAL_USER}" test -x "${POETRY}" || die "Poetry not found at ${POETRY}"

log "Installing Python dependencies via Poetry…"
cd "${PROJECT_ROOT}"
sudo -u "${REAL_USER}" "${POETRY}" install --no-interaction --quiet

VENV_DIR="$(sudo -u "${REAL_USER}" "${POETRY}" env info --path)"

# ---------------------------------------------------------------------------
# 3. Waveshare e-Paper library
# ---------------------------------------------------------------------------

WAVESHARE_DIR="${PROJECT_ROOT}/waveshare_epaper"

if [[ -d "${WAVESHARE_DIR}" ]]; then
    log "Waveshare repo already cloned — fixing ownership, then pulling latest…"
    # Must chown before git: root-owned clone + git as REAL_USER triggers
    # "dubious ownership"; pip also needs write access for *.egg-info in-tree.
    chown -R "${REAL_USER}:${REAL_USER}" "${WAVESHARE_DIR}"
    sudo -u "${REAL_USER}" git -C "${WAVESHARE_DIR}" pull --quiet
else
    log "Cloning Waveshare e-Paper library…"
    sudo -u "${REAL_USER}" git clone --depth=1 \
        https://github.com/waveshare/e-Paper.git \
        "${WAVESHARE_DIR}" --quiet
fi
chown -R "${REAL_USER}:${REAL_USER}" "${WAVESHARE_DIR}"

log "Installing Waveshare Python library via Poetry…"
sudo -u "${REAL_USER}" "${POETRY}" run pip install \
    "${WAVESHARE_DIR}/RaspberryPi_JetsonNano/python/" --quiet

# ---------------------------------------------------------------------------
# 4. SpaceGrotesk fonts (bundled in repo)
# ---------------------------------------------------------------------------

FONT_DIR="${PROJECT_ROOT}/assets/fonts"
FONT_REGULAR="${FONT_DIR}/SpaceGrotesk-Regular.ttf"
FONT_BOLD="${FONT_DIR}/SpaceGrotesk-Bold.ttf"

[[ -f "${FONT_REGULAR}" ]] || die "Missing font (clone/checkout repo): ${FONT_REGULAR}"
[[ -f "${FONT_BOLD}" ]] || die "Missing font (clone/checkout repo): ${FONT_BOLD}"
log "Space Grotesk fonts present: ${FONT_DIR}"

chown "${REAL_USER}:${REAL_USER}" "${FONT_REGULAR}" "${FONT_BOLD}"

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
