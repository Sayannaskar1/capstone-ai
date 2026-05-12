"""
pdf_processor.py
Optimised PDF extraction — opens the document ONCE per call.
"""

import fitz  # PyMuPDF
from typing import List, Tuple, Dict, Any


# ── Primary (optimised) API ────────────────────────────────────────────────────

def extract_all(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Open the PDF exactly once and return:
        full_text   – concatenated text of all pages
        pages       – list of (page_number [1-based], page_text) tuples
        page_count  – total number of pages
        word_count  – approximate word count of the full text
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: List[Tuple[int, str]] = []
    full_text_parts: List[str] = []

    for i, page in enumerate(doc, start=1):
        text = page.get_text()
        pages.append((i, text))
        full_text_parts.append(text)

    full_text = "\n".join(full_text_parts)
    return {
        "full_text":  full_text,
        "pages":      pages,
        "page_count": len(pages),
        "word_count": len(full_text.split()),
    }


# ── Backward-compat wrappers (used by old code / tests) ───────────────────────

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Return the full concatenated text of a PDF. Calls extract_all internally."""
    return extract_all(pdf_bytes)["full_text"]


def extract_pages(pdf_bytes: bytes) -> List[Tuple[int, str]]:
    """Return per-page (page_number, text) tuples. Calls extract_all internally."""
    return extract_all(pdf_bytes)["pages"]


# ── Text chunking for RAG ──────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = 700, overlap: int = 100) -> List[str]:
    """
    Splits extracted text into overlapping word-based chunks for RAG.

    Args:
        text:       Full document text.
        chunk_size: Approximate number of words per chunk.
        overlap:    Number of words to overlap between consecutive chunks.

    Returns:
        List of text chunks.
    """
    words = text.split()
    if not words:
        return []

    chunks: List[str] = []
    start = 0
    step = max(1, chunk_size - overlap)

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += step

    return chunks
