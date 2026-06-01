# Governance Alerts

The governance alert monitors help Cosmos Hub validators avoid missed votes.

They are read-only. They query governance state and send Discord alerts, but they never submit transactions.

## Included Scripts

```text
monitors/cosmos_mainnet_gov_monitor.sh
monitors/cosmos_testnet_gov_monitor.sh
```

## What They Check

For each chain, the monitor:

1. Queries active voting-period proposals.
2. Checks whether the configured voter address has voted.
3. Logs the active, voted, and unvoted proposal IDs.
4. Sends a Discord alert when a proposal has no recorded vote.
5. Sends a recovery/status message when there are no active proposals or when a previously unvoted proposal becomes voted.

## Gas Safety

The monitors only run queries such as:

```bash
gaiad-mainnet query gov proposals \
  --proposal-status voting-period \
  --node tcp://127.0.0.1:26657 \
  -o json

gaiad-mainnet query gov vote <proposal-id> <voter-address> \
  --node tcp://127.0.0.1:26657 \
  -o json
```

These commands do not broadcast transactions and do not spend gas.

The alert may include a manual vote command template, but the operator must choose the vote option and run it manually:

```bash
gaiad-mainnet tx gov vote <proposal-id> <yes|no|abstain|no_with_veto> \
  --from YOUR_MAINNET_KEY_NAME \
  --keyring-backend os \
  --chain-id cosmoshub-4 \
  --gas auto \
  --gas-adjustment 1.5 \
  --gas-prices 0.005uatom \
  --node tcp://127.0.0.1:26657
```

## Required Environment Variables

Set these in `~/.validator-monitor.env`.

Mainnet:

```bash
COSMOS_MAINNET_CHAIN_ID=cosmoshub-4
COSMOS_MAINNET_BIN=/home/YOUR_USER/go/bin/gaiad-mainnet
COSMOS_MAINNET_NODE=tcp://127.0.0.1:26657
COSMOS_MAINNET_QUERY_NODE=tcp://127.0.0.1:26657
COSMOS_MAINNET_GOV_VOTER_ADDRESS=REPLACE_WITH_MAINNET_OPERATOR_ADDRESS
COSMOS_MAINNET_GOV_KEY_NAME=YOUR_MAINNET_KEY_NAME
COSMOS_MAINNET_GOV_DISCORD_WEBHOOK_URL=
```

Testnet:

```bash
COSMOS_TESTNET_CHAIN_ID=provider
COSMOS_TESTNET_BIN=/home/YOUR_USER/go/bin/gaiad
COSMOS_TESTNET_NODE=tcp://127.0.0.1:26657
COSMOS_TESTNET_QUERY_NODE=tcp://127.0.0.1:26657
COSMOS_TESTNET_GOV_VOTER_ADDRESS=REPLACE_WITH_TESTNET_WALLET_ADDRESS
COSMOS_TESTNET_GOV_KEY_NAME=YOUR_TESTNET_KEY_NAME
COSMOS_TESTNET_GOV_DISCORD_WEBHOOK_URL=
```

If mainnet and testnet are running on the same host, replace the testnet `*_NODE` values with the alternate local port configured for that node, for example `tcp://127.0.0.1:26667`.

If `*_GOV_DISCORD_WEBHOOK_URL` is empty, the script falls back to the chain-level Discord webhook variables.

## Manual Test

```bash
bash -n /home/YOUR_USER/cosmos_mainnet_gov_monitor.sh
bash -n /home/YOUR_USER/cosmos_testnet_gov_monitor.sh

/home/YOUR_USER/cosmos_mainnet_gov_monitor.sh
/home/YOUR_USER/cosmos_testnet_gov_monitor.sh

tail -20 /home/YOUR_USER/cosmos_mainnet_gov_monitor.log
tail -20 /home/YOUR_USER/cosmos_testnet_gov_monitor.log
```

Expected log examples:

```text
ACTIVE - Open: 2 | Unvoted: 0 | Voted: 2 (...)
CLEAR - Open: 0 | Height: ...
```

## Cron

Every 30 minutes is usually enough for governance monitoring:

```cron
*/30 * * * * /bin/bash /home/YOUR_USER/cosmos_mainnet_gov_monitor.sh >> /home/YOUR_USER/cosmos_mainnet_gov_monitor.log 2>&1
*/30 * * * * /bin/bash /home/YOUR_USER/cosmos_testnet_gov_monitor.sh >> /home/YOUR_USER/cosmos_testnet_gov_monitor.log 2>&1
```

## Alert Behavior

The monitors avoid Discord spam:

- New unvoted proposal: alert.
- Still unvoted: remind after `*_GOV_REMINDER_SECONDS`, default 6 hours.
- No active proposals: clear once on state change.
- Already voted proposals: log locally without repeated Discord posts.

## Why This Matters

Governance participation is an operational responsibility for Cosmos Hub validators. Proposal and vote-status alerts reduce the chance that validators miss voting windows, especially when proposals are short-lived, noisy, or operationally urgent.
