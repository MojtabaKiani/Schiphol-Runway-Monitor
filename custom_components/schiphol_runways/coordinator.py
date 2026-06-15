"""
DataUpdateCoordinator for Schiphol Runway Monitor.

Data source: dutchplanespotters.nl JSON API
  GET https://www.dutchplanespotters.nl/api/runways/ams?date=YYYY-MM-DD

  Response example:
  {
    "times": [
      {
        "from": "2026-06-15T07:10:00+00:00",
        "until": "2026-06-15T08:25:00+00:00",
        "landingRunways":   ["27", "36C"],
        "departingRunways": ["36L"]
      },
      ...
    ]
  }

  We find the slot where now() falls between "from" and "until"
  and use its landingRunways / departingRunways lists directly.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    RUNWAYS,
    STATE_BOTH,
    STATE_INBOUND,
    STATE_NOT_IN_USE,
    STATE_OUTBOUND,
)

_LOGGER = logging.getLogger(__name__)

API_URL = "https://www.dutchplanespotters.nl/api/runways/ams"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; HomeAssistant-SchipholRunwayMonitor/1.2)"
    ),
    "Accept": "application/json",
}


class SchipholRunwayCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches Schiphol runway data from the dutchplanespotters JSON API."""

    def __init__(self, hass: HomeAssistant, scan_interval: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval),
        )

    # ── Main update ───────────────────────────────────────────────────────────

    async def _async_update_data(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")

        try:
            data = await self._fetch(date_str)
        except Exception as exc:
            raise UpdateFailed(f"Error fetching runway data: {exc}") from exc

        active = _find_active_slot(data, now)

        _LOGGER.debug(
            "Schiphol active slot — landing: %s  departing: %s",
            active["landing"],
            active["takeoff"],
        )

        return _build_runway_states(active)

    # ── Network ───────────────────────────────────────────────────────────────

    async def _fetch(self, date_str: str) -> dict:
        url = f"{API_URL}?date={date_str}"
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(headers=_HEADERS, timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise UpdateFailed(
                        f"API returned HTTP {resp.status} for {url}"
                    )
                return await resp.json(content_type=None)


# ── Pure helpers (easy to unit-test) ─────────────────────────────────────────

def _find_active_slot(data: dict, now: datetime) -> dict[str, list[str]]:
    """
    Walk the time slots in the API response and return the one that
    contains `now`. Falls back to the most recent past slot if none
    matches (e.g. data not yet updated for the last few minutes).
    """
    slots = data.get("times", [])
    best_past: dict | None = None

    for slot in slots:
        try:
            slot_from  = datetime.fromisoformat(slot["from"])
            slot_until = datetime.fromisoformat(slot["until"])
        except (KeyError, ValueError):
            continue

        if slot_from <= now <= slot_until:
            return {
                "landing": slot.get("landingRunways", []),
                "takeoff": slot.get("departingRunways", []),
            }

        # Track the latest past slot as fallback
        if slot_until < now:
            if best_past is None or slot_until > datetime.fromisoformat(best_past["until"]):
                best_past = slot

    if best_past:
        _LOGGER.debug("No exact slot match — using most recent past slot ending %s", best_past["until"])
        return {
            "landing": best_past.get("landingRunways", []),
            "takeoff": best_past.get("departingRunways", []),
        }

    _LOGGER.warning("No matching time slot found in API response for %s", now.isoformat())
    return {"landing": [], "takeoff": []}


def _build_runway_states(active: dict[str, list[str]]) -> dict[str, Any]:
    """
    Map active landing/takeoff headings onto the runway config table.

    The API already tells us which heading is landing vs departing —
    we simply check if any of the runway's headings appear in either list.
    """
    landing_set = {h.upper() for h in active.get("landing", [])}
    takeoff_set = {h.upper() for h in active.get("takeoff", [])}

    result: dict[str, Any] = {
        "_raw_landing": list(landing_set),
        "_raw_takeoff": list(takeoff_set),
    }

    for designator, meta in RUNWAYS.items():
        headings = [h.upper() for h in meta["headings"]]

        landing_heading = next((h for h in headings if h in landing_set), None)
        takeoff_heading = next((h for h in headings if h in takeoff_set), None)

        is_landing = landing_heading is not None
        is_takeoff = takeoff_heading is not None

        if is_landing and is_takeoff:
            state = STATE_BOTH
        elif is_landing:
            state = STATE_INBOUND
        elif is_takeoff:
            state = STATE_OUTBOUND
        else:
            state = STATE_NOT_IN_USE

        result[designator] = {
            "state": state,
            "name": meta["name"],
            "landing_heading": landing_heading,
            "takeoff_heading": takeoff_heading,
        }

    return result
