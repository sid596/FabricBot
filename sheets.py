"""Read-only, lazily loaded Google Sheets catalogue with a timed refresh."""
import os
import threading
import time
from pathlib import Path

import gspread
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent


class CatalogueCache:
    def __init__(self, loader, ttl=300, clock=time.monotonic):
        self.loader, self.ttl, self.clock = loader, ttl, clock
        self._snapshot = None
        self._expires = 0
        self._lock = threading.Lock()

    def get(self, force=False):
        with self._lock:
            if force or self._snapshot is None or self.clock() >= self._expires:
                values = self.loader()
                if not values or not {"Album", "Quality", "Price", "Width", "Cut Rate"}.issubset(values[0]):
                    raise ValueError("The fabric sheet is missing required price columns")
                # Replace atomically; failed refreshes must not silently quote stale prices.
                self._snapshot = (tuple(values[0]), tuple(tuple(row) for row in values[1:]))
                self._expires = self.clock() + self.ttl
            return self._snapshot


def _read_sheet():
    client = gspread.service_account(
        filename=os.getenv("GOOGLE_APPLICATION_CREDENTIALS", str(BASE_DIR / "fabricbot.json")),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly"],
    )
    client.set_timeout(30)
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    book = client.open_by_key(sheet_id) if sheet_id else client.open(
        os.getenv("GOOGLE_SHEET_NAME", "Curtains Q2 and July 2025")
    )
    return book.worksheet(os.getenv("GOOGLE_SHEET_TAB", "data")).get_all_values()


catalogue_cache = CatalogueCache(_read_sheet, ttl=max(1, int(os.getenv("SHEET_CACHE_TTL_SECONDS", "300"))))


def get_catalogue(force=False):
    return catalogue_cache.get(force=force)


def __getattr__(name):
    if name in {"headers", "rows"}:
        return get_catalogue()[0 if name == "headers" else 1]
    raise AttributeError(name)
