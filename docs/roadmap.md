# Roadmap

## Milestone 1: Cosmos Hub Monitor Baseline

- Mainnet validator health monitor.
- Provider testnet validator health monitor.
- Governance proposal discovery and vote-status alerting.
- Shared `.validator-monitor.env` template.
- Discord webhook alert support.

## Milestone 2: Documentation

- Deployment guide.
- Security model.
- Cosmos Hub runbook.
- Common incident response notes.

## Milestone 3: AI-Assisted Operations

- Local Discord bot.
- Ollama integration.
- Monitor-aware alert explanations.
- GPU-required guard for local model execution.
- Safe read-only command allowlist.

## Milestone 4: Portability

- Make monitor paths and service names easier to override.
- Add install scripts.
- Add shellcheck guidance.
- Add sample systemd timers as an alternative to cron.

## Milestone 5: Additional Proposal Watchers

- Add proposal-source watchers for chains where governance proposals are not Cosmos SDK `gov` queries.
- Add optional Snapshot/forum watchers once official sources are confirmed.
