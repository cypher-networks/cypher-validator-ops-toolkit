# Cypher AI Ops

Cypher AI Ops is a local Discord operations assistant for Cypher Networks validator infrastructure. It runs on an Ubuntu server, talks to a local Ollama model, watches monitor alerts in Discord, reads whitelisted local monitor state/log files, and performs only pre-approved read-only health checks.

This is designed for local LAN/server operations, not public SaaS.

## Safety model

- No arbitrary shell command execution from Discord.
- No `sudo` commands.
- No package installs, restarts, deletes, ownership changes, or file moves from Discord.
- Only pre-approved read-only commands are available in code.
- The bot does not read `.env`, private keys, seed phrases, wallet files, validator keystores, SSH keys, or API key files.
- Monitor context is limited to whitelisted files such as `/home/YOUR_USER/*_monitor.log`, `/home/YOUR_USER/*_status.txt`, and copied read-only files under `REMOTE_STATE_DIR`.
- Knowledge library context is limited to the configured runbook/doc folder.
- Chat context stores only recent redacted allowed-channel messages, capped by `CHAT_CONTEXT_MAX_MESSAGES`.
- Local sync probes only call localhost APIs and do not use secret-bearing URLs.
- URL lookup, when enabled, fetches only explicit public `http(s)` URLs, blocks private/local/reserved network targets, and caps response size.
- Discord replies are concise and split below message limits.
- If elevated privileges are needed, the bot should tell the operator what to run manually.

## Commands

```text
!ops help
!ops ping
!ops ask <question>
!ops health
!ops rawhealth
!ops disk
!ops services
!ops gpu
!ops network
!ops monitors
!ops monitor <name>
!ops status [name]
!ops explain
!ops sync
!ops url <url>
!ops search <problem>
!ops library <query>
!ops docs <query>
```

Known monitor names:

```text
aztec
babylon
cardano
cx
espresso
ethereum
starknet
```

## Compact morning summary

Set the channel where Cypher AI Ops should post the one-message morning summary:

```bash
CYPHER_AI_MONITOR_CHANNEL_ID=123456789012345678
AUTO_DAILY_DIGEST=true
DAILY_DIGEST_HOUR_EST=5
DAILY_DIGEST_MINUTE_EST=10
```

The validators post daily reports at about 5am Eastern. The bot captures those daily report embeds as they arrive, does not reply to each one, and posts one compact summary to `CYPHER_AI_MONITOR_CHANNEL_ID` after 5:10am Eastern by default.

Manual test command:

```text
!ops digest
```

Preferred Discord slash commands:

```text
/ops ping
/ops status monitor:<name>
/ops ask question:<text> monitor:<optional>
/ops remember note:<text> monitor:<optional> expires:<optional>
/ops notes monitor:<optional>
/ops forget note_id:<id>
/ops library query:<text>
```

The `monitor` field autocompletes known monitor names. Ops notes are persisted locally under `OPS_NOTES_PATH` and are included in future alert/status context. Use notes for maintenance state, for example:

```text
/ops remember monitor:ethereum note:lighthouse intentionally down while reth syncs expires:24h
```

This posts a summary of daily reports captured since the bot started today. The bot does not back-read old messages after restart.

## Passive alert triage

When `AUTO_RESPOND_TO_ALERTS=true`, the bot watches the allowed Discord channel for monitor webhook messages that look like alerts, such as red/yellow messages containing terms like down, stuck, warning, unhealthy, no peers, low balance, high disk, or API down.

When an alert is detected, the bot:

1. Extracts the Discord message and embed fields.
2. Infers the monitor type, for example `aztec`, `espresso`, or `ethereum`.
3. Reads only the matching whitelisted local state/log files if present.
4. Searches the local AI lookup library for matching runbook/config snippets.
5. Sends alert, live state, and matching docs/config context to Ollama.
6. Replies with likely cause and safe commands to run manually.

A cooldown prevents repeated noisy alerts from causing reply spam.

Use this to explain the latest alert seen in the current channel:

```text
!ops explain
```

Use this for a direct monitor status summary:

```text
!ops status
!ops status ethereum
!ops status cardano
```

## Local monitor context

The bot knows these monitor artifacts from the server scripts:

```text
aztec     /home/YOUR_USER/aztec_validator_status.txt      /home/YOUR_USER/aztec_monitor.log
babylon   /home/YOUR_USER/babylon_validator_status.txt    /home/YOUR_USER/babylon_monitor.log
cardano   /home/YOUR_USER/cardano_validator_status.txt    /home/YOUR_USER/cardano_monitor.log
canopy    /home/YOUR_USER/canopy_validator_status.txt     /home/YOUR_USER/canopy_monitor.log
cx        /home/YOUR_USER/cx_validator_status.txt         /home/YOUR_USER/cx_monitor.log
espresso  /home/YOUR_USER/espresso_validator_status.txt   /home/YOUR_USER/espresso_monitor.log
ethereum  /home/YOUR_USER/eth_node_status.txt             /home/YOUR_USER/eth_monitor.log
starknet  /home/YOUR_USER/starknet_validator_status.txt   no local log file configured
```

When the bot runs on the monitoring workstation instead of the validator host, it checks the expected local path first, then falls back to the newest matching file under:

```bash
REMOTE_STATE_DIR=remote-state
```

On the deployed bot this should usually be:

```bash
REMOTE_STATE_DIR=/opt/cypher-ai-ops/remote-state
```

Recommended layout:

```text
/opt/cypher-ai-ops/remote-state/ethnode/eth_node_status.txt
/opt/cypher-ai-ops/remote-state/ethnode/eth_monitor.log
/opt/cypher-ai-ops/remote-state/towerofterror/babylon_monitor.log
/opt/cypher-ai-ops/remote-state/towerofterror/cardano_monitor.log
```

The fallback is read-only. It does not SSH into validator hosts or run recovery commands.

Use:

```text
!ops monitors
!ops monitor espresso
!ops monitor ethereum
```

To push state from a validator host to the bot host:

```bash
BOT_HOST=validator@your-validator-host BOT_DIR=/opt/cypher-ai-ops /home/YOUR_USER/push-monitor-state.sh
```

If a monitor writes under `/root`, such as Canopy on `Cypher-Server-01`, run the push script as root or with sudo. The script scans `/home/YOUR_USER` and `/root` by default when readable:

```bash
sudo env BOT_HOST=validator@your-validator-host BOT_DIR=/opt/cypher-ai-ops /home/YOUR_USER/push-monitor-state.sh
```

Cron example on each validator host:

```cron
*/2 * * * * BOT_HOST=validator@your-validator-host BOT_DIR=/opt/cypher-ai-ops /home/YOUR_USER/push-monitor-state.sh >/tmp/push-monitor-state.log 2>&1
```

Copy only monitor logs/status files. Do not copy `.env`, keys, wallet files, or service secrets into `remote-state`.

## Local sync probes

`!ops sync` checks localhost-only endpoints. Unreachable endpoints are expected if the bot is not running on that specific validator host.

Current probes include:

```text
Reth: eth_syncing, eth_blockNumber, net_peerCount on 127.0.0.1:8545
Lighthouse: health, syncing, peer_count on 127.0.0.1:5052
Aztec: node_getBlockNumber, node_getProvenBlockNumber on 127.0.0.1:8080
Espresso: status API block-height, time-since-last-decide, success-rate on 127.0.0.1
Starknet Pathfinder: starknet_syncing, starknet_blockNumber on 127.0.0.1:9545
```

## URL lookup

URL lookup is opt-in. It fetches only explicit `http://` or `https://` URLs supplied by an allowed Discord user. It blocks localhost, private IP, link-local, multicast, reserved, and unresolved targets, caps response size, and does not execute JavaScript or browse interactively.

Enable it:

```bash
ENABLE_URL_LOOKUP=true
URL_LOOKUP_TIMEOUT_SECONDS=8
URL_LOOKUP_MAX_BYTES=120000
```

Optional domain allowlist:

```bash
URL_LOOKUP_ALLOWED_DOMAINS=docs.espressosys.com,docs.babylonlabs.io,docs.aztec.network
```

Use:

```text
!ops url https://docs.example.org/page
!ops ask based on https://docs.example.org/page what changed about the endpoint?
```

Treat fetched pages as untrusted reference material. Do not paste secret-bearing URLs.

