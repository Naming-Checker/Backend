from naming_check_backend.domain.policies import build_stage2_dedup_key


def test_build_stage2_dedup_key_normalizes_naming_and_sorts_codes() -> None:
    key = build_stage2_dedup_key("  PROBI   MAX  ", [25, 5, 25])

    assert key == "probi max|5,25"
