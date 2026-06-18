"""
DataUpdateCoordinator for Schiphol Runway Monitor.

Data source: dutchplanespotters.nl JSON API
  GET https://www.dutchplanespotters.nl/api/runways/ams?date=YYYY-MM-DD

Response shape:
{
  "times": [
    {
      "from": "2026-06-15T07:10:00+00:00",
      "until": "2026-06-15T08:25:00+00:00",
      "landingRunways":   ["27", "36C"],
      "departingRunways": ["36L"]
    }, ...
  ],
  "peakTimes": [
    {"inbound": "06:50 - 09:50", "outbound": "06:50 - 08:00"},
    ...
  ]
}
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
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
    STATE_NO_PEAK,
    STATE_PEAK_INBOUND,
    STATE_PEAK_OUTBOUND,
    STATE_PEAK_BOTH,
)

_LOGGER = logging.getLogger(__name__)

API_URL = "https://www.dutchplanespotters.nl/api/runways/ams"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; HomeAssistant-SchipholRunwayMonitor/1.3)",
    "Accept": "application/json",
}


class SchipholRunwayCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches Schiphol runway + peak-time data from dutchplanespotters JSON API."""

    def __init__(self, hass: HomeAssistant, scan_interval: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")

        try:
            data = await self._fetch(date_str)
        except Exception as exc:
            raise UpdateFailed(f"Error fetching runway data: {exc}") from exc

        active  = _find_active_slot(data, now)
        peaks   = _parse_peak_times(data, now, date_str)

        _LOGGER.debug(
            "Active slot — landing: %s  departing: %s | peaks: %s",
            active["landing"], active["takeoff"], peaks,
        )

        result = _build_runway_states(active)
        result["_peaks"] = peaks
        result["_raw_peak_times"] = data.get("peakTimes", [])
        return result

    async def _fetch(self, date_str: str) -> dict:
        url = f"{API_URL}?date={date_str}"
        timeout = aiohttp.ClientTimeout(total=20)
        last_exc: Exception | None = None
        for attempt in range(3):
            if attempt:
                await asyncio.sleep(3 * attempt)
            try:
                async with aiohttp.ClientSession(headers=_HEADERS, timeout=timeout) as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            return await resp.json(content_type=None)
                        # permanent client error — no point retrying
                        if resp.status < 500 and resp.status != 429:
                            raise UpdateFailed(f"API returned HTTP {resp.status} for {url}")
                        last_exc = Exception(f"HTTP {resp.status}")
                        _LOGGER.warning("Schiphol API HTTP %s (attempt %d/3)", resp.status, attempt + 1)
            except UpdateFailed:
                raise
            except Exception as exc:
                last_exc = exc
                _LOGGER.warning("Schiphol fetch attempt %d/3 failed: %s", attempt + 1, exc)
        raise UpdateFailed(f"All 3 fetch attempts failed; last error: {last_exc}") from last_exc


# ── Pure helpers ──────────────────────────────────────────────────────────────

def _find_active_slot(data: dict, now: datetime) -> dict[str, list[str]]:
    """Return landing/departing headings for the time slot containing now."""
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

        if slot_until < now:
            if best_past is None or slot_until > datetime.fromisoformat(best_past["until"]):
                best_past = slot

    if best_past:
        _LOGGER.debug("No exact slot — using most recent past slot ending %s", best_past["until"])
        return {
            "landing": best_past.get("landingRunways", []),
            "takeoff": best_past.get("departingRunways", []),
        }

    _LOGGER.warning("No matching time slot found for %s", now.isoformat())
    return {"landing": [], "takeoff": []}


def _parse_peak_hhmm(time_str: str, date_str: str) -> datetime | None:
    """Parse 'HH:MM' into a timezone-aware UTC datetime on the given date.

    Schiphol times are local NL time (CET/CEST).
    We use a simple heuristic: months 4-10 = CEST (UTC+2), else CET (UTC+1).
    """
    if not time_str.strip():
        return None
    try:
        month = int(date_str[5:7])
        offset = "+02:00" if 4 <= month <= 10 else "+01:00"
        return datetime.fromisoformat(f"{date_str}T{time_str.strip()}:00{offset}")
    except ValueError:
        return None


def _parse_peak_times(data: dict, now: datetime, date_str: str) -> dict[str, Any]:
    """
    Parse peakTimes from the API response and return:
      {
        "inbound_peak":  bool,
        "outbound_peak": bool,
        "peak_state":    "no_peak" | "inbound_peak" | "outbound_peak" | "inbound_and_outbound_peak",
        "next_inbound_peak":  "HH:MM - HH:MM" | None,
        "next_outbound_peak": "HH:MM - HH:MM" | None,
        "all_peaks": [{"inbound": "HH:MM - HH:MM", "outbound": "HH:MM - HH:MM"}, ...]
      }
    """
    raw_peaks = data.get("peakTimes", [])
    in_inbound  = False
    in_outbound = False
    next_inbound: str | None  = None
    next_outbound: str | None = None

    for pt in raw_peaks:
        for direction in ("inbound", "outbound"):
            val = pt.get(direction, "").strip()
            if not val:
                continue
            parts = val.split(" - ")
            if len(parts) != 2:
                continue
            start_dt = _parse_peak_hhmm(parts[0], date_str)
            end_dt   = _parse_peak_hhmm(parts[1], date_str)
            if start_dt is None or end_dt is None:
                continue

            currently_in = start_dt <= now <= end_dt
            is_future    = start_dt > now

            if direction == "inbound":
                if currently_in:
                    in_inbound = True
                elif is_future and next_inbound is None:
                    next_inbound = val
            else:
                if currently_in:
                    in_outbound = True
                elif is_future and next_outbound is None:
                    next_outbound = val

    if in_inbound and in_outbound:
        peak_state = STATE_PEAK_BOTH
    elif in_inbound:
        peak_state = STATE_PEAK_INBOUND
    elif in_outbound:
        peak_state = STATE_PEAK_OUTBOUND
    else:
        peak_state = STATE_NO_PEAK

    return {
        "inbound_peak":       in_inbound,
        "outbound_peak":      in_outbound,
        "peak_state":         peak_state,
        "next_inbound_peak":  next_inbound,
        "next_outbound_peak": next_outbound,
        "all_peaks":          raw_peaks,
    }


def _build_runway_states(active: dict[str, list[str]]) -> dict[str, Any]:
    """Map active landing/takeoff headings onto runway config."""
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

        if landing_heading and takeoff_heading:
            state = STATE_BOTH
        elif landing_heading:
            state = STATE_INBOUND
        elif takeoff_heading:
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
