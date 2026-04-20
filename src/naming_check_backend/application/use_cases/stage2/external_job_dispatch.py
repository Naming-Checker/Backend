from collections.abc import Iterable

from naming_check_backend.domain.entities import DeliveryChannel, Stage2Job
from naming_check_backend.domain.policies import build_stage2_dedup_key
from naming_check_backend.domain.value_objects import MktuClassSet, NamingText


class ExternalJobDispatchUseCase:
    """Prepare deduplicated Stage 2 jobs for the async pipeline."""

    def build_job(self, naming: str, mktu_codes: Iterable[int | str]) -> dict[str, object]:
        naming_text = NamingText.from_raw(naming)
        mktu_set = MktuClassSet.from_iterable(tuple(mktu_codes))
        job = Stage2Job(
            correlation_id=naming_text.canonical,
            dedup_key=build_stage2_dedup_key(naming_text.raw, mktu_set.values),
            delivery=DeliveryChannel.WEBHOOK,
        )
        return {
            "naming": naming_text.raw,
            "mktu_codes": mktu_set.as_list(),
            "dedup_key": job.dedup_key,
            "delivery": job.delivery.value,
        }
