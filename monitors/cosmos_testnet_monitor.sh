#!/bin/bash

# Cosmos Hub provider testnet validator monitor.
# Uses the shared $HOME/.validator-monitor.env pattern.

[ -f "$HOME/.validator-monitor.env" ] && source "$HOME/.validator-monitor.env"

DISCORD_WEBHOOK="${COSMOS_TESTNET_DISCORD_WEBHOOK_URL:-${COSMOS_DISCORD_WEBHOOK_URL:-${DISCORD_WEBHOOK:-REPLACE_WITH_DISCORD_WEBHOOK}}}"
STATE_FILE="${COSMOS_TESTNET_STATE_FILE:-$HOME/cosmos_testnet_status.txt}"
LOG_FILE="${COSMOS_TESTNET_LOG_FILE:-$HOME/cosmos_testnet_monitor.log}"

CHAIN_ID="${COSMOS_TESTNET_CHAIN_ID:-provider}"
SERVICE_NAME="${COSMOS_TESTNET_SERVICE:-gaiad}"
GAIAD_BIN="${COSMOS_TESTNET_BIN:-$HOME/go/bin/gaiad}"
GAIA_HOME="${COSMOS_TESTNET_HOME:-$HOME/.gaia}"
RPC_URL="${COSMOS_TESTNET_RPC:-http://127.0.0.1:26657}"
NODE_URL="${COSMOS_TESTNET_NODE:-tcp://127.0.0.1:26657}"
QUERY_NODE="${COSMOS_TESTNET_QUERY_NODE:-$NODE_URL}"
DATA_PATH="${COSMOS_TESTNET_DATA_PATH:-$GAIA_HOME/data}"

VALIDATOR_OPERATOR="${COSMOS_TESTNET_VALOPER:-REPLACE_WITH_TESTNET_VALOPER}"
WALLET_ADDRESS="${COSMOS_TESTNET_WALLET_ADDRESS:-REPLACE_WITH_TESTNET_WALLET_ADDRESS}"
VALCONS="${COSMOS_TESTNET_VALCONS:-REPLACE_WITH_TESTNET_VALCONS}"
MIN_PEERS="${COSMOS_TESTNET_MIN_PEERS:-5}"
STUCK_CHECKS="${COSMOS_TESTNET_STUCK_CHECKS:-6}"
LOW_BALANCE_UATOM="${COSMOS_TESTNET_LOW_BALANCE_UATOM:-500000}"
MISSED_BLOCK_WARN_INCREASE="${COSMOS_TESTNET_WARN_MISSED_INCREASE:-true}"
MAX_MISSED_BLOCKS="${COSMOS_TESTNET_MAX_MISSED_BLOCKS:-5}"

TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S UTC")
HOSTNAME=$(hostname)

COLOR_RED=15158332
COLOR_GREEN=5763719
COLOR_YELLOW=16776960
COLOR_BLUE=3447003

log_line() {
    echo "[$TIMESTAMP] $1" >> "$LOG_FILE"
}

send_discord() {
    local title="$1"
    local description="$2"
    local color="$3"
    local fields="$4"

    if [ -z "$DISCORD_WEBHOOK" ] || [ "$DISCORD_WEBHOOK" = "REPLACE_WITH_DISCORD_WEBHOOK" ]; then
        log_line "DISCORD WEBHOOK NOT CONFIGURED - $title - $description"
        return 0
    fi

    [ -z "$fields" ] && fields="[]"

    local payload
    payload=$(jq -n \
        --arg title "$title" \
        --arg description "$description" \
        --arg footer "${HOSTNAME} - ${TIMESTAMP}" \
        --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)" \
        --argjson color "$color" \
        --argjson fields "$fields" \
        '{embeds:[{title:$title,description:$description,color:$color,footer:{text:$footer},timestamp:$timestamp,fields:$fields}]}' 2>/dev/null)

    if [ -z "$payload" ]; then
        log_line "FAILED TO BUILD DISCORD PAYLOAD - $title"
        return 0
    fi

    curl -s -H "Content-Type: application/json" -X POST -d "$payload" "$DISCORD_WEBHOOK" > /dev/null 2>&1
}

