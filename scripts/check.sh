#!/usr/bin/env bash
# Verifies every app in the monorepo installs, typechecks, builds, and passes its tests and enforced rules.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"

echo "== docs"
"$root/scripts/check-docs.sh"

echo "== backend"
cd "$root/backend"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements-dev.txt
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/lint-imports --no-cache
.venv/bin/python manage.py test

echo "== dashboard"
cd "$root/dashboard"
npm ci --no-fund --no-audit
npm run lint
npm run build
"$root/scripts/check-design.sh"
"$root/scripts/check-react.sh"

echo "all checks passed"
