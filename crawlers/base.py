from abc import ABC, abstractmethod
from typing import Generator

import requests


class BaseCrawler(ABC):
    proxy: str | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Dataset name, used as Parquet filename stem."""
        ...

    @property
    def session(self) -> requests.Session:
        """Requests session with proxy configured if set."""
        if not hasattr(self, "_session"):
            self._session = requests.Session()
        if self.proxy:
            self._session.proxies = {
                "http": self.proxy,
                "https": self.proxy,
            }
        return self._session

    @abstractmethod
    def crawl(self) -> Generator[dict, None, None]:
        """Yield dicts with an 'id' key."""
        ...

    @abstractmethod
    def done_conditions(self) -> list:
        """Return list of DoneCondition instances for validation."""
        ...