service_running() {
    systemctl is-active --quiet "$1" 2>/dev/null
}

short_addr() {
    local value="$1"
    if [ "${#value}" -gt 18 ]; then
        echo "${value:0:12}...${value: -8}"
    else
        echo "$value"
    fi
}

is_number() {
    [[ "$1" =~ ^[0-9]+$ ]]
}

format_atom() {
    local uatom="$1"
    if is_number "$uatom"; then
        awk -v value="$uatom" 'BEGIN { printf "%.3f ATOM", value / 1000000 }'
    else
        echo "unknown"
    fi
}

get_system_stats() {
    local cpu mem swap disk
    cpu=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//')
    mem=$(free | awk 'NR==2{printf "%.1f", ($3/$2)*100}')
    swap=$(free | awk 'NR==3{if($2>0) printf "%.1f", ($3/$2)*100; else print "0"}')
    disk=$(df -h "$DATA_PATH" 2>/dev/null | awk 'NR==2{print $3"/"$2" ("$5")"}')
    [ -z "$disk" ] && disk=$(df -h / | awk 'NR==2{print $3"/"$2" ("$5")"}')
    echo "CPU: ${cpu}% | RAM: ${mem}% | Swap: ${swap}% | Disk: ${disk}"
}

get_disk_pct() {
    local disk
    disk=$(df "$DATA_PATH" 2>/dev/null | awk 'NR==2{print $5}' | sed 's/%//')
    [ -z "$disk" ] && disk=$(df / | awk 'NR==2{print $5}' | sed 's/%//')
    echo "$disk"
}

query_json() {
    "$GAIAD_BIN" "$@" -o json 2>/dev/null
}

get_balance_uatom() {
    local address="$1"
    query_json query bank balances "$address" --chain-id "$CHAIN_ID" --node "$QUERY_NODE" \
        | jq -r '.balances[]? | select(.denom == "uatom") | .amount' 2>/dev/null \
        | head -1
}

PREV_STATE=$(cat "$STATE_FILE" 2>/dev/null)

if [ ! -x "$GAIAD_BIN" ] && ! command -v "$GAIAD_BIN" > /dev/null 2>&1; then
    if [ "$PREV_STATE" != "BINARY_MISSING" ]; then
        FIELDS="[{\"name\":\"Binary\",\"value\":\"${GAIAD_BIN}\",\"inline\":false},{\"name\":\"Action\",\"value\":\"Check binary path or COSMOS_TESTNET_BIN\",\"inline\":false}]"
        send_discord "Cosmos Testnet Binary Missing" "gaiad testnet binary was not found on ${HOSTNAME}" "$COLOR_RED" "$FIELDS"
        echo "BINARY_MISSING" > "$STATE_FILE"
        log_line "BINARY MISSING - $GAIAD_BIN"
    fi
    exit 1
fi

if ! service_running "$SERVICE_NAME" && ! pgrep -x "$(basename "$GAIAD_BIN")" > /dev/null 2>&1; then
    if [ "$PREV_STATE" != "NODE_DOWN" ]; then
        SYSTEM_STATS=$(get_system_stats)
        FIELDS="[{\"name\":\"Service\",\"value\":\"${SERVICE_NAME} down\",\"inline\":true},{\"name\":\"Action\",\"value\":\"sudo systemctl status ${SERVICE_NAME}\",\"inline\":false},{\"name\":\"System\",\"value\":\"${SYSTEM_STATS}\",\"inline\":false}]"
        send_discord "Cosmos Testnet Node Down" "Provider testnet service is not running on ${HOSTNAME}" "$COLOR_RED" "$FIELDS"
        echo "NODE_DOWN" > "$STATE_FILE"
        log_line "NODE DOWN"
    fi
    exit 1
fi

