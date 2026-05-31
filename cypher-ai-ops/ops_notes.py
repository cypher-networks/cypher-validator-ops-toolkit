import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class OpsNote:
    id: int
    monitor: str | None
    note: str
    created_by: str
    created_at: str
    expires_at: str | None


def _now() -> datetime:
    return datetime.now(UTC)


def _load(path: Path) -> dict:
    if not path.exists():
        return {"next_id": 1, "notes": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"next_id": 1, "notes": []}


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _parse_expires(value: str | None) -> str | None:
    if not value:
        return None
    raw = value.strip().lower()
    if not raw or raw in {"none", "never", "no"}:
        return None
    if raw == "tomorrow":
        return (_now() + timedelta(days=1)).isoformat()
    match = re.fullmatch(r"(\d+)\s*([hdw])", raw)
    if not match:
        return value.strip()
    amount = int(match.group(1))
    unit = match.group(2)
    if unit == "h":
        delta = timedelta(hours=amount)
    elif unit == "d":
        delta = timedelta(days=amount)
    else:
        delta = timedelta(weeks=amount)
    return (_now() + delta).isoformat()


def _is_expired(note: dict) -> bool:
    expires_at = note.get("expires_at")
    if not expires_at:
        return False
    try:
        parsed = datetime.fromisoformat(expires_at)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed <= _now()


def add_note(config, *, monitor: str | None, note: str, created_by: str, expires: str | None = None) -> OpsNote:
    data = _load(config.ops_notes_path)
    note_id = int(data.get("next_id", 1))
    record = {
        "id": note_id,
        "monitor": monitor.lower().strip() if monitor else None,
        "note": note.strip(),
        "created_by": created_by,
        "created_at": _now().isoformat(),
        "expires_at": _parse_expires(expires),
    }
    data.setdefault("notes", []).append(record)
    data["next_id"] = note_id + 1
    _save(config.ops_notes_path, data)
    return OpsNote(**record)


def forget_note(config, note_id: int) -> bool:
    data = _load(config.ops_notes_path)
    notes = data.get("notes", [])
    kept = [note for note in notes if int(note.get("id", -1)) != note_id]
    if len(kept) == len(notes):
        return False
    data["notes"] = kept
    _save(config.ops_notes_path, data)
    return True


def list_notes(config, monitor: str | None = None) -> list[OpsNote]:
    data = _load(config.ops_notes_path)
    monitor_key = monitor.lower().strip() if monitor else None
    active: list[OpsNote] = []
    changed = False
    kept: list[dict] = []
    for record in data.get("notes", []):
        if _is_expired(record):
            changed = True
            continue
        kept.append(record)
        if monitor_key and record.get("monitor") not in {monitor_key, None}:
            continue
        active.append(OpsNote(**record))
    if changed:
        data["notes"] = kept
        _save(config.ops_notes_path, data)
    return active


def format_notes(notes: list[OpsNote]) -> str:
    if not notes:
        return "No active ops notes."
    lines: list[str] = []
    for note in notes:
        monitor = note.monitor or "global"
        expires = note.expires_at or "never"
        lines.append(f"#{note.id} [{monitor}] {note.note} (expires: {expires})")
    return "\n".join(lines)


def collect_notes_context(config, monitor: str | None = None) -> str:
    notes = list_notes(config, monitor=monitor)
    if not notes:
        return ""
    return "Active ops notes:\n" + format_notes(notes)
