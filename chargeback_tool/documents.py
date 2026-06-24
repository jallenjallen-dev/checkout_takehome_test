"""Load merchant evidence for the LLM.

Strategy (see README): PDFs in this dataset are text-based, so we extract text per page
with pypdf and tag each page so the model can cite '[filename p.N]'. PNGs are images, so
we base64-encode them and pass them to the vision model. This gives precise citations for
the buried-evidence PDF while still reading the image-only proofs.
"""

from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

DOCUMENTS_DIR = Path("data/documents")

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


@dataclass
class LoadedDocument:
    filename: str
    kind: str  # "pdf" | "image" | "missing" | "unreadable"
    text: str = ""  # extracted text (pdf), or "" for images
    image_data_url: str | None = None  # data: URL for vision (images only)
    note: str = ""  # problems worth surfacing to the analyst


def _read_pdf(path: Path) -> tuple[str, str]:
    """Return (page-tagged text, note)."""
    try:
        reader = PdfReader(str(path))
    except Exception as exc:  # noqa: BLE001 - take-home: surface, don't crash
        return "", f"could not parse PDF: {exc}"

    pages: list[str] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            content = (page.extract_text() or "").strip()
        except Exception:  # noqa: BLE001
            content = ""
        if content:
            pages.append(f"[{path.name} p.{i}]\n{content}")
        else:
            pages.append(f"[{path.name} p.{i}]\n(no extractable text on this page)")

    note = ""
    if not any("no extractable text" not in p for p in pages):
        note = "no extractable text - may be a scanned/image PDF"
    return "\n\n".join(pages), note


def _read_image(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def load_document(filename: str, base_dir: Path = DOCUMENTS_DIR) -> LoadedDocument:
    path = base_dir / filename
    if not path.exists():
        return LoadedDocument(filename, kind="missing", note="file not found in documents/")

    ext = path.suffix.lower()
    if ext == ".pdf":
        text, note = _read_pdf(path)
        return LoadedDocument(filename, kind="pdf", text=text, note=note)
    if ext in IMAGE_EXTS:
        try:
            data_url = _read_image(path)
        except Exception as exc:  # noqa: BLE001
            return LoadedDocument(filename, kind="unreadable", note=f"could not read image: {exc}")
        return LoadedDocument(filename, kind="image", image_data_url=data_url)

    return LoadedDocument(filename, kind="unreadable", note=f"unsupported file type {ext}")


def load_documents(filenames: list[str], base_dir: Path = DOCUMENTS_DIR) -> list[LoadedDocument]:
    return [load_document(f, base_dir) for f in filenames]
