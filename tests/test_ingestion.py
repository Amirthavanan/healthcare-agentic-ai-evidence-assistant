import pytest
from pathlib import Path
from retrieval.hybrid import clean_text, chunk_text, _load_source, _tokens, SOURCE_DIR


def test_clean_text_ligatures():
    dirty = "The workﬂow and patient identiﬁcation in the ofﬁce"
    cleaned = clean_text(dirty)
    assert "workflow" in cleaned
    assert "identification" in cleaned
    assert "office" in cleaned


def test_clean_text_noise_removal():
    raw = (
        "10/23/26. 12:32 PM Patient safety\n"
        "Actual clinical guideline content.\n"
        "https://www.who.int/news-room/fact-sheets/detail/patient-safety 1/8"
    )
    cleaned = clean_text(raw)
    assert "Actual clinical guideline content." in cleaned
    assert "10/23/26" not in cleaned
    assert "https://" not in cleaned


def test_chunk_text_short():
    short = "Brief clinical note."
    chunks = chunk_text(short, max_chars=1000)
    assert len(chunks) == 1
    assert chunks[0] == short


def test_chunk_text_long_paragraphs():
    long_text = "\n\n".join([f"Paragraph {i}: " + "clinical facts " * 30 for i in range(10)])
    chunks = chunk_text(long_text, max_chars=800, overlap=100)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 1200


def test_tokens_normalization():
    assert _tokens("Patient-Centered Care (2021)!") == ["patient", "centered", "care", "2021"]


def test_load_source_missing_file():
    with pytest.raises(FileNotFoundError):
        _load_source(Path("non_existent_file.pdf"))


def test_load_source_valid_ocr_text():
    ocr_path = SOURCE_DIR / "patient_safety_fact_sheet_ocr.txt"
    if ocr_path.is_file():
        chunks = _load_source(ocr_path)
        assert len(chunks) >= 8
        pages = {c["page"] for c in chunks if c.get("page")}
        assert 1 in pages
        assert 4 in pages
