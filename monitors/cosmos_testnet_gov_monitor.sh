#!/bin/bash

# Cosmos Hub provider testnet governance proposal/vote monitor.
# Read-only: queries active proposals and whether the configured voter address has voted.

[ -f "$HOME/.validator-monitor.env" ] && source "$HOME/.validator-monitor.env"

DISCORD_WEBHOOK="${COSMOS_TESTNET_GOV_DISCORD_WEBHOOK_URL:-${COSMOS_TESTNET_DISCORD_WEBHOOK_URL:-${COSMOS_DISCORD_WEBHOOK_URL:-${DISCORD_WEBHOOK:-REPLACE_WITH_DISCORD_WEBHOOK}}}}"
STATE_FILE="${COSMOS_TESTNET_GOV_STATE_FILE:-$HOME/cosmos_testnet_gov_status.txt}"
LOG_FILE="${COSMOS_TESTNET_GOV_LOG_FILE:-$HOME/cosmos_testnet_gov_monitor.log}"

CHAIN_ID="${COSMOS_TESTNET_CHAIN_ID:-provider}"
GAIAD_BIN="${COSMOS_TESTNET_BIN:-$HOME/go/bin/gaiad}"
RPC_URL="${COSMOS_TESTNET_RPC:-http://127.0.0.1:26657}"
NODE_URL="${COSMOS_TESTNET_NODE:-tcp://127.0.0.1:26657}"
QUERY_NODE="${COSMOS_TESTNET_QUERY_NODE:-$NODE_URL}"
VOTER_ADDRESS="${COSMOS_TESTNET_GOV_VOTER_ADDRESS:-${COSMOS_TESTNET_WALLET_ADDRESS:-REPLACE_WITH_TESTNET_WALLET_ADDRESS}}"
KEY_NAME="${COSMOS_TESTNET_GOV_KEY_NAME:-YOUR_TESTNET_KEY_NAME}"
GAS_PRICES="${COSMOS_TESTNET_GOV_GAS_PRICES:-0.005uatom}"
REMINDER_SECONDS="${COSMOS_TESTNET_GOV_REMINDER_SECONDS:-21600}"

TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S UTC")
HOSTNAME=$(hostname)

COLOR_RED=15158332
COLOR_GREEN=5763719
COLOR_YELLOW=16776960
COLOR_BLUE=3447003

ALERT_DIR="/tmp/cosmos_testnet_gov_alerts"
mkdir -p "$ALERT_DIR"

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

short_value() {
    local value="$1"
    local max="${2:-850}"
    if [ "${#value}" -gt "$max" ]; then
        echo "${value:0:$max}..."
    else
        echo "$value"
    fi
}

short_addr() {
    local value="$1"
    if [ "${#value}" -gt 18 ]; then
        echo "${value:0:12}...${value: -8}"
    else
        echo "$value"
    fi
}

query_json() {
    "$GAIAD_BIN" "$@" -o json 2>/dev/null
}

query_active_proposals() {
    local result
    result=$(query_json query gov proposals --proposal-status voting-period --chain-id "$CHAIN_ID" --node "$QUERY_NODE")
    if echo "$result" | jq -e '.proposals' > /dev/null 2>&1; then
        echo "$result"
        return 0
    fi

    query_json query gov proposals --status voting_period --chain-id "$CHAIN_ID" --node "$QUERY_NODE"
}

