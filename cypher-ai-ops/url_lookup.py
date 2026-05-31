import ipaddress
import re
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests

from config import AppConfig


URL_RE = re.compile(r"https?://[^\s<>()\"']+", re.IGNORECASE)


class UrlLookupError(RuntimeError):
    pass


@dataclass(frozen=True)
class UrlLookupResult:
    url: str
    final_url: str
    status_code: int
    content_type: str
    title: str
    text: str


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3"}:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text or self._skip_depth:
            return
        if self._in_title:
            self.title_parts.append(text)
        self.text_parts.append(text)


def extract_urls(text: str) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for match in URL_RE.finditer(text):
        url = match.group(0).rstrip(".,;:)]}")
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _domain_allowed(hostname: str, allowed_domains: tuple[str, ...]) -> bool:
    if not allowed_domains:
        return True
    hostname = hostname.lower().rstrip(".")
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in allowed_domains)


def _ip_is_public(ip_text: str) -> bool:
    ip = ipaddress.ip_address(ip_text)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _validate_url(url: str, cfg: AppConfig) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UrlLookupError("Only http and https URLs are allowed")
    if not parsed.hostname:
        raise UrlLookupError("URL must include a hostname")
    if not _domain_allowed(parsed.hostname, cfg.url_lookup_allowed_domains):
        allowed = ", ".join(cfg.url_lookup_allowed_domains)
        raise UrlLookupError(f"Domain is not in URL_LOOKUP_ALLOWED_DOMAINS: {allowed}")

    try:
        addresses = socket.getaddrinfo(
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise UrlLookupError(f"Could not resolve hostname: {parsed.hostname}") from exc

    resolved_ips = {item[4][0] for item in addresses}
    if not resolved_ips:
        raise UrlLookupError("Hostname resolved to no addresses")
    if any(not _ip_is_public(ip) for ip in resolved_ips):
        raise UrlLookupError("URL resolves to a private, local, or reserved address")


def _normalize_text(text: str, max_chars: int = 5000) -> str:
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n\s*", "\n", text)
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return text[:max_chars].strip()


def lookup_url(url: str, cfg: AppConfig) -> UrlLookupResult:
    if not cfg.enable_url_lookup:
        raise UrlLookupError("URL lookup is disabled. Set ENABLE_URL_LOOKUP=true to enable it.")

    _validate_url(url, cfg)

    current_url = url
    response = None
    try:
        for _ in range(6):
            _validate_url(current_url, cfg)
            response = requests.get(
                current_url,
                timeout=cfg.url_lookup_timeout_seconds,
                allow_redirects=False,
                stream=True,
                headers={"User-Agent": "CypherAIOps/1.0 (+operator-url-lookup)"},
            )
            if response.is_redirect or response.is_permanent_redirect:
                location = response.headers.get("location")
                if not location:
                    raise UrlLookupError("Redirect response did not include a Location header")
                next_url = urljoin(current_url, location)
                _validate_url(next_url, cfg)
                current_url = next_url
                response.close()
                continue
            break
        else:
            raise UrlLookupError("Too many redirects")

        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=8192):
            if not chunk:
                continue
            total += len(chunk)
            if total > cfg.url_lookup_max_bytes:
                remaining = cfg.url_lookup_max_bytes - (total - len(chunk))
                if remaining > 0:
                    chunks.append(chunk[:remaining])
                break
            chunks.append(chunk)
    except requests.RequestException as exc:
        raise UrlLookupError(f"Fetch failed: {exc}") from exc

    if response is None:
        raise UrlLookupError("Fetch did not return a response")

    final_url = response.url
    _validate_url(final_url, cfg)
    content_type = response.headers.get("content-type", "unknown").split(";")[0].strip().lower()
    raw = b"".join(chunks)

    if "text/html" in content_type:
        parser = _TextExtractor()
        parser.feed(raw.decode(response.encoding or "utf-8", errors="replace"))
        title = _normalize_text(" ".join(parser.title_parts), max_chars=200)
        text = _normalize_text(" ".join(parser.text_parts))
    elif content_type.startswith("text/") or content_type in {"application/json", "application/xml"}:
        title = ""
        text = _normalize_text(raw.decode(response.encoding or "utf-8", errors="replace"))
    else:
        title = ""
        text = f"Fetched non-text content type: {content_type}. Content was not included."

    if not text:
        text = "No readable text was found in the fetched page."

    return UrlLookupResult(
        url=url,
        final_url=final_url,
        status_code=response.status_code,
        content_type=content_type,
        title=title,
        text=text,
    )


def format_lookup_result(result: UrlLookupResult) -> str:
    parts = [
        f"URL: {result.url}",
        f"Final URL: {result.final_url}",
        f"Status: {result.status_code}",
        f"Content-Type: {result.content_type}",
    ]
    if result.title:
        parts.append(f"Title: {result.title}")
    parts.append(f"Text:\n{result.text}")
    return "\n".join(parts)
