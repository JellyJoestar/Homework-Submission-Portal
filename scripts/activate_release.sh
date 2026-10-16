#!/usr/bin/env bash
set -Eeuo pipefail
umask 027

# This script must run as the Flask runtime account.
if [[ "$(id -un)" != "ubuntu" ]]; then
  echo "ERROR: Activation requires the ubuntu account" >&2
  exit 1
fi

if [[ "$#" -ne 1 || ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR: Expected one full Git commit SHA" >&2
  exit 1
fi

sha="$1"
root="/opt/homework-portal"
release="$root/releases/$sha"
venv="/home/ubuntu/.venvs/homework-portal"
pm2="/usr/local/bin/pm2"

# Validate the target release and its dependencies.
test -r "$release/DEPLOYED_COMMIT"
test "$(cat "$release/DEPLOYED_COMMIT")" = "$sha"
test -r "$release/app.py"
test -r "$release/requirements.txt"
test -r "$release/.env"
test -x "$venv/bin/gunicorn"

# Validate shared NFS storage before restarting Flask.
test "$(findmnt -rn -M "$root/uploads" -o FSTYPE)" = "nfs4"
test -d "$root/uploads/resources"
test -d "$root/uploads/submissions"

# Identify the previous release from the running PM2 process.
running_pid="$("$pm2" pid homework-portal)"

if [[ ! "$running_pid" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: PM2 application is not running" >&2
  exit 1
fi

previous="$(readlink -f "/proc/$running_pid/cwd" 2>/dev/null || true)"
previous_sha="${previous##*/}"

if [[ ! "$previous_sha" =~ ^[0-9a-f]{40}$ ||
      "$previous" != "$root/releases/$previous_sha" ]]; then
  echo "ERROR: Invalid previous release directory" >&2
  exit 1
fi

test -r "$previous/DEPLOYED_COMMIT"
test "$(cat "$previous/DEPLOYED_COMMIT")" = "$previous_sha"

# Confirm that Gunicorn is serving the specified release.
check_health() {
  local expected="$1"
  local pid cwd status

  for attempt in {1..12}; do
    pid="$("$pm2" pid homework-portal)"

    if [[ "$pid" =~ ^[1-9][0-9]*$ ]]; then
      cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
      status="$(curl -sS --max-time 3 -o /dev/null \
        -w '%{http_code}' http://127.0.0.1/login 2>/dev/null || true)"

      if [[ "$cwd" == "$expected" && "$status" == "200" ]]; then
        return 0
      fi
    fi

    sleep 1
  done

  return 1
}

# Start Gunicorn with an explicit release working directory.
start_release() {
  local target="$1"

  if "$pm2" describe homework-portal >/dev/null 2>&1; then
    "$pm2" delete homework-portal || return 1
  fi

  "$pm2" start "$venv/bin/gunicorn" \
    --name homework-portal \
    --interpreter none \
    --cwd "$target" \
    -- \
    --bind 127.0.0.1:8000 \
    --workers 2 \
    --timeout 30 \
    --access-logfile - \
    --error-logfile - \
    app:app || return 1

  check_health "$target"
}

# Repeating an already active deployment should be safe.
if [[ "$previous" == "$release" ]]; then
  check_health "$release"
  echo "Release already active: $sha"
  exit 0
fi

echo "Activating release: $sha"

if start_release "$release" && "$pm2" save; then
  echo "Application activation: PASS"
  echo "Running release: $sha"
  exit 0
fi

# Restore the last recorded working release if activation fails.
echo "ERROR: Activation failed; attempting rollback" >&2

if start_release "$previous" && "$pm2" save; then
  echo "Previous release restored: $previous_sha" >&2
else
  echo "CRITICAL: Automatic rollback failed" >&2
fi

exit 1