#!/usr/bin/env bash
# Fetch a fresh project snapshot, then hand off to the Python installer.
set -Eeuo pipefail
REPOSITORY='TIR3D4/marzban-panel-tunnel'
REF="${PANEL_TUNNEL_REF:-main}"
[[ "$REF" =~ ^[a-zA-Z0-9._-]+$ ]] || { echo 'Invalid ref' >&2; exit 1; }
command -v curl >/dev/null || { echo 'Install curl first: apt-get update && apt-get install -y curl' >&2; exit 1; }
command -v python3 >/dev/null || { echo 'Install python3 first: apt-get update && apt-get install -y python3' >&2; exit 1; }
[[ "$EUID" -eq 0 ]] || { echo 'Run this installer with sudo or as root.' >&2; exit 1; }
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT
curl --fail --show-error --silent --location --retry 2 --connect-timeout 15 --max-time 120 \
  "https://codeload.github.com/$REPOSITORY/tar.gz/$REF" -o "$work_dir/project.tar.gz"
mkdir "$work_dir/source"
tar -xzf "$work_dir/project.tar.gz" --strip-components=1 -C "$work_dir/source"
case "${1:-}" in
  iran|foreign) python3 "$work_dir/source/manage.py" install --role "$1" ;;
  --resume) python3 "$work_dir/source/manage.py" install --resume ;;
  --update) python3 "$work_dir/source/manage.py" update ;;
  '') python3 "$work_dir/source/manage.py" install ;;
  *) echo 'Usage: install.sh [iran|foreign|--resume|--update]' >&2; exit 1 ;;
esac
