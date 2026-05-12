import fitz  # PyMuPDF
from typing import List, Tuple

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extracts raw text from a PDF file."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text


# --- NEW CODE START ---
def extract_pages(pdf_bytes: bytes) -> List[Tuple[int, str]]:
    """
    Extract text from each page individually.

    Returns:
        List of (page_number, page_text) tuples. Page numbers are 1-based.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for i, page in enumerate(doc, start=1):
        pages.append((i, page.get_text()))
    return pages
# --- NEW CODE END ---


# --- NEW CODE START ---
def chunk_text(text: str, chunk_size: int = 700, overlap: int = 100) -> List[str]:
    """
    Splits extracted text into overlapping word-based chunks for RAG.

    Args:
        text: Full document text.
        chunk_size: Approximate number of words per chunk.
        overlap: Number of words to overlap between consecutive chunks.

    Returns:
        List of text chunks.
    """
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == len(words):
            break
        start += chunk_size - overlap  # slide forward with overlap

    return chunks
# --- NEW CODE END ---
