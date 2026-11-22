"""Citation and provenance tracking for query answers."""

import html as _html
import re
from pathlib import Path

# Matches both legacy `[source: X]` / `[ref: X]` and canonical `[[X]]` formats.
# Cycle 5 redo T1: prompt at engine.py instructs the new wikilink form; the
# extractor accepts both so legacy LLM outputs and persisted answers continue
# to parse.
_CITATION_PATTERN = re.compile(r"\[(source|ref):\s*([\w/_.-]+)\]|\[\[([\w/_.-]+)\]\]")

_VALID_FORMAT_MODES = frozenset({"markdown", "html", "marp"})


def extract_citations(text: str) -> list[dict]:
    """Extract citation references from an LLM-generated answer.

    Looks for patterns like [source: wiki/path] or [ref: raw/path] in text.
    Overrides type based on path prefix: raw/ paths are always type="raw".

    Item 17 (cycle 2): deduplicate by `(type, path)` preserving the first
    occurrence's context. Prior behaviour produced duplicate citations from
    the same page/source mentioned multiple times in one answer, inflating
    the downstream Sources list.

    Returns:
        List of dicts with keys: type ('wiki' or 'raw'), path, context (surrounding text).
    """
    citations = []
    seen: set[tuple[str, str]] = set()
    for match in _CITATION_PATTERN.finditer(text):
        # Group 2 = legacy `[source|ref: X]` path; group 3 = canonical `[[X]]` path.
        # Exactly one will be non-None per match.
        legacy_kind = match.group(1)
        path = match.group(2) if legacy_kind is not None else match.group(3)
        if ".." in path or path.startswith("/"):
            continue
        # Q_K_a fix (Phase 4.5 HIGH): reject per-segment leading-dot (e.g. raw/articles/.env)
        # while allowing legitimate dot-in-name (e.g. raw/articles/foo.env.md).
        # The old path.startswith(".") check was too broad — it only caught top-level dotfiles.
        if any(not part or part.startswith(".") for part in path.split("/")):
            continue
        if legacy_kind == "ref":
            cite_type = "raw"
        else:
            # legacy `[source: X]` and canonical `[[X]]` both default to wiki;
            # path-prefix check below promotes raw/ paths.
            cite_type = "wiki"
        # Override type based on path prefix
        if path.startswith("raw/"):
            cite_type = "raw"
        key = (cite_type, path)
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            {
                "type": cite_type,
                "path": path,
                "context": text[max(0, match.start() - 50) : match.end() + 50].strip(),
            }
        )
    return citations


def partition_citations(
    citations: list[dict],
    *,
    wiki_ids: set[str] | list[str],
    raw_ids: set[str] | list[str],
    wiki_dir: Path,
    raw_dir: Path,
) -> tuple[list[dict], list[dict]]:
    """Split extracted citations into those that were in the prompt and the rest.

    T0-KBFIX-CITECTX (#189): a ``wiki`` citation is accepted only when its path,
    compared case-insensitively, is one of ``wiki_ids`` (``context_pages``); a
    ``raw`` citation only when it is one of ``raw_ids`` (the raw ids the raw-source
    fallback put in the prompt). The two sets are checked per type, so a
    ``[ref: <wiki id>]`` citation does not pass on a wiki page's allowance.
    Each other citation is returned with ``reason``: ``"out_of_context"`` when the
    page or raw file exists, ``"nonexistent"`` when it does not. The existence
    probe only ever sees paths that passed ``extract_citations``' shape filter
    (no ``..``, no leading ``/``, no empty or dot-leading segment), so it stays
    under ``wiki_dir`` / ``raw_dir``.

    Returns:
        ``(accepted, rejected)``. Accepted entries are the input dicts unchanged;
        rejected entries are copies with an added ``reason`` key.
    """
    allowed = {
        "wiki": {pid.lower() for pid in wiki_ids},
        "raw": {rid.lower() for rid in raw_ids},
    }
    accepted: list[dict] = []
    rejected: list[dict] = []
    for cite in citations:
        path = cite["path"]
        if path.lower() in allowed.get(cite["type"], set()):
            accepted.append(cite)
            continue
        if cite["type"] == "raw":
            # The raw/ prefix is matched case-insensitively, as the id comparison is.
            relative = path[len("raw/") :] if path.lower().startswith("raw/") else path
            exists = _is_file_ignoring_case(raw_dir, relative.split("/"))
        else:
            parts = path.split("/")
            parts[-1] += ".md"
            exists = _is_file_ignoring_case(wiki_dir, parts)
        reason = "out_of_context" if exists else "nonexistent"
        rejected.append({**cite, "reason": reason})
    return accepted, rejected


def _is_file_ignoring_case(base: Path, parts: list[str]) -> bool:
    """True when ``base/<parts>`` names a file, each segment matched case-insensitively.

    Ids are compared lower-cased (``page_id`` lower-cases the file path), so on a
    case-sensitive filesystem ``concepts/hydration`` must still find
    ``concepts/Hydration.md``. An exact-case segment is tried first; otherwise the
    directory is listed once for that segment. Any ``OSError`` (for example
    ``ENAMETOOLONG`` on a model-written name, or an unreadable directory) means
    the file is not found: a citation's reason must never abort the query.
    """
    current = base
    try:
        for part in parts:
            exact = current / part
            if exact.exists():
                current = exact
                continue
            if not current.is_dir():
                return False
            wanted = part.lower()
            match = next((c for c in current.iterdir() if c.name.lower() == wanted), None)
            if match is None:
                return False
            current = match
        return current.is_file()
    except OSError:
        return False


def format_citations(citations: list[dict], mode: str = "markdown") -> str:
    """Format citations as a sources section in the requested mode.

    Modes:
        "markdown" (default): legacy behavior — `[[wikilinks]]` + `` `raw/paths` ``.
        "html":     `<ul>` list of `<a href="./wiki/path.md">path</a>` + `<code>raw/path</code>`.
        "marp":     same rendering as markdown (kept as distinct mode so future
                    Marp-specific link syntax can diverge).

    Raises:
        ValueError: unknown mode.
    """
    if mode not in _VALID_FORMAT_MODES:
        raise ValueError(
            f"format_citations: unknown mode '{mode}'; "
            f"expected one of {sorted(_VALID_FORMAT_MODES)}"
        )
    if not citations:
        return ""

    seen: set[str] = set()
    deduped: list[dict] = []
    for cite in citations:
        path = cite["path"]
        if path in seen:
            continue
        seen.add(path)
        deduped.append(cite)

    if mode == "html":
        lines = ['<ul class="sources">']
        for cite in deduped:
            escaped_path = _html.escape(cite["path"], quote=True)
            if cite["type"] == "wiki":
                href = f"./wiki/{escaped_path}.md"
                lines.append(f'  <li><a href="{href}">{escaped_path}</a></li>')
            else:
                lines.append(f"  <li><code>{escaped_path}</code></li>")
        lines.append("</ul>")
        return "\n".join(lines)

    # markdown + marp share the current legacy rendering
    lines = ["\n---\n**Sources:**\n"]
    for cite in deduped:
        path = cite["path"]
        if cite["type"] == "wiki":
            lines.append(f"- [[{path}]]")
        else:
            lines.append(f"- `{path}`")
    return "\n".join(lines)
