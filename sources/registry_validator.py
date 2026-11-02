"""Source Registry validation, freshness checking, and deduplication verification."""
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCES_DIR = ROOT / "sources"
REGISTRY_FILE = SOURCES_DIR / "registry.json"


def validate_source_registry(registry_path: Path = REGISTRY_FILE) -> tuple[bool, list[str], list[dict[str, Any]]]:
    """Validate registry structure, check file existence, check uniqueness, and detect duplicates."""
    errors: list[str] = []
    if not registry_path.is_file():
        return False, ["Registry file does not exist."], []

    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, [f"Failed to parse registry JSON: {exc}"], []

    if not isinstance(data, list):
        return False, ["Registry root must be a list of source entries."], []

    seen_ids = set()
    file_hashes: dict[str, str] = {}
    validated_sources: list[dict[str, Any]] = []

    required_fields = ["id", "file", "title", "publisher", "version", "review_status"]

    for idx, entry in enumerate(data):
        entry_id = entry.get("id") or entry.get("source_id")
        if not entry_id:
            errors.append(f"Entry {idx} is missing 'id'.")
            continue

        if entry_id in seen_ids:
            errors.append(f"Duplicate source ID detected: '{entry_id}'.")
        seen_ids.add(entry_id)

        for field in required_fields:
            if field not in entry:
                errors.append(f"Source '{entry_id}' missing required metadata field: '{field}'.")

        # Verify physical file existence
        file_name = entry.get("file", "")
        fpath = SOURCES_DIR / file_name
        if not fpath.is_file():
            errors.append(f"Source '{entry_id}' references non-existent file: '{file_name}'.")
        else:
            # Check for duplicate document content via sha256
            fhash = hashlib.sha256(fpath.read_bytes()).hexdigest()
            if fhash in file_hashes:
                errors.append(f"Duplicate document detected: '{entry_id}' matches '{file_hashes[fhash]}'.")
            file_hashes[fhash] = entry_id

        validated_sources.append(entry)

    passed = len(errors) == 0
    return passed, errors, validated_sources


if __name__ == "__main__":
    passed, errors, sources = validate_source_registry()
    print(f"Registry Validation: {'PASSED' if passed else 'FAILED'}")
    if errors:
        for err in errors:
            print(f"- {err}")
    else:
        print(f"Successfully validated {len(sources)} knowledge sources.")
