# Security Model

This toolkit is designed around read-only visibility and manual operator control.

## Allowed

- Query local node RPC endpoints.
- Query validator status, slashing signing info, and governance proposals.
- Read local monitor logs and status files.
- Send Discord alerts.
- Suggest safe commands for manual operator review.

## Not Allowed

- No private keys.
- No mnemonics or seed phrases.
- No wallet files.
- No validator key files.
- No arbitrary shell commands from Discord.
- No automatic votes.
- No automatic unjail, delegate, withdraw, restart, upgrade, or transaction submission.
- No committed `.env` files or real webhook URLs.

## Governance Monitors

The governance monitors only run queries:

```bash
gaiad query gov proposals
gaiad query gov vote <proposal-id> <voter-address>
```

They do not broadcast transactions and do not spend gas.

## Discord Bot

The bot uses a fixed allowlist of read-only commands. If a task needs elevated privileges or a transaction, the bot should tell the operator what to run manually instead of executing it.

## Publishing Checklist

Before publishing or pushing a fork:

```bash
rg -n "discord.com/api/webhooks|DISCORD_BOT_TOKEN=.+|PRIVATE_KEY|MNEMONIC|SEED|SECRET|API_KEY|\\.env" .
rg -n "cosmos1|cosmosvaloper|cosmosvalcons|192\\.168\\.|10\\.|172\\.16\\." .
```

Review every match and remove anything environment-specific that should not be public.
