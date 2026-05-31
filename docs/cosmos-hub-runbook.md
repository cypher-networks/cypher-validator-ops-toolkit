# Cosmos Hub Validator Runbook

This runbook is a template for Cosmos Hub validator operations. Replace all `REPLACE_WITH_*` values before use.

## Host Layout

| Component | Example |
|---|---|
| Mainnet service | `gaiad-mainnet` |
| Testnet service | `gaiad` |
| Mainnet home | `~/.gaia-mainnet` |
| Testnet home | `~/.gaia` |
| Mainnet RPC | `tcp://127.0.0.1:26657` |
| Testnet RPC | `tcp://127.0.0.1:26667` |

## Required Local Values

| Value | Placeholder |
|---|---|
| Mainnet valoper | `REPLACE_WITH_MAINNET_VALOPER` |
| Mainnet operator address | `REPLACE_WITH_MAINNET_OPERATOR_ADDRESS` |
| Mainnet payment address | `REPLACE_WITH_MAINNET_PAYMENT_ADDRESS` |
| Mainnet key name | `YOUR_MAINNET_KEY_NAME` |
| Testnet valoper | `REPLACE_WITH_TESTNET_VALOPER` |
| Testnet wallet address | `REPLACE_WITH_TESTNET_WALLET_ADDRESS` |
| Testnet consensus address | `REPLACE_WITH_TESTNET_VALCONS` |
| Testnet key name | `YOUR_TESTNET_KEY_NAME` |

## Service Status

```bash
systemctl status gaiad-mainnet --no-pager
systemctl status gaiad --no-pager
```

## Sync Status

```bash
curl -s http://127.0.0.1:26657/status | jq '.result.sync_info'
curl -s http://127.0.0.1:26667/status | jq '.result.sync_info'
```

Key fields:

- `catching_up` should be `false`.
- `latest_block_height` should advance.
- `latest_block_time` should be recent.

## Peer Count

```bash
curl -s http://127.0.0.1:26657/net_info | jq '.result.n_peers'
curl -s http://127.0.0.1:26667/net_info | jq '.result.n_peers'
```

## Validator State

```bash
gaiad-mainnet query staking validator REPLACE_WITH_MAINNET_VALOPER \
  --node tcp://127.0.0.1:26657 \
  -o json | jq

gaiad query staking validator REPLACE_WITH_TESTNET_VALOPER \
  --node tcp://127.0.0.1:26667 \
  -o json | jq
```

Check:

- `status` should be `BOND_STATUS_BONDED` for active validators.
- `jailed` should be `false`.

## Missed Blocks

```bash
gaiad-mainnet query slashing signing-info \
  "$(gaiad-mainnet tendermint show-validator --home ~/.gaia-mainnet)" \
  --node tcp://127.0.0.1:26657 \
  -o json | jq

gaiad query slashing signing-info REPLACE_WITH_TESTNET_VALCONS \
  --node tcp://127.0.0.1:26667 \
  -o json | jq
```

If missed blocks are increasing:

1. Check service health.
2. Check sync status.
3. Check peers.
4. Check CPU, RAM, disk, and swap.
5. Check recent logs.

```bash
free -h
df -h
vmstat 1 10
journalctl -u gaiad-mainnet -n 100 --no-pager
journalctl -u gaiad -n 100 --no-pager
```

## Governance

List active mainnet proposals:

```bash
gaiad-mainnet query gov proposals \
  --proposal-status voting-period \
  --node tcp://127.0.0.1:26657 \
  -o json | jq
```

Check whether a voter address has voted:

```bash
gaiad-mainnet query gov vote <proposal-id> REPLACE_WITH_MAINNET_OPERATOR_ADDRESS \
  --node tcp://127.0.0.1:26657 \
  -o json | jq
```

Manual vote command:

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

The toolkit's governance monitors only query proposals and vote status. They do not submit transactions.

## Balances

```bash
gaiad-mainnet query bank balances REPLACE_WITH_MAINNET_OPERATOR_ADDRESS \
  --node tcp://127.0.0.1:26657 \
  -o json | jq
```

## Monitor Scripts

Run manually before installing cron:

```bash
~/cosmos_mainnet_monitor.sh
~/cosmos_testnet_monitor.sh
~/cosmos_mainnet_gov_monitor.sh
~/cosmos_testnet_gov_monitor.sh
```

Check logs:

```bash
tail -20 ~/cosmos_mainnet_monitor.log
tail -20 ~/cosmos_testnet_monitor.log
tail -20 ~/cosmos_mainnet_gov_monitor.log
tail -20 ~/cosmos_testnet_gov_monitor.log
```

## Incident Triage

For validator alerts, collect:

```bash
systemctl status gaiad-mainnet --no-pager
curl -s http://127.0.0.1:26657/status | jq '.result.sync_info'
curl -s http://127.0.0.1:26657/net_info | jq '.result.n_peers'
journalctl -u gaiad-mainnet -n 100 --no-pager
free -h
df -h
```

Do not run restart, unjail, vote, delegate, or upgrade commands from automation. Review and execute those manually.
