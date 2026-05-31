import json
from datetime import datetime, timezone
from pathlib import Path

from health_checks import redact_sensitive, truncate_report


def _context_dir(config) -> Path:
    context_dir = config.chat_context_dir
    if not context_dir.is_absolute():
        context_dir = Path(__file__).resolve().parent / context_dir
    return context_dir.resolve()


def _channel_file(config, channel_id: int) -> Path:
    return _context_dir(config) / f"{channel_id}.jsonl"


def record_chat_context(config, *, channel_id: int, author: str, content: str) -> None:
    if not config.chat_context_enabled:
        return
    clean_content = truncate_report(redact_sensitive(content.strip()), max_chars=2000)
    if not clean_content:
        return
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "channel_id": str(channel_id),
        "author": redact_sensitive(author)[:80],
        "content": clean_content,
    }
    path = _channel_file(config, channel_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
        _trim_file(path, config.chat_context_max_messages)
    except OSError:
        return


def _trim_file(path: Path, max_messages: int) -> None:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    if len(lines) <= max_messages:
        return
    try:
        path.write_text("\n".join(lines[-max_messages:]) + "\n", encoding="utf-8")
    except OSError:
        return


def collect_recent_chat_context(config, *, channel_id: int, max_chars: int = 2500) -> str:
    if not config.chat_context_enabled:
        return ""
    path = _channel_file(config, channel_id)
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""

    entries = []
    for line in lines[-config.chat_context_max_messages :]:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = str(entry.get("ts", ""))
        author = str(entry.get("author", "unknown"))
        content = str(entry.get("content", "")).strip()
        if not content:
            continue
        entries.append(f"[{ts}] {author}: {content}")

    if not entries:
        return ""
    return "Recent channel context:\n" + truncate_report("\n".join(entries), max_chars=max_chars)
