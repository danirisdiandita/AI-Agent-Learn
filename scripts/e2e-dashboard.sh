#!/usr/bin/env bash
# End-to-end test of the dashboard against the real Django backend, in Chrome.
#   scripts/e2e-dashboard.sh [screenshot-dir]
# Set COLOR_SCHEME=light or COLOR_SCHEME=dark to take the screenshots in that theme.
# Creates a throwaway database with two users and their saved chats (scripts/e2e/seed-chats.py), starts Django and
# the dashboard on spare ports, and removes everything it created, even when a step fails. It runs in two parts:
# 1. scripts/e2e/signin.mjs, with no OpenRouter key, so sending a message checks the error path.
# 2. scripts/e2e/calendar.mjs, after restarting Django with AGENTS_SCRIPTED_MODEL=1, which the DEBUG dev server
#    honors with a scripted model (engine/testing.py). It declines a calendar event the seed left waiting for approval.
# Neither part calls a model or Google.
# Needs: PostgreSQL reachable with the credentials in .env, backend/.venv, dashboard/node_modules, Chrome.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
out="${1:-$(mktemp -d)}"
mkdir -p "$out"

[[ -f "$root/.env" ]] && { set -a; . "$root/.env"; set +a; }
export POSTGRES_DB="nextsci_agents_e2e_$$"
# Set, even when empty, so Django does not read the key from .env.
export OPENROUTER_API_KEY=""
email="e2e-admin@example.com"
password="e2e-$$-agent-test"
calendar_email="e2e-calendar@example.com"
# Set E2E_API_PORT, E2E_DASH_PORT, or E2E_CDP_PORT when another run holds the default port.
api_port=${E2E_API_PORT:-8777} dash_port=${E2E_DASH_PORT:-5199} cdp_port=${E2E_CDP_PORT:-9333}
chrome="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
profile="$(mktemp -d)"
pids=()

cleanup() {
  for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
  sleep 1
  PGPASSWORD="${POSTGRES_PASSWORD:-}" dropdb --if-exists -h "${POSTGRES_HOST:-localhost}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER:-postgres}" "$POSTGRES_DB" 2>/dev/null || true
  rm -rf "$profile"
}
trap cleanup EXIT

for port in $api_port $dash_port $cdp_port; do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then echo "port $port is busy; stop what uses it and retry" >&2; exit 1; fi
done

free_port() {
  for _ in $(seq 40); do lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1 || return 0; sleep 0.25; done
  echo "port $1 stayed busy" >&2; return 1
}

wait_for() {
  for _ in $(seq 60); do curl -s -o /dev/null "$1" && return 0; sleep 0.5; done
  echo "timed out waiting for $1" >&2; return 1
}

echo "== backend on :$api_port with database $POSTGRES_DB"
PGPASSWORD="${POSTGRES_PASSWORD:-}" createdb -h "${POSTGRES_HOST:-localhost}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER:-postgres}" "$POSTGRES_DB"
cd "$root/backend"
# The seed stores fake Google tokens, which need an encryption key even when .env has none.
export INTEGRATIONS_ENCRYPTION_KEY="${INTEGRATIONS_ENCRYPTION_KEY:-$(.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')}"
.venv/bin/python manage.py migrate -v0
for user in "$email" "$calendar_email"; do
  .venv/bin/python manage.py shell -v0 -c "from django.contrib.auth import get_user_model as g; g().objects.create_user(email='$user', password='$password')"
done
E2E_EMAIL="$email" E2E_CALENDAR_EMAIL="$calendar_email" .venv/bin/python manage.py shell -v0 <"$root/scripts/e2e/seed-chats.py"
# --noreload keeps Django in one process, so killing its pid frees the port for the restart below.
.venv/bin/python manage.py runserver --noreload "$api_port" >"$out/backend.log" 2>&1 &
backend=$!
pids+=($backend)

echo "== dashboard on :$dash_port"
cd "$root/dashboard"
API_PROXY_TARGET="http://localhost:$api_port" npx vite --port "$dash_port" --strictPort >"$out/dashboard.log" 2>&1 &
pids+=($!)

"$chrome" --headless=new --disable-gpu --remote-debugging-port="$cdp_port" --user-data-dir="$profile" about:blank >/dev/null 2>&1 &
pids+=($!)

wait_for "http://localhost:$api_port/admin/login/"
wait_for "http://localhost:$dash_port/"
wait_for "http://localhost:$cdp_port/json/version"

echo "== sign-in flow"
node "$root/scripts/e2e/signin.mjs" "$cdp_port" "http://localhost:$dash_port/" "$out" "$email" "$password"

echo "== tool approval, with the scripted model"
kill "$backend"; free_port "$api_port"
cd "$root/backend"
AGENTS_SCRIPTED_MODEL=1 .venv/bin/python manage.py runserver --noreload "$api_port" >"$out/backend-scripted.log" 2>&1 &
pids+=($!)
wait_for "http://localhost:$api_port/admin/login/"
node "$root/scripts/e2e/calendar.mjs" "$cdp_port" "http://localhost:$dash_port/" "$out" "$calendar_email" "$password"
echo "screenshots and logs: $out"
