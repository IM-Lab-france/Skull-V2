#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${SKULL_DEPLOY_REPO_URL:-https://github.com/IM-Lab-france/Skull-V2.git}"
REF="${SKULL_DEPLOY_REF:-}"
TARGET="${SKULL_DEPLOY_TARGET:-/opt/skull-candidate}"
STATE_DIR="${SKULL_DEPLOY_STATE_DIR:-/var/lib/skull/deploy}"
RELEASES_DIR="$STATE_DIR/releases"
CURRENT_LINK="$STATE_DIR/current"
SERVICE="${SKULL_DEPLOY_SERVICE:-skull-candidate.service}"
HEALTH_BASE="${SKULL_DEPLOY_HEALTH_BASE:-http://127.0.0.1:5000}"
KEEP_RELEASES="${SKULL_DEPLOY_KEEP_RELEASES:-3}"

log() { printf '%s\n' "SKULL_DEPLOY: $*"; }
fail() { log "FAILED: $*" >&2; exit 1; }
require_root() { [ "$(id -u)" -eq 0 ] || fail root_required; }
require_ref() {
  [ -n "$REF" ] || fail 'SKULL_DEPLOY_REF must be an immutable commit or tag'
  case "$REF" in -*|*..*|*/*) fail invalid_ref ;; esac
}
healthcheck() {
  systemctl is-active --quiet "$SERVICE" || return 1
  curl --fail --silent --show-error --max-time 5 "$HEALTH_BASE/health/live" >/dev/null
  curl --fail --silent --show-error --max-time 5 "$HEALTH_BASE/health/ready" >/dev/null
  curl --fail --silent --show-error --max-time 5 "$HEALTH_BASE/status" >/dev/null
}

require_root
require_ref
mkdir -p "$RELEASES_DIR" "$STATE_DIR"
exec 9>"$STATE_DIR/deploy.lock"
flock -n 9 || fail deployment_already_running

stamp=$(date -u +%Y%m%d-%H%M%S)
stage=$(mktemp -d "$STATE_DIR/.stage.XXXXXX")
release="$RELEASES_DIR/$stamp-$REF"
previous_target=""
trap 'rm -rf "$stage" "$TARGET.new"' EXIT

git init --quiet "$stage/source"
git -C "$stage/source" remote add origin "$REPO_URL"
git -C "$stage/source" fetch --quiet --depth 1 origin "$REF"
commit=$(git -C "$stage/source" rev-parse FETCH_HEAD)
[ -n "$commit" ] || fail commit_resolution_failed
git -C "$stage/source" archive "$commit" | tar -x -C "$stage"

if [ -n "${SKULL_DEPLOY_EXPECTED_COMMIT:-}" ] && [ "$commit" != "$SKULL_DEPLOY_EXPECTED_COMMIT" ]; then fail commit_mismatch; fi
test -f "$stage/web_app.py" || fail release_missing_web_app
test -f "$stage/templates/index.html" || fail release_missing_template
test -f "$stage/static/app.js" || fail release_missing_app_js
test -f "$stage/static/style.css" || fail release_missing_style

mv "$stage" "$release"
stage=''
if [ -e "$TARGET" ] || [ -L "$TARGET" ]; then previous_target=$(readlink -f "$TARGET" || true); fi
ln -sfn "$release" "$TARGET.new"
mv -Tf "$TARGET.new" "$TARGET"
systemctl restart "$SERVICE"

healthy=false
for _ in $(seq 1 30); do
  if healthcheck; then healthy=true; break; fi
  sleep 1
done
if [ "$healthy" != true ]; then
  log healthcheck_failed_rolling_back
  if [ -n "$previous_target" ] && [ -d "$previous_target" ]; then
    ln -sfn "$previous_target" "$TARGET.new"
    mv -Tf "$TARGET.new" "$TARGET"
    systemctl restart "$SERVICE" || true
  fi
  fail healthcheck_failed_rollback_done
fi

ln -sfn "$release" "$CURRENT_LINK"
find "$RELEASES_DIR" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' | sort -nr | tail -n +$((KEEP_RELEASES + 1)) | cut -d' ' -f2- | xargs -r rm -rf
printf 'SKULL_DEPLOY_OK ref=%s commit=%s release=%s previous=%s\n' "$REF" "$commit" "$release" "$previous_target"
