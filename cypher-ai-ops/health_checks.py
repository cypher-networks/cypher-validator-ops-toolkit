import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Iterable


SENSITIVE_PATTERNS = [
    re.compile(r"(DISCORD_BOT_TOKEN|API_KEY|SECRET|TOKEN|PRIVATE_KEY|SEED|MNEMONIC)=\S+", re.IGNORECASE),
    re.compile(r"https://discord\.com/api/webhooks/\S+", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]+\b"),
    re.compile(r"\b[A-Fa-f0-9]{64}\b"),
]


@dataclass(frozen=True)
class CommandResult:
    name: str
    command: list[str]
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool = False


BASE_COMMANDS: dict[str, list[str]] = {
    "hostname": ["hostname"],
    "date": ["date"],
    "uptime": ["uptime"],
    "df": ["df", "-h"],
    "free": ["free", "-h"],
    "lscpu": ["lscpu"],
    "lsblk": ["lsblk"],
    "ip_addr": ["ip", "a"],
    "ip_route": ["ip", "route"],
    "ss_listen": ["ss", "-tulpn"],
    "systemctl_failed": ["systemctl", "--failed", "--no-pager"],
    "nvidia_smi": ["nvidia-smi"],
    "journal_errors": ["journalctl", "-p", "3", "-n", "50", "--no-pager"],
}


def redact_sensitive(text: str) -> str:
    redacted = text
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub("<redacted>", redacted)
    return redacted


def command_available(command: list[str]) -> bool:
    if not command:
        return False
    return shutil.which(command[0]) is not None


def run_command(name: str, command_list: list[str], timeout: int = 10) -> CommandResult:
    if not command_available(command_list):
        return CommandResult(
            name=name,
            command=command_list,
            returncode=None,
            stdout="",
            stderr=f"Command not found: {command_list[0]}",
        )

    try:
        completed = subprocess.run(
            command_list,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return CommandResult(
            name=name,
            command=command_list,
            returncode=completed.returncode,
            stdout=redact_sensitive(completed.stdout.strip()),
            stderr=redact_sensitive(completed.stderr.strip()),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        return CommandResult(
            name=name,
            command=command_list,
            returncode=None,
            stdout=redact_sensitive(stdout.strip()),
            stderr=redact_sensitive(stderr.strip() or f"Timed out after {timeout}s"),
            timed_out=True,
        )
    except OSError as exc:
        return CommandResult(
            name=name,
            command=command_list,
            returncode=None,
            stdout="",
            stderr=f"Failed to run command: {exc}",
        )


def format_result(result: CommandResult, max_chars: int = 6000) -> str:
    command = " ".join(result.command)
    status = "timeout" if result.timed_out else f"exit={result.returncode}"
    body_parts = []
    if result.stdout:
        body_parts.append(result.stdout)
    if result.stderr:
        body_parts.append(f"stderr:\n{result.stderr}")
    body = "\n".join(body_parts) or "<no output>"
    section = f"## {result.name} ({command}) [{status}]\n{body}"
    if len(section) > max_chars:
        section = section[: max_chars - 80] + "\n<truncated>"
    return section


def collect_commands(names: Iterable[str]) -> str:
    sections = []
    for name in names:
        command = BASE_COMMANDS[name]
        sections.append(format_result(run_command(name, command)))
    return "\n\n".join(sections)


def collect_health_report() -> str:
    names = [
        "hostname",
        "date",
        "uptime",
        "df",
        "free",
        "systemctl_failed",
        "journal_errors",
    ]
    sections = [collect_commands(names)]

    if shutil.which("docker"):
        sections.append(format_result(run_command("docker_ps", ["docker", "ps"])))
    else:
        sections.append("## docker_ps (docker ps) [skipped]\nDocker not installed or not in PATH")

    return "\n\n".join(sections)


def collect_disk_report() -> str:
    return collect_commands(["df", "lsblk"])


def collect_services_report() -> str:
    return collect_commands(["systemctl_failed"])


def collect_gpu_report() -> str:
    return collect_commands(["nvidia_smi"])


def collect_network_report() -> str:
    return collect_commands(["ip_addr", "ip_route", "ss_listen"])


def truncate_report(text: str, max_chars: int = 10000) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 80] + "\n<truncated>"