STATUS_JSON=$(curl -s --max-time 8 "${RPC_URL}/status" 2>/dev/null)
NET_JSON=$(curl -s --max-time 8 "${RPC_URL}/net_info" 2>/dev/null)

if [ -z "$STATUS_JSON" ] || ! echo "$STATUS_JSON" | jq -e '.result.sync_info' > /dev/null 2>&1; then
    if [ "$PREV_STATE" != "RPC_DOWN" ]; then
        SYSTEM_STATS=$(get_system_stats)
        FIELDS="[{\"name\":\"Service\",\"value\":\"Running\",\"inline\":true},{\"name\":\"RPC\",\"value\":\"${RPC_URL} not responding\",\"inline\":true},{\"name\":\"System\",\"value\":\"${SYSTEM_STATS}\",\"inline\":false}]"
        send_discord "Cosmos Testnet RPC Issue" "Testnet service is running but local CometBFT RPC is not responding" "$COLOR_YELLOW" "$FIELDS"
        echo "RPC_DOWN" > "$STATE_FILE"
        log_line "RPC DOWN"
    fi
    exit 0
fi

HEIGHT=$(echo "$STATUS_JSON" | jq -r '.result.sync_info.latest_block_height // "0"')
CATCHING_UP=$(echo "$STATUS_JSON" | jq -r '.result.sync_info.catching_up // "unknown"')
LATEST_TIME=$(echo "$STATUS_JSON" | jq -r '.result.sync_info.latest_block_time // "unknown"')
NODE_MONIKER=$(echo "$STATUS_JSON" | jq -r '.result.node_info.moniker // "unknown"')
NODE_CHAIN_ID=$(echo "$STATUS_JSON" | jq -r '.result.node_info.network // "unknown"')
PEERS=$(echo "$NET_JSON" | jq -r '.result.n_peers // "0"' 2>/dev/null)
[ -z "$PEERS" ] || [ "$PEERS" = "null" ] && PEERS="0"

if [ "$NODE_CHAIN_ID" != "$CHAIN_ID" ]; then
    if [ "$PREV_STATE" != "CHAIN_MISMATCH" ]; then
        SYSTEM_STATS=$(get_system_stats)
        FIELDS="[{\"name\":\"Expected\",\"value\":\"${CHAIN_ID}\",\"inline\":true},{\"name\":\"Actual\",\"value\":\"${NODE_CHAIN_ID}\",\"inline\":true},{\"name\":\"Height\",\"value\":\"${HEIGHT}\",\"inline\":true},{\"name\":\"System\",\"value\":\"${SYSTEM_STATS}\",\"inline\":false}]"
        send_discord "Cosmos Testnet Chain Mismatch" "Local testnet RPC reports the wrong chain ID" "$COLOR_RED" "$FIELDS"
        echo "CHAIN_MISMATCH" > "$STATE_FILE"
        log_line "CHAIN MISMATCH - Expected: $CHAIN_ID | Actual: $NODE_CHAIN_ID"
    fi
    exit 1
fi

VALIDATOR_JSON=$(query_json query staking validator "$VALIDATOR_OPERATOR" --chain-id "$CHAIN_ID" --node "$QUERY_NODE")
VAL_STATUS=$(echo "$VALIDATOR_JSON" | jq -r '.status // .validator.status // "unknown"' 2>/dev/null)
VAL_JAILED=$(echo "$VALIDATOR_JSON" | jq -r '.jailed // .validator.jailed // "unknown"' 2>/dev/null)
VAL_TOKENS=$(echo "$VALIDATOR_JSON" | jq -r '.tokens // .validator.tokens // "unknown"' 2>/dev/null)
COMMISSION_RATE=$(echo "$VALIDATOR_JSON" | jq -r '.commission.commission_rates.rate // .validator.commission.commission_rates.rate // "unknown"' 2>/dev/null)
[ -z "$VAL_STATUS" ] || [ "$VAL_STATUS" = "null" ] && VAL_STATUS="unknown"
[ -z "$VAL_JAILED" ] || [ "$VAL_JAILED" = "null" ] && VAL_JAILED="unknown"

