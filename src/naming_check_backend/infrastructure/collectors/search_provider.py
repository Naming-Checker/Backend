from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class TextSearchResult:
    title: str
    url: str
    snippet: str | None = None


class TextSearchProvider(ABC):
    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> list[TextSearchResult]:
        pass
