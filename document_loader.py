
from pathlib import Path
from pypdf import PdfReader

# Find the documents folder next to this Python file.
BASE_DIR = Path(__file__).resolve().parent
DOCUMENTS_DIR = BASE_DIR / "documents"


def extract_pdf_text(filename):
    """Extract readable text from a PDF in the documents folder."""
    pdf_path = DOCUMENTS_DIR / filename

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF not found: {pdf_path}\n"
            "Check the filename and documents folder."
        )

    reader = PdfReader(str(pdf_path))
    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(f"--- Page {page_number} ---\n{text}")

    full_text = "\n\n".join(pages)

    if not full_text.strip():
        raise ValueError(
            f"No readable text found in {filename}. "
            "The PDF may be scanned and need OCR."
        )

    return full_text


if __name__ == "__main__":
    for filename in [
        "vt_honor_code.pdf",
        "research_readiness_rubric.pdf",
    ]:
        text = extract_pdf_text(filename)
        print(f"\n{filename}: extracted {len(text)} characters")
        print(text[:300])
