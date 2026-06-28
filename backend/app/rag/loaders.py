"""Document loaders: .pdf / .docx / .txt / .md → list[str] of page-level text."""
from __future__ import annotations

from pathlib import Path


class UnsupportedFormatError(Exception):
    """Raised when a file extension has no registered loader."""


def load_document(path: Path | str) -> list[str]:
    """Load a document, returning one string per page/section.

    For .txt / .md → single-element list with full content.
    For .pdf → one element per page.
    For .docx → one element with paragraphs joined by '\n\n'.
    """
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in (".txt", ".md"):
        return [p.read_text(encoding="utf-8")]
    if suffix == ".pdf":
        return _load_pdf(p)
    if suffix == ".docx":
        return _load_docx(p)
    raise UnsupportedFormatError(f"No loader for extension: {suffix}")


def _load_pdf(p: Path) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(str(p))
    return [(page.extract_text() or "") for page in reader.pages]


def _load_docx(p: Path) -> list[str]:
    from docx import Document

    doc = Document(str(p))
    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    return ["\n\n".join(paragraphs)]