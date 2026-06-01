# Cypher Validator Ops Toolkit

Open validator operations tooling for Cosmos Hub operators.

This repository contains read-only monitor scripts, governance proposal/vote alerting, a local Discord/Ollama operations assistant, and practical runbooks for validator infrastructure.

The initial release focuses on Cosmos Hub mainnet and provider testnet operations.

## What Is Included

```text
monitors/
  cosmos_mainnet_monitor.sh
  cosmos_testnet_monitor.sh
  cosmos_mainnet_gov_monitor.sh
  cosmos_testnet_gov_monitor.sh

cypher-ai-ops/
  Python Discord bot for read-only validator operations help
  Local Ollama integration
  Monitor-aware alert triage
  Safe command allowlist

docs/
  cosmos-hub-runbook.md
  deployment.md
  governance-alerts.md
  security-model.md
  roadmap.md
```

## Goals

- Improve validator reliability through simple health checks.
- Reduce missed governance votes with proposal/vote alerts.
- Give operators clear runbooks for common incidents.
- Provide a local AI assistant that suggests safe read-only checks without executing arbitrary commands.
- Keep secrets and signing actions outside automation.

## Safety Model

- Monitor scripts are read-only.
- Governance monitors only query proposals and votes.
- No script submits transactions.
- The Discord bot does not run arbitrary user-supplied commands.
- Secrets belong in local `.env` files, never in git.
- Real Discord webhooks, bot tokens, private keys, mnemonics, validator keys, and wallet files must never be committed.

See [docs/security-model.md](docs/security-model.md).

## Quick Start

There are two local environment files:

- `~/.validator-monitor.env` for the shell monitor scripts.
- `cypher-ai-ops/.env` for the optional Discord/Ollama bot.

Both are created from examples and edited locally. Do not commit real `.env` files.

1. Copy the monitor environment template:

```bash
cp .env.example ~/.validator-monitor.env
nano ~/.validator-monitor.env
chmod 600 ~/.validator-monitor.env
```

2. Install monitor scripts:

```bash
cp monitors/*.sh /home/YOUR_USER/
chmod +x /home/YOUR_USER/cosmos_*_monitor.sh
```

3. Test the scripts:

```bash
bash -n /home/YOUR_USER/cosmos_mainnet_monitor.sh
bash -n /home/YOUR_USER/cosmos_testnet_monitor.sh
bash -n /home/YOUR_USER/cosmos_mainnet_gov_monitor.sh
bash -n /home/YOUR_USER/cosmos_testnet_gov_monitor.sh

/home/YOUR_USER/cosmos_mainnet_monitor.sh
/home/YOUR_USER/cosmos_mainnet_gov_monitor.sh
```

4. Add cron after validation:

```cron
*/5 * * * * /bin/bash /home/YOUR_USER/cosmos_mainnet_monitor.sh >> /home/YOUR_USER/cosmos_mainnet_monitor.log 2>&1
*/5 * * * * /bin/bash /home/YOUR_USER/cosmos_testnet_monitor.sh >> /home/YOUR_USER/cosmos_testnet_monitor.log 2>&1
*/30 * * * * /bin/bash /home/YOUR_USER/cosmos_mainnet_gov_monitor.sh >> /home/YOUR_USER/cosmos_mainnet_gov_monitor.log 2>&1
*/30 * * * * /bin/bash /home/YOUR_USER/cosmos_testnet_gov_monitor.sh >> /home/YOUR_USER/cosmos_testnet_gov_monitor.log 2>&1
```

See [docs/deployment.md](docs/deployment.md) for full setup.

## Governance Alerts

The Cosmos governance monitors are a first-class part of this toolkit. They query active voting-period proposals, check whether the configured voter address has voted, and alert when operator action is needed.

They do not submit votes or spend gas.

See [docs/governance-alerts.md](docs/governance-alerts.md).

## Cypher AI Ops

The `cypher-ai-ops/` bot is optional. It runs locally, connects to Discord, and uses a local Ollama model to summarize alerts and suggest safe next checks.

The current release uses local Ollama only. Operators configure the bot by copying `cypher-ai-ops/.env.example` to `cypher-ai-ops/.env`, entering the Discord token/channel IDs, and setting the local Ollama URL/model.

Install details are in [cypher-ai-ops/README.md](cypher-ai-ops/README.md).

## Status

This is an early operational toolkit. It is intended to be practical, auditable, and easy to adapt. Operators should review scripts before use and test against their own node layout.

## License

MIT. See [LICENSE](LICENSE).
<img width="361" height="166" alt="Screenshot 2026-05-31 213954" src="https://github.com/user-attachments/assets/97788b5c-649b-496c-8cef-2817392396c5" />
