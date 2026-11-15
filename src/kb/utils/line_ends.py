"""Read a page as LF text plus its line ends, and write an edit of it back with them."""

from pathlib import Path


def read_page_text(path: Path) -> tuple[str, list[str]]:
    return "", []


def restore_line_ends(text: str, original: str, ends: list[str]) -> str:
    return ""
