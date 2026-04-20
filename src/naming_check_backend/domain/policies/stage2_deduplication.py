from collections.abc import Iterable

from naming_check_backend.domain.policies.preprocessing import normalize_for_dedup


def build_stage2_dedup_key(naming: str, mktu_codes: Iterable[int | str]) -> str:
    """Build a stable deduplication key for Stage 2 async jobs."""
    normalized_naming = normalize_for_dedup(naming)
    normalized_codes = sorted({int(code) for code in mktu_codes})
    code_part = ",".join(str(code) for code in normalized_codes)
    return f"{normalized_naming}|{code_part}"