## Problem search

Problem search is opt-in and intended for symptom-based troubleshooting against configured docs/GitHub sources. It expects a SearXNG-compatible search endpoint.

Enable it:

```bash
ENABLE_PROBLEM_SEARCH=true
PROBLEM_SEARCH_URL=http://127.0.0.1:8080
PROBLEM_SEARCH_MAX_RESULTS=3
PROBLEM_SEARCH_FETCH_PAGES=true
```

Restrict searchable domains:

```bash
PROBLEM_SEARCH_ALLOWED_DOMAINS=github.com,docs.github.com,gitbook.io,docs.espressosys.com,docs.babylonlabs.io,docs.aztec.network,docs.starknet.io,docs.cardano.org,ethereum.org,lighthouse-book.sigmaprime.io,reth.rs
```

Use:

```text
!ops search pathfinder attestation missed epoch
!ops search reth eth_getLogs archive history query fails
!ops search espresso failed fetching leaf chain from every peer
```

When enabled, passive alert triage and incident-shaped `!ops ask` questions can also include problem-search context. External pages are treated as untrusted reference material.

## AI lookup library

Put runbooks and reference docs here by default:

```text
../ai-lookup-library
```

From this project, that resolves to:

```text
../ai-lookup-library
```

Supported files include Markdown, text, JSON, YAML/Compose, TOML, env examples, conf files, and systemd service snapshots.

Enable/configure:

```bash
KNOWLEDGE_LIBRARY_DIR=../ai-lookup-library
KNOWLEDGE_MAX_SNIPPETS=5
KNOWLEDGE_MAX_CHARS=7000
```

Use:

```text
!ops library espresso finality
!ops docs babylon rpc
!ops ask what does the espresso runbook say about stuck height?
```

The bot does not dump the whole library into Ollama. It keyword-ranks small snippets and sends only the top matches with the operator question.

The same library search is also used during passive alert triage, so runbooks and sanitized config snapshots become part of normal alert handling.

## Chat context

Small models handle chat context best as a short rolling window, not a full transcript. When enabled, the bot stores recent redacted messages from allowed channels under `data/chat-context/` and includes a small recent-context block in `!ops ask`.

```bash
CHAT_CONTEXT_ENABLED=true
CHAT_CONTEXT_DIR=data/chat-context
CHAT_CONTEXT_MAX_MESSAGES=30
```

The `data/` directory is git-ignored. Do not paste secrets into Discord; redaction is a guardrail, not a vault.

## Discord bot setup

1. Go to the Discord Developer Portal: https://discord.com/developers/applications
2. Create a new application, for example `Cypher AI Ops`.
3. Open **Bot** and create/reset the bot token.
4. Copy the bot token into `.env` as `DISCORD_BOT_TOKEN`.
5. Enable **Message Content Intent** under the bot settings. Prefix commands and passive alert watching require this.
6. Open **OAuth2 -> URL Generator**.
7. Select scopes:
   - `bot`
   - `applications.commands`
8. Select bot permissions:
   - `View Channels`
   - `Read Message History`
   - `Send Messages`
   - `Embed Links` optional, useful later
9. Open the generated invite URL and add the bot to the Cypher Networks Discord server.
10. Copy each alert channel ID and put them in `DISCORD_ALLOWED_CHANNEL_IDS`.

To copy a channel ID, enable Discord Developer Mode, right-click the channel, and choose **Copy Channel ID**.

Single-channel mode is still supported:

```bash
DISCORD_ALLOWED_CHANNEL_ID=123456789012345678
```

Preferred multi-channel mode:

```bash
DISCORD_ALLOWED_CHANNEL_IDS=123456789012345678,234567890123456789,345678901234567890
```

Optional channel-to-monitor mapping:

```bash
DISCORD_CHANNEL_MAP=123456789012345678:espresso,234567890123456789:aztec,345678901234567890:ethereum
```

When a mapped channel receives an alert, the bot uses the mapped monitor context instead of guessing from alert text.

## Ollama requirement

Ollama should be running locally with the selected model installed:

```bash
ollama list
ollama pull qwen2.5-coder:7b
```

Test Ollama directly:

```bash
curl http://localhost:11434/api/generate \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen2.5-coder:7b","prompt":"Say ready in one word.","stream":false}'
```

