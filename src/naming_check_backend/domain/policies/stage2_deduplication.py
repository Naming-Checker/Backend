from collections.abc import Iterable


def build_stage2_dedup_key(naming: str, mktu_codes: Iterable[int | str]) -> str:
    """Build a stable deduplication key for Stage 2 async jobs."""
    normalized_naming = " ".join(naming.casefold().split())
    normalized_codes = sorted({int(code) for code in mktu_codes})
    code_part = ",".join(str(code) for code in normalized_codes)
    return f"{normalized_naming}|{code_part}"
