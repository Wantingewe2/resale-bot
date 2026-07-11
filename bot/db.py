"""
Tiny SQLite dedupe store. Each (platform, listing_id) pair is only ever
alerted once. Safe to delete the .db file to reset and re-alert everything.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager


class SeenStore:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS seen_listings (
                    platform    TEXT NOT NULL,
                    listing_id  TEXT NOT NULL,
                    first_seen  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (platform, listing_id)
                )
                """
            )

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def is_new(self, platform: str, listing_id: str) -> bool:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM seen_listings WHERE platform = ? AND listing_id = ?",
                (platform, listing_id),
            ).fetchone()
            return row is None

    def mark_seen(self, platform: str, listing_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO seen_listings (platform, listing_id) VALUES (?, ?)",
                (platform, listing_id),
            )
