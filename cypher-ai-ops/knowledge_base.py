import re
from dataclasses import dataclass
from pathlib import Path

from health_checks import redact_sensitive, truncate_report


SUPPORTED_EXTENSIONS = {
    ".conf",
    ".env",
    ".json",
    ".md",
    ".markdown",
    ".service",
    ".toml",
    ".txt",
    ".rst",
    ".yaml",
    ".yml",
}
WORD_PATTERN = re.compile(r"[a-z0-9][a-z0-9_.:/-]*", re.IGNORECASE)
HEADING_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class KnowledgeSnippet:
    path: Path
    title: str
    score: int
    text: str


def _resolve_library_dir(config) -> Path:
    library_dir = config.knowledge_library_dir
    if not library_dir.is_absolute():
        library_dir = Path(__file__).resolve().parent / library_dir
    return library_dir.resolve()


def _tokens(text: str) -> set[str]:
    return {match.group(0).lower() for match in WORD_PATTERN.finditer(text)}


def _title_for(path: Path, text: str) -> str:
    match = HEADING_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    return path.stem.replace("-", " ").replace("_", " ").strip().title()


def _chunk_text(text: str, max_chars: int = 1800) -> list[str]:
    sections = re.split(r"(?=^\s{0,3}#{1,6}\s+)", text, flags=re.MULTILINE)
    chunks: list[str] = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        if len(section) <= max_chars:
            chunks.append(section)
            continue
        paragraphs = [part.strip() for part in section.split("\n\n") if part.strip()]
        current = ""
        for paragraph in paragraphs:
            candidate = f"{current}\n\n{paragraph}".strip()
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                chunks.append(current)
            current = paragraph[:max_chars]
        if current:
            chunks.append(current)
    return chunks


def _iter_library_files(library_dir: Path) -> list[Path]:
    if not library_dir.exists() or not library_dir.is_dir():
        return []
    return sorted(
        path
        for path in library_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
        and not any(part.startswith(".") for part in path.parts)
    )


def search_knowledge_library(query: str, config, *, monitor_name: str | None = None) -> list[KnowledgeSnippet]:
    library_dir = _resolve_library_dir(config)
    query_terms = _tokens(query)
    if monitor_name:
        query_terms.update(_tokens(monitor_name))
    if not query_terms:
        return []

    snippets: list[KnowledgeSnippet] = []
    for path in _iter_library_files(library_dir):
        try:
            raw_text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        text = redact_sensitive(raw_text)
        title = _title_for(path, text)
        path_terms = _tokens(path.stem)
        title_terms = _tokens(title)
        for chunk in _chunk_text(text):
            chunk_terms = _tokens(chunk)
            score = len(query_terms & chunk_terms)
            score += 3 * len(query_terms & title_terms)
            score += 2 * len(query_terms & path_terms)
            if monitor_name and monitor_name.lower() in path.stem.lower():
                score += 5
            if score <= 0:
                continue
            snippets.append(KnowledgeSnippet(path=path, title=title, score=score, text=chunk))

    snippets.sort(key=lambda item: (item.score, str(item.path)), reverse=True)
    return snippets[: config.knowledge_max_snippets]


def format_knowledge_snippets(snippets: list[KnowledgeSnippet], config) -> str:
    if not snippets:
        return ""
    library_dir = _resolve_library_dir(config)
    sections = []
    for index, snippet in enumerate(snippets, start=1):
        try:
            rel_path = snippet.path.relative_to(library_dir)
        except ValueError:
            rel_path = snippet.path
        sections.append(
            "\n".join(
                [
                    f"## Library snippet {index}: {snippet.title}",
                    f"File: {rel_path}",
                    f"Score: {snippet.score}",
                    snippet.text,
                ]
            )
        )
    return truncate_report("\n\n".join(sections), max_chars=config.knowledge_max_chars)


def collect_knowledge_context(query: str, config, *, monitor_name: str | None = None) -> str:
    snippets = search_knowledge_library(query, config, monitor_name=monitor_name)
    formatted = format_knowledge_snippets(snippets, config)
    if not formatted:
        return ""
    return f"Knowledge library context:\n{formatted}"


def describe_knowledge_library(config) -> str:
    library_dir = _resolve_library_dir(config)
    files = _iter_library_files(library_dir)
    if not library_dir.exists():
        return f"Library path: {library_dir}\nStatus: missing"
    return "\n".join(
        [
            f"Library path: {library_dir}",
            f"Indexed file types: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
            f"Indexed files: {len(files)}",
        ]
    )