proposal_title() {
    local proposals_json="$1"
    local proposal_id="$2"
    echo "$proposals_json" | jq -r --arg id "$proposal_id" '
        .proposals[]?
        | select(((.id // .proposal_id // "") | tostring) == $id)
        | (.title // .content.title // .messages[0].content.title // .metadata // "No title")
    ' 2>/dev/null | head -1
}

proposal_end_time() {
    local proposals_json="$1"
    local proposal_id="$2"
    echo "$proposals_json" | jq -r --arg id "$proposal_id" '
        .proposals[]?
        | select(((.id // .proposal_id // "") | tostring) == $id)
        | (.voting_end_time // .final_tally_result.voting_end_time // "unknown")
    ' 2>/dev/null | head -1
}

vote_summary() {
    local vote_json="$1"
    echo "$vote_json" | jq -r '
        (.vote.options // .options // []) as $options
        | if ($options | length) > 0 then
            ($options | map((.option // "unknown") + ":" + (.weight // "")) | join(", "))
          else
            (.vote.option // .option // empty)
          end
    ' 2>/dev/null | head -1
}

should_remind() {
    local proposal_id="$1"
    local now last file
    now=$(date +%s)
    file="${ALERT_DIR}/proposal_${proposal_id}.last"
    last=$(cat "$file" 2>/dev/null || echo 0)
    if [ $((now - last)) -ge "$REMINDER_SECONDS" ]; then
        echo "$now" > "$file"
        return 0
    fi
    return 1
}

if [ ! -x "$GAIAD_BIN" ] && ! command -v "$GAIAD_BIN" > /dev/null 2>&1; then
    send_discord "Cosmos Testnet Gov Monitor Error" "gaiad testnet binary was not found" "$COLOR_RED" "[{\"name\":\"Binary\",\"value\":\"${GAIAD_BIN}\",\"inline\":false}]"
    echo "BINARY_MISSING" > "$STATE_FILE"
    log_line "BINARY MISSING - $GAIAD_BIN"
    exit 1
fi

STATUS_JSON=$(curl -s --max-time 8 "${RPC_URL}/status" 2>/dev/null)
HEIGHT=$(echo "$STATUS_JSON" | jq -r '.result.sync_info.latest_block_height // "unknown"' 2>/dev/null)

PROPOSALS_JSON=$(query_active_proposals)
if [ -z "$PROPOSALS_JSON" ] || ! echo "$PROPOSALS_JSON" | jq -e '.proposals' > /dev/null 2>&1; then
    PREV_STATE=$(cat "$STATE_FILE" 2>/dev/null)
    if [ "$PREV_STATE" != "QUERY_FAILED" ]; then
        FIELDS="[{\"name\":\"Chain\",\"value\":\"${CHAIN_ID}\",\"inline\":true},{\"name\":\"Query Node\",\"value\":\"${QUERY_NODE}\",\"inline\":false},{\"name\":\"Height\",\"value\":\"${HEIGHT}\",\"inline\":true}]"
        send_discord "Cosmos Testnet Gov Query Failed" "Could not query active governance proposals" "$COLOR_YELLOW" "$FIELDS"
        echo "QUERY_FAILED" > "$STATE_FILE"
    fi
    log_line "QUERY FAILED - Height: $HEIGHT | Query node: $QUERY_NODE"
    exit 0
fi

mapfile -t PROPOSAL_IDS < <(echo "$PROPOSALS_JSON" | jq -r '
    .proposals[]?
    | select((.status == "PROPOSAL_STATUS_VOTING_PERIOD") or (.status == "voting_period") or (.status == "VotingPeriod"))
    | (.id // .proposal_id // empty)
' 2>/dev/null)

OPEN_COUNT="${#PROPOSAL_IDS[@]}"
UNVOTED_COUNT=0
VOTED_COUNT=0
UNVOTED_IDS=()
VOTED_IDS=()

if [ "$OPEN_COUNT" -eq 0 ]; then
    PREV_STATE=$(cat "$STATE_FILE" 2>/dev/null)
    if [ "$PREV_STATE" != "NO_ACTIVE_PROPOSALS" ]; then
        FIELDS="[{\"name\":\"Chain\",\"value\":\"${CHAIN_ID}\",\"inline\":true},{\"name\":\"Height\",\"value\":\"${HEIGHT}\",\"inline\":true},{\"name\":\"Voter\",\"value\":\"$(short_addr "$VOTER_ADDRESS")\",\"inline\":true}]"
        send_discord "Cosmos Testnet Gov Clear" "No active voting-period proposals" "$COLOR_GREEN" "$FIELDS"
        echo "NO_ACTIVE_PROPOSALS" > "$STATE_FILE"
    fi
    log_line "CLEAR - Open: 0 | Height: $HEIGHT"
    exit 0
fi

for proposal_id in "${PROPOSAL_IDS[@]}"; do
    TITLE=$(proposal_title "$PROPOSALS_JSON" "$proposal_id")
    [ -z "$TITLE" ] && TITLE="No title"
    END_TIME=$(proposal_end_time "$PROPOSALS_JSON" "$proposal_id")

    VOTE_JSON=$(query_json query gov vote "$proposal_id" "$VOTER_ADDRESS" --chain-id "$CHAIN_ID" --node "$QUERY_NODE")
    VOTE=$(vote_summary "$VOTE_JSON")

    if [ -n "$VOTE" ] && [ "$VOTE" != "null" ]; then
        VOTED_COUNT=$((VOTED_COUNT + 1))
        VOTED_IDS+=("${proposal_id}:${VOTE}")
        if [ -f "${ALERT_DIR}/proposal_${proposal_id}.last" ] && [ ! -f "${ALERT_DIR}/proposal_${proposal_id}.voted" ]; then
            FIELDS="[{\"name\":\"Proposal\",\"value\":\"#${proposal_id} - $(short_value "$TITLE" 650)\",\"inline\":false},{\"name\":\"Vote\",\"value\":\"${VOTE}\",\"inline\":true},{\"name\":\"Voter\",\"value\":\"$(short_addr "$VOTER_ADDRESS")\",\"inline\":true},{\"name\":\"Height\",\"value\":\"${HEIGHT}\",\"inline\":true}]"
            send_discord "Cosmos Testnet Gov Vote Recorded" "Configured voter has voted on proposal #${proposal_id}" "$COLOR_GREEN" "$FIELDS"
            touch "${ALERT_DIR}/proposal_${proposal_id}.voted"
        fi
    else
        UNVOTED_COUNT=$((UNVOTED_COUNT + 1))
        UNVOTED_IDS+=("$proposal_id")
        if should_remind "$proposal_id"; then
            MANUAL_CMD="${GAIAD_BIN} tx gov vote ${proposal_id} <yes|no|abstain|no_with_veto> --from ${KEY_NAME} --keyring-backend os --chain-id ${CHAIN_ID} --gas auto --gas-adjustment 1.5 --gas-prices ${GAS_PRICES} --node ${NODE_URL}"
            FIELDS="[{\"name\":\"Proposal\",\"value\":\"#${proposal_id} - $(short_value "$TITLE" 650)\",\"inline\":false},{\"name\":\"Voting Ends\",\"value\":\"${END_TIME}\",\"inline\":true},{\"name\":\"Voter\",\"value\":\"$(short_addr "$VOTER_ADDRESS")\",\"inline\":true},{\"name\":\"Height\",\"value\":\"${HEIGHT}\",\"inline\":true},{\"name\":\"Manual Vote Command\",\"value\":\"$(short_value "$MANUAL_CMD" 950)\",\"inline\":false}]"
            send_discord "Cosmos Testnet Gov Vote Needed" "Active proposal has no recorded vote from configured voter" "$COLOR_YELLOW" "$FIELDS"
        fi
    fi
done

echo "ACTIVE" > "$STATE_FILE"
log_line "ACTIVE - Open: $OPEN_COUNT | Unvoted: $UNVOTED_COUNT (${UNVOTED_IDS[*]}) | Voted: $VOTED_COUNT (${VOTED_IDS[*]}) | Height: $HEIGHT"

HOUR=$(date +%H)
DAILY_FILE="/tmp/cosmos_testnet_gov_daily_$(date +%Y%m%d)"
if [ "$HOUR" = "09" ] && [ ! -f "$DAILY_FILE" ]; then
    FIELDS="[{\"name\":\"Open Proposals\",\"value\":\"${OPEN_COUNT}\",\"inline\":true},{\"name\":\"Unvoted\",\"value\":\"${UNVOTED_COUNT}\",\"inline\":true},{\"name\":\"Voted\",\"value\":\"${VOTED_COUNT}\",\"inline\":true},{\"name\":\"Unvoted IDs\",\"value\":\"${UNVOTED_IDS[*]:-none}\",\"inline\":false},{\"name\":\"Height\",\"value\":\"${HEIGHT}\",\"inline\":true}]"
    send_discord "Cosmos Testnet Gov Daily Report" "${HOSTNAME} provider testnet governance summary" "$COLOR_BLUE" "$FIELDS"
    touch "$DAILY_FILE"
fi

find "$ALERT_DIR" -type f -mtime +14 -delete 2>/dev/null
find /tmp -name "cosmos_testnet_gov_daily_*" -mtime +2 -delete 2>/dev/null

exit 0
