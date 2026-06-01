#!/usr/bin/env bash
set -euo pipefail

# Push read-only monitor state/log files from a validator host to the bot host.
# Example:
# BOT_HOST=validator@your-validator-host BOT_DIR=/opt/cypher-ai-ops ./push-monitor-state.sh

BOT_HOST="${BOT_HOST:-}"
BOT_DIR="${BOT_DIR:-/opt/cypher-ai-ops}"
SOURCE_DIRS_RAW="${SOURCE_DIRS:-${SOURCE_DIR:-$HOME /root}}"
HOST_LABEL="${HOST_LABEL:-$(hostname -s)}"
SSH_CMD_RAW="${RSYNC_RSH:-ssh}"
read -r -a SSH_CMD <<< "$SSH_CMD_RAW"

if [[ -z "$BOT_HOST" ]]; then
  echo "BOT_HOST is required, for example: BOT_HOST=validator@your-validator-host" >&2
  exit 2
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync is required" >&2
  exit 2
fi

if ! command -v ssh >/dev/null 2>&1; then
  echo "ssh is required" >&2
  exit 2
fi

shopt -s nullglob
files=()
read -r -a source_dirs <<< "$SOURCE_DIRS_RAW"
for source_dir in "${source_dirs[@]}"; do
  if [[ ! -d "$source_dir" || ! -r "$source_dir" ]]; then
    continue
  fi
  candidates=(
      "$source_dir"/cosmos_mainnet_monitor.log
      "$source_dir"/cosmos_mainnet_status.txt
      "$source_dir"/cosmos_mainnet_gov_monitor.log
      "$source_dir"/cosmos_mainnet_gov_status.txt
      "$source_dir"/cosmos_testnet_monitor.log
      "$source_dir"/cosmos_testnet_status.txt
      "$source_dir"/cosmos_testnet_gov_monitor.log
      "$source_dir"/cosmos_testnet_gov_status.txt
    )
  for candidate in "${candidates[@]}"; do
    [[ -f "$candidate" ]] && files+=("$candidate")
  done
done

if (( ${#files[@]} == 0 )); then
  echo "No monitor files found in: $SOURCE_DIRS_RAW" >&2
  exit 1
fi

remote_dir="$BOT_DIR/remote-state/$HOST_LABEL"
"${SSH_CMD[@]}" "$BOT_HOST" "mkdir -p '$remote_dir'"
rsync -a "${files[@]}" "$BOT_HOST:$remote_dir/"
echo "Pushed ${#files[@]} monitor files to $BOT_HOST:$remote_dir"
