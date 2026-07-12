"""
Sends new-listing alerts to Discord and/or Telegram.
Both are best-effort: a notification failure is logged, never raised, so it
can't take down the polling loop.
"""
from __future__ import annotations

import logging
import time

import requests

from bot.config import Settings
from bot.platforms.base import Listing

log = logging.getLogger("notifier")

# Discord webhooks are rate-limited (roughly 5 requests / 2 seconds per
# webhook). A backlog of new listings - e.g. the first run, or right after
# a redeploy resets the dedupe database - can easily fire 20+ notifications
# in one cycle and get 429'd. This delay paces sends so that doesn't happen,
# and _post_with_retry below handles the rare 429 that slips through anyway.
DISCORD_SEND_DELAY_SECONDS = 0.4


class Notifier:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, listing: Listing, search_name: str) -> None:
        if self.settings.notify_discord and self.settings.discord_webhook_url:
            self._send_discord(listing, search_name)
        if self.settings.notify_telegram and self.settings.telegram_bot_token:
            self._send_telegram(listing, search_name)

    def _send_discord(self, listing: Listing, search_name: str) -> None:
        embed = {
            "title": listing.title[:256],
            "url": listing.url,
            "description": f"**{listing.price_display}**\nMatched: {search_name}",
            "color": 0x2ECC71,
        }
        if listing.image_url:
            embed["thumbnail"] = {"url": listing.image_url}
        embed["footer"] = {"text": listing.platform.upper()}

        time.sleep(DISCORD_SEND_DELAY_SECONDS)  # pace sends to stay under Discord's rate limit

        try:
            resp = requests.post(
                self.settings.discord_webhook_url,
                json={"embeds": [embed]},
                timeout=10,
            )
            if resp.status_code == 429:
                # Rate-limited anyway (e.g. big backlog) - Discord tells us
                # exactly how long to wait, so respect that and retry once.
                retry_after = float(resp.json().get("retry_after", 1.0))
                log.warning("Discord rate limit hit, retrying in %.1fs", retry_after)
                time.sleep(retry_after + 0.1)
                resp = requests.post(
                    self.settings.discord_webhook_url,
                    json={"embeds": [embed]},
                    timeout=10,
                )
            resp.raise_for_status()
        except requests.RequestException as e:
            log.warning("Discord notification failed: %s", e)

    def _send_telegram(self, listing: Listing, search_name: str) -> None:
        text = (
            f"🔔 *{search_name}* ({listing.platform.upper()})\n"
            f"{listing.title}\n"
            f"{listing.price_display}\n"
            f"{listing.url}"
        )
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        try:
            resp = requests.post(
                url,
                json={
                    "chat_id": self.settings.telegram_chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": False,
                },
                timeout=10,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            log.warning("Telegram notification failed: %s", e)
