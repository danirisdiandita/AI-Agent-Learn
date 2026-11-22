#!/usr/bin/env bash
# Sets up the Google OAuth client for the Google Calendar integration and writes it to .env.
#   scripts/make-oauth-client.sh [project-id]
# The project comes from the argument, then $GOOGLE_CLOUD_PROJECT, then `gcloud config get project`.
# gcloud signs you in, creates the project if it is missing, and enables the Google Calendar API.
# Google offers no CLI or API for a "Web application" OAuth client, so the script opens each Console
# page with the values to enter, then asks for the client ID and secret and saves them.
# Safe to rerun: it replaces the GOOGLE_OAUTH_* values and keeps an existing INTEGRATIONS_ENCRYPTION_KEY.
# ENV_FILE overrides the file it writes (default: .env at the repository root).
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
env_file="${ENV_FILE:-$root/.env}"
scopes="openid, email, https://www.googleapis.com/auth/calendar"

die() { echo "error: $*" >&2; exit 1; }
ask() { local reply; read -r -p "$1 [y/N] " reply; [[ "$reply" == [yY]* ]]; }
open_url() {
  echo "  $1"
  if command -v open >/dev/null; then open "$1"; elif command -v xdg-open >/dev/null; then xdg-open "$1" >/dev/null 2>&1; fi
}
env_value() { [[ -f "$env_file" ]] && sed -n "s/^$1=//p" "$env_file" | tail -1 || true; }
set_env() {
  local tmp; tmp="$(mktemp)"
  [[ -f "$env_file" ]] || : > "$env_file"
  awk -v k="$1" -v v="$2" 'BEGIN { done = 0 } index($0, k "=") == 1 { if (!done) print k "=" v; done = 1; next } { print } END { if (!done) print k "=" v }' "$env_file" > "$tmp"
  cat "$tmp" > "$env_file" && rm -f "$tmp"
}

command -v gcloud >/dev/null || die "gcloud is not installed. Install it from https://cloud.google.com/sdk/docs/install"

echo "== Google account"
account="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | head -1)"
if [[ -z "$account" ]]; then gcloud auth login; account="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -1)"; fi
echo "  signed in as $account"

echo "== Project"
project="${1:-${GOOGLE_CLOUD_PROJECT:-$(gcloud config get project 2>/dev/null || true)}}"
[[ -n "$project" ]] || die "name a project: scripts/make-oauth-client.sh <project-id>"
if ! gcloud projects describe "$project" >/dev/null 2>&1; then
  ask "Project $project does not exist or you cannot see it. Create it?" || die "no project"
  gcloud projects create "$project"
fi
echo "  using $project"

echo "== Google Calendar API"
gcloud services enable calendar-json.googleapis.com --project "$project"
echo "  enabled"

redirect_uri="$(env_value GOOGLE_OAUTH_REDIRECT_URI)"
redirect_uri="${redirect_uri:-http://localhost:5174/api/v1/integrations/google-calendar/callback/}"
console="https://console.cloud.google.com/auth"

echo "== OAuth client (Google Cloud Console; no CLI exists for this step)"
echo "1. Consent screen. Skip it if the project already has one."
echo "   App name: Nextsci Agents. Audience: External."
open_url "$console/overview?project=$project"
read -r -p "   Press Enter when the consent screen exists. "
echo "   Add $account as a test user, so it can connect while the app is in testing."
open_url "$console/audience?project=$project"
read -r -p "   Press Enter when the test user is saved. "
echo "2. Scopes. Add: $scopes"
open_url "$console/scopes?project=$project"
read -r -p "   Press Enter when the scopes are saved. "
echo "3. Client. Application type: Web application. Authorized redirect URI, exactly:"
echo "   $redirect_uri"
command -v pbcopy >/dev/null && printf '%s' "$redirect_uri" | pbcopy && echo "   (copied to the clipboard)"
open_url "$console/clients/create?project=$project"

read -r -p "Client ID: " client_id
[[ "$client_id" =~ ^[0-9]+-[a-z0-9]+\.apps\.googleusercontent\.com$ ]] || die "that is not a Google OAuth client ID (it ends in .apps.googleusercontent.com)"
read -r -s -p "Client secret (hidden): " client_secret; echo
[[ -n "$client_secret" ]] || die "the client secret is empty"

set_env GOOGLE_OAUTH_CLIENT_ID "$client_id"
set_env GOOGLE_OAUTH_CLIENT_SECRET "$client_secret"
set_env GOOGLE_OAUTH_REDIRECT_URI "$redirect_uri"
if [[ -z "$(env_value INTEGRATIONS_ENCRYPTION_KEY)" ]]; then
  # A Fernet key is 32 random bytes in URL-safe base64.
  set_env INTEGRATIONS_ENCRYPTION_KEY "$(openssl rand -base64 32 | tr '+/' '-_')"
  echo "  generated INTEGRATIONS_ENCRYPTION_KEY"
fi
echo "== Saved to $env_file. Restart the backend, then connect Google Calendar on the Integrations screen."