SIGNING_JSON=""
MISSED_BLOCKS="unknown"
TOMBSTONED="unknown"
if [ -n "$VALCONS" ]; then
    SIGNING_JSON=$(query_json query slashing signing-info "$VALCONS" --chain-id "$CHAIN_ID" --node "$QUERY_NODE")
    MISSED_BLOCKS=$(echo "$SIGNING_JSON" | jq -r '.missed_blocks_counter // .val_signing_info.missed_blocks_counter // "unknown"' 2>/dev/null)
    TOMBSTONED=$(echo "$SIGNING_JSON" | jq -r '.tombstoned // .val_signing_info.tombstoned // "unknown"' 2>/dev/null)
fi

WALLET_BALANCE_UATOM=$(get_balance_uatom "$WALLET_ADDRESS")
[ -z "$WALLET_BALANCE_UATOM" ] && WALLET_BALANCE_UATOM="0"
WALLET_BALANCE=$(format_atom "$WALLET_BALANCE_UATOM")
SYSTEM_STATS=$(get_system_stats)

if [ "$TOMBSTONED" = "true" ]; then
    if [ "$PREV_STATE" != "TOMBSTONED" ]; then
        FIELDS="[{\"name\":\"Validator\",\"value\":\"$(short_addr "$VALIDATOR_OPERATOR")\",\"inline\":true},{\"name\":\"Missed Blocks\",\"value\":\"${MISSED_BLOCKS}\",\"inline\":true},{\"name\":\"Height\",\"value\":\"${HEIGHT}\",\"inline\":true},{\"name\":\"System\",\"value\":\"${SYSTEM_STATS}\",\"inline\":false}]"
        send_discord "Cosmos Testnet Validator Tombstoned" "Provider testnet validator is tombstoned" "$COLOR_RED" "$FIELDS"
        echo "TOMBSTONED" > "$STATE_FILE"
        log_line "TOMBSTONED - Height: $HEIGHT | Missed: $MISSED_BLOCKS"
    fi
    exit 0
fi

if [ "$VAL_JAILED" = "true" ]; then
    if [ "$PREV_STATE" != "JAILED" ]; then
        FIELDS="[{\"name\":\"Validator\",\"value\":\"$(short_addr "$VALIDATOR_OPERATOR")\",\"inline\":true},{\"name\":\"Status\",\"value\":\"${VAL_STATUS}\",\"inline\":true},{\"name\":\"Jailed\",\"value\":\"true\",\"inline\":true},{\"name\":\"Missed Blocks\",\"value\":\"${MISSED_BLOCKS}\",\"inline\":true},{\"name\":\"System\",\"value\":\"${SYSTEM_STATS}\",\"inline\":false}]"
        send_discord "Cosmos Testnet Validator Jailed" "Provider testnet validator is jailed" "$COLOR_RED" "$FIELDS"
        echo "JAILED" > "$STATE_FILE"
        log_line "JAILED - Height: $HEIGHT | Missed: $MISSED_BLOCKS"
    fi
    exit 0
fi

if [ "$VAL_STATUS" = "unknown" ]; then
    if [ "$PREV_STATE" != "VALIDATOR_UNKNOWN" ]; then
        FIELDS="[{\"name\":\"Validator\",\"value\":\"$(short_addr "$VALIDATOR_OPERATOR")\",\"inline\":true},{\"name\":\"Query Node\",\"value\":\"${QUERY_NODE}\",\"inline\":false},{\"name\":\"Height\",\"value\":\"${HEIGHT}\",\"inline\":true},{\"name\":\"System\",\"value\":\"${SYSTEM_STATS}\",\"inline\":false}]"
        send_discord "Cosmos Testnet Validator Query Issue" "Monitor could not confirm provider testnet validator state" "$COLOR_YELLOW" "$FIELDS"
        echo "VALIDATOR_UNKNOWN" > "$STATE_FILE"
        log_line "VALIDATOR UNKNOWN - Height: $HEIGHT | Query node: $QUERY_NODE"
    fi
