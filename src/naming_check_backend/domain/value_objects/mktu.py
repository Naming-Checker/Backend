from collections.abc import Iterable
from dataclasses import dataclass

from naming_check_backend.domain.exceptions import DomainError


@dataclass(frozen=True, slots=True)
class MktuClassSet:
    values: tuple[int, ...]

    @classmethod
    def from_iterable(cls, values: Iterable[int | str]) -> "MktuClassSet":
        normalized: set[int] = set()
        for value in values:
            code = int(value)
            if code <= 0:
                raise DomainError("MKTU code must be a positive integer.")
            normalized.add(code)
        return cls(values=tuple(sorted(normalized)))

    def as_list(self) -> list[int]:
        return list(self.values)
