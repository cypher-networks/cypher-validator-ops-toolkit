import json
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


def collect_sync_status_report() -> str:
    sections = [
        _post_json("ethereum_reth_eth_syncing", "http://127.0.0.1:8545", _json_rpc("eth_syncing")),
        _post_json("ethereum_reth_eth_blockNumber", "http://127.0.0.1:8545", _json_rpc("eth_blockNumber")),
        _post_json("ethereum_reth_net_peerCount", "http://127.0.0.1:8545", _json_rpc("net_peerCount")),
        _get("ethereum_lighthouse_health", "http://127.0.0.1:5052/eth/v1/node/health"),
        _get("ethereum_lighthouse_syncing", "http://127.0.0.1:5052/eth/v1/node/syncing"),
        _get("ethereum_lighthouse_peer_count", "http://127.0.0.1:5052/eth/v1/node/peer_count"),
        _post_json("aztec_block_number", "http://127.0.0.1:8080", _json_rpc("node_getBlockNumber")),
        _post_json("aztec_proven_block_number", "http://127.0.0.1:8080", _json_rpc("node_getProvenBlockNumber")),
        _get("espresso_status_block_height", "http://127.0.0.1/v1/status/block-height"),
        _get("espresso_time_since_last_decide", "http://127.0.0.1/v1/status/time-since-last-decide"),
        _get("espresso_success_rate", "http://127.0.0.1/v1/status/success-rate"),
        _get("cosmos_mainnet_status", "http://127.0.0.1:26657/status"),
        _get("cosmos_mainnet_net_info", "http://127.0.0.1:26657/net_info"),
        _get("cosmos_testnet_status", "http://127.0.0.1:26667/status"),
        _get("cosmos_testnet_net_info", "http://127.0.0.1:26667/net_info"),
        _post_json("starknet_syncing", "http://127.0.0.1:9545/rpc/v0_9", _json_rpc("starknet_syncing")),
        _post_json("starknet_blockNumber", "http://127.0.0.1:9545/rpc/v0_9", _json_rpc("starknet_blockNumber")),
    ]
    return truncate_report("\n\n".join(sections), max_chars=14000)