elif [ "$VAL_STATUS" != "BOND_STATUS_BONDED" ]; then
    if [ "$PREV_STATE" != "NOT_BONDED" ]; then
        FIELDS="[{\"name\":\"Validator\",\"value\":\"$(short_addr "$VALIDATOR_OPERATOR")\",\"inline\":true},{\"name\":\"Status\",\"value\":\"${VAL_STATUS}\",\"inline\":true},{\"name\":\"Jailed\",\"value\":\"${VAL_JAILED}\",\"inline\":true},{\"name\":\"Height\",\"value\":\"${HEIGHT}\",\"inline\":true},{\"name\":\"System\",\"value\":\"${SYSTEM_STATS}\",\"inline\":false}]"
        send_discord "Cosmos Testnet Validator Not Bonded" "Provider testnet validator is not bonded" "$COLOR_YELLOW" "$FIELDS"
        echo "NOT_BONDED" > "$STATE_FILE"
        log_line "NOT BONDED - Status: $VAL_STATUS | Height: $HEIGHT"
    fi
elif [ "$CATCHING_UP" = "true" ]; then
    if [ "$PREV_STATE" != "SYNCING" ]; then
        FIELDS="[{\"name\":\"Sync\",\"value\":\"catching up\",\"inline\":true},{\"name\":\"Height\",\"value\":\"${HEIGHT}\",\"inline\":true},{\"name\":\"Peers\",\"value\":\"${PEERS}\",\"inline\":true},{\"name\":\"Validator\",\"value\":\"${VAL_STATUS}\",\"inline\":true},{\"name\":\"System\",\"value\":\"${SYSTEM_STATS}\",\"inline\":false}]"
        send_discord "Cosmos Testnet Node Syncing" "Provider testnet node is catching up" "$COLOR_YELLOW" "$FIELDS"
        echo "SYNCING" > "$STATE_FILE"
        log_line "SYNCING - Height: $HEIGHT | Peers: $PEERS"
    fi
elif [ "$PEERS" -lt "$MIN_PEERS" ]; then
    if [ "$PREV_STATE" != "LOW_PEERS" ]; then
        FIELDS="[{\"name\":\"Peers\",\"value\":\"${PEERS}\",\"inline\":true},{\"name\":\"Minimum\",\"value\":\"${MIN_PEERS}\",\"inline\":true},{\"name\":\"Height\",\"value\":\"${HEIGHT}\",\"inline\":true},{\"name\":\"System\",\"value\":\"${SYSTEM_STATS}\",\"inline\":false}]"
        send_discord "Cosmos Testnet Low Peers" "Provider testnet peer count is below threshold" "$COLOR_YELLOW" "$FIELDS"
        echo "LOW_PEERS" > "$STATE_FILE"
        log_line "LOW PEERS - Peers: $PEERS | Height: $HEIGHT"
    fi
else
    if [ "$PREV_STATE" != "ACTIVE" ]; then
        VERSION=$("$GAIAD_BIN" version 2>/dev/null | head -1)
        [ -z "$VERSION" ] && VERSION="unknown"
        FIELDS="[{\"name\":\"Node\",\"value\":\"${NODE_MONIKER}\",\"inline\":true},{\"name\":\"Chain\",\"value\":\"${NODE_CHAIN_ID}\",\"inline\":true},{\"name\":\"Height\",\"value\":\"${HEIGHT}\",\"inline\":true},{\"name\":\"Peers\",\"value\":\"${PEERS}\",\"inline\":true},{\"name\":\"Validator\",\"value\":\"${VAL_STATUS}\",\"inline\":true},{\"name\":\"Jailed\",\"value\":\"${VAL_JAILED}\",\"inline\":true},{\"name\":\"Missed Blocks\",\"value\":\"${MISSED_BLOCKS}\",\"inline\":true},{\"name\":\"Wallet Balance\",\"value\":\"${WALLET_BALANCE}\",\"inline\":true},{\"name\":\"Version\",\"value\":\"${VERSION}\",\"inline\":false},{\"name\":\"System\",\"value\":\"${SYSTEM_STATS}\",\"inline\":false}]"
        send_discord "Cosmos Testnet Validator Active" "Provider testnet monitor is healthy on ${HOSTNAME}" "$COLOR_GREEN" "$FIELDS"
        echo "ACTIVE" > "$STATE_FILE"
    fi
    log_line "ACTIVE - Height: $HEIGHT | Peers: $PEERS | Validator: $VAL_STATUS | Jailed: $VAL_JAILED | Missed: $MISSED_BLOCKS | Balance: $WALLET_BALANCE"
