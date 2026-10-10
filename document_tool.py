"""Document Tool: extract clean text from an uploaded PDF."""
import io
import re

from pypdf import PdfReader

MAX_CHARS = 60_000  # keep the prompt within a sensible size


def extract_text(pdf_bytes: bytes):
    """Return (text, info). info = {pages, chars, warnings}. Never raises on bad PDFs."""
    info = {"pages": 0, "chars": 0, "warnings": []}
    if not pdf_bytes.startswith(b"%PDF"):
        info["warnings"].append("File does not look like a PDF (missing %PDF header).")
        return "", info
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        if reader.is_encrypted:
            reader.decrypt("")
        info["pages"] = len(reader.pages)
        parts = []
        for i, page in enumerate(reader.pages, 1):
            parts.append(f"[Page {i}]\n{page.extract_text() or ''}")
        text = "\n\n".join(parts)
    except Exception as exc:  # corrupt / encrypted PDFs
        info["warnings"].append(f"PDF could not be read: {exc}")
        return "", info

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(re.sub(r"\[Page \d+\]", "", text).strip()) < 200:
        info["warnings"].append("Very little text extracted - the PDF may be scanned (OCR needed).")
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]
        info["warnings"].append(f"Text truncated to {MAX_CHARS} characters.")
    info["chars"] = len(text)
    return text, info
