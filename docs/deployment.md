# Deployment

This guide assumes Ubuntu Server and a local Cosmos Hub node.

## Requirements

- `bash`
- `curl`
- `jq`
- `systemd`
- Gaia binary, for example `gaiad` or `gaiad-mainnet`
- Local CometBFT RPC exposed on localhost
- Optional Discord webhook URL

## Monitor Setup

Create a local environment file:

```bash
cp .env.example ~/.validator-monitor.env
nano ~/.validator-monitor.env
chmod 600 ~/.validator-monitor.env
```

Install scripts:

```bash
cp monitors/*.sh /home/YOUR_USER/
chmod +x /home/YOUR_USER/cosmos_*_monitor.sh
```

Normalize line endings if files were copied from Windows:

```bash
sed -i 's/\r$//' /home/YOUR_USER/cosmos_*_monitor.sh ~/.validator-monitor.env
```

Validate syntax:

```bash
bash -n /home/YOUR_USER/cosmos_mainnet_monitor.sh
bash -n /home/YOUR_USER/cosmos_testnet_monitor.sh
bash -n /home/YOUR_USER/cosmos_mainnet_gov_monitor.sh
bash -n /home/YOUR_USER/cosmos_testnet_gov_monitor.sh
```

Run manually:

```bash
/home/YOUR_USER/cosmos_mainnet_monitor.sh
/home/YOUR_USER/cosmos_testnet_monitor.sh
/home/YOUR_USER/cosmos_mainnet_gov_monitor.sh
/home/YOUR_USER/cosmos_testnet_gov_monitor.sh
```

Check logs:

```bash
tail -20 /home/YOUR_USER/cosmos_mainnet_monitor.log
tail -20 /home/YOUR_USER/cosmos_mainnet_gov_monitor.log
```

Governance monitor details are documented in [governance-alerts.md](governance-alerts.md).

## Cron

Add after manual validation:

```bash
crontab -e
```

Example:

```cron
*/5 * * * * /bin/bash /home/YOUR_USER/cosmos_mainnet_monitor.sh >> /home/YOUR_USER/cosmos_mainnet_monitor.log 2>&1
*/5 * * * * /bin/bash /home/YOUR_USER/cosmos_testnet_monitor.sh >> /home/YOUR_USER/cosmos_testnet_monitor.log 2>&1
*/30 * * * * /bin/bash /home/YOUR_USER/cosmos_mainnet_gov_monitor.sh >> /home/YOUR_USER/cosmos_mainnet_gov_monitor.log 2>&1
*/30 * * * * /bin/bash /home/YOUR_USER/cosmos_testnet_gov_monitor.sh >> /home/YOUR_USER/cosmos_testnet_gov_monitor.log 2>&1
```

## Cypher AI Ops

The Discord bot is optional.

```bash
cd cypher-ai-ops
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
python bot.py
```

For systemd, review and edit `cypher-ai-ops/systemd/cypher-ai-ops.service` for your user and install path before copying it to `/etc/systemd/system/`.
