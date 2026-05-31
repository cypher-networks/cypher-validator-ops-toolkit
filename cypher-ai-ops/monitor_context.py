import os
from dataclasses import dataclass
from pathlib import Path

from health_checks import redact_sensitive, truncate_report


@dataclass(frozen=True)
class MonitorProfile:
    name: str
    aliases: tuple[str, ...]
    state_path: Path | None
    log_path: Path | None
    notes: str


HOME = Path.home()
REMOTE_STATE_ENV = "REMOTE_STATE_DIR"

MONITORS: dict[str, MonitorProfile] = {
    "aztec": MonitorProfile(
        name="aztec",
        aliases=("aztec", "aztec-node", "aztec sequencer"),
        state_path=HOME / "aztec_validator_status.txt",
        log_path=HOME / "aztec_monitor.log",
        notes="Aztec Docker node on port 8080. Monitor tracks container, L1 RPC, L2 block, proven block, ETH gas balance, stuck block, and resources. If Aztec stalls, first check docker ps/logs for aztec-node, node_getBlockNumber, node_getProvenBlockNumber, L1 RPC eth_blockNumber/eth_syncing, peer/connectivity messages, and whether the block/proven gap is growing. Avoid restart/resync advice until container, RPC, and L1 health are proven.",
    ),
    "babylon": MonitorProfile(
        name="babylon",
        aliases=("babylon", "baby"),
        state_path=HOME / "babylon_validator_status.txt",
        log_path=HOME / "babylon_monitor.log",
        notes="Babylon validator monitor. Checks babylond service/process, RPC on the configured localhost port, latest block/syncing, validator jailed/status/voting power, and resources. If Babylon alerts, first check systemctl status babylond, journalctl for consensus/errors, babylond status sync_info, validator query output, and disk/RAM pressure. Avoid key changes, unjail, or restart advice unless diagnostics clearly point there.",
    ),
    "cardano": MonitorProfile(
        name="cardano",
        aliases=("cardano", "ada", "cardano producer", "cardano relay"),
        state_path=HOME / "cardano_validator_status.txt",
        log_path=HOME / "cardano_monitor.log",
        notes="Cardano monitor. Checks cardano-node service/process, node socket, cardano-cli query tip, sync progress, peers, relay/producer role, pledge/pool params where configured. If Cardano stalls, first check systemctl status cardano-node, cardano-cli query tip --mainnet, journalctl errors, socket path, peers/inbound connectivity, and disk growth. Producer should not expose keys or run relay-only assumptions.",
    ),
    "canopy": MonitorProfile(
        name="canopy",
        aliases=("canopy", "cnpy", "canopy node"),
        state_path=HOME / "canopy_validator_status.txt",
        log_path=HOME / "canopy_monitor.log",
        notes="Canopy monitor. Checks Canopy node containers/processes, block/height progress, validator state, peer/connectivity signals, exposed service ports, disk, and resources. If Canopy alerts, first check docker ps/logs for node1/node2, local RPC or status endpoints used by the monitor, recent canopy_monitor.log entries, validator status, and host resource pressure. Do not suggest destructive container/data recovery until process, network, and disk evidence are checked.",
    ),
    "cosmos-mainnet": MonitorProfile(
        name="cosmos-mainnet",
        aliases=("cosmos-mainnet", "cosmos_mainnet", "cosmos mainnet", "cosmos hub", "cosmoshub", "cosmoshub-4", "gaiad-mainnet", "gaiad_mainnet"),
        state_path=HOME / "cosmos_mainnet_status.txt",
        log_path=HOME / "cosmos_mainnet_monitor.log",
        notes="Cosmos Hub mainnet monitor on your-validator-host. Checks gaiad-mainnet service, local RPC 127.0.0.1:26657, peers, catching_up, validator bonded/jailed/tombstoned state, missed blocks, operator hot-wallet balance, and resources. If mainnet alerts, first check systemctl status gaiad-mainnet, curl 127.0.0.1:26657/status and /net_info, gaiad-mainnet query staking validator, slashing signing-info, recent journal logs, and disk/RAM. Governance voting must stay above 80 percent for ICF delegation eligibility; do not suggest key or unjail transactions from Discord without manual confirmation.",
    ),
    "cosmos-testnet": MonitorProfile(
        name="cosmos-testnet",
        aliases=("cosmos-testnet", "cosmos_testnet", "cosmos testnet", "provider testnet", "gaia testnet", "gaiad provider"),
        state_path=HOME / "cosmos_testnet_status.txt",
        log_path=HOME / "cosmos_testnet_monitor.log",
        notes="Cosmos Hub provider testnet monitor on your-validator-host. Checks gaiad service, local RPC 127.0.0.1:26667, peers, catching_up, validator bonded/jailed/tombstoned state, missed blocks, wallet balance, and resources. TIP performance depends on signing especially around upgrade events; if testnet alerts, first check systemctl status gaiad, curl 127.0.0.1:26667/status and /net_info, gaiad query staking validator against the configured provider RPC, slashing signing-info, recent journal logs, and whether an upgrade event occurred.",
    ),
    "cx": MonitorProfile(
        name="cx",
        aliases=("cx", "cx-chain", "avalanche", "subnet"),
        state_path=HOME / "cx_validator_status.txt",
        log_path=HOME / "cx_monitor.log",
        notes="CX/Avalanche validator monitor. Checks process/RPC, P-Chain/CX sync, block height, validator state, peers, and disk/resources. If CX alerts, first check docker/process status, local RPC health, P-Chain/CX latest height, peer count, validator state, and recent logs for consensus/network errors. Do not suggest stop/start or database deletion from Discord.",
    ),
    "espresso": MonitorProfile(
        name="espresso",
        aliases=("espresso", "espresso sequencer", "espresso validator"),
        state_path=HOME / "espresso_validator_status.txt",
        log_path=HOME / "espresso_monitor.log",
        notes="Espresso sequencer monitor. Checks container, status API, peers, current view, decided view, synced height, L1 head, and resources. If peers exist but views stop deciding, check /v1/status/block-height, /v1/status/time-since-last-decide, /v1/status/success-rate, /v1/status/metrics for consensus_current_view, consensus_last_decided_view, consensus_connected_peers, consensus_last_synced_block_height, then recent sequencer logs for NoValidValidators, No Stake table, catchup, NoPeersYet, view timed out, panicked, decided. Also verify L1 provider/log proxy health before blaming P2P. Do not wipe/resync unless low-risk checks prove stake table or DB corruption.",
    ),
    "ethereum": MonitorProfile(
        name="ethereum",
        aliases=("ethereum", "eth", "ethnode", "reth", "lighthouse"),
        state_path=HOME / "eth_node_status.txt",
        log_path=HOME / "eth_monitor.log",
        notes="Ethereum node monitor for Reth execution plus Lighthouse consensus on mainnet. Checks reth/lighthouse services, Reth eth_syncing, eth_blockNumber, peer count, Lighthouse node health/sync/peers, /data disk, and logs. If Ethereum is not ready, first check systemctl status reth/lighthouse, eth_syncing stage progress, current eth_blockNumber, Lighthouse /eth/v1/node/health, peer count, and historical eth_getLogs if archive readiness matters. Do not move validators/RPC consumers back until sync is false, block is current, and required historical log queries pass.",
    ),
    "starknet": MonitorProfile(
        name="starknet",
        aliases=("starknet", "pathfinder", "starknet attestation"),
        state_path=HOME / "starknet_validator_status.txt",
        log_path=None,
        notes="Starknet monitor. Checks pathfinder and attestation containers, Pathfinder RPC sync/block status, Ethereum L1 provider reachability, validator/attestation logs, and resources. If Starknet alerts, first check docker ps/logs for pathfinder and attestation, starknet_syncing, starknet_blockNumber, L1 provider health, and recent attestation misses/errors. Avoid restart/remediation advice until container, L1, and sync state are identified.",
    ),
}


