import os
from typing import Any

import requests

from health_checks import redact_sensitive, truncate_report


def _post_json(name: str, url: str, payload: dict[str, Any], timeout: int = 5) -> str:
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        return f"## {name}\nHTTP {response.status_code}\n{redact_sensitive(response.text[:3000])}"
    except requests.RequestException as exc:
        return f"## {name}\n<unreachable: {exc}>"


def _get(name: str, url: str, timeout: int = 5) -> str:
    try:
        response = requests.get(url, timeout=timeout)
        return f"## {name}\nHTTP {response.status_code}\n{redact_sensitive(response.text[:3000])}"
    except requests.RequestException as exc:
        return f"## {name}\n<unreachable: {exc}>"


def _json_rpc(method: str, params: list[Any] | None = None) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}


def _env_rpc(name: str, default: str) -> str:
    return os.getenv(name, default).strip().rstrip("/")


def collect_sync_status_report() -> str:
    mainnet_rpc = _env_rpc("COSMOS_MAINNET_RPC", "http://127.0.0.1:26657")
    testnet_rpc = _env_rpc("COSMOS_TESTNET_RPC", "http://127.0.0.1:26657")

    sections = [
        _get("cosmos_mainnet_status", f"{mainnet_rpc}/status"),
        _get("cosmos_mainnet_net_info", f"{mainnet_rpc}/net_info"),
        _get("cosmos_testnet_status", f"{testnet_rpc}/status"),
        _get("cosmos_testnet_net_info", f"{testnet_rpc}/net_info"),
    ]
    return truncate_report("\n\n".join(sections), max_chars=14000)
