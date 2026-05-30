#!/bin/bash
set -e

OPTIONS=/data/options.json

# Helper: read a key from options.json; returns empty string if missing/null
get_opt() {
    jq --raw-output ".${1} // empty" "${OPTIONS}" 2>/dev/null || true
}

# Export personal info as env vars (the Flask app and bots read these)
export USER_FIRST_NAME=$(get_opt first_name)
export USER_LAST_NAME=$(get_opt last_name)
export USER_CITY=$(get_opt city)
export USER_STATE=$(get_opt state)
export USER_STATE_FULL=$(get_opt state_full)
export USER_EMAIL=$(get_opt email)
export USER_PHONE=$(get_opt phone)
export WEB_PASSWORD=$(get_opt web_password)

# Always headless in the container
export HEADLESS="true"
export PORT="8099"

# Secret key: use configured value, or load/generate a persistent one.
# We store the auto-generated key in /data so it survives addon restarts.
SECRET=$(get_opt secret_key)
if [ -z "${SECRET}" ]; then
    KEY_FILE=/data/.secret_key
    if [ -f "${KEY_FILE}" ]; then
        SECRET=$(cat "${KEY_FILE}")
    else
        SECRET=$(cat /proc/sys/kernel/random/uuid 2>/dev/null | tr -d '-')
        printf '%s' "${SECRET}" > "${KEY_FILE}"
        chmod 600 "${KEY_FILE}"
    fi
fi
export SECRET_KEY="${SECRET}"

echo "[Data Removal] Starting addon on port 8099..."

cd /app
exec python3 app.py
