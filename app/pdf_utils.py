# app/pdf_utils.py
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Try imports
PDF2IMAGE_AVAILABLE = False
FITZ_AVAILABLE = False
PDF2IMAGE_EXC = None
try:
    from pdf2image import convert_from_path
    from pdf2image.exceptions import PDFInfoNotInstalledError
    PDF2IMAGE_AVAILABLE = True
    PDF2IMAGE_EXC = PDFInfoNotInstalledError
except Exception:
    try:
        import fitz  # PyMuPDF
        FITZ_AVAILABLE = True
    except Exception:
        FITZ_AVAILABLE = False

# If both libraries are present, prefer PyMuPDF (faster, fewer external deps),
# but we still support pdf2image if you want Poppler usage.
try:
    import fitz
    FITZ_AVAILABLE = True
except Exception:
    FITZ_AVAILABLE = FITZ_AVAILABLE  # unchanged

def convert_pdf_to_images(pdf_path: str, out_dir: str, dpi: int = 300):
    """
    Convert a PDF to JPEG images saved in out_dir.
    Returns list of image file paths.
    Priority:
      1) PyMuPDF (fitz) if available
      2) pdf2image (requires poppler) if available
    Raises RuntimeError with actionable message if conversion not possible.
    """
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    images = []

    # Try PyMuPDF / fitz first (no external dependency)
    if FITZ_AVAILABLE:
        try:
            import fitz
            doc = fitz.open(pdf_path)
            for i, page in enumerate(doc):
                mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                outp = Path(out_dir) / f"page_{i + 1:03d}.jpg"
                pix.save(str(outp))
                images.append(str(outp))
            return images
        except Exception as e:
            logger.exception("PyMuPDF conversion failed: %s", e)
            # fallthrough to try pdf2image if available

    # Try pdf2image (requires Poppler)
    if PDF2IMAGE_AVAILABLE:
        try:
            # Optionally, caller may supply poppler_path via environment or config.
            # convert_from_path will use system PATH to find poppler binaries.
            pil_images = convert_from_path(pdf_path, dpi=dpi)
            for i, pil in enumerate(pil_images):
                p = Path(out_dir) / f"page_{i + 1:03d}.jpg"
                pil.save(str(p), "JPEG")
                images.append(str(p))
            return images
        except Exception as e:
            # If this was a Poppler-missing issue, raise helpful message
            if PDF2IMAGE_EXC and isinstance(e, PDF2IMAGE_EXC):
                msg = (
                    "pdf2image failed because Poppler is not installed or not in PATH. "
                    "Install Poppler and add its 'bin' folder to PATH, or install PyMuPDF "
                    "(`pip install pymupdf`) so the service can fallback to it."
                )
                logger.error(msg)
                raise RuntimeError(msg) from e
            logger.exception("pdf2image.convert_from_path failed: %s", e)
            # fallthrough

    # If neither method produced images, return helpful error
    raise RuntimeError(
        "No PDF conversion method available. "
        "Install PyMuPDF (pip install pymupdf) or Poppler (for pdf2image) and ensure binaries are on PATH."
    )
