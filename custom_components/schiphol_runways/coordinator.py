"""DataUpdateCoordinator for Schiphol Runway Monitor."""
from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LVNL_EN_PAGE_URL,
    LVNL_PAGE_URL,
    RUNWAYS,
    STATE_BOTH,
    STATE_INBOUND,
    STATE_NOT_IN_USE,
    STATE_OUTBOUND,
    STATE_UNAVAILABLE,
)

_LOGGER = logging.getLogger(__name__)

# Request headers that mimic a browser (needed for LVNL site)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
}


class SchipholRunwayCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that polls LVNL for active Schiphol runway data."""

    def __init__(self, hass: HomeAssistant, scan_interval: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Public helpers
    # ─────────────────────────────────────────────────────────────────────────

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from LVNL and return per-runway state dict."""
        try:
            raw_html = await self._fetch_page()
        except Exception as exc:
            raise UpdateFailed(f"Error fetching LVNL runway page: {exc}") from exc

        active = self._parse_runways(raw_html)
        _LOGGER.debug("LVNL parsed active runways: %s", active)

        return self._build_runway_states(active)

    # ─────────────────────────────────────────────────────────────────────────
    # Network
    # ─────────────────────────────────────────────────────────────────────────

    async def _fetch_page(self) -> str:
        """Fetch the LVNL runway page. Tries NL then EN version."""
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(headers=_HEADERS, timeout=timeout) as session:
            for url in (LVNL_PAGE_URL, LVNL_EN_PAGE_URL):
                try:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            text = await resp.text(encoding="utf-8", errors="replace")
                            _LOGGER.debug("Fetched LVNL page from %s (%d chars)", url, len(text))
                            return text
                        _LOGGER.warning("LVNL returned HTTP %s for %s", resp.status, url)
                except aiohttp.ClientError as exc:
                    _LOGGER.warning("Request failed for %s: %s", url, exc)

        raise UpdateFailed("Could not reach LVNL runway page on any URL")

    # ─────────────────────────────────────────────────────────────────────────
    # Parsing
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_runways(self, html: str) -> dict[str, list[str]]:
        """
        Parse LVNL HTML and return {"landing": [...], "takeoff": [...]} of
        active runway headings (e.g. ["18L", "36R"]).

        LVNL encodes the runway widget data as JSON embedded in the page
        (inside a <script type="application/json"> or window.__INITIAL_STATE__
        variable) or as individual class-marked elements.

        We try several patterns in priority order so the integration is
        resilient to minor site updates.
        """
        landing: set[str] = set()
        takeoff: set[str] = set()

        # ── Pattern 1: JSON object with "landing" / "takeoff" / "arrivals" / "departures" keys ──
        json_blocks = re.findall(
            r'\{[^{}]{0,2000}(?:landing|arrival|aankomst|takeoff|departure|vertrek)[^{}]{0,2000}\}',
            html,
            re.IGNORECASE | re.DOTALL,
        )
        for block in json_blocks:
            # landing/arrivals list
            for m in re.finditer(
                r'(?:landing|arrival|aankomst)[s]?\s*["\']?\s*[:\]]\s*["\']?([0-9]{2}[LRC]?)',
                block,
                re.IGNORECASE,
            ):
                landing.add(m.group(1).upper())
            # takeoff/departures list
            for m in re.finditer(
                r'(?:takeoff|departure|vertrek)[s]?\s*["\']?\s*[:\]]\s*["\']?([0-9]{2}[LRC]?)',
                block,
                re.IGNORECASE,
            ):
                takeoff.add(m.group(1).upper())

        # ── Pattern 2: LVNL widget JSON — "runway":"18L","type":"L" (L=landing, D=departure) ──
        for m in re.finditer(
            r'"runway"\s*:\s*"([0-9]{2}[LRC]?)"\s*,\s*[^}]*"type"\s*:\s*"([LD])"',
            html,
            re.IGNORECASE,
        ):
            rwy, rtype = m.group(1).upper(), m.group(2).upper()
            (landing if rtype == "L" else takeoff).add(rwy)

        # Also try reversed key order: "type":"L","runway":"18L"
        for m in re.finditer(
            r'"type"\s*:\s*"([LD])"\s*,\s*[^}]*"runway"\s*:\s*"([0-9]{2}[LRC]?)"',
            html,
            re.IGNORECASE,
        ):
            rtype, rwy = m.group(1).upper(), m.group(2).upper()
            (landing if rtype == "L" else takeoff).add(rwy)

        # ── Pattern 3: CSS-class based markup ─────────────────────────────
        # <div class="landing active">18L</div> or <span class="runway landing">06</span>
        for m in re.finditer(
            r'class="[^"]*(?:landing|arrival)[^"]*active[^"]*"[^>]*>([0-9]{2}[LRC]?)<',
            html,
            re.IGNORECASE,
        ):
            landing.add(m.group(1).upper())

        for m in re.finditer(
            r'class="[^"]*active[^"]*(?:landing|arrival)[^"]*"[^>]*>([0-9]{2}[LRC]?)<',
            html,
            re.IGNORECASE,
        ):
            landing.add(m.group(1).upper())

        for m in re.finditer(
            r'class="[^"]*(?:takeoff|departure|vertrek)[^"]*active[^"]*"[^>]*>([0-9]{2}[LRC]?)<',
            html,
            re.IGNORECASE,
        ):
            takeoff.add(m.group(1).upper())

        for m in re.finditer(
            r'class="[^"]*active[^"]*(?:takeoff|departure|vertrek)[^"]*"[^>]*>([0-9]{2}[LRC]?)<',
            html,
            re.IGNORECASE,
        ):
            takeoff.add(m.group(1).upper())

        # ── Pattern 4: Fallback — any runway code near "actief" / "active" ─
        if not landing and not takeoff:
            _LOGGER.warning(
                "Primary runway parsing yielded no results — falling back to generic pattern"
            )
            # Look for runway codes (2-digit + optional LRC) near context words
            context_block = re.sub(r'<[^>]+>', ' ', html)  # strip tags
            for m in re.finditer(
                r'(?:actief|active|gebruik|in.use)\W{0,40}?([0-9]{2}[LRC]?)',
                context_block,
                re.IGNORECASE,
            ):
                code = m.group(1).upper()
                if re.match(r'^(?:06|09|18[LRC]?|27|22|24|36[LRC]?|04)$', code):
                    # Can't determine direction, put in both so sensor shows "in use"
                    landing.add(code)

        _LOGGER.debug("Parsed landing=%s  takeoff=%s", landing, takeoff)
        return {"landing": list(landing), "takeoff": list(takeoff)}

    # ─────────────────────────────────────────────────────────────────────────
    # State building
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_runway_states(active: dict[str, list[str]]) -> dict[str, Any]:
        """
        Combine parsed landing/takeoff lists with the runway config table
        and return a dict keyed by runway designator (e.g. "06/24").

        Each value is a dict:
          state: not_in_use | inbound | outbound | inbound_and_outbound
          landing_heading: "06" | None
          takeoff_heading: "36" | None
          name: "Kaagbaan"
        """
        landing_set = {h.upper() for h in active.get("landing", [])}
        takeoff_set = {h.upper() for h in active.get("takeoff", [])}

        result: dict[str, Any] = {
            "_raw_landing": list(landing_set),
            "_raw_takeoff": list(takeoff_set),
        }

        for designator, meta in RUNWAYS.items():
            is_landing = any(h in landing_set for h in meta["inbound_headings"])
            is_takeoff = any(h in takeoff_set for h in meta["outbound_headings"])

            active_landing = next(
                (h for h in meta["inbound_headings"] if h in landing_set), None
            )
            active_takeoff = next(
                (h for h in meta["outbound_headings"] if h in takeoff_set), None
            )

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
                "landing_heading": active_landing,
                "takeoff_heading": active_takeoff,
            }

        return result