fi

HEIGHT_FILE="/tmp/cosmos_testnet_last_height"
STUCK_FILE="/tmp/cosmos_testnet_stuck_count"
if is_number "$HEIGHT" && [ "$HEIGHT" != "0" ] && [ -f "$HEIGHT_FILE" ]; then
    LAST_HEIGHT=$(cat "$HEIGHT_FILE")
    if [ "$HEIGHT" = "$LAST_HEIGHT" ] && [ "$CATCHING_UP" != "true" ]; then
        STUCK_COUNT=$(cat "$STUCK_FILE" 2>/dev/null || echo 0)
        STUCK_COUNT=$((STUCK_COUNT + 1))
        echo "$STUCK_COUNT" > "$STUCK_FILE"
        if [ "$STUCK_COUNT" -ge "$STUCK_CHECKS" ]; then
            FIELDS="[{\"name\":\"Height\",\"value\":\"${HEIGHT} stuck\",\"inline\":true},{\"name\":\"Peers\",\"value\":\"${PEERS}\",\"inline\":true},{\"name\":\"Checks\",\"value\":\"${STUCK_COUNT}\",\"inline\":true},{\"name\":\"Latest Time\",\"value\":\"${LATEST_TIME}\",\"inline\":false},{\"name\":\"System\",\"value\":\"${SYSTEM_STATS}\",\"inline\":false}]"
            send_discord "Cosmos Testnet Height Stuck" "Testnet block height has not advanced across repeated checks" "$COLOR_RED" "$FIELDS"
            echo "0" > "$STUCK_FILE"
            log_line "HEIGHT STUCK - Height: $HEIGHT"
        fi
    else
        echo "0" > "$STUCK_FILE"
    fi
fi
is_number "$HEIGHT" && [ "$HEIGHT" != "0" ] && echo "$HEIGHT" > "$HEIGHT_FILE"

MISSED_FILE="/tmp/cosmos_testnet_missed_blocks"
if [ "$MISSED_BLOCK_WARN_INCREASE" = "true" ] && is_number "$MISSED_BLOCKS"; then
    if [ -f "$MISSED_FILE" ]; then
        LAST_MISSED=$(cat "$MISSED_FILE")
        if is_number "$LAST_MISSED" && [ "$MISSED_BLOCKS" -gt "$LAST_MISSED" ]; then
            FIELDS="[{\"name\":\"Previous\",\"value\":\"${LAST_MISSED}\",\"inline\":true},{\"name\":\"Current\",\"value\":\"${MISSED_BLOCKS}\",\"inline\":true},{\"name\":\"Height\",\"value\":\"${HEIGHT}\",\"inline\":true},{\"name\":\"TIP Note\",\"value\":\"Upgrade events may require signing within 5 blocks\",\"inline\":false},{\"name\":\"System\",\"value\":\"${SYSTEM_STATS}\",\"inline\":false}]"
            send_discord "Cosmos Testnet Missed Blocks Increased" "Provider testnet validator missed block counter increased" "$COLOR_YELLOW" "$FIELDS"
            log_line "MISSED INCREASE - Previous: $LAST_MISSED | Current: $MISSED_BLOCKS"
        fi
    fi
    echo "$MISSED_BLOCKS" > "$MISSED_FILE"
fi

