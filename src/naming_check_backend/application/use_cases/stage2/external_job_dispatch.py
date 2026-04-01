from collections.abc import Iterable

from naming_check_backend.domain.policies import build_stage2_dedup_key


class ExternalJobDispatchUseCase:
    """Prepare deduplicated Stage 2 jobs for the async pipeline."""

    def build_job(self, naming: str, mktu_codes: Iterable[int | str]) -> dict[str, object]:
        normalized_codes = sorted({int(code) for code in mktu_codes})
        return {
            "naming": naming,
            "mktu_codes": normalized_codes,
            "dedup_key": build_stage2_dedup_key(naming, normalized_codes),
            "delivery": "webhook",
        }
