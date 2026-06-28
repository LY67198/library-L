from pathlib import Path

import pytest

from app.rag.loaders import load_document, UnsupportedFormatError


def test_load_text(tmp_path: Path):
    f = tmp_path / "doc.txt"
    f.write_text("hello world", encoding="utf-8")
    pages = load_document(f)
    assert len(pages) == 1
    assert pages[0] == "hello world"


def test_load_markdown(tmp_path: Path):
    f = tmp_path / "doc.md"
    f.write_text("# Title\n\nBody", encoding="utf-8")
    pages = load_document(f)
    assert pages == ["# Title\n\nBody"]


def test_unsupported_format_raises(tmp_path: Path):
    f = tmp_path / "doc.xyz"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(UnsupportedFormatError):
        load_document(f)


def test_load_docx(tmp_path: Path):
    from docx import Document
    f = tmp_path / "doc.docx"
    doc = Document()
    doc.add_paragraph("paragraph one")
    doc.add_paragraph("paragraph two")
    doc.save(f)
    pages = load_document(f)
    assert len(pages) == 1
    assert "paragraph one" in pages[0]
    assert "paragraph two" in pages[0]


def test_load_pdf(tmp_path: Path):
    # Use a real PDF if pypdf can find one; skip if generation is too involved
    pytest.importorskip("pypdf")
    # Minimal: write a 1-page PDF using pypdf's writer
    from pypdf import PdfWriter
    f = tmp_path / "doc.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    # pypdf cannot write text easily without reportlab; skip real content
    writer.write(str(f))
    pages = load_document(f)
    # blank page returns empty string
    assert isinstance(pages, list)