## Install

Use Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
python bot.py
```

Example `.env`:

```bash
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_ALLOWED_CHANNEL_IDS=123456789012345678,234567890123456789
DISCORD_CHANNEL_MAP=123456789012345678:espresso,234567890123456789:aztec
DISCORD_GUILD_ID=
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:7b
AUTO_RESPOND_TO_ALERTS=true
ALERT_RESPONSE_COOLDOWN_SECONDS=60
CYPHER_AI_MONITOR_CHANNEL_ID=123456789012345678
AUTO_DAILY_DIGEST=true
DAILY_DIGEST_HOUR_EST=5
DAILY_DIGEST_MINUTE_EST=10
ENABLE_URL_LOOKUP=false
KNOWLEDGE_LIBRARY_DIR=../ai-lookup-library
REMOTE_STATE_DIR=remote-state
OPS_NOTES_PATH=data/ops-notes.json
CHAT_CONTEXT_ENABLED=true
ENABLE_PROBLEM_SEARCH=false
```

## Systemd service

The included service assumes the project lives at `/opt/cypher-ai-ops` and contains a placeholder Linux user that must be edited before install. If you install it somewhere else or use another Linux user, edit `systemd/cypher-ai-ops.service` before copying it.

The easiest boot-start install is:

```bash
cd /path/to/cypher-networks-ai/cypher-ai-ops
sudo bash install-systemd.sh
```

That script:

- copies the bot to `/opt/cypher-ai-ops`
- copies `../ai-lookup-library` to `/opt/ai-lookup-library`
- creates `/opt/cypher-ai-ops/.venv`
- installs `requirements.txt`
- points `KNOWLEDGE_LIBRARY_DIR` at `/opt/ai-lookup-library`
- enables and starts `cypher-ai-ops.service`

If using the install script, set the Linux user explicitly when needed:

```bash
sudo APP_USER="$USER" APP_GROUP="$USER" bash install-systemd.sh
```

Manual service install:

```bash
sudo cp systemd/cypher-ai-ops.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cypher-ai-ops
sudo systemctl status cypher-ai-ops --no-pager
journalctl -u cypher-ai-ops -f
```

## Check logs

```bash
journalctl -u cypher-ai-ops -n 100 --no-pager
journalctl -u cypher-ai-ops -f
```

## Allowed read-only commands

The bot only runs these command lists through `subprocess.run(..., shell=False)`:

```text
hostname
date
uptime
df -h
free -h
lscpu
lsblk
ip a
ip route
ss -tulpn
systemctl --failed --no-pager
nvidia-smi
docker ps, only if Docker exists
journalctl -p 3 -n 50 --no-pager
```

## Not allowed

The bot does not run:

```text
rm
mv
cp
chmod
chown
sudo
apt
docker stop/start/restart
systemctl restart/stop/start
anything user-supplied as a command
```

## Data to give the assistant over time

Best first knowledge sources:

- Existing monitor scripts and their alert meanings.
- Local runbooks for each host: Espresso, Ethereum/Reth, Aztec, Starknet, Cardano, Babylon, CX.
- Known incident notes: symptoms, root cause, exact safe checks, final fix.
- Public docs snapshots for each network/client.
- A small host inventory with non-secret service names, ports, log paths, and expected healthy states.

Avoid giving it secrets, private keys, wallet files, validator keystores, `.env` files, SSH private keys, or API-token-bearing URLs.

## MCP guidance

For v1, do not give the Discord bot broad MCP tools or remote shell access. The safer path is:

1. Local whitelisted file/log context.
2. Localhost-only HTTP health probes.
3. Optional read-only Prometheus/Grafana query access later.
4. Optional read-only Git/runbook/doc search later.

Avoid MCP servers that can execute shell commands, write files, restart services, modify Docker containers, or read arbitrary filesystem paths from Discord.

## Operational notes

- Keep this bot in a private ops channel.
- Do not paste secrets into Discord prompts.
- Treat LLM output as operator guidance, not automatic remediation.
- Keep validator keys and seed material off this workflow.
- Prefer running this on a monitoring workstation or local server with read-only visibility, not directly on critical validator hosts unless that is intentional.


