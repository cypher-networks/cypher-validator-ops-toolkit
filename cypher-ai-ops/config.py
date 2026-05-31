import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    discord_bot_token: str
    discord_allowed_channel_ids: set[int]
    discord_channel_map: dict[int, str]
    discord_guild_id: int | None
    cypher_ai_monitor_channel_id: int | None
    ollama_url: str
    ollama_model: str
    ollama_require_gpu: bool
    auto_respond_to_alerts: bool
    alert_response_cooldown_seconds: int
    auto_daily_digest: bool
    daily_digest_hour_est: int
    daily_digest_minute_est: int
    enable_url_lookup: bool
    url_lookup_allowed_domains: tuple[str, ...]
    url_lookup_timeout_seconds: int
    url_lookup_max_bytes: int
    knowledge_library_dir: Path
    knowledge_max_snippets: int
    knowledge_max_chars: int
    remote_state_dir: Path
    ops_notes_path: Path
    chat_context_enabled: bool
    chat_context_dir: Path
    chat_context_max_messages: int
    enable_problem_search: bool
    problem_search_url: str
    problem_search_allowed_domains: tuple[str, ...]
    problem_search_max_results: int
    problem_search_fetch_pages: bool


class ConfigError(RuntimeError):
    pass


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc


def _env_optional_int(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc


def _parse_channel_ids() -> set[int]:
    values: list[str] = []

    single = os.getenv("DISCORD_ALLOWED_CHANNEL_ID", "").strip()
    if single:
        values.append(single)

    multi = os.getenv("DISCORD_ALLOWED_CHANNEL_IDS", "").strip()
    if multi:
        values.extend(item.strip() for item in multi.split(",") if item.strip())

    if not values:
        raise ConfigError("DISCORD_ALLOWED_CHANNEL_ID or DISCORD_ALLOWED_CHANNEL_IDS is required")

    channel_ids: set[int] = set()
    for value in values:
        try:
            channel_ids.add(int(value))
        except ValueError as exc:
            raise ConfigError(f"Invalid Discord channel ID: {value}") from exc
    return channel_ids


def _parse_channel_map() -> dict[int, str]:
    raw = os.getenv("DISCORD_CHANNEL_MAP", "").strip()
    if not raw:
        return {}

    mapping: dict[int, str] = {}
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ConfigError("DISCORD_CHANNEL_MAP entries must look like channel_id:monitor_name")
        channel_id_raw, monitor_name = item.split(":", 1)
        try:
            channel_id = int(channel_id_raw.strip())
        except ValueError as exc:
            raise ConfigError(f"Invalid Discord channel ID in DISCORD_CHANNEL_MAP: {channel_id_raw}") from exc
        monitor_name = monitor_name.strip().lower()
        if not monitor_name:
            raise ConfigError("DISCORD_CHANNEL_MAP monitor names cannot be empty")
        mapping[channel_id] = monitor_name
    return mapping


def _validate_digest_time(hour: int, minute: int) -> None:
    if not 0 <= hour <= 23:
        raise ConfigError("DAILY_DIGEST_HOUR_EST must be between 0 and 23")
    if not 0 <= minute <= 59:
        raise ConfigError("DAILY_DIGEST_MINUTE_EST must be between 0 and 59")


def _parse_allowed_domains() -> tuple[str, ...]:
    raw = os.getenv("URL_LOOKUP_ALLOWED_DOMAINS", "").strip()
    if not raw:
        return ()
    return tuple(item.strip().lower() for item in raw.split(",") if item.strip())


def _parse_csv_env(name: str, default: str = "") -> tuple[str, ...]:
    raw = os.getenv(name, default).strip()
    if not raw:
        return ()
    return tuple(item.strip().lower() for item in raw.split(",") if item.strip())


def _env_path(name: str, default: str) -> Path:
    value = os.getenv(name, default).strip()
    return Path(value).expanduser()


def load_config() -> AppConfig:
    load_dotenv()

    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434").strip().rstrip("/")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b").strip()
    ollama_require_gpu = _env_bool("OLLAMA_REQUIRE_GPU", False)
    auto_respond_to_alerts = _env_bool("AUTO_RESPOND_TO_ALERTS", True)
    alert_response_cooldown_seconds = _env_int("ALERT_RESPONSE_COOLDOWN_SECONDS", 60)
    discord_guild_id = _env_optional_int("DISCORD_GUILD_ID")
    cypher_ai_monitor_channel_id = _env_optional_int("CYPHER_AI_MONITOR_CHANNEL_ID")
    auto_daily_digest = _env_bool("AUTO_DAILY_DIGEST", cypher_ai_monitor_channel_id is not None)
    daily_digest_hour_est = _env_int("DAILY_DIGEST_HOUR_EST", 5)
    daily_digest_minute_est = _env_int("DAILY_DIGEST_MINUTE_EST", 10)
    enable_url_lookup = _env_bool("ENABLE_URL_LOOKUP", False)
    url_lookup_allowed_domains = _parse_allowed_domains()
    url_lookup_timeout_seconds = _env_int("URL_LOOKUP_TIMEOUT_SECONDS", 8)
    url_lookup_max_bytes = _env_int("URL_LOOKUP_MAX_BYTES", 120000)
    knowledge_library_dir = _env_path("KNOWLEDGE_LIBRARY_DIR", "../ai-lookup-library")
    knowledge_max_snippets = _env_int("KNOWLEDGE_MAX_SNIPPETS", 5)
    knowledge_max_chars = _env_int("KNOWLEDGE_MAX_CHARS", 7000)
    remote_state_dir = _env_path("REMOTE_STATE_DIR", "remote-state")
    ops_notes_path = _env_path("OPS_NOTES_PATH", "data/ops-notes.json")
    chat_context_enabled = _env_bool("CHAT_CONTEXT_ENABLED", True)
    chat_context_dir = _env_path("CHAT_CONTEXT_DIR", "data/chat-context")
    chat_context_max_messages = _env_int("CHAT_CONTEXT_MAX_MESSAGES", 30)
    enable_problem_search = _env_bool("ENABLE_PROBLEM_SEARCH", False)
    problem_search_url = os.getenv("PROBLEM_SEARCH_URL", "http://127.0.0.1:8080").strip().rstrip("/")
    problem_search_allowed_domains = _parse_csv_env(
        "PROBLEM_SEARCH_ALLOWED_DOMAINS",
        "github.com,docs.github.com,gitbook.io,docs.espressosys.com,docs.babylonlabs.io,docs.aztec.network,docs.starknet.io,docs.cardano.org,ethereum.org,lighthouse-book.sigmaprime.io,reth.rs",
    )
    problem_search_max_results = _env_int("PROBLEM_SEARCH_MAX_RESULTS", 3)
    problem_search_fetch_pages = _env_bool("PROBLEM_SEARCH_FETCH_PAGES", True)
    _validate_digest_time(daily_digest_hour_est, daily_digest_minute_est)
    if not 1 <= url_lookup_timeout_seconds <= 30:
        raise ConfigError("URL_LOOKUP_TIMEOUT_SECONDS must be between 1 and 30")
    if not 1000 <= url_lookup_max_bytes <= 1000000:
        raise ConfigError("URL_LOOKUP_MAX_BYTES must be between 1000 and 1000000")
    if not 1 <= knowledge_max_snippets <= 10:
        raise ConfigError("KNOWLEDGE_MAX_SNIPPETS must be between 1 and 10")
    if not 1000 <= knowledge_max_chars <= 20000:
        raise ConfigError("KNOWLEDGE_MAX_CHARS must be between 1000 and 20000")
    if not 1 <= chat_context_max_messages <= 200:
        raise ConfigError("CHAT_CONTEXT_MAX_MESSAGES must be between 1 and 200")
    if not 1 <= problem_search_max_results <= 8:
        raise ConfigError("PROBLEM_SEARCH_MAX_RESULTS must be between 1 and 8")
    if enable_problem_search and not problem_search_url:
        raise ConfigError("PROBLEM_SEARCH_URL is required when ENABLE_PROBLEM_SEARCH=true")

    if not token:
        raise ConfigError("DISCORD_BOT_TOKEN is required")

    allowed_channel_ids = _parse_channel_ids()
    channel_map = _parse_channel_map()

    unknown_mapped_channels = set(channel_map) - allowed_channel_ids
    if unknown_mapped_channels:
        raise ConfigError(
            "Every DISCORD_CHANNEL_MAP channel must also be in DISCORD_ALLOWED_CHANNEL_IDS. "
            f"Missing: {sorted(unknown_mapped_channels)}"
        )

    return AppConfig(
        discord_bot_token=token,
        discord_allowed_channel_ids=allowed_channel_ids,
        discord_channel_map=channel_map,
        discord_guild_id=discord_guild_id,
        cypher_ai_monitor_channel_id=cypher_ai_monitor_channel_id,
        ollama_url=ollama_url,
        ollama_model=ollama_model,
        ollama_require_gpu=ollama_require_gpu,
        auto_respond_to_alerts=auto_respond_to_alerts,
        alert_response_cooldown_seconds=alert_response_cooldown_seconds,
        auto_daily_digest=auto_daily_digest,
        daily_digest_hour_est=daily_digest_hour_est,
        daily_digest_minute_est=daily_digest_minute_est,
        enable_url_lookup=enable_url_lookup,
        url_lookup_allowed_domains=url_lookup_allowed_domains,
        url_lookup_timeout_seconds=url_lookup_timeout_seconds,
        url_lookup_max_bytes=url_lookup_max_bytes,
        knowledge_library_dir=knowledge_library_dir,
        knowledge_max_snippets=knowledge_max_snippets,
        knowledge_max_chars=knowledge_max_chars,
        remote_state_dir=remote_state_dir,
        ops_notes_path=ops_notes_path,
        chat_context_enabled=chat_context_enabled,
        chat_context_dir=chat_context_dir,
        chat_context_max_messages=chat_context_max_messages,
        enable_problem_search=enable_problem_search,
        problem_search_url=problem_search_url,
        problem_search_allowed_domains=problem_search_allowed_domains,
        problem_search_max_results=problem_search_max_results,
        problem_search_fetch_pages=problem_search_fetch_pages,
    )
