#!/usr/bin/env bash
# Install nightly snapshot and daily anomaly scan cron entries.
# Idempotent: if a marker comment is already present, the script exits
# without touching the crontab.

set -euo pipefail

MARKER="# ═══ teacher-snapshot + anomaly detector ═══"
ASI_DIR="${HOME}/local-asi"
LOG_DIR="${ASI_DIR}/logs"

mkdir -p "${LOG_DIR}"

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR  python3 not on PATH" >&2
    exit 1
fi

current="$(crontab -l 2>/dev/null || true)"

if echo "${current}" | grep -qF "${MARKER}"; then
    echo "Cron entries already installed. Nothing to do."
    echo "Remove the marker block in \`crontab -e\` first if you want to reinstall."
    exit 0
fi

new_block=$(cat <<BLOCK

${MARKER}
# 02:30 — nightly knowledge snapshot; keeps TEACHER_SNAPSHOT_KEEP most recent (default 14)
30 2 * * * /usr/bin/env python3 ${ASI_DIR}/export-snapshot.py >> ${LOG_DIR}/snapshot.log 2>&1

# 08:00 — daily anomaly scan; exit code is non-zero when findings exist
0 8 * * * /usr/bin/env python3 ${ASI_DIR}/detect-anomalies.py >> ${LOG_DIR}/anomaly.log 2>&1
# ═══════════════════════════════════════════════════════
BLOCK
)

tmp="$(mktemp)"
{
    printf '%s\n' "${current}"
    printf '%s\n' "${new_block}"
} > "${tmp}"

crontab "${tmp}"
rm -f "${tmp}"

echo "Installed:"
echo "  nightly snapshot   02:30  → ${LOG_DIR}/snapshot.log"
echo "  daily anomaly scan 08:00  → ${LOG_DIR}/anomaly.log"
echo
echo "Verify with:  crontab -l | grep teacher-snapshot -A 4"
echo "Logs roll via the standard cron MAILTO path; check ${LOG_DIR}/ for stdout."
