from abc import ABC, abstractmethod
from typing import Generator


class BaseCrawler(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Dataset name, used as Parquet filename stem."""
        ...

    @abstractmethod
    def crawl(self) -> Generator[dict, None, None]:
        """Yield dicts with an 'id' key."""
        ...

    @abstractmethod
    def done_conditions(self) -> list:
        """Return list of DoneCondition instances for validation."""
        ...
