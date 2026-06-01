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
    "cosmos-mainnet": MonitorProfile(
        name="cosmos-mainnet",
        aliases=("cosmos-mainnet", "cosmos_mainnet", "cosmos mainnet", "cosmos hub", "cosmoshub", "cosmoshub-4", "gaiad-mainnet", "gaiad_mainnet"),
        state_path=HOME / "cosmos_mainnet_status.txt",
        log_path=HOME / "cosmos_mainnet_monitor.log",
        notes="Cosmos Hub mainnet monitor on the validator host. Checks gaiad-mainnet service, local RPC 127.0.0.1:26657, peers, catching_up, validator bonded/jailed/tombstoned state, missed blocks, operator hot-wallet balance, and resources. If mainnet alerts, first check systemctl status gaiad-mainnet, curl 127.0.0.1:26657/status and /net_info, gaiad-mainnet query staking validator, slashing signing-info, recent journal logs, and disk/RAM. Do not suggest key or unjail transactions from Discord without manual confirmation.",
    ),
    "cosmos-testnet": MonitorProfile(
        name="cosmos-testnet",
        aliases=("cosmos-testnet", "cosmos_testnet", "cosmos testnet", "provider testnet", "gaia testnet", "gaiad provider"),
        state_path=HOME / "cosmos_testnet_status.txt",
        log_path=HOME / "cosmos_testnet_monitor.log",
        notes="Cosmos Hub provider testnet monitor on the validator host. Checks gaiad service, configured localhost RPC, peers, catching_up, validator bonded/jailed/tombstoned state, missed blocks, wallet balance, and resources. If testnet alerts, first check systemctl status gaiad, local /status and /net_info endpoints, gaiad query staking validator against the configured provider RPC, slashing signing-info, recent journal logs, and whether an upgrade event occurred.",
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
