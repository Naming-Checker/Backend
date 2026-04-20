from naming_check_backend.domain.value_objects.naming import normalize_naming


def normalize_for_dedup(value: str) -> str:
    return normalize_naming(value)