def list_monitor_names() -> list[str]:
    return sorted(MONITORS)


def normalize_monitor_name(name: str) -> str:
    return name.lower().strip().replace("_", "-")


def infer_monitor_name(text: str) -> str | None:
    lower_text = text.lower().replace("_", "-")
    for profile in MONITORS.values():
        if any(alias.replace("_", "-") in lower_text for alias in profile.aliases):
            return profile.name
    return None


@dataclass(frozen=True)
class ResolvedMonitorFile:
    path: Path
    source: str


def _remote_state_root() -> Path:
    raw = os.getenv(REMOTE_STATE_ENV, "remote-state").strip() or "remote-state"
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _find_remote_copy(local_path: Path) -> ResolvedMonitorFile | None:
    root = _remote_state_root()
    if not root.exists() or not root.is_dir():
        return None

    filename = local_path.name
    try:
        matches = [path for path in root.rglob(filename) if path.is_file()]
    except OSError:
        return None
    if not matches:
        return None

    newest = max(matches, key=lambda path: path.stat().st_mtime)
    return ResolvedMonitorFile(path=newest, source=f"remote copy under {root}")


def _resolve_monitor_file(path: Path) -> ResolvedMonitorFile | None:
    if path.exists() and path.is_file():
        return ResolvedMonitorFile(path=path, source="local file")
    return _find_remote_copy(path)


