"""文档加载器 — 支持 .pdf / .docx / .txt / .md 转 list[str] 形式的页面级文本。"""
from __future__ import annotations

from pathlib import Path


class UnsupportedFormatError(Exception):
    """当文件扩展名没有注册对应加载器时抛出。"""


def load_document(path: Path | str) -> list[str]:
    """加载一个文档,按页/节返回文本列表。

    - `.txt` / `.md` → 单元素列表,包含完整内容。
    - `.pdf` → 每页一个元素。
    - `.docx` → 单元素,段落以 `\\n\\n` 拼接。

    参数:
        path: 文件路径(Path 或 str)。

    返回值:
        list[str]: 按页/节切分的文本列表。

    抛出:
        UnsupportedFormatError: 当扩展名不被支持时。
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
    """加载 PDF 文件,每页返回一段文本。

    参数:
        p: PDF 文件路径。

    返回值:
        list[str]: 每页提取的文本列表。
    """
    from pypdf import PdfReader

    reader = PdfReader(str(p))
    return [(page.extract_text() or "") for page in reader.pages]


def _load_docx(p: Path) -> list[str]:
    """加载 DOCX 文件,段落以双换行拼接返回单段文本。

    参数:
        p: DOCX 文件路径。

    返回值:
        list[str]: 单元素列表,包含全部段落拼接后的文本。
    """
    from docx import Document

    doc = Document(str(p))
    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    return ["\n\n".join(paragraphs)]