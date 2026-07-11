"""
Mercari is the shakiest of the four. Their JSON search API requires a signed
DPoP proof-of-possession token (real request signing, rotated client-side) -
that's deliberately hard to replicate outside their own app and will break
often even if reproduced.

Workaround used here: fetch the normal search results *page*
(mercari.com/search/) like a browser would, and pull the search results out
of the embedded __NEXT_DATA__ JSON blob that Next.js ships inline with the
page. This is more stable than fighting their signed API, but it's still
scraping a rendered page, so:
- If Mercari changes their frontend framework/build, this breaks.
- Expect this adapter to need maintenance more often than the other three.
- If it stops working entirely, consider dropping Mercari from your
  `platforms:` list in config.yaml rather than sinking time into it.
"""
from __future__ import annotations

import json
import logging

import requests
from bs4 import BeautifulSoup

from bot.platforms.base import Listing, Platform, network_retry

log = logging.getLogger("platforms.mercari")

SEARCH_PAGE_URL = "https://www.mercari.com/search/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}


class MercariPlatform(Platform):
    name = "mercari"

    @network_retry
    def _fetch_page(self, params: dict) -> str:
        resp = requests.get(SEARCH_PAGE_URL, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.text

    def _extract_next_data(self, html: str) -> dict | None:
        soup = BeautifulSoup(html, "html.parser")
        tag = soup.find("script", id="__NEXT_DATA__")
        if not tag or not tag.string:
            return None
        try:
            return json.loads(tag.string)
        except json.JSONDecodeError:
            return None

    def search(
        self,
        query: str,
        min_price: float | None = None,
        max_price: float | None = None,
        limit: int = 25,
    ) -> list[Listing]:
        params = {"keyword": query, "sortBy": "created_time", "sortOrder": "desc"}
        if min_price is not None:
            params["priceMin"] = int(min_price)
        if max_price is not None:
            params["priceMax"] = int(max_price)

        try:
            html = self._fetch_page(params)
        except requests.RequestException as e:
            log.error("Mercari search failed for %r: %s", query, e)
            return []

        data = self._extract_next_data(html)
        if not data:
            log.warning(
                "Mercari: couldn't find __NEXT_DATA__ - page structure likely "
                "changed. This adapter needs updating."
            )
            return []

        try:
            # Path into Next.js's data blob for the search results collection.
            # This is the part most likely to need adjusting if it breaks.
            items = (
                data["props"]["pageProps"]["initialState"]["items"]["itemsCollection"]["items"]
            )
        except (KeyError, TypeError):
            log.warning("Mercari: expected data path not found - page structure changed.")
            return []

        listings = []
        for item in items[:limit]:
            try:
                price = float(item["price"])
                item_id = item["id"]
                thumbnails = item.get("thumbnails") or []
                listings.append(
                    Listing(
                        platform=self.name,
                        listing_id=item_id,
                        title=item.get("name", "Mercari item"),
                        price=price,
                        currency="USD",
                        url=f"https://www.mercari.com/us/item/{item_id}/",
                        image_url=thumbnails[0] if thumbnails else None,
                    )
                )
            except (KeyError, TypeError, ValueError) as e:
                log.debug("Skipping malformed Mercari item: %s", e)
                continue

        return listings
