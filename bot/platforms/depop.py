"""
Depop has no public developer API. This calls the same JSON endpoint their
own web app (depop.com) uses for search results. It's unauthenticated and
works without a login, but it IS an unofficial/reverse-engineered endpoint:
- It can change shape or move without notice.
- Hitting it too frequently can get your IP soft-blocked. Respect
  inter_platform_delay_seconds in config.yaml.
If this stops returning results, open depop.com in a browser, search
something, check Network tab (XHR) for the request to webapi.depop.com and
diff it against SEARCH_URL/params below.
"""
from __future__ import annotations

import logging

import requests

from bot.platforms.base import Listing, Platform, network_retry

log = logging.getLogger("platforms.depop")

SEARCH_URL = "https://webapi.depop.com/api/v2/search/products/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


class DepopPlatform(Platform):
    name = "depop"

    @network_retry
    def _do_search(self, params: dict) -> dict:
        resp = requests.get(SEARCH_URL, params=params, headers=HEADERS, timeout=15)
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
            "what": query,
            "currency": "USD",
            "itemsPerPage": limit,
            "sortId": "newlyListed",
        }
        if min_price is not None:
            params["priceMin"] = min_price
        if max_price is not None:
            params["priceMax"] = max_price

        try:
            data = self._do_search(params)
        except requests.RequestException as e:
            log.error("Depop search failed for %r: %s", query, e)
            return []
        except ValueError as e:
            log.error("Depop returned non-JSON (endpoint may have changed): %s", e)
            return []

        listings = []
        for item in data.get("products", []):
            try:
                price_info = item["price"]
                price = float(price_info["priceAmount"])
                currency = price_info.get("currencyCode", "USD")
                slug = item.get("slug")
                item_id = str(item["id"])
                url = f"https://www.depop.com/products/{slug}/" if slug else f"https://www.depop.com/products/{item_id}/"
                images = item.get("previewImage", {}).get("url")
                listings.append(
                    Listing(
                        platform=self.name,
                        listing_id=item_id,
                        title=item.get("description", "")[:120] or "Depop item",
                        price=price,
                        currency=currency,
                        url=url,
                        image_url=images,
                    )
                )
            except (KeyError, TypeError, ValueError) as e:
                log.debug("Skipping malformed Depop item: %s", e)
                continue

        return listings
