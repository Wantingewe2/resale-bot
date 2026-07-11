"""
eBay Browse API - the only one of the four with an official, stable public
search endpoint. Docs: https://developer.ebay.com/api-docs/buy/browse/overview.html

Uses the OAuth2 client-credentials flow (app-only token, no user login
needed for public search). Token is cached in memory until ~1 min before
expiry.
"""
from __future__ import annotations

import logging
import time

import requests

from bot.platforms.base import Listing, Platform, network_retry

log = logging.getLogger("platforms.ebay")

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
SCOPE = "https://api.ebay.com/oauth/api_scope"


class EbayPlatform(Platform):
    name = "ebay"

    def __init__(self, client_id: str, client_secret: str, marketplace_id: str = "EBAY_US"):
        if not client_id or not client_secret:
            raise ValueError(
                "eBay platform enabled but EBAY_CLIENT_ID / EBAY_CLIENT_SECRET "
                "are not set. Get them from https://developer.ebay.com"
            )
        self.client_id = client_id
        self.client_secret = client_secret
        self.marketplace_id = marketplace_id
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token

        resp = requests.post(
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "scope": SCOPE},
            auth=(self.client_id, self.client_secret),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expires_at = time.time() + int(data["expires_in"])
        return self._token

    @network_retry
    def _do_search(self, params: dict, headers: dict) -> dict:
        resp = requests.get(SEARCH_URL, params=params, headers=headers, timeout=15)
        if resp.status_code == 401:
            # token expired mid-flight - force refresh once
            self._token = None
            headers["Authorization"] = f"Bearer {self._get_token()}"
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
        token = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": self.marketplace_id,
        }

        filters = ["buyingOptions:{FIXED_PRICE|AUCTION}"]
        if min_price is not None or max_price is not None:
            lo = min_price if min_price is not None else ""
            hi = max_price if max_price is not None else ""
            filters.append(f"price:[{lo}..{hi}]")
            filters.append("priceCurrency:USD")

        params = {
            "q": query,
            "limit": str(limit),
            "filter": ",".join(filters),
            "sort": "newlyListed",
        }

        try:
            data = self._do_search(params, headers)
        except requests.RequestException as e:
            log.error("eBay search failed for %r: %s", query, e)
            return []

        listings = []
        for item in data.get("itemSummaries", []):
            try:
                price = float(item["price"]["value"])
                currency = item["price"]["currency"]
                image = item.get("image", {}).get("imageUrl")
                listings.append(
                    Listing(
                        platform=self.name,
                        listing_id=item["itemId"],
                        title=item["title"],
                        price=price,
                        currency=currency,
                        url=item["itemWebUrl"],
                        image_url=image,
                    )
                )
            except (KeyError, TypeError, ValueError) as e:
                log.debug("Skipping malformed eBay item: %s", e)
                continue

        return listings
