"""
Vinted has no public developer API either. This hits the same JSON endpoint
vinted.com's own frontend uses for catalog search.

Vinted runs bot-detection (Datadome) in front of this endpoint. In practice:
- It often works unauthenticated for light traffic.
- If you start getting 401/403s, copy your browser's `_vinted_fr_session` /
  datadome cookie into VINTED_COOKIE in .env - see .env.example.
- Keep request volume low (this is the most detection-sensitive of the four).
"""
from __future__ import annotations

import logging

import requests

from bot.platforms.base import Listing, Platform, network_retry

log = logging.getLogger("platforms.vinted")

SEARCH_URL = "https://www.vinted.com/api/v2/catalog/items"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


class VintedPlatform(Platform):
    name = "vinted"

    def __init__(self, cookie: str = ""):
        self.cookie = cookie

    @network_retry
    def _do_search(self, params: dict) -> dict:
        headers = dict(HEADERS)
        if self.cookie:
            headers["Cookie"] = self.cookie
        resp = requests.get(SEARCH_URL, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def search(
        self,
        query: str,
        min_price: float | None = None,
        max_price: float | None = None,
        limit: int = 25,
    ) -> list[Listing]:
        params = {
            "search_text": query,
            "per_page": limit,
            "order": "newest_first",
        }
        if min_price is not None:
            params["price_from"] = min_price
        if max_price is not None:
            params["price_to"] = max_price

        try:
            data = self._do_search(params)
        except requests.RequestException as e:
            log.error("Vinted search failed for %r: %s", query, e)
            return []
        except ValueError as e:
            log.error("Vinted returned non-JSON (likely bot-blocked or endpoint changed): %s", e)
            return []

        listings = []
        for item in data.get("items", []):
            try:
                price_info = item.get("total_item_price") or item.get("price")
                price = float(price_info["amount"])
                currency = price_info.get("currency_code", "EUR")
                photo = (item.get("photo") or {}).get("url")
                listings.append(
                    Listing(
                        platform=self.name,
                        listing_id=str(item["id"]),
                        title=item.get("title", "Vinted item"),
                        price=price,
                        currency=currency,
                        url=item.get("url", f"https://www.vinted.com/items/{item['id']}"),
                        image_url=photo,
                    )
                )
            except (KeyError, TypeError, ValueError) as e:
                log.debug("Skipping malformed Vinted item: %s", e)
                continue

        return listings
