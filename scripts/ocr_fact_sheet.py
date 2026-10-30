from pathlib import Path
import pymupdf
import fitz
import pytesseract
from PIL import Image

PDF_PATH = Path("sources/Patient Safety Fact Sheet.pdf")
OUTPUT_PATH = Path("sources/patient_safety_fact_sheet_ocr.txt")

# Uncomment and adjust this if Tesseract is not detected automatically.
# pytesseract.pytesseract.tesseract_cmd = (
#     r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# )

doc = fitz.open(PDF_PATH)
all_pages = []

for page_number, page in enumerate(doc, start=1):
    # Render each page at a resolution suitable for OCR.
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    text = pytesseract.image_to_string(image, lang="eng")
    all_pages.append(f"\n--- Page {page_number} ---\n{text}")

    print(f"Processed page {page_number}/{len(doc)}: {len(text)} characters")

extracted_text = "\n".join(all_pages).strip()
OUTPUT_PATH.write_text(extracted_text, encoding="utf-8")

print("\nOCR complete.")
print("Extracted characters:", len(extracted_text))
print("Saved to:", OUTPUT_PATH)
print("\nPreview:\n", extracted_text[:1500])
