"""Extract plain text from an uploaded PDF's raw bytes."""

import io
from pypdf import PdfReader


def extract_text(file_bytes: bytes, max_chars: int = 45000) -> str:
    """Read every page and join the text. Truncated to max_chars so the
    extraction prompt stays a reasonable size for the LLM call -- for a
    typical journal paper this comfortably covers title, abstract,
    introduction, method, results and conclusion."""
    reader = PdfReader(io.BytesIO(file_bytes))
    chunks = []
    for page in reader.pages:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            continue
    text = "\n".join(chunks)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[... truncated ...]"
    return text