def _read_small_file(path: Path, max_chars: int = 2000) -> str:
    if not path.exists():
        return "<missing>"
    if not path.is_file():
        return "<not a file>"
    try:
        data = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"<unreadable: {exc}>"
    return redact_sensitive(data.strip())[:max_chars] or "<empty>"


def _tail_file(path: Path, lines: int = 30, max_bytes: int = 65536) -> str:
    if not path.exists():
        return "<missing>"
    if not path.is_file():
        return "<not a file>"
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes))
            data = handle.read().decode("utf-8", errors="replace")
    except OSError as exc:
        return f"<unreadable: {exc}>"
    return redact_sensitive("\n".join(data.splitlines()[-lines:])) or "<empty>"


def collect_monitor_report(name: str | None = None) -> str:
    if name:
        key = normalize_monitor_name(name)
        if key not in MONITORS:
            inferred = infer_monitor_name(key)
            if not inferred:
                return f"Unknown monitor: {name}. Known monitors: {', '.join(list_monitor_names())}"
            key = inferred
        profiles = [MONITORS[key]]
    else:
        profiles = [MONITORS[key] for key in list_monitor_names()]

    sections: list[str] = []
    for profile in profiles:
        sections.append(f"## {profile.name}\nNotes: {profile.notes}")
        if profile.state_path:
            resolved_state = _resolve_monitor_file(profile.state_path)
            if resolved_state:
                sections.append(
                    f"State file {resolved_state.path} ({resolved_state.source}; expected local path {profile.state_path}):\n"
                    f"{_read_small_file(resolved_state.path, max_chars=800)}"
                )
            else:
                sections.append(
                    f"State file {profile.state_path}: <missing locally and no remote copy found under {_remote_state_root()}>"
                )
        if profile.log_path:
            resolved_log = _resolve_monitor_file(profile.log_path)
            if resolved_log:
                sections.append(
                    f"Recent log {resolved_log.path} ({resolved_log.source}; expected local path {profile.log_path}):\n"
                    f"{_tail_file(resolved_log.path)}"
                )
            else:
                sections.append(
                    f"Recent log {profile.log_path}: <missing locally and no remote copy found under {_remote_state_root()}>"
                )
        else:
            sections.append("Recent log: <no local log file configured in monitor profile>")
    return truncate_report("\n\n".join(sections), max_chars=12000)