HOUR_FILE="/tmp/cosmos_testnet_resource_alert_$(date +%Y%m%d%H)"
if [ ! -f "$HOUR_FILE" ]; then
    DISK_PCT=$(get_disk_pct)
    RAM_PCT=$(free | awk 'NR==2{printf "%.0f", ($3/$2)*100}')
    SWAP_PCT=$(free | awk 'NR==3{if($2>0) printf "%.0f", ($3/$2)*100; else print "0"}')
    WARNING=""

    if is_number "$MISSED_BLOCKS" && [ "$MISSED_BLOCKS" -gt "$MAX_MISSED_BLOCKS" ]; then
        WARNING="Missed block counter above threshold: ${MISSED_BLOCKS}"
    elif is_number "$WALLET_BALANCE_UATOM" && [ "$WALLET_BALANCE_UATOM" -lt "$LOW_BALANCE_UATOM" ]; then
        WARNING="Low testnet wallet balance: ${WALLET_BALANCE}"
    elif [ -n "$DISK_PCT" ] && [ "$DISK_PCT" -gt 85 ]; then
        WARNING="High disk usage: ${DISK_PCT}%"
    elif [ -n "$RAM_PCT" ] && [ "$RAM_PCT" -gt 90 ]; then
        WARNING="High RAM usage: ${RAM_PCT}%"
    elif [ -n "$SWAP_PCT" ] && [ "$SWAP_PCT" -gt 50 ]; then
        WARNING="High swap usage: ${SWAP_PCT}%"
    fi

    if [ -n "$WARNING" ]; then
        FIELDS="[{\"name\":\"Warning\",\"value\":\"${WARNING}\",\"inline\":false},{\"name\":\"Height\",\"value\":\"${HEIGHT}\",\"inline\":true},{\"name\":\"Peers\",\"value\":\"${PEERS}\",\"inline\":true},{\"name\":\"System\",\"value\":\"${SYSTEM_STATS}\",\"inline\":false}]"
        send_discord "Cosmos Testnet Resource Warning" "Attention needed on ${HOSTNAME}" "$COLOR_YELLOW" "$FIELDS"
        touch "$HOUR_FILE"
    fi
fi

HOUR=$(date +%H)
DAILY_FILE="/tmp/cosmos_testnet_daily_$(date +%Y%m%d)"
if [ "$HOUR" = "09" ] && [ ! -f "$DAILY_FILE" ]; then
    FIELDS="[{\"name\":\"Node\",\"value\":\"${NODE_MONIKER}\",\"inline\":true},{\"name\":\"Chain\",\"value\":\"${NODE_CHAIN_ID}\",\"inline\":true},{\"name\":\"Syncing\",\"value\":\"${CATCHING_UP}\",\"inline\":true},{\"name\":\"Height\",\"value\":\"${HEIGHT}\",\"inline\":true},{\"name\":\"Peers\",\"value\":\"${PEERS}\",\"inline\":true},{\"name\":\"Validator\",\"value\":\"${VAL_STATUS}\",\"inline\":true},{\"name\":\"Jailed\",\"value\":\"${VAL_JAILED}\",\"inline\":true},{\"name\":\"Tokens\",\"value\":\"$(format_atom "$VAL_TOKENS")\",\"inline\":true},{\"name\":\"Commission\",\"value\":\"${COMMISSION_RATE}\",\"inline\":true},{\"name\":\"Missed Blocks\",\"value\":\"${MISSED_BLOCKS}\",\"inline\":true},{\"name\":\"Wallet Balance\",\"value\":\"${WALLET_BALANCE}\",\"inline\":true},{\"name\":\"System\",\"value\":\"${SYSTEM_STATS}\",\"inline\":false}]"
    send_discord "Cosmos Testnet Daily Report" "${HOSTNAME} provider testnet daily health summary" "$COLOR_BLUE" "$FIELDS"
    touch "$DAILY_FILE"
fi

find /tmp -name "cosmos_testnet_resource_alert_*" -mtime +1 -delete 2>/dev/null
find /tmp -name "cosmos_testnet_daily_*" -mtime +1 -delete 2>/dev/null

exit 0
