import re
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

from config import AppConfig
from health_checks import truncate_report
from url_lookup import UrlLookupError, format_lookup_result, lookup_url


class ProblemSearchError(RuntimeError):
    pass


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    content: str


NOISE_PATTERNS = (
    re.compile(r"https?://\S+", re.IGNORECASE),
    re.compile(r"\b0x[a-fA-F0-9]{20,}\b"),
    re.compile(r"\b[a-z0-9]{24,}\b", re.IGNORECASE),
)


def _clean_query(text: str) -> str:
    cleaned = text
    for pattern in NOISE_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    cleaned = re.sub(r"[^a-zA-Z0-9_./: -]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:240]


def _domain_allowed(url: str, allowed_domains: tuple[str, ...]) -> bool:
    hostname = (urlparse(url).hostname or "").lower().rstrip(".")
    if not hostname:
        return False
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in allowed_domains)


def build_problem_query(problem_text: str, *, monitor_name: str | None = None) -> str:
    base = _clean_query(problem_text)
    parts = []
    if monitor_name:
        parts.append(monitor_name)
    parts.append(base)
    parts.append("troubleshooting docs github")
    return " ".join(part for part in parts if part).strip()


def search_problem(problem_text: str, cfg: AppConfig, *, monitor_name: str | None = None) -> list[SearchResult]:
    if not cfg.enable_problem_search:
        raise ProblemSearchError("Problem search is disabled. Set ENABLE_PROBLEM_SEARCH=true to enable it.")
    if not cfg.problem_search_allowed_domains:
        raise ProblemSearchError("PROBLEM_SEARCH_ALLOWED_DOMAINS cannot be empty")

    query = build_problem_query(problem_text, monitor_name=monitor_name)
    try:
        response = requests.get(
            f"{cfg.problem_search_url}/search",
            params={"q": query, "format": "json"},
            timeout=cfg.url_lookup_timeout_seconds,
            headers={"User-Agent": "CypherAIOps/1.0 (+problem-search)"},
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise ProblemSearchError(f"Search request failed: {exc}") from exc
    except ValueError as exc:
        raise ProblemSearchError("Search endpoint did not return JSON") from exc

    results = []
    for item in payload.get("results", []):
        url = str(item.get("url") or "").strip()
        if not url or not _domain_allowed(url, cfg.problem_search_allowed_domains):
            continue
        results.append(
            SearchResult(
                title=str(item.get("title") or "Untitled").strip(),
                url=url,
                content=str(item.get("content") or "").strip(),
            )
        )
        if len(results) >= cfg.problem_search_max_results:
            break
    return results


def collect_problem_search_context(problem_text: str, cfg: AppConfig, *, monitor_name: str | None = None) -> str:
    results = search_problem(problem_text, cfg, monitor_name=monitor_name)
    if not results:
        return "Problem search context:\nNo allowed search results found."

    sections = []
    for index, result in enumerate(results, start=1):
        section = [
            f"## Search result {index}: {result.title}",
            f"URL: {result.url}",
        ]
        if result.content:
            section.append(f"Search snippet: {result.content}")
        if cfg.problem_search_fetch_pages:
            try:
                fetched = lookup_url(result.url, cfg)
                section.append(format_lookup_result(fetched))
            except UrlLookupError as exc:
                section.append(f"Fetch skipped/failed: {exc}")
        sections.append("\n".join(section))
    return "Problem search context:\n" + truncate_report("\n\n".join(sections), max_chars=7000)
