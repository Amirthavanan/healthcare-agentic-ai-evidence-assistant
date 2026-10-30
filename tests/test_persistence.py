
from retrieval.hybrid import HybridRetriever, INDEX_DIR


def test_faiss_index_is_persisted():
    first = HybridRetriever()

    if not first.chunks:
        assert first.index is None
        return

    assert first.index is not None
    assert (INDEX_DIR / "index.faiss").is_file()
    assert (INDEX_DIR / "chunks.json").is_file()
    assert (INDEX_DIR / "manifest.json").is_file()


def test_persisted_index_can_be_reloaded():
    first = HybridRetriever()

    if not first.chunks:
        return

    first_index = first.index
    first_count = len(first.chunks)

    second = HybridRetriever()

    assert second.index is not None
    assert second.index.ntotal == first_index.ntotal
    assert len(second.chunks) == first_count
