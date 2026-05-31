from dataclasses import dataclass


STATUS_TERMS = {
    "healthy",
    "health",
    "status",
    "running",
    "synced",
    "syncing",
    "sync",
    "high",
    "low",
    "memory",
    "ram",
    "swap",
    "disk",
    "peers",
    "stuck",
}
LIBRARY_TERMS = {
    "runbook",
    "docs",
    "doc",
    "config",
    "compose",
    "service",
    "systemd",
    "env",
    "where",
    "path",
}
ALERT_TERMS = {
    "alert",
    "why did",
    "why is",
    "down",
    "offline",
    "failed",
    "failure",
    "critical",
    "warning",
    "error",
    "missed",
    "panic",
    "panicked",
}


@dataclass(frozen=True)
class Intent:
    name: str
    answer_style: str


def classify_intent(text: str) -> Intent:
    lower_text = text.lower()
    words = set(lower_text.replace("?", " ").replace(",", " ").split())

    if any(term in lower_text for term in ALERT_TERMS):
        return Intent(
            name="alert_or_incident",
            answer_style="Treat this as a possible incident, but confirm with live evidence before escalating.",
        )
    if words & STATUS_TERMS or lower_text.startswith(("is ", "are ", "does ", "do ")):
        return Intent(
            name="status_question",
            answer_style="Answer directly from current evidence first. Only provide troubleshooting steps if evidence shows a problem or current evidence is missing.",
        )
    if words & LIBRARY_TERMS:
        return Intent(
            name="knowledge_lookup",
            answer_style="Answer from runbook/config context first. Mention when live state is unavailable or not checked.",
        )
    return Intent(
        name="operator_question",
        answer_style="Give a concise operator answer with practical next steps and clear evidence labels.",
    )
