from __future__ import annotations

from io import BytesIO
from pathlib import Path

MAX_CONTEXT_CHARS = 24000


def extract_document_text(data: bytes, filename: str, mime_type: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    mime = (mime_type or "").lower()
    try:
        if suffix == ".pdf" or mime == "application/pdf":
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(data))
            text = "\n".join((page.extract_text() or "") for page in reader.pages[:30])
        elif suffix == ".docx" or "wordprocessingml" in mime:
            from docx import Document
            document = Document(BytesIO(data))
            text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        elif suffix in {".txt", ".md", ".csv", ".json", ".xml", ".html", ".py", ".js", ".ts", ".css"} or mime.startswith("text/"):
            text = data.decode("utf-8", errors="replace")
        else:
            return ""
    except Exception:
        return ""
    return " ".join(text.split())[:MAX_CONTEXT_CHARS]
