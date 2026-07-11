"""
The main loop. For each configured search, for each platform it targets,
fetch current listings, filter to ones we haven't seen, notify, mark seen.
One platform throwing an unexpected exception never stops the others.
"""
from __future__ import annotations

import logging
import time

from bot.config import Settings
from bot.db import SeenStore
from bot.notifier import Notifier
from bot.platforms import PLATFORM_REGISTRY
from bot.platforms.base import Platform

log = logging.getLogger("scheduler")


def build_platforms(settings: Settings) -> dict[str, Platform]:
    """Instantiate only the platforms actually referenced in config.yaml."""
    needed = {p for s in settings.searches for p in s.platforms}
    instances: dict[str, Platform] = {}

    for name in needed:
        cls = PLATFORM_REGISTRY.get(name)
        if cls is None:
            log.warning("Unknown platform %r in config.yaml - skipping", name)
            continue
        try:
            if name == "ebay":
                instances[name] = cls(settings.ebay_client_id, settings.ebay_client_secret)
            elif name == "vinted":
                instances[name] = cls(settings.vinted_cookie)
            else:
                instances[name] = cls()
        except ValueError as e:
            log.error("Could not initialize platform %r: %s", name, e)

    return instances


def run_forever(settings: Settings) -> None:
    store = SeenStore(settings.database_path)
    notifier = Notifier(settings)
    platforms = build_platforms(settings)

    if not platforms:
        log.error("No platforms initialized - check your config.yaml and .env. Exiting.")
        return

    log.info(
        "Starting: %d search(es) across platforms %s, polling every %ss",
        len(settings.searches),
        sorted(platforms.keys()),
        settings.poll_interval_seconds,
    )

    while True:
        cycle_start = time.time()

        for search in settings.searches:
            for platform_name in search.platforms:
                platform = platforms.get(platform_name)
                if platform is None:
                    continue

                try:
                    results = platform.search(
                        query=search.query,
                        min_price=search.min_price,
                        max_price=search.max_price,
                    )
                except Exception:
                    log.exception(
                        "Unexpected error searching %s for %r - skipping this cycle",
                        platform_name,
                        search.name,
                    )
                    results = []

                new_count = 0
                for listing in results:
                    if store.is_new(listing.platform, listing.listing_id):
                        notifier.send(listing, search.name)
                        store.mark_seen(listing.platform, listing.listing_id)
                        new_count += 1

                if new_count:
                    log.info(
                        "[%s/%s] %d new listing(s)", search.name, platform_name, new_count
                    )

                time.sleep(settings.inter_platform_delay_seconds)

        elapsed = time.time() - cycle_start
        sleep_for = max(0.0, settings.poll_interval_seconds - elapsed)
        log.info("Cycle complete in %.1fs, sleeping %.1fs", elapsed, sleep_for)
        time.sleep(sleep_for)
