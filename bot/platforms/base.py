"""
Common interface every platform adapter implements. Keeping this contract
narrow (one method: search()) is what lets the scheduler treat eBay's clean
official API and Depop's reverse-engineered JSON endpoint identically - and
lets you patch a single file when a scraped platform changes its response
shape without touching anything else.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

import requests

log = logging.getLogger("platforms")

# Shared retry policy: 3 attempts, exponential backoff, only on network-ish errors.
# Import this into each adapter and decorate the network call, not the whole
# search() method, so a single flaky request retries without re-running
# unrelated parsing logic.
network_retry = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
)


@dataclass
class Listing:
    platform: str
    listing_id: str
    title: str
    price: float
    currency: str
    url: str
    image_url: str | None = None

    @property
    def price_display(self) -> str:
        symbol = {"USD": "$", "EUR": "€", "GBP": "£"}.get(self.currency, self.currency + " ")
        return f"{symbol}{self.price:,.2f}"


class Platform(ABC):
    name: str = "base"

    @abstractmethod
    def search(
        self,
        query: str,
        min_price: float | None = None,
        max_price: float | None = None,
        limit: int = 25,
    ) -> list[Listing]:
        """Return current listings matching query. Must not raise on
        expected per-request failures (rate limit, empty results) - log and
        return [] instead. Let unexpected errors propagate so the scheduler
        can log and skip this platform for the current cycle."""
        raise NotImplementedError
